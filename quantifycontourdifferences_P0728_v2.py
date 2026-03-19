"""
quantifycontourdifferences_P0728_v2 - Automated contour comparison using DICOM chain identification

This script automatically fetches the correct data from all patients in the dataset
using the DICOM chain identification method:
1. Find all approved RTPLANs in patient folder
2. For each approved RTPLAN → find referenced clinical ARIA RTSTRUCT (via SOP Instance UID)
3. From clinical RTSTRUCT → find CT series (Frame of Reference + CT Series UID match)
4. From clinical RTSTRUCT → find Limbus AI RTSTRUCT (Frame of Reference + CT Series UID match)
5. Compare clinical ARIA RTSTRUCT with Limbus AI RTSTRUCT

Folder structure:
DICOM -> Pxxxxxxxxxxxxxxxx -> CT/RTDOSE/RTPLAN/RTSTRUCT (folders) -> yyyymmdd -> .dcm files

History
-------
Created for P0728 dataset analysis
Refactored from quantifycontourdifferences_P0728.py to use new DICOM chain identification
"""

import os
import sys
import warnings
import random
import pydicom
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional

from read_dicomct_light import read_dicomct_light
from read_dicomrtstruct import read_dicomrtstruct
from read_dicomrtplan import read_dicomrtplan
from compose_struct_matrix import compose_struct_matrix
from calculate_dice_logical import calculate_dice_logical
from calculate_surface_dsc import calculate_surface_dsc
from calculate_path_length import calculate_path_length
from has_contour_points_local import has_contour_points_local


# ============================================================================
# DICOM CHAIN IDENTIFICATION FUNCTIONS (from test_limbus_reference_detection_v2.py)
# ============================================================================

def scan_rtplan_files(patient_folder: str) -> Tuple[List[Dict], List[Dict]]:
    """
    Scan patient folder for all RTPLAN files and identify approved ones.
    
    Parameters
    ----------
    patient_folder : str
        Path to patient folder
        
    Returns
    -------
    tuple
        (all_rtplans, approved_rtplans) - Lists of RTPLAN info dictionaries
    """
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
    
    all_rtplans = []
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
            
            # Get referenced RTSTRUCT SOP Instance UID
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
            
            all_rtplans.append(rtplan_info)
            
            if approval_status == 'APPROVED':
                approved_rtplans.append(rtplan_info)
                
        except Exception as e:
            pass
    
    return all_rtplans, approved_rtplans


def scan_rtstruct_files(patient_folder: str) -> Tuple[List[Dict], List[Dict]]:
    """
    Scan patient folder for all RTSTRUCT files.
    
    Parameters
    ----------
    patient_folder : str
        Path to patient folder
        
    Returns
    -------
    tuple
        (all_rtstructs, limbus_ai_rtstructs) - Lists of RTSTRUCT info dictionaries
    """
    rtstruct_folder = os.path.join(patient_folder, 'RTSTRUCT')
    if not os.path.isdir(rtstruct_folder):
        rtstruct_folder = patient_folder
    
    all_rtstructs = []
    limbus_ai_rtstructs = []
    
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
                    series_uid = str(ds.get('SeriesInstanceUID', ''))
                    
                    # Extract referenced CT series UID from ReferencedFrameOfReferenceSequence
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
                        'path': filepath,
                        'filename': os.path.basename(filepath),
                        'model_name': model_name,
                        'sop_instance_uid': sop_uid,
                        'series_instance_uid': series_uid,
                        'frame_of_reference_uid': frame_ref_uid,
                        'referenced_ct_series_uid': referenced_ct_series_uid,
                        'structure_set_label': struct_label
                    }
                    
                    all_rtstructs.append(info)
                    if model_name == 'ARIA RTM':
                        limbus_ai_rtstructs.append(info)
                        
                except:
                    pass
    
    return all_rtstructs, limbus_ai_rtstructs


def scan_ct_series(patient_folder: str) -> Dict[str, Dict]:
    """
    Scan patient folder for all CT series.
    
    Parameters
    ----------
    patient_folder : str
        Path to patient folder
        
    Returns
    -------
    dict
        Dictionary mapping CT Series UID to CT series info
    """
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
                                'folder': root,
                                'files': []
                            }
                        ct_series_dict[series_uid]['file_count'] += 1
                        ct_series_dict[series_uid]['files'].append(filepath)
                except:
                    pass
    
    return ct_series_dict


def identify_dicom_chain(patient_folder: str, verbose: bool = True) -> List[Dict]:
    """
    Identify complete DICOM chains for all approved RTPLANs in a patient folder.
    
    Chain: Approved RTPLAN → Clinical RTSTRUCT → CT Series → Limbus AI RTSTRUCT
    
    Parameters
    ----------
    patient_folder : str
        Path to patient folder
    verbose : bool, optional
        Print detailed output. Default is True.
        
    Returns
    -------
    list of dict
        List of chain dictionaries, each containing:
        - rtplan: RTPLAN info dict
        - clinical_rtstruct: Clinical ARIA RTSTRUCT info dict (or None)
        - ct_series: CT series info dict (or None)
        - limbus_ai_rtstruct: Limbus AI RTSTRUCT info dict (or None)
        - chain_complete: bool indicating if chain is complete
        - chain_status: str describing chain status
    """
    chains = []
    
    if verbose:
        print(f"\n  Scanning DICOM files in patient folder...")
    
    # Step 1: Scan all RTPLAN files
    all_rtplans, approved_rtplans = scan_rtplan_files(patient_folder)
    
    if verbose:
        print(f"    Found {len(all_rtplans)} RTPLAN(s), {len(approved_rtplans)} approved")
    
    if not approved_rtplans:
        if verbose:
            print(f"    ✗ No approved RTPLANs found")
        return chains
    
    # Step 2: Scan all RTSTRUCT files
    all_rtstructs, limbus_ai_rtstructs = scan_rtstruct_files(patient_folder)
    
    if verbose:
        print(f"    Found {len(all_rtstructs)} RTSTRUCT(s), {len(limbus_ai_rtstructs)} Limbus AI")
    
    # Step 3: Scan all CT series
    ct_series_dict = scan_ct_series(patient_folder)
    
    if verbose:
        print(f"    Found {len(ct_series_dict)} CT series")
    
    # Step 4: Build chains for each approved RTPLAN
    for rtplan in approved_rtplans:
        chain = {
            'rtplan': rtplan,
            'clinical_rtstruct': None,
            'ct_series': None,
            'limbus_ai_rtstruct': None,
            'chain_complete': False,
            'chain_status': 'Starting'
        }
        
        if verbose:
            print(f"\n    Processing approved RTPLAN: {rtplan['plan_name']} ({rtplan['filename']})")
        
        # Find clinical RTSTRUCT referenced by RTPLAN (via SOP Instance UID match)
        clinical_rtstruct = None
        for rtstruct in all_rtstructs:
            if rtstruct['sop_instance_uid'] == rtplan['referenced_rtstruct_sop_uid']:
                clinical_rtstruct = rtstruct
                break
        
        if not clinical_rtstruct:
            chain['chain_status'] = 'Clinical RTSTRUCT not found'
            if verbose:
                print(f"      ✗ Clinical RTSTRUCT not found (SOP UID: {rtplan['referenced_rtstruct_sop_uid']})")
            chains.append(chain)
            continue
        
        chain['clinical_rtstruct'] = clinical_rtstruct
        
        if verbose:
            print(f"      ✓ Found clinical RTSTRUCT: {clinical_rtstruct['filename']} (Model: {clinical_rtstruct['model_name']})")
        
        # Find CT series matching Frame of Reference + CT Series UID
        matched_ct = None
        for series_uid, ct_info in ct_series_dict.items():
            frame_match = ct_info['frame_ref_uid'] == clinical_rtstruct['frame_of_reference_uid']
            series_match = series_uid == clinical_rtstruct['referenced_ct_series_uid']
            
            if frame_match and series_match:
                matched_ct = ct_info
                break
        
        if not matched_ct:
            chain['chain_status'] = 'CT series not found'
            if verbose:
                print(f"      ✗ CT series not found (Frame: {clinical_rtstruct['frame_of_reference_uid'][:20]}...)")
            chains.append(chain)
            continue
        
        chain['ct_series'] = matched_ct
        
        if verbose:
            print(f"      ✓ Found CT series: {matched_ct['file_count']} slices")
        
        # Find Limbus AI RTSTRUCT matching Frame of Reference + CT Series UID
        matched_limbus = None
        for limbus in limbus_ai_rtstructs:
            frame_match = limbus['frame_of_reference_uid'] == clinical_rtstruct['frame_of_reference_uid']
            series_match = limbus['referenced_ct_series_uid'] == clinical_rtstruct['referenced_ct_series_uid']
            
            if frame_match and series_match:
                matched_limbus = limbus
                break
        
        # Fallback: if only one Limbus AI exists, use it
        if not matched_limbus and len(limbus_ai_rtstructs) == 1:
            matched_limbus = limbus_ai_rtstructs[0]
            if verbose:
                print(f"      ⚠ Using single Limbus AI RTSTRUCT as fallback")
        
        if not matched_limbus:
            chain['chain_status'] = 'Limbus AI RTSTRUCT not found'
            if verbose:
                print(f"      ✗ Limbus AI RTSTRUCT not found")
            chains.append(chain)
            continue
        
        chain['limbus_ai_rtstruct'] = matched_limbus
        chain['chain_complete'] = True
        chain['chain_status'] = 'Complete'
        
        if verbose:
            print(f"      ✓ Found Limbus AI RTSTRUCT: {matched_limbus['filename']}")
            print(f"      ✓✓ CHAIN COMPLETE")
        
        chains.append(chain)
    
    return chains


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def find_dicom_files_in_folder(folder_path: str) -> List[str]:
    """
    Recursively find all DICOM files (.dcm) in a folder structure.
    
    Parameters
    ----------
    folder_path : str
        Path to folder to search
        
    Returns
    -------
    list of str
        List of full paths to DICOM files
    """
    dicom_files = []
    
    if not os.path.isdir(folder_path):
        return dicom_files
    
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith('.dcm'):
                dicom_files.append(os.path.join(root, file))
    
    return dicom_files


def discover_patient_folders(dicom_root_folder: str) -> List[Dict]:
    """
    Discover all patient folders in the DICOM directory structure.
    
    Parameters
    ----------
    dicom_root_folder : str
        Root folder containing patient subdirectories
        
    Returns
    -------
    list of dict
        List of patient data dictionaries with keys:
        - patient_id: Patient identifier
        - patient_folder: Path to patient folder
    """
    patients = []
    
    if not os.path.isdir(dicom_root_folder):
        print(f"Error: DICOM root folder does not exist: {dicom_root_folder}")
        return patients
    
    # Find all patient folders (starting with P)
    for item in os.listdir(dicom_root_folder):
        patient_folder = os.path.join(dicom_root_folder, item)
        
        if not os.path.isdir(patient_folder):
            continue
        
        # Check if this looks like a patient folder
        if not item.startswith('P'):
            continue
        
        patient_data = {
            'patient_id': item,
            'patient_folder': patient_folder
        }
        
        patients.append(patient_data)
    
    return patients


# ============================================================================
# MAIN PROCESSING FUNCTION
# ============================================================================

def quantify_contour_differences_p0728(dicom_root_folder: str, calc_all_parameters: int = 1,
                                        max_patients: Optional[int] = None) -> pd.DataFrame:
    """
    Quantify differences between contours for all patients using DICOM chain identification.
    
    This function automatically processes all patients in the DICOM folder structure,
    comparing Limbus AI RTSTRUCT with clinical ARIA RTSTRUCT using the approved RTPLAN
    as the entry point for chain identification.
    
    Parameters
    ----------
    dicom_root_folder : str
        Root folder containing patient subdirectories with DICOM data
    calc_all_parameters : int, optional
        Switch on (1) or off (0) calculation of added path length (APL) 
        and surface DICE in addition to volumetric DICE. Default = 1.
    max_patients : int, optional
        Maximum number of patients to process. If None, all patients will be processed.
        Use this for sample/test runs. Default is None (process all patients).
        
    Returns
    -------
    pd.DataFrame
        Table with quantitative results containing:
        - pNumber : Patient number(s)
        - VOIName : Structure name(s)
        - Dice : Volumetric DICE value(s)
        - APL : Added Path Length value(s) (if calc_all_parameters=1)
        - SDSC : Surface DICE value(s) (if calc_all_parameters=1)
    """
    # Set tolerances
    apl_tolerance = 0.1
    sdsc_tolerance = 0.1
    
    # Discover all patients
    print(f"Scanning for patients in: {dicom_root_folder}")
    patients = discover_patient_folders(dicom_root_folder)
    
    if not patients:
        print("No patient folders found.")
        return pd.DataFrame()
    
    print(f"Found {len(patients)} patient folder(s)")
    
    # Limit number of patients if max_patients is specified
    if max_patients is not None and max_patients > 0:
        patients = random.sample(patients, min(max_patients, len(patients)))
        print(f"Randomly selected {len(patients)} patient(s) for sample test")
    
    # Process each patient
    all_results = []
    
    for patient_idx, patient_data in enumerate(patients):
        patient_id = patient_data['patient_id']
        patient_folder = patient_data['patient_folder']
        
        print(f"\n{'='*80}")
        print(f"Processing patient {patient_idx + 1}/{len(patients)}: {patient_id}")
        print(f"{'='*80}")
        
        # Identify DICOM chains using the new method
        print("  Using DICOM chain identification...")
        chains = identify_dicom_chain(patient_folder, verbose=True)
        
        if not chains:
            print(f"  ✗ No valid DICOM chains found for this patient")
            skip_result = {
                'pNumber': patient_id,
                'CTSeriesUID': 'N/A',
                'ChainStatus': 'No approved RTPLANs',
                'Enough_RTSTRUCTs': 'No',
                'RTPLAN_Present': 'No',
                'Common VOI': 'N/A',
                'VOIName': 'N/A',
                'Dice': None,
                'Status': 'No valid DICOM chains found'
            }
            if calc_all_parameters != 0:
                skip_result['APL'] = None
                skip_result['SDSC'] = None
            all_results.append(skip_result)
            continue
        
        # Process each complete chain
        print(f"\n  Found {len(chains)} chain(s) to process")
        
        for chain_idx, chain in enumerate(chains):
            print(f"\n  {'-'*76}")
            print(f"  Processing chain {chain_idx + 1}/{len(chains)}: {chain['chain_status']}")
            print(f"  {'-'*76}")
            
            if not chain['chain_complete']:
                print(f"  ✗ Incomplete chain: {chain['chain_status']}")
                skip_result = {
                    'pNumber': patient_id,
                    'CTSeriesUID': chain['ct_series']['series_uid'][-12:] if chain['ct_series'] else 'N/A',
                    'ChainStatus': chain['chain_status'],
                    'RTPLAN_Name': chain['rtplan']['plan_name'],
                    'RTPLAN_File': chain['rtplan']['filename'],
                    'Clinical_RTSTRUCT': chain['clinical_rtstruct']['filename'] if chain['clinical_rtstruct'] else 'N/A',
                    'Limbus_AI_RTSTRUCT': chain['limbus_ai_rtstruct']['filename'] if chain['limbus_ai_rtstruct'] else 'N/A',
                    'Enough_RTSTRUCTs': 'No',
                    'RTPLAN_Present': 'Yes',
                    'Common VOI': 'N/A',
                    'VOIName': 'N/A',
                    'Dice': None,
                    'Status': f'Incomplete chain: {chain["chain_status"]}'
                }
                if calc_all_parameters != 0:
                    skip_result['APL'] = None
                    skip_result['SDSC'] = None
                all_results.append(skip_result)
                continue
            
            # Extract chain components
            rtplan_info = chain['rtplan']
            clinical_rtstruct_info = chain['clinical_rtstruct']
            ct_series_info = chain['ct_series']
            limbus_rtstruct_info = chain['limbus_ai_rtstruct']
            
            print(f"    RTPLAN: {rtplan_info['plan_name']}")
            print(f"    Clinical RTSTRUCT: {clinical_rtstruct_info['filename']}")
            print(f"    Limbus AI RTSTRUCT: {limbus_rtstruct_info['filename']}")
            print(f"    CT Series: {ct_series_info['file_count']} slices")
            
            # Read RTPLAN metadata
            rtplan_data = None
            try:
                rtplan_data = read_dicomrtplan(rtplan_info['path'])
                if rtplan_data:
                    print(f"\n    RTPLAN Metadata:")
                    print(f"      Study Description: {rtplan_data.get('StudyDescription', 'N/A')}")
                    print(f"      RT Plan Name: {rtplan_data.get('RTPlanName', 'N/A')}")
                    print(f"      Number of Fractions: {rtplan_data.get('NumberOfFractionsPlanned', 'N/A')}")
                    print(f"      Target Prescription Dose: {rtplan_data.get('TargetPrescriptionDose', 'N/A')}")
                    print(f"      Dose Reference Description: {rtplan_data.get('DoseReferenceDescription', 'N/A')}")
            except Exception as e:
                print(f"    Warning: Could not read RTPLAN metadata: {str(e)}")
            
            # Read CT data
            print("\n    Reading CT data...")
            ct_files = ct_series_info['files']
            
            if not ct_files:
                print(f"    ✗ No CT files found in series")
                continue
            
            try:
                imaging_data = read_dicomct_light(ct_files)
                print(f"    ✓ Loaded {len(ct_files)} CT slices")
            except Exception as e:
                print(f"    ✗ Error reading CT data: {str(e)}")
                continue
            
            # Read RTSTRUCT files
            # RTSTRUCT 1 = Limbus AI (comparison target)
            # RTSTRUCT 2 = Clinical ARIA (reference)
            print("\n    Reading RTSTRUCT files...")
            try:
                rtstruct1 = read_dicomrtstruct(limbus_rtstruct_info['path'], verbose=True)
                rtstruct2 = read_dicomrtstruct(clinical_rtstruct_info['path'], verbose=True)
                
                rtstruct1_series_desc = rtstruct1.get('PlanID', limbus_rtstruct_info['structure_set_label'])
                rtstruct2_series_desc = rtstruct2.get('PlanID', clinical_rtstruct_info['structure_set_label'])
                
                print(f"    ✓ Limbus AI RTSTRUCT: {rtstruct1_series_desc}")
                print(f"    ✓ Clinical RTSTRUCT: {rtstruct2_series_desc}")
            except Exception as e:
                print(f"    ✗ Error reading RTSTRUCT files: {str(e)}")
                continue
            
            # Get structure names
            vois1 = [s['Name'] for s in rtstruct1['Struct']]
            vois2 = [s['Name'] for s in rtstruct2['Struct']]
            
            print(f"\n    Limbus AI structures ({len(vois1)}): {', '.join(vois1[:5])}{'...' if len(vois1) > 5 else ''}")
            print(f"    Clinical structures ({len(vois2)}): {', '.join(vois2[:5])}{'...' if len(vois2) > 5 else ''}")
            
            # Find common VOIs
            common_vois = [v for v in vois1 if v in vois2]
            
            # Exclude specific VOIs (case-insensitive)
            excluded_vois = ['body', 'skin']
            common_vois_filtered = [v for v in common_vois if v.lower() not in excluded_vois]
            
            if len(common_vois) > len(common_vois_filtered):
                excluded_found = [v for v in common_vois if v.lower() in excluded_vois]
                print(f"    Excluded VOIs: {', '.join(excluded_found)}")
            
            common_vois = common_vois_filtered
            
            if not common_vois:
                warnings.warn(f'No valid VOIs found after exclusions. Skipping this chain.')
                skip_result = {
                    'pNumber': patient_id,
                    'CTSeriesUID': ct_series_info['series_uid'][-12:],
                    'ChainStatus': 'Complete',
                    'RTPLAN_Name': rtplan_info['plan_name'],
                    'RTPLAN_File': rtplan_info['filename'],
                    'Clinical_RTSTRUCT': clinical_rtstruct_info['filename'],
                    'Limbus_AI_RTSTRUCT': limbus_rtstruct_info['filename'],
                    'RTSTRUCT1_SeriesDescription': rtstruct1_series_desc,
                    'RTSTRUCT2_SeriesDescription': rtstruct2_series_desc,
                    'Enough_RTSTRUCTs': 'Yes',
                    'RTPLAN_Present': 'Yes',
                    'Common VOI': 'No',
                    'VOIName': 'N/A',
                    'Dice': None,
                    'Status': 'No common VOIs after exclusions'
                }
                # Add RTPLAN metadata
                if rtplan_data:
                    skip_result['RTPLAN_StudyDescription'] = rtplan_data.get('StudyDescription', 'N/A')
                    skip_result['RTPLAN_RTPlanName'] = rtplan_data.get('RTPlanName', 'N/A')
                    skip_result['RTPLAN_NumberOfFractions'] = rtplan_data.get('NumberOfFractionsPlanned', 'N/A')
                    skip_result['RTPLAN_TargetPrescriptionDose'] = rtplan_data.get('TargetPrescriptionDose', 'N/A')
                    skip_result['RTPLAN_DoseReferenceDescription'] = rtplan_data.get('DoseReferenceDescription', 'N/A')
                    skip_result['RTPLAN_SetupTechniqueDescription'] = rtplan_data.get('SetupTechniqueDescription', 'N/A')
                if calc_all_parameters != 0:
                    skip_result['APL'] = None
                    skip_result['SDSC'] = None
                all_results.append(skip_result)
                continue
            
            print(f"\n    Common structures ({len(common_vois)}): {', '.join(common_vois)}")
            
            # Get indices for comparison
            to_compare = [i for i, v in enumerate(vois1) if v in common_vois and v in vois2]
            
            if not to_compare:
                warnings.warn(f'None of the common VOIs are present. Skipping this chain.')
                continue
            
            print(f"    Comparing {len(to_compare)} structure(s)")
            
            # Compose structure matrices
            print("\n    Composing structure matrices...")
            try:
                voi1 = compose_struct_matrix(imaging_data, rtstruct1)
                voi2 = compose_struct_matrix(imaging_data, rtstruct2)
            except Exception as e:
                print(f"    ✗ Error composing structure matrices: {str(e)}")
                continue
            
            # Calculate metrics for each structure
            print("    Calculating metrics...")
            for comparison_no, method1_struct_no in enumerate(to_compare):
                voi_name = vois1[method1_struct_no]
                method2_struct_no = vois2.index(voi_name)
                
                print(f"      Processing: {voi_name}")
                
                # Check if VOIs are empty
                is_empty1 = not has_contour_points_local(rtstruct1['Struct'][method1_struct_no])
                is_empty2 = not has_contour_points_local(rtstruct2['Struct'][method2_struct_no])
                
                if is_empty1 or is_empty2:
                    which_side = 'both' if is_empty1 and is_empty2 else ('Limbus AI' if is_empty1 else 'Clinical')
                    warnings.warn(f'Skipping VOI "{voi_name}": empty contour in {which_side}.')
                    continue
                
                # Initialize result
                result = {
                    'pNumber': patient_id,
                    'CTSeriesUID': ct_series_info['series_uid'][-12:],
                    'ChainStatus': 'Complete',
                    'RTPLAN_Name': rtplan_info['plan_name'],
                    'RTPLAN_File': rtplan_info['filename'],
                    'Clinical_RTSTRUCT': clinical_rtstruct_info['filename'],
                    'Limbus_AI_RTSTRUCT': limbus_rtstruct_info['filename'],
                    'RTSTRUCT1_SeriesDescription': rtstruct1_series_desc,
                    'RTSTRUCT2_SeriesDescription': rtstruct2_series_desc,
                    'Enough_RTSTRUCTs': 'Yes',
                    'RTPLAN_Present': 'Yes',
                    'Common VOI': 'Yes',
                    'VOIName': voi_name
                }
                
                # Add RTPLAN metadata
                if rtplan_data:
                    result['RTPLAN_StudyDescription'] = rtplan_data.get('StudyDescription', 'N/A')
                    result['RTPLAN_RTPlanName'] = rtplan_data.get('RTPlanName', 'N/A')
                    result['RTPLAN_NumberOfFractions'] = rtplan_data.get('NumberOfFractionsPlanned', 'N/A')
                    result['RTPLAN_TargetPrescriptionDose'] = rtplan_data.get('TargetPrescriptionDose', 'N/A')
                    result['RTPLAN_DoseReferenceDescription'] = rtplan_data.get('DoseReferenceDescription', 'N/A')
                    result['RTPLAN_SetupTechniqueDescription'] = rtplan_data.get('SetupTechniqueDescription', 'N/A')
                else:
                    result['RTPLAN_StudyDescription'] = 'N/A'
                    result['RTPLAN_RTPlanName'] = 'N/A'
                    result['RTPLAN_NumberOfFractions'] = 'N/A'
                    result['RTPLAN_TargetPrescriptionDose'] = 'N/A'
                    result['RTPLAN_DoseReferenceDescription'] = 'N/A'
                    result['RTPLAN_SetupTechniqueDescription'] = 'N/A'
                
                try:
                    # Calculate volumetric DICE
                    result['Dice'] = calculate_dice_logical(voi1, voi2, method1_struct_no + 1, method2_struct_no + 1)
                    
                    # Calculate APL and Surface DSC if requested
                    if calc_all_parameters != 0:
                        # Calculate APL
                        temp_path_length = calculate_path_length(
                            imaging_data, rtstruct1, rtstruct2, 
                            method1_struct_no, method2_struct_no, apl_tolerance
                        )
                        result['APL'] = np.sum(temp_path_length)
                        
                        # Calculate Surface DSC
                        result['SDSC'] = calculate_surface_dsc(
                            imaging_data, rtstruct1, rtstruct2,
                            method1_struct_no, method2_struct_no, sdsc_tolerance
                        )
                    
                    all_results.append(result)
                    print(f"        DICE: {result['Dice']:.4f}")
                    if calc_all_parameters != 0:
                        print(f"        APL:  {result['APL']:.4f}")
                        print(f"        SDSC: {result['SDSC']:.4f}")
                
                except Exception as e:
                    print(f"      ✗ Error calculating metrics for {voi_name}: {str(e)}")
                    continue
    
    # Create results table
    if all_results:
        results_table = pd.DataFrame(all_results)
        results_table = results_table.sort_values(['pNumber', 'CTSeriesUID', 'VOIName'])
        return results_table
    else:
        return pd.DataFrame()


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == '__main__':
    # Configuration
    DICOM_ROOT_FOLDER = "Z:\\ICoNEA\\DICOM\\P0728C0006I13396576"  # Update this path
    MAX_PATIENTS = 10  # Limit for sample test (set to None for all patients)
    
    # Parse command-line arguments if provided
    if len(sys.argv) > 1:
        DICOM_ROOT_FOLDER = sys.argv[1]
    if len(sys.argv) > 2:
        MAX_PATIENTS = int(sys.argv[2]) if sys.argv[2].lower() != 'none' else None
    
    print("=" * 80)
    print("Quantify Contour Differences - P0728 Dataset (v2 - DICOM Chain Identification)")
    print("=" * 80)
    print(f"DICOM Root Folder: {DICOM_ROOT_FOLDER}")
    print(f"Max Patients: {MAX_PATIENTS if MAX_PATIENTS is not None else 'All'}")
    print("=" * 80)
    print("\nIdentification Method:")
    print("  1. Find approved RTPLAN(s) in patient folder")
    print("  2. Get referenced clinical RTSTRUCT from RTPLAN (SOP Instance UID)")
    print("  3. Find matching CT series (Frame of Reference + Series UID)")
    print("  4. Find matching Limbus AI RTSTRUCT (Frame of Reference + Series UID)")
    print("  5. Compare Limbus AI vs Clinical RTSTRUCT contours")
    print("=" * 80)
    
    # Run analysis
    results = quantify_contour_differences_p0728(
        dicom_root_folder=DICOM_ROOT_FOLDER,
        calc_all_parameters=1,
        max_patients=MAX_PATIENTS
    )
    
    if results is not None and not results.empty:
        print("\n" + "=" * 80)
        print("RESULTS")
        print("=" * 80)
        print(results.to_string(index=False))
        
        # Save to Excel
        output_file = 'contour_comparison_results_P0728_v2.xlsx'
        results.to_excel(output_file, index=False, engine='openpyxl')
        print(f"\nResults saved to {output_file}")
    else:
        print("\nNo results generated.")
