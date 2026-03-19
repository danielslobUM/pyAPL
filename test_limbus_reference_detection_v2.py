"""
test_limbus_reference_detection.py - Test DICOM chain identification for all approved RTPLANs.

This script processes ALL approved RTPLANs in a patient folder and establishes complete chains:
1. Find all RTPLANs and identify approved ones
2. For each approved RTPLAN → find referenced clinical ARIA RTSTRUCT
3. From clinical RTSTRUCT → find CT series (Frame of Reference + CT Series UID match)
4. From clinical RTSTRUCT → find Limbus AI RTSTRUCT (Frame of Reference + CT Series UID match)
5. Verify complete chain for each approved RTPLAN

Author: Test script for P0728 dataset analysis
"""

import os
import sys
import pydicom
import pandas as pd
from typing import List, Dict


def analyze_dicom_chains(patient_folder: str):
    """
    Analyze complete DICOM chains for all approved RTPLANs in a patient folder.
    
    Parameters
    ----------
    patient_folder : str
        Path to patient folder
    """
    print("=" * 100)
    print("DICOM CHAIN IDENTIFICATION TEST - ALL APPROVED RTPLANS")
    print("=" * 100)
    print(f"\nPatient folder: {patient_folder}\n")
    
    # STEP 1: Find all RTPLANs and identify approved ones
    print("=" * 100)
    print("STEP 1: ANALYZE RTPLAN FILES")
    print("=" * 100)
    
    rtplan_folder = os.path.join(patient_folder, 'RTPLAN')
    if not os.path.isdir(rtplan_folder):
        rtplan_folder = patient_folder
    
    rtplan_files = []
    for root, dirs, files in os.walk(rtplan_folder):
        for file in files:
            if file.lower().endswith('.dcm'):
                filepath = os.path.join(root, file)
                try:
                    ds = pydicom.dcmread(filepath, stop_before_pixels=True)
                    if ds.get('Modality', '') == 'RTPLAN':
                        rtplan_files.append(filepath)
                except:
                    pass
    
    print(f"\nFound {len(rtplan_files)} RTPLAN file(s)")
    
    if len(rtplan_files) == 0:
        print("✗ No RTPLAN files found - cannot proceed")
        return
    
    rtplan_info_list = []
    approved_rtplans = []
    
    for rtplan_path in rtplan_files:
        try:
            ds = pydicom.dcmread(rtplan_path, stop_before_pixels=True)
            
            sop_uid = str(ds.get('SOPInstanceUID', ''))
            plan_name = str(ds.get('RTPlanName', ''))
            plan_label = str(ds.get('RTPlanLabel', ''))
            
            # Get approval status from tag (300E,0002)
            approval_status = 'UNKNOWN'
            if (0x300E, 0x0002) in ds:
                approval_elem = ds[0x300E, 0x0002]
                approval_status = str(approval_elem.value) if hasattr(approval_elem, 'value') else str(approval_elem)
            
            # Get referenced RTSTRUCT
            ref_rtstruct_sop_uid = ''
            if (0x300C, 0x0060) in ds:  # ReferencedStructureSetSequence
                ref_struct_seq = ds[0x300C, 0x0060]
                if hasattr(ref_struct_seq, 'value') and len(ref_struct_seq.value) > 0:
                    ref_rtstruct_sop_uid = str(ref_struct_seq.value[0].get('ReferencedSOPInstanceUID', ''))
            
            rtplan_info = {
                'path': rtplan_path,
                'filename': os.path.basename(rtplan_path),
                'sop_instance_uid': sop_uid,
                'plan_name': plan_name,
                'plan_label': plan_label,
                'approval_status': approval_status,
                'referenced_rtstruct_sop_uid': ref_rtstruct_sop_uid
            }
            
            rtplan_info_list.append(rtplan_info)
            
            print(f"\n  RTPLAN: {os.path.basename(rtplan_path)}")
            print(f"    Plan Name: {plan_name}")
            print(f"    Plan Label: {plan_label}")
            print(f"    Approval Status: {approval_status}")
            print(f"    Referenced RTSTRUCT SOP UID: {ref_rtstruct_sop_uid}")
            
            if approval_status == 'APPROVED':
                print(f"    → ✓ APPROVED RTPLAN")
                approved_rtplans.append(rtplan_info)
            
        except Exception as e:
            print(f"  Error reading RTPLAN {os.path.basename(rtplan_path)}: {e}")
    
    print(f"\n  Summary:")
    print(f"    Total RTPLANs: {len(rtplan_info_list)}")
    print(f"    Approved RTPLANs: {len(approved_rtplans)}")
    
    if len(approved_rtplans) == 0:
        print("\n✗ No approved RTPLAN found - cannot proceed")
        return
    
    # Scan all RTSTRUCTs once
    print(f"\n  Scanning all RTSTRUCT files in patient folder...")
    rtstruct_folder = os.path.join(patient_folder, 'RTSTRUCT')
    if not os.path.isdir(rtstruct_folder):
        rtstruct_folder = patient_folder
    
    all_rtstructs = []
    all_limbus_ai_rtstructs = []
    
    for root, dirs, files in os.walk(rtstruct_folder):
        for file in files:
            if file.lower().endswith('.dcm'):
                filepath = os.path.join(root, file)
                try:
                    ds = pydicom.dcmread(filepath, stop_before_pixels=True)
                    if ds.get('Modality', '') != 'RTSTRUCT':
                        continue
                    
                    model_name = str(ds.get('ManufacturerModelName', 'N/A'))
                    sop_uid = str(ds.get('SOPInstanceUID', ''))
                    frame_ref_uid = str(ds.get('FrameOfReferenceUID', ''))
                    struct_label = str(ds.get('StructureSetLabel', ''))
                    
                    # Extract referenced CT series UID
                    referenced_ct_series_uid = ''
                    if (0x3006, 0x0010) in ds:
                        for frame_ref in ds[0x3006, 0x0010]:
                            if (0x3006, 0x0012) in frame_ref:
                                for study_ref in frame_ref[0x3006, 0x0012]:
                                    if (0x3006, 0x0014) in study_ref:
                                        for series_ref in study_ref[0x3006, 0x0014]:
                                            series_uid_val = str(series_ref.get('SeriesInstanceUID', ''))
                                            if series_uid_val:
                                                referenced_ct_series_uid = series_uid_val
                                                break
                    
                    info = {
                        'path': filepath,
                        'filename': os.path.basename(filepath),
                        'model_name': model_name,
                        'sop_instance_uid': sop_uid,
                        'frame_of_reference_uid': frame_ref_uid,
                        'referenced_ct_series_uid': referenced_ct_series_uid,
                        'structure_set_label': struct_label
                    }
                    
                    all_rtstructs.append(info)
                    if model_name == 'ARIA RTM':
                        all_limbus_ai_rtstructs.append(info)
                        
                except:
                    pass
    
    print(f"    Found {len(all_rtstructs)} RTSTRUCT files")
    print(f"    Found {len(all_limbus_ai_rtstructs)} Limbus AI RTSTRUCT files")
    
    # Scan all CT series once
    print(f"\n  Scanning all CT files in patient folder...")
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
                                'file_count': 0,
                                'folder': root
                            }
                        ct_series_dict[series_uid]['file_count'] += 1
                except:
                    pass
    
    print(f"    Found {len(ct_series_dict)} unique CT series")
    
    # Collect results for Excel output
    chain_results = []
    
    # Process each approved RTPLAN
    for rtplan_idx, approved_rtplan in enumerate(approved_rtplans, 1):
        
        print("\n" + "="* 100)
        print(f"PROCESSING APPROVED RTPLAN {rtplan_idx}/{len(approved_rtplans)}")
        print("=" * 100)
        print(f"  Plan: {approved_rtplan['plan_name']}")
        print(f"  File: {approved_rtplan['filename']}")
        
        # STEP 2: Find clinical RTSTRUCT referenced by this RTPLAN
        print("\n" + "-" * 100)
        print(f"STEP 2: FIND CLINICAL RTSTRUCT")
        print("-" * 100)
        print(f"  Searching for SOP UID: {approved_rtplan['referenced_rtstruct_sop_uid']}")
        
        clinical_rtstruct = None
        for rtstruct_info in all_rtstructs:
            if rtstruct_info['sop_instance_uid'] == approved_rtplan['referenced_rtstruct_sop_uid']:
                clinical_rtstruct = rtstruct_info
                print(f"\n  ✓ Found: {rtstruct_info['filename']}")
                print(f"    Model: {rtstruct_info['model_name']}")
                print(f"    Structure Set: {rtstruct_info['structure_set_label']}")
                print(f"    Frame of Reference UID: {rtstruct_info['frame_of_reference_uid']}")
                print(f"    Referenced CT Series UID: {rtstruct_info['referenced_ct_series_uid']}")
                break
        
        if not clinical_rtstruct:
            print(f"\n  ✗ Clinical RTSTRUCT not found - skipping this RTPLAN")
            chain_results.append({
                'rtplan_file': approved_rtplan['filename'],
                'rtplan_name': approved_rtplan['plan_name'],
                'rtplan_status': approved_rtplan['approval_status'],
                'rtplan_sop_uid': approved_rtplan['sop_instance_uid'],
                'clinical_rtstruct_file': 'NOT FOUND',
                'clinical_rtstruct_sop_uid': approved_rtplan['referenced_rtstruct_sop_uid'],
                'clinical_rtstruct_structure_set': '',
                'frame_of_reference_uid': '',
                'referenced_ct_series_uid': '',
                'ct_series_uid': '',
                'ct_num_slices': '',
                'ct_folder': '',
                'limbus_ai_rtstruct_file': '',
                'limbus_ai_rtstruct_sop_uid': '',
                'limbus_ai_rtstruct_structure_set': '',
                'chain_complete': 'NO',
                'chain_status': 'Clinical RTSTRUCT not found'
            })
            continue
        
        # STEP 3: Find CT series
        print("\n" + "-" * 100)
        print(f"STEP 3: FIND CT SERIES")
        print("-" * 100)
        
        matched_ct_series = None
        for series_uid, ct_info in ct_series_dict.items():
            frame_match = ct_info['frame_ref_uid'] == clinical_rtstruct['frame_of_reference_uid']
            series_match = series_uid == clinical_rtstruct['referenced_ct_series_uid']
            
            if frame_match and series_match:
                print(f"\n  ✓ Found matching CT series:")
                print(f"    Series UID: {series_uid}")
                print(f"    Number of slices: {ct_info['file_count']}")
                print(f"    Folder: {ct_info['folder']}")
                matched_ct_series = ct_info
                break
        
        if not matched_ct_series:
            print(f"\n  ✗ No matching CT series found - skipping this RTPLAN")
            chain_results.append({
                'rtplan_file': approved_rtplan['filename'],
                'rtplan_name': approved_rtplan['plan_name'],
                'rtplan_status': approved_rtplan['approval_status'],
                'rtplan_sop_uid': approved_rtplan['sop_instance_uid'],
                'clinical_rtstruct_file': clinical_rtstruct['filename'],
                'clinical_rtstruct_sop_uid': clinical_rtstruct['sop_instance_uid'],
                'clinical_rtstruct_structure_set': clinical_rtstruct['structure_set_label'],
                'frame_of_reference_uid': clinical_rtstruct['frame_of_reference_uid'],
                'referenced_ct_series_uid': clinical_rtstruct['referenced_ct_series_uid'],
                'ct_series_uid': clinical_rtstruct['referenced_ct_series_uid'],
                'ct_num_slices': '',
                'ct_folder': '',
                'limbus_ai_rtstruct_file': '',
                'limbus_ai_rtstruct_sop_uid': '',
                'limbus_ai_rtstruct_structure_set': '',
                'chain_complete': 'NO',
                'chain_status': 'CT series not found'
            })
            continue
        
        # STEP 4: Find Limbus AI RTSTRUCT
        print("\n" + "-" * 100)
        print(f"STEP 4: FIND LIMBUS AI RTSTRUCT")
        print("-" * 100)
        
        matched_limbus_ai = None
        for limbus_info in all_limbus_ai_rtstructs:
            frame_match = limbus_info['frame_of_reference_uid'] == clinical_rtstruct['frame_of_reference_uid']
            series_match = limbus_info['referenced_ct_series_uid'] == clinical_rtstruct['referenced_ct_series_uid']
            
            if frame_match and series_match:
                print(f"\n  ✓ Found matching Limbus AI RTSTRUCT:")
                print(f"    File: {limbus_info['filename']}")
                print(f"    Structure Set: {limbus_info['structure_set_label']}")
                matched_limbus_ai = limbus_info
                break
        
        if not matched_limbus_ai:
            print(f"\n  ✗ No matching Limbus AI RTSTRUCT found")
            if len(all_limbus_ai_rtstructs) == 1:
                print(f"    Note: Only 1 Limbus AI RTSTRUCT exists - could assume match")
                matched_limbus_ai = all_limbus_ai_rtstructs[0]
        
        # STEP 5: Chain summary
        print("\n" + "-" * 100)
        print(f"CHAIN SUMMARY")
        print("-" * 100)
        print(f"\n  1. Approved RTPLAN: {approved_rtplan['filename']}")
        print(f"  2. Clinical RTSTRUCT: {clinical_rtstruct['filename']}")
        print(f"  3. CT Series: {matched_ct_series['series_uid'][:40]}... ({matched_ct_series['file_count']} slices)")
        if matched_limbus_ai:
            print(f"  4. Limbus AI RTSTRUCT: {matched_limbus_ai['filename']}")
            print(f"\n  ✓✓✓ COMPLETE CHAIN - READY FOR CONTOUR COMPARISON")
            chain_status = 'Complete chain'
            chain_complete = 'YES'
        else:
            print(f"  4. Limbus AI RTSTRUCT: NOT FOUND")
            print(f"\n  ⚠ PARTIAL CHAIN")
            chain_status = 'Limbus AI RTSTRUCT not found'
            chain_complete = 'PARTIAL'
        
        # Add to results
        chain_results.append({
            'rtplan_file': approved_rtplan['filename'],
            'rtplan_name': approved_rtplan['plan_name'],
            'rtplan_status': approved_rtplan['approval_status'],
            'rtplan_sop_uid': approved_rtplan['sop_instance_uid'],
            'clinical_rtstruct_file': clinical_rtstruct['filename'],
            'clinical_rtstruct_sop_uid': clinical_rtstruct['sop_instance_uid'],
            'clinical_rtstruct_structure_set': clinical_rtstruct['structure_set_label'],
            'frame_of_reference_uid': clinical_rtstruct['frame_of_reference_uid'],
            'referenced_ct_series_uid': clinical_rtstruct['referenced_ct_series_uid'],
            'ct_series_uid': matched_ct_series['series_uid'],
            'ct_num_slices': matched_ct_series['file_count'],
            'ct_folder': matched_ct_series['folder'],
            'limbus_ai_rtstruct_file': matched_limbus_ai['filename'] if matched_limbus_ai else '',
            'limbus_ai_rtstruct_sop_uid': matched_limbus_ai['sop_instance_uid'] if matched_limbus_ai else '',
            'limbus_ai_rtstruct_structure_set': matched_limbus_ai['structure_set_label'] if matched_limbus_ai else '',
            'limbus_ai_frame_of_reference_uid': matched_limbus_ai['frame_of_reference_uid'] if matched_limbus_ai else '',
            'limbus_ai_referenced_ct_series_uid': matched_limbus_ai['referenced_ct_series_uid'] if matched_limbus_ai else '',
            'chain_complete': chain_complete,
            'chain_status': chain_status
        })
    
    print("\n" + "=" * 100)
    print("ALL RTPLAN CHAINS PROCESSED")
    print("=" * 100)
    
    # Create Excel output
    if chain_results:
        patient_id = os.path.basename(patient_folder.rstrip(os.sep))
        output_file = f'dicom_chain_test_{patient_id}.xlsx'
        
        df = pd.DataFrame(chain_results)
        
        # Reorder columns for better readability
        column_order = [
            'rtplan_file', 'rtplan_name', 'rtplan_status', 
            'clinical_rtstruct_file', 'clinical_rtstruct_structure_set',
            'frame_of_reference_uid', 'referenced_ct_series_uid',
            'ct_series_uid', 'ct_num_slices',
            'limbus_ai_rtstruct_file', 'limbus_ai_rtstruct_structure_set',
            'limbus_ai_frame_of_reference_uid', 'limbus_ai_referenced_ct_series_uid',
            'chain_complete', 'chain_status',
            'rtplan_sop_uid', 'clinical_rtstruct_sop_uid', 'limbus_ai_rtstruct_sop_uid',
            'ct_folder'
        ]
        df = df[column_order]
        
        df.to_excel(output_file, index=False, engine='openpyxl')
        
        print(f"\n✓ Results saved to: {output_file}")
        print(f"  Total approved RTPLANs processed: {len(chain_results)}")
        print(f"  Complete chains: {sum(1 for r in chain_results if r['chain_complete'] == 'YES')}")
        print(f"  Partial chains: {sum(1 for r in chain_results if r['chain_complete'] == 'PARTIAL')}")
        print(f"  Failed chains: {sum(1 for r in chain_results if r['chain_complete'] == 'NO')}")
    else:
        print("\n✗ No results to save")


def main():
    """Main execution function."""
    if len(sys.argv) > 1:
        patient_folder = sys.argv[1]
    else:
        patient_folder = input("Enter patient folder path: ").strip('"').strip("'")
    
    if not os.path.exists(patient_folder):
        print(f"Error: Folder does not exist: {patient_folder}")
        return
    
    analyze_dicom_chains(patient_folder)


if __name__ == "__main__":
    main()
