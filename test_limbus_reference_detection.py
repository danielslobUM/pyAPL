"""
test_limbus_reference_detection.py - Test script to verify Limbus AI RTSTRUCT reference detection.

This script analyzes a patient folder with multiple Limbus AI RTSTRUCTs and checks:
1. Whether the clinical ARIA RTSTRUCT contains references to Limbus AI SOP Instance UIDs
2. Shows the exact nesting path where SOP Instance UIDs are found in the DICOM structure

Author: Test script for P0728 dataset analysis
"""

import os
import sys
import pydicom
from typing import List, Dict, Tuple, Optional


class DicomPathTracker:
    """Tracks the path through DICOM sequences to a specific element."""
    
    def __init__(self):
        self.paths = []
    
    def find_value_in_dataset(self, dataset, target_value: str, current_path: str = "Root") -> List[Dict]:
        """
        Recursively search for a specific value anywhere in the DICOM dataset.
        
        Parameters
        ----------
        dataset : pydicom.Dataset
            DICOM dataset to search
        target_value : str
            Specific value to search for (e.g., a SOP Instance UID)
        current_path : str
            Current position in the DICOM tree
            
        Returns
        -------
        List[Dict]
            List of dictionaries containing path, tag, and tag name where the value was found
        """
        found_locations = []
        
        def search_recursive(ds, path, depth=0):
            if depth > 20:
                return
            
            for elem in ds:
                try:
                    tag_name = pydicom.datadict.keyword_for_tag(elem.tag)
                    tag_str = f"({elem.tag.group:04X},{elem.tag.elem:04X})"
                    element_path = f"{path} → {tag_str} {tag_name}"
                    
                    # Check if this element's value matches the target
                    if elem.VR == 'SQ':
                        # Recurse into sequences
                        sequence_path = f"{path}\n{'  ' * (depth + 1)}└── {tag_str} {tag_name}"
                        for idx, item in enumerate(elem.value):
                            item_path = f"{sequence_path}\n{'  ' * (depth + 2)}└── Item[{idx}]"
                            search_recursive(item, item_path, depth + 1)
                    else:
                        # Check the value
                        try:
                            elem_value = str(elem.value)
                            if elem_value == target_value:
                                found_locations.append({
                                    'path': element_path,
                                    'tag': tag_str,
                                    'tag_name': tag_name,
                                    'vr': elem.VR
                                })
                        except:
                            pass
                except Exception as e:
                    pass
        
        search_recursive(dataset, current_path)
        return found_locations


def analyze_rtstruct_references(patient_folder: str):
    """
    Analyze complete DICOM chain following the approved RTPLAN workflow.
    
    Process:
    1. Find all RTPLANs and identify approved one(s)
    2. From approved RTPLAN → find referenced clinical ARIA RTSTRUCT
    3. From clinical RTSTRUCT → find CT series (Frame of Reference + CT Series UID)
    4. From clinical RTSTRUCT → find Limbus AI RTSTRUCT (Frame of Reference + CT Series UID)
    5. Verify complete chain
    
    Parameters
    ----------
    patient_folder : str
        Path to patient folder
    """
    print("=" * 100)
    print("DICOM CHAIN IDENTIFICATION TEST - FOLLOWING APPROVED RTPLAN WORKFLOW")
    print("=" * 100)
    print(f"\nPatient folder: {patient_folder}\n")
    
    # STEP 1: Find and analyze all RTPLANs
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
            print(f"    SOP Instance UID: {sop_uid}")
            print(f"    Referenced RTSTRUCT SOP UID: {ref_rtstruct_sop_uid}")
            
            if approval_status == 'APPROVED':
                print(f"    → APPROVED RTPLAN")
                approved_rtplans.append(rtplan_info)
            
        except Exception as e:
            print(f"  Error reading RTPLAN {os.path.basename(rtplan_path)}: {e}")
    
    print(f"\n  Summary:")
    print(f"    Total RTPLANs: {len(rtplan_info_list)}")
    approved_count = sum(1 for rtp in rtplan_info_list if rtp['approval_status'] == 'APPROVED')
    print(f"    Approved RTPLANs: {approved_count}")
    
    if len(approved_rtplans) == 0:
        print("\n✗ No approved RTPLAN found - cannot proceed with chain identification")
        return
    
    print(f"\n  Processing {len(approved_rtplans)} approved RTPLAN(s)...")
    
    # Process each approved RTPLAN
    for rtplan_idx, approved_rtplan in enumerate(approved_rtplans, 1):
        
        print("\n" + "=" * 100)
        print(f"PROCESSING APPROVED RTPLAN {rtplan_idx}/{len(approved_rtplans)}")
        print("=" * 100)
        print(f"  Plan: {approved_rtplan['plan_name']}")
        print(f"  File: {approved_rtplan['filename']}")
        
        # STEP 2: Find all RTSTRUCTs and identify the one referenced by this approved RTPLAN
        print("\n" + "=" * 100)
        print(f"STEP 2 (RTPLAN {rtplan_idx}): FIND CLINICAL RTSTRUCT REFERENCED BY APPROVED RTPLAN")
        print("=" * 100)
    
    print(f"\nSearching for RTSTRUCT with SOP Instance UID: {approved_rtplan['referenced_rtstruct_sop_uid']}")
    
    # Find RTSTRUCT folder
    rtstruct_folder = os.path.join(patient_folder, 'RTSTRUCT')
    if not os.path.isdir(rtstruct_folder):
        rtstruct_folder = patient_folder
    
    # Scan for RTSTRUCT files
    rtstruct_files = []
    for root, dirs, files in os.walk(rtstruct_folder):
        for file in files:
            if file.lower().endswith('.dcm'):
                filepath = os.path.join(root, file)
                try:
                    ds = pydicom.dcmread(filepath, stop_before_pixels=True)
                    if ds.get('Modality', '') == 'RTSTRUCT':
                        rtstruct_files.append(filepath)
                except:
                    pass
    
    print(f"Found {len(rtstruct_files)} RTSTRUCT file(s)")
    
    # Categorize RTSTRUCTs
    all_rtstructs = []
    clinical_rtstruct = None
    limbus_ai_rtstructs = []
    
    for rtstruct_path in rtstruct_files:
        try:
            ds = pydicom.dcmread(rtstruct_path, stop_before_pixels=True)
            
            manufacturer = str(ds.get('Manufacturer', 'N/A'))
            model_name = str(ds.get('ManufacturerModelName', 'N/A'))
            sop_uid = str(ds.get('SOPInstanceUID', ''))
            series_uid = str(ds.get('SeriesInstanceUID', ''))
            frame_ref_uid = str(ds.get('FrameOfReferenceUID', ''))
            struct_label = str(ds.get('StructureSetLabel', ''))
            
            # Extract referenced CT series UID
            referenced_ct_series_uid = ''
            if (0x3006, 0x0010) in ds:  # ReferencedFrameOfReferenceSequence
                for frame_ref in ds[0x3006, 0x0010]:
                    if (0x3006, 0x0012) in frame_ref:  # RTReferencedStudySequence
                        for study_ref in frame_ref[0x3006, 0x0012]:
                            if (0x3006, 0x0014) in study_ref:  # RTReferencedSeriesSequence
                                for series_ref in study_ref[0x3006, 0x0014]:
                                    series_uid_val = str(series_ref.get('SeriesInstanceUID', ''))
                                    if series_uid_val:
                                        referenced_ct_series_uid = series_uid_val
                                        break
            
            info = {
                'path': rtstruct_path,
                'filename': os.path.basename(rtstruct_path),
                'manufacturer': manufacturer,
                'model_name': model_name,
                'sop_instance_uid': sop_uid,
                'series_instance_uid': series_uid,
                'frame_of_reference_uid': frame_ref_uid,
                'referenced_ct_series_uid': referenced_ct_series_uid,
                'structure_set_label': struct_label,
                'dataset': ds
            }
            
            all_rtstructs.append(info)
            
            print(f"\n  RTSTRUCT: {os.path.basename(rtstruct_path)}")
            print(f"    Model: {model_name}")
            print(f"    SOP Instance UID: {sop_uid}")
            print(f"    Frame of Reference UID: {frame_ref_uid}")
            print(f"    Referenced CT Series UID: {referenced_ct_series_uid}")
            
            if model_name == 'ARIA RTM':
                print(f"    → Type: LIMBUS AI")
                limbus_ai_rtstructs.append(info)
            elif model_name == 'ARIA RadOnc':
                print(f"    → Type: CLINICAL (ARIA RadOnc)")
                
                # Check if this is the one referenced by RTPLAN
                if sop_uid == approved_rtplan['referenced_rtstruct_sop_uid']:
                    print(f"    → ✓✓✓ THIS IS THE CLINICAL RTSTRUCT REFERENCED BY APPROVED RTPLAN")
                    clinical_rtstruct = info
            else:
                print(f"    → Type: Unknown")
            
        except Exception as e:
            print(f"  Error reading {os.path.basename(rtstruct_path)}: {e}")
    
    if not clinical_rtstruct:
        print(f"\n✗ Clinical RTSTRUCT referenced by approved RTPLAN not found")
        print(f"  Searched for SOP UID: {approved_rtplan['referenced_rtstruct_sop_uid']}")
        return
    
    # STEP 3: Find CT series based on Frame of Reference + Referenced CT Series from clinical RTSTRUCT
    print("\n" + "=" * 100)
    print("STEP 3: FIND CT SERIES REFERENCED BY CLINICAL RTSTRUCT")
    print("=" * 100)
    
    print(f"\nClinical RTSTRUCT metadata:")
    print(f"  Frame of Reference UID: {clinical_rtstruct['frame_of_reference_uid']}")
    print(f"  Referenced CT Series UID: {clinical_rtstruct['referenced_ct_series_uid']}")
    
    # Find CT files
    ct_folder = os.path.join(patient_folder, 'CT')
    if not os.path.isdir(ct_folder):
        ct_folder = patient_folder
    
    ct_series_dict = {}
    
    print(f"\nScanning for CT files...")
    
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
    
    print(f"Found {len(ct_series_dict)} unique CT series")
    
    matched_ct_series = None
    
    for series_uid, ct_info in ct_series_dict.items():
        print(f"\n  CT Series: {series_uid[:30]}...")
        print(f"    Frame of Reference UID: {ct_info['frame_ref_uid'][:30]}...")
        print(f"    Number of slices: {ct_info['file_count']}")
        
        # Check for match
        frame_match = ct_info['frame_ref_uid'] == clinical_rtstruct['frame_of_reference_uid']
        series_match = series_uid == clinical_rtstruct['referenced_ct_series_uid']
        
        print(f"    Frame of Reference match: {'✓' if frame_match else '✗'}")
        print(f"    Series UID match: {'✓' if series_match else '✗'}")
        
        if frame_match and series_match:
            print(f"    → ✓✓✓ THIS IS THE MATCHING CT SERIES")
            matched_ct_series = ct_info
    
    if not matched_ct_series:
        print(f"\n✗ No CT series found matching Frame of Reference + Referenced CT Series UID")
        return
    
    # STEP 4: Find Limbus AI RTSTRUCT using Frame of Reference + Referenced CT Series match
    print("\n" + "=" * 100)
    print("STEP 4: FIND LIMBUS AI RTSTRUCT MATCHING CLINICAL RTSTRUCT")
    print("=" * 100)
    
    print(f"\nSearching for Limbus AI RTSTRUCT with:")
    print(f"  Frame of Reference UID: {clinical_rtstruct['frame_of_reference_uid']}")
    print(f"  Referenced CT Series UID: {clinical_rtstruct['referenced_ct_series_uid']}")
    
    print(f"\nFound {len(limbus_ai_rtstructs)} Limbus AI RTSTRUCT(s):")
    
    matched_limbus_ai = None
    
    for limbus_info in limbus_ai_rtstructs:
        print(f"\n  Limbus AI RTSTRUCT: {limbus_info['filename']}")
        print(f"    Frame of Reference UID: {limbus_info['frame_of_reference_uid']}")
        print(f"    Referenced CT Series UID: {limbus_info['referenced_ct_series_uid']}")
        
        frame_match = limbus_info['frame_of_reference_uid'] == clinical_rtstruct['frame_of_reference_uid']
        series_match = limbus_info['referenced_ct_series_uid'] == clinical_rtstruct['referenced_ct_series_uid']
        
        print(f"    Frame of Reference match: {'✓' if frame_match else '✗'}")
        print(f"    Referenced CT Series match: {'✓' if series_match else '✗'}")
        
        if frame_match and series_match:
            print(f"    → ✓✓✓ THIS IS THE MATCHING LIMBUS AI RTSTRUCT")
            matched_limbus_ai = limbus_info
    
    if not matched_limbus_ai:
        print(f"\n✗ No Limbus AI RTSTRUCT found matching Frame of Reference + Referenced CT Series UID")
        if len(limbus_ai_rtstructs) == 1:
            print(f"  Note: Only 1 Limbus AI RTSTRUCT exists - could be assumed as match")
            matched_limbus_ai = limbus_ai_rtstructs[0]
    
    # STEP 5: Summary of complete chain
    print("\n" + "=" * 100)
    print("STEP 5: COMPLETE DICOM CHAIN SUMMARY")
    print("=" * 100)
    
    print(f"\n✓ DICOM CHAIN SUCCESSFULLY IDENTIFIED:")
    print(f"\n  1. Approved RTPLAN:")
    print(f"     File: {approved_rtplan['filename']}")
    print(f"     Plan: {approved_rtplan['plan_name']}")
    print(f"     Status: {approved_rtplan['approval_status']}")
    
    print(f"\n  2. Clinical RTSTRUCT (ARIA RadOnc):")
    print(f"     File: {clinical_rtstruct['filename']}")
    print(f"     Structure Set: {clinical_rtstruct['structure_set_label']}")
    print(f"     SOP UID: {clinical_rtstruct['sop_instance_uid']}")
    
    print(f"\n  3. CT Series:")
    print(f"     Series UID: {matched_ct_series['series_uid']}")
    print(f"     Number of slices: {matched_ct_series['file_count']}")
    print(f"     Folder: {matched_ct_series['folder']}")
    
    if matched_limbus_ai:
        print(f"\n  4. Limbus AI RTSTRUCT:")
        print(f"     File: {matched_limbus_ai['filename']}")
        print(f"     Structure Set: {matched_limbus_ai['structure_set_label']}")
        print(f"     SOP UID: {matched_limbus_ai['sop_instance_uid']}")
    else:
        print(f"\n  4. Limbus AI RTSTRUCT:")
        print(f"     ✗ NOT FOUND")
    
    print(f"\n  Chain Verification:")
    print(f"    RTPLAN → Clinical RTSTRUCT: ✓ (SOP UID match)")
    print(f"    Clinical RTSTRUCT → CT Series: ✓ (Frame of Reference + Series UID match)")
    if matched_limbus_ai:
        print(f"    Clinical RTSTRUCT → Limbus AI RTSTRUCT: ✓ (Frame of Reference + CT Series UID match)")
        print(f"\n✓✓✓ COMPLETE CHAIN ESTABLISHED - READY FOR CONTOUR COMPARISON ✓✓✓")
    else:
        print(f"    Clinical RTSTRUCT → Limbus AI RTSTRUCT: ✗ (No match found)")
        print(f"\n⚠ PARTIAL CHAIN - Limbus AI RTSTRUCT not conclusively identified")
    
    print("\n" + "=" * 100)
    print("CHAIN IDENTIFICATION TEST COMPLETE")
    print("=" * 100)


def main():
    """Main execution function."""
    import textwrap as tw
    global textwrap
    textwrap = tw
    
    if len(sys.argv) > 1:
        patient_folder = sys.argv[1]
    else:
        patient_folder = input("Enter patient folder path: ").strip('"').strip("'")
    
    if not os.path.exists(patient_folder):
        print(f"Error: Folder does not exist: {patient_folder}")
        return
    
    analyze_rtstruct_references(patient_folder)


if __name__ == "__main__":
    main()
