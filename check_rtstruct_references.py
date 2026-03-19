"""
Check RTSTRUCT References - Verify if Limbus AI RTSTRUCT SOP Instance UID 
is referenced in the clinically approved RTSTRUCT metadata.

This script analyzes random patients to determine if there's a metadata link
between AI-generated and clinically approved structure sets.
"""

import os
import sys
import random
import pydicom
import pandas as pd
from pathlib import Path
from linkeddicom_helper import get_structs_for_ct


def translate_linkeddicom_path(linkeddicom_path, dicom_root_folder):
    """
    Translate a path from linkeddicom.ttl to the actual Windows path.
    """
    linkeddicom_path = linkeddicom_path.replace('\\', '/')
    parts = linkeddicom_path.split('/')
    
    try:
        dicom_idx = parts.index('DICOM')
        relative_parts = parts[dicom_idx + 1:]
        relative_path = os.path.join(*relative_parts)
        translated_path = os.path.join(dicom_root_folder, relative_path)
        return translated_path
    except ValueError:
        return linkeddicom_path


def discover_patient_folders(dicom_root_folder):
    """
    Discover all patient folders in the DICOM directory.
    """
    patient_folders = []
    
    if not os.path.isdir(dicom_root_folder):
        print(f"Error: DICOM root folder does not exist: {dicom_root_folder}")
        return patient_folders
    
    for item in os.listdir(dicom_root_folder):
        patient_folder = os.path.join(dicom_root_folder, item)
        if os.path.isdir(patient_folder) and item.startswith('P'):
            patient_folders.append({'patient_id': item, 'patient_folder': patient_folder})
    
    return patient_folders


def check_rtstruct_cross_references(limbus_path, aria_path):
    """
    Comprehensively check if ARIA RTSTRUCT metadata contains reference to Limbus AI RTSTRUCT.
    Searches ALL possible metadata locations including standard tags, private tags, and text fields.
    
    Parameters
    ----------
    limbus_path : str
        Path to Limbus AI RTSTRUCT file
    aria_path : str
        Path to ARIA RADonc (clinically approved) RTSTRUCT file
        
    Returns
    -------
    dict
        Dictionary with analysis results
    """
    result = {
        'limbus_sop_uid': None,
        'aria_sop_uid': None,
        'limbus_series_uid': None,
        'aria_series_uid': None,
        'series_uid_match': False,
        'reference_found': False,
        'reference_location': None,
        'reference_details': None,
        'all_findings': []  # Track all locations where UID is found
    }
    
    try:
        # Read Limbus AI RTSTRUCT
        limbus_ds = pydicom.dcmread(limbus_path, stop_before_pixels=True)
        result['limbus_sop_uid'] = str(limbus_ds.get('SOPInstanceUID', ''))
        result['limbus_series_uid'] = str(limbus_ds.get('SeriesInstanceUID', ''))
        
        # Read ARIA RADonc RTSTRUCT
        aria_ds = pydicom.dcmread(aria_path, stop_before_pixels=True)
        result['aria_sop_uid'] = str(aria_ds.get('SOPInstanceUID', ''))
        result['aria_series_uid'] = str(aria_ds.get('SeriesInstanceUID', ''))
        
        # Check if Series Instance UIDs match
        if result['limbus_series_uid'] and result['aria_series_uid']:
            result['series_uid_match'] = (result['limbus_series_uid'] == result['aria_series_uid'])
            print(f"    Series Instance UID comparison:")
            print(f"      Limbus AI: {result['limbus_series_uid']}")
            print(f"      ARIA:      {result['aria_series_uid']}")
            if result['series_uid_match']:
                print(f"      ✓✓ MATCH - Both RTSTRUCTs have the same Series Instance UID")
            else:
                print(f"      ✗ NO MATCH - Different Series Instance UIDs")
        else:
            print(f"    ⚠ Could not compare Series Instance UIDs (one or both missing)")
        
        if not result['limbus_sop_uid']:
            print(f"    ✗ No SOP Instance UID found in Limbus AI RTSTRUCT")
            return result
        
        print(f"    Searching for Limbus SOP UID: {result['limbus_sop_uid']}")
        
        # List of all DICOM tags that could potentially contain SOP Instance UID references
        sop_uid_tags = [
            (0x0008, 0x1155),  # Referenced SOP Instance UID (most common)
            (0x0008, 0x0018),  # SOP Instance UID (in referenced items)
            (0x0008, 0x1150),  # Referenced SOP Class UID (check anyway)
            (0x0008, 0x3010),  # Irradiation Event UID
            (0x0020, 0x0052),  # Frame of Reference UID (check for any match)
            (0x0040, 0xA124),  # UID in concept name code sequence
            (0x0040, 0xDB0C),  # Template Extension Creator UID
            (0x0040, 0xDB0D),  # Template Extension Organization UID
        ]
        
        # 1. Check all standard SOP UID reference tags
        print(f"    [1] Checking standard SOP UID reference tags...")
        for tag in sop_uid_tags:
            if tag in aria_ds:
                value = str(aria_ds[tag].value) if aria_ds[tag].value else ''
                if result['limbus_sop_uid'] in value:
                    finding = f"Direct tag {tag}: {value}"
                    result['all_findings'].append(finding)
                    print(f"      ✓✓ FOUND at {tag}: {value}")
                    if not result['reference_found']:
                        result['reference_found'] = True
                        result['reference_location'] = f'Direct tag {tag}'
                        result['reference_details'] = value
        
        # 2. Check specific important sequences
        print(f"    [2] Checking important sequences...")
        important_sequences = [
            ((0x300E, 0x0013), 'PredecessorStructureSetSequence'),
            ((0x0008, 0x2112), 'SourceImageSequence'),
            ((0x0008, 0x114A), 'ReferencedInstanceSequence'),
            ((0x0008, 0x1115), 'ReferencedSeriesSequence'),
            ((0x0008, 0x1140), 'ReferencedImageSequence'),
            ((0x0008, 0x1199), 'ReferencedSOPSequence'),
            ((0x0040, 0xA370), 'ReferencedRequestSequence'),
            ((0x3006, 0x0010), 'ReferencedFrameOfReferenceSequence'),
            ((0x3006, 0x0012), 'RTReferencedStudySequence'),
            ((0x3006, 0x0014), 'RTReferencedSeriesSequence'),
        ]
        
        for tag, name in important_sequences:
            if tag in aria_ds:
                print(f"      Found {name} {tag}")
                seq = aria_ds[tag]
                for idx, item in enumerate(seq):
                    # Check all possible SOP UID tags within the sequence item
                    for sop_tag in sop_uid_tags:
                        if sop_tag in item:
                            ref_uid = str(item[sop_tag].value)
                            if ref_uid == result['limbus_sop_uid']:
                                finding = f"{name}[{idx}]/{sop_tag}: {ref_uid}"
                                result['all_findings'].append(finding)
                                print(f"        ✓✓ FOUND in {name}[{idx}] at {sop_tag}")
                                if not result['reference_found']:
                                    result['reference_found'] = True
                                    result['reference_location'] = f'{name}[{idx}]'
                                    result['reference_details'] = f'Tag {sop_tag}: {ref_uid}'
        
        # 3. Deep recursive search through ALL sequences (standard and private)
        print(f"    [3] Performing comprehensive recursive search (all sequences, all tags)...")
        
        def search_all_metadata(dataset, path="", depth=0):
            """Recursively search ALL metadata for the Limbus SOP Instance UID"""
            if depth > 20:  # Prevent infinite recursion
                return
            
            for elem in dataset:
                elem_path = f"{path}/{elem.tag}" if path else str(elem.tag)
                
                try:
                    # Check if element value contains the UID (handle different VR types)
                    if elem.value is not None:
                        # For UID type values
                        if elem.VR in ['UI']:
                            if str(elem.value) == result['limbus_sop_uid']:
                                finding = f"{elem_path} (VR={elem.VR}): {elem.value}"
                                if finding not in result['all_findings']:
                                    result['all_findings'].append(finding)
                                    print(f"      ✓✓ FOUND at {elem_path} (VR={elem.VR})")
                                    if not result['reference_found']:
                                        result['reference_found'] = True
                                        result['reference_location'] = elem_path
                                        result['reference_details'] = f'VR={elem.VR}, Value={elem.value}'
                        
                        # For string type values (in case UID is stored as text)
                        elif elem.VR in ['LO', 'SH', 'ST', 'LT', 'UT', 'PN', 'CS']:
                            str_value = str(elem.value)
                            if result['limbus_sop_uid'] in str_value:
                                finding = f"{elem_path} (VR={elem.VR}): {str_value[:100]}"
                                if finding not in result['all_findings']:
                                    result['all_findings'].append(finding)
                                    print(f"      ✓✓ FOUND in text at {elem_path} (VR={elem.VR})")
                                    if not result['reference_found']:
                                        result['reference_found'] = True
                                        result['reference_location'] = elem_path
                                        result['reference_details'] = f'VR={elem.VR}, Text contains UID'
                        
                        # For sequences, recurse
                        elif elem.VR == 'SQ':
                            for idx, item in enumerate(elem.value):
                                search_all_metadata(item, f"{elem_path}[{idx}]", depth + 1)
                
                except Exception as e:
                    # Skip elements that can't be processed
                    pass
        
        search_all_metadata(aria_ds)
        
        # 4. Check private tags specifically
        print(f"    [4] Checking private tags...")
        private_tag_count = 0
        for elem in aria_ds:
            # Private tags have odd group numbers (except 0001, 0003, 0005, 0007)
            if elem.tag.group % 2 == 1 and elem.tag.group > 0x0008:
                private_tag_count += 1
                try:
                    if elem.value is not None:
                        str_value = str(elem.value)
                        if result['limbus_sop_uid'] in str_value:
                            finding = f"PRIVATE {elem.tag} (VR={elem.VR}): {str_value[:100]}"
                            if finding not in result['all_findings']:
                                result['all_findings'].append(finding)
                                print(f"      ✓✓ FOUND in private tag {elem.tag}")
                                if not result['reference_found']:
                                    result['reference_found'] = True
                                    result['reference_location'] = f'Private tag {elem.tag}'
                                    result['reference_details'] = f'VR={elem.VR}, Value={str_value[:200]}'
                except:
                    pass
        
        if private_tag_count > 0:
            print(f"      Checked {private_tag_count} private tags")
        
        # 5. Summary
        if result['all_findings']:
            print(f"    ✓✓ Total findings: {len(result['all_findings'])}")
            for finding in result['all_findings']:
                print(f"       - {finding}")
        else:
            print(f"    ✗ No references found in any metadata")
        
    except Exception as e:
        print(f"    ✗✗ Error reading RTSTRUCT files: {str(e)}")
        import traceback
        traceback.print_exc()
    
    return result


def analyze_patients(dicom_root_folder, num_patients=10):
    """
    Analyze random patients to check for RTSTRUCT cross-references.
    
    Parameters
    ----------
    dicom_root_folder : str
        Root folder containing patient subdirectories
    num_patients : int
        Number of random patients to analyze
        
    Returns
    -------
    pd.DataFrame
        Table with analysis results
    """
    print(f"Discovering patient folders in: {dicom_root_folder}")
    all_patients = discover_patient_folders(dicom_root_folder)
    
    if not all_patients:
        print("No patient folders found.")
        return pd.DataFrame()
    
    print(f"Found {len(all_patients)} patient folder(s)")
    
    # Randomly select patients
    num_to_analyze = min(num_patients, len(all_patients))
    selected_patients = random.sample(all_patients, num_to_analyze)
    print(f"Randomly selected {num_to_analyze} patient(s) for analysis\n")
    
    results = []
    
    for patient_idx, patient_data in enumerate(selected_patients):
        patient_id = patient_data['patient_id']
        patient_folder = patient_data['patient_folder']
        
        print(f"{'='*80}")
        print(f"[{patient_idx + 1}/{num_to_analyze}] Analyzing patient: {patient_id}")
        print(f"{'='*80}")
        
        # Get CT series and linked RTSTRUCTs using linkeddicom_helper
        try:
            ct_series_dict = get_structs_for_ct(patient_folder)
        except Exception as e:
            print(f"  Error reading LinkedDICOM metadata: {str(e)}\n")
            continue
        
        if not ct_series_dict:
            print(f"  No CT series found in LinkedDICOM metadata\n")
            continue
        
        print(f"  Found {len(ct_series_dict)} CT series")
        
        # Process each CT series
        for ct_series_idx, (ct_series_uid, ct_data) in enumerate(ct_series_dict.items()):
            print(f"\n  CT Series {ct_series_idx + 1}/{len(ct_series_dict)}: ...{ct_series_uid[-12:]}")
            
            # Get all RTSTRUCTs
            available_rtstructs = [(rt_uid, translate_linkeddicom_path(rt_data['path'], dicom_root_folder), rt_data) 
                                    for rt_uid, rt_data in ct_data['RTSTRUCT'].items()]
            
            print(f"  Found {len(available_rtstructs)} RTSTRUCT(s)")
            
            if len(available_rtstructs) < 2:
                print(f"  Skipping - need at least 2 RTSTRUCTs for comparison\n")
                continue
            
            # Identify Limbus AI and ARIA RADonc RTSTRUCTs
            limbus_rtstructs = []
            aria_rtstructs = []
            
            for rt_uid, rt_path, rt_data in available_rtstructs:
                try:
                    ds = pydicom.dcmread(rt_path, stop_before_pixels=True)
                    model_name = str(ds.get('ManufacturerModelName', ''))
                    
                    if model_name == 'ARIA RTM':
                        limbus_rtstructs.append((rt_uid, rt_path, rt_data))
                        print(f"    ✓ Found Limbus AI: {os.path.basename(rt_path)}")
                    elif model_name == 'ARIA RadOnc':
                        aria_rtstructs.append((rt_uid, rt_path, rt_data))
                        print(f"    ✓ Found ARIA RADonc: {os.path.basename(rt_path)}")
                except Exception as e:
                    print(f"    ✗ Error reading {os.path.basename(rt_path)}: {str(e)}")
            
            if not limbus_rtstructs or not aria_rtstructs:
                print(f"  Skipping - missing required RTSTRUCTs (Limbus: {len(limbus_rtstructs)}, ARIA: {len(aria_rtstructs)})\n")
                continue
            
            # Analyze cross-references
            limbus_path = limbus_rtstructs[0][1]
            aria_path = aria_rtstructs[0][1]
            
            print(f"\n  Checking if ARIA RTSTRUCT references Limbus AI RTSTRUCT...")
            cross_ref_result = check_rtstruct_cross_references(limbus_path, aria_path)
            
            # Record result
            result = {
                'patient_id': patient_id,
                'ct_series_uid': ct_series_uid[-12:],
                'limbus_sop_instance_uid': cross_ref_result['limbus_sop_uid'],
                'aria_sop_instance_uid': cross_ref_result['aria_sop_uid'],
                'limbus_series_instance_uid': cross_ref_result['limbus_series_uid'],
                'aria_series_instance_uid': cross_ref_result['aria_series_uid'],
                'series_uid_match': cross_ref_result['series_uid_match'],
                'reference_found': cross_ref_result['reference_found'],
                'num_findings': len(cross_ref_result['all_findings']),
                'reference_location': cross_ref_result['reference_location'] if cross_ref_result['reference_found'] else 'N/A',
                'reference_details': cross_ref_result['reference_details'] if cross_ref_result['reference_found'] else 'N/A',
                'all_findings': '; '.join(cross_ref_result['all_findings']) if cross_ref_result['all_findings'] else 'None',
                'limbus_file': os.path.basename(limbus_path),
                'aria_file': os.path.basename(aria_path)
            }
            
            results.append(result)
            
            # Print result
            if cross_ref_result['reference_found']:
                print(f"  ✓✓ REFERENCE(S) FOUND! ({len(cross_ref_result['all_findings'])} location(s))")
                print(f"     Primary location: {cross_ref_result['reference_location']}")
                print(f"     Details: {cross_ref_result['reference_details']}")
            else:
                print(f"  ✗ NO REFERENCE FOUND")
                print(f"     Limbus SOP UID not found anywhere in ARIA RTSTRUCT metadata")
            
            if cross_ref_result['series_uid_match']:
                print(f"  ℹ Series Instance UIDs MATCH between both RTSTRUCTs")
            
            print()
    
    # Create results DataFrame
    if results:
        df = pd.DataFrame(results)
        return df
    else:
        return pd.DataFrame()


def main():
    """Main execution function."""
    print("="*80)
    print("RTSTRUCT Cross-Reference Analysis")
    print("Check if Limbus AI RTSTRUCT SOP Instance UID is referenced in")
    print("clinically approved (ARIA RADonc) RTSTRUCT metadata")
    print("="*80)
    print()
    
    # Get DICOM root folder
    if len(sys.argv) > 1:
        dicom_root_folder = sys.argv[1]
    else:
        dicom_root_folder = input("Enter DICOM root folder path: ").strip('"').strip("'")
    
    if not os.path.exists(dicom_root_folder):
        print(f"Error: Folder does not exist: {dicom_root_folder}")
        return
    
    # Get number of patients to analyze
    if len(sys.argv) > 2:
        num_patients = int(sys.argv[2])
    else:
        num_patients_input = input("Number of random patients to analyze (default 10): ").strip()
        num_patients = int(num_patients_input) if num_patients_input else 10
    
    print()
    
    # Run analysis
    results = analyze_patients(dicom_root_folder, num_patients)
    
    if not results.empty:
        print("\n" + "="*80)
        print("SUMMARY RESULTS")
        print("="*80)
        print(f"\nTotal CT series analyzed: {len(results)}")
        print(f"References found: {results['reference_found'].sum()}")
        print(f"No references found: {(~results['reference_found']).sum()}")
        print(f"Series UIDs match: {results['series_uid_match'].sum()}")
        print(f"Series UIDs differ: {(~results['series_uid_match']).sum()}")
        
        if results['reference_found'].any():
            print(f"\nReference locations found:")
            for location in results[results['reference_found']]['reference_location'].unique():
                count = (results['reference_location'] == location).sum()
                print(f"  - {location}: {count} case(s)")
        
        print("\n" + "="*80)
        print("DETAILED RESULTS")
        print("="*80)
        print(results.to_string(index=False))
        
        # Save to Excel
        output_file = 'rtstruct_reference_analysis.xlsx'
        results.to_excel(output_file, index=False, engine='openpyxl')
        print(f"\nResults saved to {output_file}")
    else:
        print("\nNo results generated - no valid patient data found.")


if __name__ == "__main__":
    main()
