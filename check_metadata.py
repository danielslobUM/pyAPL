"""
Check metadata - Inspect DICOM chain identification following v5 protocol.

This script visualizes the DICOM chain identification process:
1. Find APPROVED RTPLAN(s)
2. Match to CLINICAL RTSTRUCT via ReferencedSOPInstanceUID
3. Match to CT SERIES via FrameOfReferenceUID + ReferencedCTSeriesUID
4. Find LIMBUS AI RTSTRUCT using two-step matching:
   a. Geometry match (FrameOfReferenceUID + ReferencedCTSeriesUID)
   b. Metadata verification (SeriesDescription + StructureSetLabel)

DICOM Chain Protocol:
    APPROVED RTPLAN
          │
          ▼ (match by ReferencedSOPInstanceUID)
    CLINICAL RTSTRUCT
          │
          ▼ (match by FrameOfReferenceUID + ReferencedCTSeriesUID)
    CT SERIES
          │
          ▼ (v5: TWO-STEP MATCHING)
    LIMBUS AI RTSTRUCT
          Step A: Geometry match (FrameOfReferenceUID + ReferencedCTSeriesUID)
          Step B: Metadata verify (SeriesDescription + StructureSetLabel)
"""

import os
import sys
import random
import pydicom
import pandas as pd
from datetime import datetime
from collections import defaultdict
from typing import List, Dict, Tuple, Optional


# ============================================================================
# DICOM SCANNING FUNCTIONS
# ============================================================================

def scan_rtplan_files(patient_folder: str) -> Tuple[List[Dict], List[Dict]]:
    """Scan for all RTPLAN files and identify approved ones."""
    rtplan_folder = os.path.join(patient_folder, 'RTPLAN')
    if not os.path.isdir(rtplan_folder):
        rtplan_folder = patient_folder
    
    all_rtplans = []
    approved_rtplans = []
    
    for root, dirs, files in os.walk(rtplan_folder):
        for file in files:
            if file.lower().endswith('.dcm'):
                filepath = os.path.join(root, file)
                try:
                    ds = pydicom.dcmread(filepath, stop_before_pixels=True)
                    if ds.get('Modality', '') != 'RTPLAN':
                        continue
                    
                    # Get approval status (300E,0002)
                    approval_status = 'UNKNOWN'
                    if (0x300E, 0x0002) in ds:
                        approval_elem = ds[0x300E, 0x0002]
                        approval_status = str(approval_elem.value) if hasattr(approval_elem, 'value') else str(approval_elem)
                    
                    # Get referenced RTSTRUCT SOP Instance UID (300C,0060)
                    ref_rtstruct_sop_uid = ''
                    if (0x300C, 0x0060) in ds:  # ReferencedStructureSetSequence
                        ref_struct_seq = ds[0x300C, 0x0060]
                        if hasattr(ref_struct_seq, 'value') and len(ref_struct_seq.value) > 0:
                            ref_rtstruct_sop_uid = str(ref_struct_seq.value[0].get('ReferencedSOPInstanceUID', ''))
                    
                    rtplan_info = {
                        'path': filepath,
                        'filename': os.path.basename(filepath),
                        'sop_instance_uid': str(ds.get('SOPInstanceUID', '')),
                        'plan_name': str(ds.get('RTPlanName', '')),
                        'plan_label': str(ds.get('RTPlanLabel', '')),
                        'treatment_protocols': str(ds.get((0x300A, 0x0009), '')),
                        'approval_status': approval_status,
                        'referenced_rtstruct_sop_uid': ref_rtstruct_sop_uid
                    }
                    
                    all_rtplans.append(rtplan_info)
                    if approval_status == 'APPROVED':
                        approved_rtplans.append(rtplan_info)
                        
                except Exception as e:
                    pass
    
    return all_rtplans, approved_rtplans


def scan_rtstruct_files(patient_folder: str) -> List[Dict]:
    """Scan for all RTSTRUCT files with full metadata."""
    rtstruct_folder = os.path.join(patient_folder, 'RTSTRUCT')
    if not os.path.isdir(rtstruct_folder):
        rtstruct_folder = patient_folder
    
    all_rtstructs = []
    
    for root, dirs, files in os.walk(rtstruct_folder):
        for file in files:
            if file.lower().endswith('.dcm'):
                filepath = os.path.join(root, file)
                try:
                    ds = pydicom.dcmread(filepath, stop_before_pixels=True)
                    if ds.get('Modality', '') != 'RTSTRUCT':
                        continue
                    
                    # Extract Referenced CT Series UID from nested sequence
                    # Path: (3006,0010) → (3006,0012) → (3006,0014) → (0020,000E)
                    referenced_ct_series_uid = ''
                    if (0x3006, 0x0010) in ds:  # ReferencedFrameOfReferenceSequence
                        for frame_ref in ds[0x3006, 0x0010]:
                            if (0x3006, 0x0012) in frame_ref:  # RTReferencedStudySequence
                                for study_ref in frame_ref[0x3006, 0x0012]:
                                    if (0x3006, 0x0014) in study_ref:  # RTReferencedSeriesSequence
                                        for series_ref in study_ref[0x3006, 0x0014]:
                                            uid = str(series_ref.get('SeriesInstanceUID', ''))
                                            if uid:
                                                referenced_ct_series_uid = uid
                                                break
                    
                    # Extract ROI Interpreted Types from RTROIObservationsSequence (3006,0080)
                    # Join with StructureSetROISequence (3006,0020) via ROI number to get names
                    roi_number_to_name = {}
                    if (0x3006, 0x0020) in ds:  # StructureSetROISequence
                        for roi_item in ds[0x3006, 0x0020]:
                            roi_num = str(roi_item.get('ROINumber', ''))
                            roi_name = str(roi_item.get('ROIName', ''))
                            roi_number_to_name[roi_num] = roi_name
                    
                    roi_interpreted_types = {}  # {roi_name: interpreted_type}
                    roi_interpreters = {}        # {roi_name: interpreter}
                    if (0x3006, 0x0080) in ds:  # RTROIObservationsSequence
                        for obs_item in ds[0x3006, 0x0080]:
                            roi_num = str(obs_item.get('ReferencedROINumber', ''))
                            roi_type = str(obs_item.get('RTROIInterpretedType', ''))
                            roi_interpreter = str(obs_item.get((0x3006, 0x00A6), ''))
                            roi_name = roi_number_to_name.get(roi_num, f'ROI_{roi_num}')
                            roi_interpreted_types[roi_name] = roi_type
                            roi_interpreters[roi_name] = roi_interpreter
                    
                    info = {
                        'path': filepath,
                        'filename': os.path.basename(filepath),
                        'sop_instance_uid': str(ds.get('SOPInstanceUID', '')),
                        'series_instance_uid': str(ds.get('SeriesInstanceUID', '')),
                        'frame_of_reference_uid': str(ds.get('FrameOfReferenceUID', '')),
                        'referenced_ct_series_uid': referenced_ct_series_uid,
                        'structure_set_label': str(ds.get('StructureSetLabel', '')),
                        'series_description': str(ds.get('SeriesDescription', '')),
                        'manufacturer': str(ds.get('Manufacturer', '')),
                        'manufacturer_model': str(ds.get('ManufacturerModelName', '')),
                        'operators_name': str(ds.get('OperatorsName', '')),
                        'roi_interpreted_types': roi_interpreted_types,
                        'roi_interpreters': roi_interpreters
                    }
                    
                    all_rtstructs.append(info)
                        
                except Exception as e:
                    pass
    
    return all_rtstructs


def scan_ct_series(patient_folder: str) -> Dict[str, Dict]:
    """Scan for all CT series."""
    ct_folder = os.path.join(patient_folder, 'CT')
    if not os.path.isdir(ct_folder):
        ct_folder = patient_folder
    
    ct_series_dict = {}
    
    for root, dirs, files in os.walk(ct_folder):
        for file in files:
            if file.lower().endswith('.dcm'):
                filepath = os.path.join(root, file)
                try:
                    ds = pydicom.dcmread(filepath, stop_before_pixels=True)
                    if ds.get('Modality', '') == 'CT':
                        series_uid = str(ds.get('SeriesInstanceUID', ''))
                        frame_ref_uid = str(ds.get('FrameOfReferenceUID', ''))
                        
                        if series_uid not in ct_series_dict:
                            ct_series_dict[series_uid] = {
                                'series_uid': series_uid,
                                'frame_ref_uid': frame_ref_uid,
                                'series_description': str(ds.get('SeriesDescription', '')),
                                'file_count': 0,
                                'folder': root,
                                'files': []
                            }
                        ct_series_dict[series_uid]['file_count'] += 1
                        ct_series_dict[series_uid]['files'].append(filepath)
                except:
                    pass
    
    return ct_series_dict


def is_verified_limbus_rtstruct(rtstruct_info: dict) -> bool:
    """
    Verify if an RTSTRUCT is a valid Limbus AI structure set.
    
    v5 Verification Criteria (BOTH must be true):
    1. SeriesDescription equals 'Limbus RTSS v1.8.0' (exact match)
    2. StructureSetLabel equals 'Limbus RTStruct' (exact match)
    """
    series_desc = rtstruct_info.get('series_description', '')
    struct_label = rtstruct_info.get('structure_set_label', '')
    
    return (
        series_desc == 'Limbus RTSS v1.8.0' and
        struct_label == 'Limbus RTStruct'
    )


# ============================================================================
# CHAIN IDENTIFICATION (v5 PROTOCOL)
# ============================================================================

def identify_dicom_chain_v5(patient_folder: str, patient_id: str) -> List[Dict]:
    """
    Identify DICOM chains following v5 protocol.
    
    Protocol:
        APPROVED RTPLAN
              │
              ▼ (match by ReferencedSOPInstanceUID)
        CLINICAL RTSTRUCT
              │
              ▼ (match by FrameOfReferenceUID + ReferencedCTSeriesUID)
        CT SERIES
              │
              ▼ (v5: TWO-STEP MATCHING)
        LIMBUS AI RTSTRUCT
              Step A: Geometry match (FrameOfReferenceUID + ReferencedCTSeriesUID)
              Step B: Metadata verify (SeriesDescription + StructureSetLabel)
    
    Returns
    -------
    list of dict
        List of chain result dictionaries for Excel export
    """
    chain_results = []  # Collect results for Excel export
    print(f"\n{'='*80}")
    print(f"DICOM CHAIN IDENTIFICATION (v5 Protocol)")
    print(f"Patient: {patient_id}")
    print(f"{'='*80}")
    
    # ========================================================================
    # STEP 1: Scan all DICOM files
    # ========================================================================
    print(f"\n┌─ STEP 1: Scanning DICOM files...")
    
    all_rtplans, approved_rtplans = scan_rtplan_files(patient_folder)
    all_rtstructs = scan_rtstruct_files(patient_folder)
    ct_series_dict = scan_ct_series(patient_folder)
    
    print(f"│")
    print(f"│  RTPLAN files:   {len(all_rtplans):3d} total, {len(approved_rtplans)} APPROVED")
    print(f"│  RTSTRUCT files: {len(all_rtstructs):3d} total")
    print(f"│  CT series:      {len(ct_series_dict):3d} unique")
    print(f"└─ Scan complete")
    
    # ========================================================================
    # STEP 2: Display all scanned items
    # ========================================================================
    print(f"\n{'─'*80}")
    print("SCANNED RTPLAN FILES:")
    print(f"{'─'*80}")
    for i, rtplan in enumerate(all_rtplans, 1):
        status_icon = "✓" if rtplan['approval_status'] == 'APPROVED' else "○"
        print(f"  {i}. [{status_icon}] {rtplan['filename']}")
        print(f"       Plan Name: {rtplan['plan_name']}")
        print(f"       Plan Label (300A,0002): {rtplan['plan_label']}")
        print(f"       Treatment Protocols (300A,0009): {rtplan['treatment_protocols']}")
        print(f"       Approval Status: {rtplan['approval_status']}")
        print(f"       SOP Instance UID: {rtplan['sop_instance_uid'][-20:]}...")
        print(f"       Referenced RTSTRUCT SOP UID: {rtplan['referenced_rtstruct_sop_uid'][-20:] if rtplan['referenced_rtstruct_sop_uid'] else 'N/A'}...")
    
    print(f"\n{'─'*80}")
    print("SCANNED RTSTRUCT FILES:")
    print(f"{'─'*80}")
    for i, rtstruct in enumerate(all_rtstructs, 1):
        limbus_icon = "★" if is_verified_limbus_rtstruct(rtstruct) else "○"
        print(f"  {i}. [{limbus_icon}] {rtstruct['filename']}")
        print(f"       Manufacturer Model: {rtstruct['manufacturer_model']}")
        print(f"       Operators' Name (0008,1070): {rtstruct['operators_name']}")
        print(f"       Structure Set Label: {rtstruct['structure_set_label']}")
        print(f"       Series Description: {rtstruct['series_description']}")
        print(f"       SOP Instance UID: ...{rtstruct['sop_instance_uid'][-20:]}")
        print(f"       Frame of Reference UID: ...{rtstruct['frame_of_reference_uid'][-20:]}")
        print(f"       Referenced CT Series UID: ...{rtstruct['referenced_ct_series_uid'][-20:] if rtstruct['referenced_ct_series_uid'] else 'N/A'}")
        if rtstruct['roi_interpreted_types']:
            print(f"       RT ROI Interpreted Types (3006,00A4) / Interpreters (3006,00A6):")
            for roi_name, roi_type in rtstruct['roi_interpreted_types'].items():
                interpreter = rtstruct['roi_interpreters'].get(roi_name, '')
                interp_str = f" | {interpreter}" if interpreter else ''
                print(f"         {roi_name}: {roi_type}{interp_str}")
    
    print(f"\n{'─'*80}")
    print("SCANNED CT SERIES:")
    print(f"{'─'*80}")
    for i, (series_uid, ct_info) in enumerate(ct_series_dict.items(), 1):
        print(f"  {i}. CT Series: ...{series_uid[-20:]}")
        print(f"       Frame of Reference UID: ...{ct_info['frame_ref_uid'][-20:]}")
        print(f"       Number of slices: {ct_info['file_count']}")
        print(f"       Description: {ct_info['series_description']}")
    
    # ========================================================================
    # STEP 3: Build chains for each APPROVED RTPLAN
    # ========================================================================
    if not approved_rtplans:
        print(f"\n{'='*80}")
        print("⚠ NO APPROVED RTPLANS FOUND - Cannot build chain")
        print(f"{'='*80}")
        # Record no approved RTPLAN found
        chain_results.append({
            'patient_id': patient_id,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'rtplan_name': 'N/A',
            'rtplan_label': 'N/A',
            'rtplan_treatment_protocols': 'N/A',
            'rtplan_file': 'N/A',
            'rtplan_approval_status': 'NO APPROVED RTPLAN',
            'clinical_rtstruct_file': 'N/A',
            'clinical_rtstruct_model': 'N/A',
            'clinical_frame_of_ref_uid': 'N/A',
            'clinical_ref_ct_series_uid': 'N/A',
            'ct_series_uid': 'N/A',
            'ct_series_slices': 0,
            'geometry_matched_count': 0,
            'limbus_rtstruct_file': 'N/A',
            'limbus_series_description': 'N/A',
            'limbus_structure_set_label': 'N/A',
            'clinical_rtstruct_roi_types': 'N/A',
            'clinical_rtstruct_roi_interpreters': 'N/A',
            'clinical_rtstruct_operators_name': 'N/A',
            'chain_status': 'NO APPROVED RTPLAN',
            'link1_clinical_found': False,
            'link2_ct_found': False,
            'link3_geometry_match': False,
            'link3_metadata_verified': False,
            'chain_complete': False
        })
        return chain_results
    
    for rtplan in approved_rtplans:
        print(f"\n{'='*80}")
        print(f"BUILDING CHAIN FOR APPROVED RTPLAN: {rtplan['plan_name']}")
        print(f"{'='*80}")
        
        # ====================================================================
        # Chain Link 1: RTPLAN → CLINICAL RTSTRUCT
        # ====================================================================
        print(f"\n┌─ CHAIN LINK 1: RTPLAN → CLINICAL RTSTRUCT")
        print(f"│  Matching by: ReferencedSOPInstanceUID")
        print(f"│")
        print(f"│  RTPLAN.referenced_rtstruct_sop_uid:")
        print(f"│    {rtplan['referenced_rtstruct_sop_uid']}")
        print(f"│")
        
        clinical_rtstruct = None
        for rtstruct in all_rtstructs:
            if rtstruct['sop_instance_uid'] == rtplan['referenced_rtstruct_sop_uid']:
                clinical_rtstruct = rtstruct
                break
        
        if clinical_rtstruct:
            print(f"│  ✓ MATCH FOUND:")
            print(f"│    File: {clinical_rtstruct['filename']}")
            print(f"│    Model: {clinical_rtstruct['manufacturer_model']}")
            print(f"│    Label: {clinical_rtstruct['structure_set_label']}")
            print(f"│    Frame of Reference UID: {clinical_rtstruct['frame_of_reference_uid']}")
            print(f"│    Referenced CT Series UID: {clinical_rtstruct['referenced_ct_series_uid']}")
        else:
            print(f"│  ✗ NO MATCH - Clinical RTSTRUCT not found")
            print(f"└─ CHAIN BROKEN")
            # Record broken chain at Link 1
            chain_results.append({
                'patient_id': patient_id,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'rtplan_name': rtplan['plan_name'],
                'rtplan_label': rtplan['plan_label'],
                'rtplan_treatment_protocols': rtplan['treatment_protocols'],
                'rtplan_file': rtplan['filename'],
                'rtplan_approval_status': rtplan['approval_status'],
                'clinical_rtstruct_file': 'NOT FOUND',
                'clinical_rtstruct_model': 'N/A',
                'clinical_frame_of_ref_uid': 'N/A',
                'clinical_ref_ct_series_uid': 'N/A',
                'ct_series_uid': 'N/A',
                'ct_series_slices': 0,
                'geometry_matched_count': 0,
                'limbus_rtstruct_file': 'N/A',
                'limbus_series_description': 'N/A',
                'limbus_structure_set_label': 'N/A',
                'clinical_rtstruct_roi_types': 'N/A',
                'clinical_rtstruct_roi_interpreters': 'N/A',
                'clinical_rtstruct_operators_name': 'N/A',
                'chain_status': 'BROKEN - Clinical RTSTRUCT not found',
                'link1_clinical_found': False,
                'link2_ct_found': False,
                'link3_geometry_match': False,
                'link3_metadata_verified': False,
                'chain_complete': False
            })
            continue
        print(f"└─ Link 1 complete")
        
        # ====================================================================
        # Chain Link 2: CLINICAL RTSTRUCT → CT SERIES
        # ====================================================================
        print(f"\n┌─ CHAIN LINK 2: CLINICAL RTSTRUCT → CT SERIES")
        print(f"│  Matching by: FrameOfReferenceUID + ReferencedCTSeriesUID")
        print(f"│")
        print(f"│  Clinical RTSTRUCT values:")
        print(f"│    frame_of_reference_uid: {clinical_rtstruct['frame_of_reference_uid']}")
        print(f"│    referenced_ct_series_uid: {clinical_rtstruct['referenced_ct_series_uid']}")
        print(f"│")
        
        matched_ct = None
        for series_uid, ct_info in ct_series_dict.items():
            frame_match = ct_info['frame_ref_uid'] == clinical_rtstruct['frame_of_reference_uid']
            series_match = series_uid == clinical_rtstruct['referenced_ct_series_uid']
            
            print(f"│  Checking CT Series: ...{series_uid[-20:]}")
            print(f"│    frame_ref_uid match: {frame_match} ({ct_info['frame_ref_uid'][-20:]}...)")
            print(f"│    series_uid match: {series_match}")
            
            if frame_match and series_match:
                matched_ct = ct_info
                print(f"│    → BOTH MATCH!")
                break
            print(f"│")
        
        if matched_ct:
            print(f"│")
            print(f"│  ✓ MATCH FOUND:")
            print(f"│    CT Series UID: {matched_ct['series_uid']}")
            print(f"│    Number of slices: {matched_ct['file_count']}")
        else:
            print(f"│  ✗ NO MATCH - CT series not found")
            print(f"└─ CHAIN BROKEN")
            # Record broken chain at Link 2
            chain_results.append({
                'patient_id': patient_id,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'rtplan_name': rtplan['plan_name'],
                'rtplan_label': rtplan['plan_label'],
                'rtplan_treatment_protocols': rtplan['treatment_protocols'],
                'rtplan_file': rtplan['filename'],
                'rtplan_approval_status': rtplan['approval_status'],
                'clinical_rtstruct_file': clinical_rtstruct['filename'],
                'clinical_rtstruct_model': clinical_rtstruct['manufacturer_model'],
                'clinical_frame_of_ref_uid': clinical_rtstruct['frame_of_reference_uid'],
                'clinical_ref_ct_series_uid': clinical_rtstruct['referenced_ct_series_uid'],
                'ct_series_uid': 'NOT FOUND',
                'ct_series_slices': 0,
                'geometry_matched_count': 0,
                'limbus_rtstruct_file': 'N/A',
                'limbus_series_description': 'N/A',
                'limbus_structure_set_label': 'N/A',
                'clinical_rtstruct_roi_types': '; '.join(f"{n}:{t}" for n, t in clinical_rtstruct['roi_interpreted_types'].items()),
                'clinical_rtstruct_roi_interpreters': '; '.join(f"{n}:{v}" for n, v in clinical_rtstruct['roi_interpreters'].items()),
                'clinical_rtstruct_operators_name': clinical_rtstruct['operators_name'],
                'chain_status': 'BROKEN - CT series not found',
                'link1_clinical_found': True,
                'link2_ct_found': False,
                'link3_geometry_match': False,
                'link3_metadata_verified': False,
                'chain_complete': False
            })
            continue
        print(f"└─ Link 2 complete")
        
        # ====================================================================
        # Chain Link 3: CT SERIES → LIMBUS AI RTSTRUCT (v5 TWO-STEP)
        # ====================================================================
        print(f"\n┌─ CHAIN LINK 3: CT SERIES → LIMBUS AI RTSTRUCT (v5 Two-Step)")
        print(f"│")
        print(f"│  ┌─ STEP A: Geometry Match")
        print(f"│  │  Matching by: FrameOfReferenceUID + ReferencedCTSeriesUID")
        print(f"│  │")
        print(f"│  │  Looking for RTSTRUCTs with:")
        print(f"│  │    frame_of_reference_uid == {clinical_rtstruct['frame_of_reference_uid'][-30:]}...")
        print(f"│  │    referenced_ct_series_uid == {clinical_rtstruct['referenced_ct_series_uid'][-30:]}...")
        print(f"│  │")
        
        geometry_matched = []
        for rtstruct in all_rtstructs:
            # Skip clinical RTSTRUCT itself
            if rtstruct['sop_instance_uid'] == clinical_rtstruct['sop_instance_uid']:
                continue
            
            frame_match = rtstruct['frame_of_reference_uid'] == clinical_rtstruct['frame_of_reference_uid']
            series_match = rtstruct['referenced_ct_series_uid'] == clinical_rtstruct['referenced_ct_series_uid']
            
            if frame_match and series_match:
                geometry_matched.append(rtstruct)
                print(f"│  │  ✓ Geometry match: {rtstruct['filename']}")
        
        print(f"│  │")
        print(f"│  │  Found {len(geometry_matched)} geometry-matched candidate(s)")
        print(f"│  └─ Step A complete")
        
        print(f"│")
        print(f"│  ┌─ STEP B: Metadata Verification")
        print(f"│  │  Criteria (BOTH must be true):")
        print(f"│  │    SeriesDescription == 'Limbus RTSS v1.8.0'")
        print(f"│  │    StructureSetLabel == 'Limbus RTStruct'")
        print(f"│  │")
        
        matched_limbus = None
        for candidate in geometry_matched:
            sd_match = candidate['series_description'] == 'Limbus RTSS v1.8.0'
            ssl_match = candidate['structure_set_label'] == 'Limbus RTStruct'
            
            print(f"│  │  Checking: {candidate['filename']}")
            print(f"│  │    SeriesDescription: '{candidate['series_description']}'")
            print(f"│  │      → Match: {sd_match}")
            print(f"│  │    StructureSetLabel: '{candidate['structure_set_label']}'")
            print(f"│  │      → Match: {ssl_match}")
            
            if sd_match and ssl_match:
                matched_limbus = candidate
                print(f"│  │    → VERIFIED LIMBUS!")
                break
            else:
                print(f"│  │    → NOT Limbus (failed verification)")
            print(f"│  │")
        
        print(f"│  └─ Step B complete")
        
        if matched_limbus:
            print(f"│")
            print(f"│  ✓ LIMBUS AI RTSTRUCT FOUND:")
            print(f"│    File: {matched_limbus['filename']}")
            print(f"│    Series Description: {matched_limbus['series_description']}")
            print(f"│    Structure Set Label: {matched_limbus['structure_set_label']}")
        else:
            print(f"│")
            print(f"│  ✗ NO VERIFIED LIMBUS FOUND")
            if geometry_matched:
                print(f"│    ({len(geometry_matched)} geometry-matched candidate(s) failed metadata verification)")
        print(f"└─ Link 3 complete")
        
        # ====================================================================
        # Chain Summary
        # ====================================================================
        print(f"\n{'─'*80}")
        print("CHAIN SUMMARY:")
        print(f"{'─'*80}")
        
        chain_complete = clinical_rtstruct and matched_ct and matched_limbus
        
        print(f"  APPROVED RTPLAN: {rtplan['plan_name']}")
        print(f"       │")
        print(f"       ▼ (ReferencedSOPInstanceUID match)")
        if clinical_rtstruct:
            print(f"  CLINICAL RTSTRUCT: {clinical_rtstruct['filename']} ✓")
        else:
            print(f"  CLINICAL RTSTRUCT: NOT FOUND ✗")
        print(f"       │")
        print(f"       ▼ (FrameOfReferenceUID + ReferencedCTSeriesUID)")
        if matched_ct:
            print(f"  CT SERIES: {matched_ct['file_count']} slices ✓")
        else:
            print(f"  CT SERIES: NOT FOUND ✗")
        print(f"       │")
        print(f"       ▼ (v5: Geometry + Metadata verification)")
        if matched_limbus:
            print(f"  LIMBUS AI RTSTRUCT: {matched_limbus['filename']} ✓")
        else:
            print(f"  LIMBUS AI RTSTRUCT: NOT FOUND ✗")
        
        print(f"\n  CHAIN STATUS: {'✓✓ COMPLETE' if chain_complete else '✗ INCOMPLETE'}")
        
        # Record the chain result
        chain_results.append({
            'patient_id': patient_id,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'rtplan_name': rtplan['plan_name'],
            'rtplan_label': rtplan['plan_label'],
            'rtplan_treatment_protocols': rtplan['treatment_protocols'],
            'rtplan_file': rtplan['filename'],
            'rtplan_approval_status': rtplan['approval_status'],
            'clinical_rtstruct_file': clinical_rtstruct['filename'],
            'clinical_rtstruct_model': clinical_rtstruct['manufacturer_model'],
            'clinical_frame_of_ref_uid': clinical_rtstruct['frame_of_reference_uid'],
            'clinical_ref_ct_series_uid': clinical_rtstruct['referenced_ct_series_uid'],
            'ct_series_uid': matched_ct['series_uid'] if matched_ct else 'N/A',
            'ct_series_slices': matched_ct['file_count'] if matched_ct else 0,
            'geometry_matched_count': len(geometry_matched),
            'limbus_rtstruct_file': matched_limbus['filename'] if matched_limbus else 'NOT FOUND',
            'limbus_series_description': matched_limbus['series_description'] if matched_limbus else 'N/A',
            'limbus_structure_set_label': matched_limbus['structure_set_label'] if matched_limbus else 'N/A',
            'clinical_rtstruct_roi_types': '; '.join(f"{n}:{t}" for n, t in clinical_rtstruct['roi_interpreted_types'].items()),
            'clinical_rtstruct_roi_interpreters': '; '.join(f"{n}:{v}" for n, v in clinical_rtstruct['roi_interpreters'].items()),
            'clinical_rtstruct_operators_name': clinical_rtstruct['operators_name'],
            'chain_status': 'COMPLETE' if chain_complete else 'INCOMPLETE - Limbus not found',
            'link1_clinical_found': True,
            'link2_ct_found': True,
            'link3_geometry_match': len(geometry_matched) > 0,
            'link3_metadata_verified': matched_limbus is not None,
            'chain_complete': chain_complete
        })
    
    return chain_results


# ============================================================================
# EXCEL FILE HANDLING
# ============================================================================

def save_results_to_excel(results: List[Dict], output_file: str = 'dicom_chain_results.xlsx'):
    """
    Save chain identification results to Excel file.
    
    If the file exists, updates existing patient entries or appends new ones.
    
    Parameters
    ----------
    results : list of dict
        Chain results from identify_dicom_chain_v5
    output_file : str
        Path to Excel file (default: dicom_chain_results.xlsx)
    """
    if not results:
        print("No results to save.")
        return
    
    new_df = pd.DataFrame(results)
    
    if os.path.exists(output_file):
        # Load existing data
        try:
            existing_df = pd.read_excel(output_file, engine='openpyxl')
            print(f"Loaded existing file with {len(existing_df)} record(s)")
            
            # Create a unique key for matching (patient_id + rtplan_name)
            new_df['_key'] = new_df['patient_id'] + '|' + new_df['rtplan_name']
            existing_df['_key'] = existing_df['patient_id'] + '|' + existing_df['rtplan_name']
            
            # Find which records to update vs append
            keys_to_update = set(new_df['_key']) & set(existing_df['_key'])
            keys_to_append = set(new_df['_key']) - set(existing_df['_key'])
            
            if keys_to_update:
                print(f"Updating {len(keys_to_update)} existing record(s)")
                # Remove old records that will be updated
                existing_df = existing_df[~existing_df['_key'].isin(keys_to_update)]
            
            if keys_to_append:
                print(f"Appending {len(keys_to_append)} new record(s)")
            
            # Combine: existing (without updated) + all new
            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
            
            # Remove the temporary key column
            combined_df = combined_df.drop(columns=['_key'])
            
            # Sort by patient_id and timestamp
            combined_df = combined_df.sort_values(['patient_id', 'rtplan_name', 'timestamp'])
            
            combined_df.to_excel(output_file, index=False, engine='openpyxl')
            print(f"Saved {len(combined_df)} total record(s) to {output_file}")
            
        except Exception as e:
            print(f"Error reading existing file: {e}")
            print("Creating new file instead...")
            new_df.to_excel(output_file, index=False, engine='openpyxl')
            print(f"Saved {len(new_df)} record(s) to {output_file}")
    else:
        # Create new file
        new_df.to_excel(output_file, index=False, engine='openpyxl')
        print(f"Created new file with {len(new_df)} record(s): {output_file}")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function."""
    print("="*80)
    print("DICOM Chain Metadata Inspector (v5 Protocol)")
    print("="*80)
    print()
    print("This script follows the v5 identification protocol:")
    print("  1. Find APPROVED RTPLAN")
    print("  2. Match CLINICAL RTSTRUCT by ReferencedSOPInstanceUID")
    print("  3. Match CT SERIES by FrameOfReferenceUID + ReferencedCTSeriesUID")
    print("  4. Find LIMBUS AI RTSTRUCT:")
    print("     a. Geometry match (FrameOfReferenceUID + ReferencedCTSeriesUID)")
    print("     b. Metadata verify (SeriesDescription + StructureSetLabel)")
    print()

    # -------------------------------------------------------------------------
    # Parse arguments:
    #   python check_metadata.py <folder> [max_patients]
    #
    # <folder> can be:
    #   - A single patient folder  (e.g. Z:\ICoNEA\DICOM\P0728)
    #   - A root folder containing multiple patient sub-folders
    #
    # [max_patients] optional integer: how many random patients to sample.
    #   Omit or pass 0 / 'all' to process every patient found.
    # -------------------------------------------------------------------------
    if len(sys.argv) > 1:
        input_folder = sys.argv[1]
    else:
        input_folder = input("Enter patient folder (or root DICOM folder) path: ").strip('"').strip("'")

    max_patients = 10
    if len(sys.argv) > 2:
        arg2 = sys.argv[2].strip().lower()
        if arg2 not in ('0', 'all', 'none', ''):
            try:
                max_patients = int(arg2)
            except ValueError:
                print(f"Warning: could not parse max_patients '{sys.argv[2]}', processing all patients.")

    if not os.path.exists(input_folder):
        print(f"Error: Folder does not exist: {input_folder}")
        return

    # -------------------------------------------------------------------------
    # Determine whether input_folder is a single patient or a root folder
    # -------------------------------------------------------------------------
    # Heuristic: a patient folder contains RTPLAN/RTSTRUCT/CT sub-folders
    def is_patient_folder(path):
        for sub in ('RTPLAN', 'RTSTRUCT', 'CT'):
            if os.path.isdir(os.path.join(path, sub)):
                return True
        return False

    if is_patient_folder(input_folder):
        # Single patient mode
        patient_folders = [input_folder]
    else:
        # Batch mode: collect all sub-folders that look like patient folders
        patient_folders = []
        for item in sorted(os.listdir(input_folder)):
            full_path = os.path.join(input_folder, item)
            if os.path.isdir(full_path):
                patient_folders.append(full_path)

        if not patient_folders:
            print(f"No patient sub-folders found in: {input_folder}")
            return

        print(f"Found {len(patient_folders)} patient folder(s) in root directory.")

        # Random sampling
        if max_patients is not None and max_patients < len(patient_folders):
            patient_folders = random.sample(patient_folders, max_patients)
            print(f"Randomly selected {max_patients} patient(s) for this run.")
        else:
            print(f"Processing all {len(patient_folders)} patient(s).")

    print()

    # -------------------------------------------------------------------------
    # Process each patient folder
    # -------------------------------------------------------------------------
    all_results = []
    for patient_folder in patient_folders:
        patient_id = os.path.basename(patient_folder.rstrip(os.sep))
        print(f"\n{'='*80}")
        print(f"Patient: {patient_id}")
        print(f"{'='*80}")

        results = identify_dicom_chain_v5(patient_folder, patient_id)
        if results:
            all_results.extend(results)

    # Save combined results to Excel
    if all_results:
        print(f"\n{'='*80}")
        print("SAVING RESULTS TO EXCEL")
        print(f"{'='*80}")
        save_results_to_excel(all_results)
    else:
        print("\nNo results generated.")


if __name__ == "__main__":
    main()
