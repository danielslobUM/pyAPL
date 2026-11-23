"""
quantifycontourdifferences_P0728_v5_excl_RTPLAN - Automated contour comparison WITHOUT RTPLAN

This script works when RTPLAN files are not available. It identifies DICOM chains using:
1. Scan all RTSTRUCT files
2. Identify Limbus AI RTSTRUCTs by metadata (SeriesDescription + StructureSetLabel)
3. All non-Limbus RTSTRUCTs are considered clinical candidates
4. Match Limbus ↔ Clinical by Frame of Reference + Referenced CT Series UID
5. Find corresponding CT series
6. Compare clinical RTSTRUCT with Limbus AI RTSTRUCT

Note: Without RTPLAN, we cannot filter by approval status. All non-Limbus RTSTRUCTs
referencing the same CT as a Limbus RTSTRUCT are treated as clinical candidates.

Based on quantifycontourdifferences_P0728_v5.py

Folder structure:
DICOM -> Pxxxxxxxxxxxxxxxx -> CT/RTSTRUCT (folders) -> yyyymmdd -> .dcm files

History
-------
Created from v5 to work without RTPLAN files
"""

import os
import sys
import warnings
import random
import pydicom
import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from skimage.draw import polygon

from read_dicomct_light import read_dicomct_light
from read_dicomrtstruct import read_dicomrtstruct
from calculate_dice_logical import calculate_dice_logical
from calculate_surface_dsc import calculate_surface_dsc
from calculate_path_length import calculate_path_length
from has_contour_points_local import has_contour_points_local


# ============================================================================
# OPTIMIZED STRUCTURE MATRIX COMPOSITION (v3 - COMMON STRUCTURES ONLY)
# ============================================================================

def compose_struct_matrix_filtered(scan: dict, rtstruct: dict, structure_indices: List[int]) -> np.ndarray:
    """
    Compose a matrix representation of SELECTED structures from RTSTRUCT.
    
    This function only processes the specified structures, avoiding the 64-structure
    limit and improving performance by not computing unused structures.
    
    The bit position for each structure corresponds to its position in the 
    structure_indices list (0-indexed in the list, but 1-indexed bit positions
    for compatibility with calculate_dice_logical).
    
    Parameters
    ----------
    scan : dict
        CT/PET scan data from read_dicomct_light
    rtstruct : dict
        RTSTRUCT data from read_dicomrtstruct
    structure_indices : list of int
        List of structure indices (0-indexed) to include in the matrix
        
    Returns
    -------
    ndarray
        Matrix containing contours in binary representation.
        Each selected structure occupies one bit position based on its
        position in structure_indices list.
    """
    num_structures = len(structure_indices)
    
    if num_structures == 0:
        warnings.warn("No structures specified for composition")
        return np.zeros(scan['Image'].shape, dtype=np.uint16)
    
    print(f'Composing VOI matrix for {num_structures} selected structures')
    
    # Calculate Y coordinate grid
    yct = scan['PixelFirstYi'] + np.arange(scan['PixelNumYi']) * scan['PixelSpacingYi']
    
    # Determine matrix data type based on number of SELECTED structures
    if num_structures <= 16:
        matrix = np.zeros(scan['Image'].shape, dtype=np.uint16)
    elif num_structures <= 32:
        matrix = np.zeros(scan['Image'].shape, dtype=np.uint32)
    elif num_structures <= 64:
        matrix = np.zeros(scan['Image'].shape, dtype=np.uint64)
    else:
        print(f'-   Warning: {num_structures} common structures exceeds 64. Only doing first 64.')
        matrix = np.zeros(scan['Image'].shape, dtype=np.uint64)
        structure_indices = structure_indices[:64]
        num_structures = 64
    
    # Process each SELECTED structure
    for bit_position, struct_idx in enumerate(structure_indices):
        if struct_idx >= len(rtstruct['Struct']):
            warnings.warn(f"Structure index {struct_idx} out of range, skipping")
            continue
            
        struct = rtstruct['Struct'][struct_idx]
        struct_name = struct.get('Name', f'Structure_{struct_idx}')
        
        if len(struct['Slice']) > 1:
            warning1 = False
            warning2 = False
            
            for j, slice_data in enumerate(struct['Slice']):
                do_process = False
                
                if slice_data['Y'] is not None and len(slice_data['Y']) > 0:
                    # Convert structure coordinates to grid indices
                    x_samp = (slice_data['X'] - scan['PixelFirstXi']) / scan['PixelSpacingXi']
                    z_samp = (slice_data['Z'] - scan['PixelFirstZi']) / scan['PixelSpacingZi']
                    y_samp = (slice_data['Y'][0] - scan['PixelFirstYi']) / scan['PixelSpacingYi']
                    
                    # Check if Y position matches a CT slice
                    y_diff = np.abs(yct - slice_data['Y'][0])
                    
                    if np.any(y_diff < 0.0001):
                        do_process = True
                    elif slice_data['Y'][0] < np.min(yct) or slice_data['Y'][0] > np.max(yct):
                        warning1 = True
                    elif np.any(y_diff <= 0.11):
                        warning2 = True
                        do_process = True
                    else:
                        print(f'-   Discrepancy between y-position slice and contour for {struct_name}')
                        break
                    
                    if do_process:
                        # Use polygon to fill the contour
                        y_idx = int(np.round(y_samp))
                        
                        if 0 <= y_idx < scan['PixelNumYi']:
                            try:
                                # Create polygon mask
                                rr, cc = polygon(z_samp, x_samp, 
                                               shape=(scan['PixelNumXi'], scan['PixelNumZi']))
                                
                                # Set bit for this structure (bit_position, not struct_idx)
                                for r, c in zip(rr, cc):
                                    if (0 <= r < scan['PixelNumXi'] and 
                                        0 <= c < scan['PixelNumZi']):
                                        matrix[r, y_idx, c] |= (1 << bit_position)
                            except:
                                # If polygon fails, skip this slice
                                pass
            
            if warning1:
                print(f'-   Warning: span y-pos contour larger than image for {struct_name}')
            if warning2:
                print(f'-   Warning: 1 mm discrepancy allowed for {struct_name}')
    
    return matrix


# ============================================================================
# LIMBUS VERIFICATION HELPER
# ============================================================================

def is_verified_limbus_rtstruct(rtstruct_info: dict) -> bool:
    """
    Verify if an RTSTRUCT is a valid Limbus AI structure set.
    
    Verification Criteria (BOTH must be true):
    1. SeriesDescription equals 'Limbus RTSS v1.8.0' (exact match)
    2. StructureSetLabel equals 'Limbus RTStruct' (exact match)
    
    Parameters
    ----------
    rtstruct_info : dict
        Dictionary containing RTSTRUCT metadata with keys:
        - series_description
        - structure_set_label
        
    Returns
    -------
    bool
        True if this is a verified Limbus AI RTSTRUCT
    """
    series_desc = rtstruct_info.get('series_description', '')
    struct_label = rtstruct_info.get('structure_set_label', '')
    
    return (
        series_desc == 'Limbus RTSS v1.8.0' and
        struct_label == 'Limbus RTStruct'
    )


# ============================================================================
# DICOM CHAIN IDENTIFICATION FUNCTIONS (WITHOUT RTPLAN)
# ============================================================================

def scan_rtstruct_files(patient_folder: str) -> List[Dict]:
    """
    Scan patient folder for all RTSTRUCT files.
    
    Returns ALL RTSTRUCTs with metadata.
    
    Parameters
    ----------
    patient_folder : str
        Path to patient folder
        
    Returns
    -------
    list
        List of all RTSTRUCT info dictionaries
    """
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
                    
                    model_name = str(ds.get('ManufacturerModelName', 'N/A'))
                    manufacturer = str(ds.get('Manufacturer', 'N/A'))
                    sop_uid = str(ds.get('SOPInstanceUID', ''))
                    frame_ref_uid = str(ds.get('FrameOfReferenceUID', ''))
                    struct_label = str(ds.get('StructureSetLabel', ''))
                    series_uid = str(ds.get('SeriesInstanceUID', ''))
                    series_desc = str(ds.get('SeriesDescription', ''))
                    
                    # Extract timestamp for temporal ordering
                    # Chronological order: CT → Limbus → Clinical (approved)
                    struct_date = str(ds.get('StructureSetDate', ''))  # (3006,0008)
                    struct_time = str(ds.get('StructureSetTime', ''))  # (3006,0009)
                    
                    # Combine date and time into sortable datetime
                    timestamp = None
                    if struct_date:
                        try:
                            if struct_time:
                                # Handle time with or without fractional seconds
                                time_str = struct_time.split('.')[0]  # Remove fractional seconds
                                timestamp = datetime.strptime(f"{struct_date}{time_str}", '%Y%m%d%H%M%S')
                            else:
                                timestamp = datetime.strptime(struct_date, '%Y%m%d')
                        except ValueError:
                            timestamp = None
                    
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
                        'manufacturer_model': model_name,
                        'manufacturer': manufacturer,
                        'sop_instance_uid': sop_uid,
                        'series_instance_uid': series_uid,
                        'frame_of_reference_uid': frame_ref_uid,
                        'referenced_ct_series_uid': referenced_ct_series_uid,
                        'structure_set_label': struct_label,
                        'series_description': series_desc,
                        'structure_set_date': struct_date,
                        'structure_set_time': struct_time,
                        'timestamp': timestamp
                    }
                    
                    all_rtstructs.append(info)
                        
                except:
                    pass
    
    return all_rtstructs


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
                        series_desc = str(ds.get('SeriesDescription', ''))
                        
                        if series_uid not in ct_series_dict:
                            ct_series_dict[series_uid] = {
                                'series_uid': series_uid,
                                'frame_ref_uid': frame_ref_uid,
                                'series_description': series_desc,
                                'file_count': 0,
                                'folder': root,
                                'files': []
                            }
                        ct_series_dict[series_uid]['file_count'] += 1
                        ct_series_dict[series_uid]['files'].append(filepath)
                except:
                    pass
    
    return ct_series_dict


def identify_dicom_chain_no_rtplan(patient_folder: str, verbose: bool = True) -> List[Dict]:
    """
    Identify DICOM chains WITHOUT using RTPLAN files.
    
    Chain identification:
    1. Find all Limbus AI RTSTRUCTs (by metadata verification)
    2. For each Limbus RTSTRUCT, find clinical RTSTRUCTs with same:
       - Frame of Reference UID
       - Referenced CT Series UID
    3. Find matching CT series
    
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
        - rtplan: None (no RTPLAN used)
        - clinical_rtstruct: Clinical RTSTRUCT info dict (or None)
        - ct_series: CT series info dict (or None)
        - limbus_ai_rtstruct: Limbus AI RTSTRUCT info dict (or None)
        - chain_complete: bool indicating if chain is complete
        - chain_status: str describing chain status
    """
    chains = []
    
    if verbose:
        print(f"\n  Scanning DICOM files in patient folder (NO RTPLAN mode)...")
    
    # Step 1: Scan all RTSTRUCT files
    all_rtstructs = scan_rtstruct_files(patient_folder)
    
    if verbose:
        print(f"    Found {len(all_rtstructs)} RTSTRUCT(s)")
    
    if not all_rtstructs:
        if verbose:
            print(f"    ✗ No RTSTRUCT files found")
        return chains
    
    # Step 2: Separate Limbus RTSTRUCTs from clinical candidates
    limbus_rtstructs = []
    clinical_rtstructs = []
    
    for rtstruct in all_rtstructs:
        if is_verified_limbus_rtstruct(rtstruct):
            limbus_rtstructs.append(rtstruct)
        else:
            clinical_rtstructs.append(rtstruct)
    
    if verbose:
        print(f"    → Limbus AI RTSTRUCTs: {len(limbus_rtstructs)}")
        print(f"    → Clinical candidate RTSTRUCTs: {len(clinical_rtstructs)}")
    
    if not limbus_rtstructs:
        if verbose:
            print(f"    ✗ No Limbus AI RTSTRUCT found")
        return chains
    
    if not clinical_rtstructs:
        if verbose:
            print(f"    ✗ No clinical RTSTRUCT candidates found")
        return chains
    
    # Step 3: Scan all CT series
    ct_series_dict = scan_ct_series(patient_folder)
    
    if verbose:
        print(f"    Found {len(ct_series_dict)} CT series")
    
    # Step 4: Build chains starting from each Limbus RTSTRUCT
    for limbus_rtstruct in limbus_rtstructs:
        if verbose:
            print(f"\n    Processing Limbus RTSTRUCT: {limbus_rtstruct['filename']}")
        
        # Find clinical RTSTRUCTs matching Frame of Reference + CT Series UID
        matching_clinical = []
        for clinical in clinical_rtstructs:
            frame_match = clinical['frame_of_reference_uid'] == limbus_rtstruct['frame_of_reference_uid']
            series_match = clinical['referenced_ct_series_uid'] == limbus_rtstruct['referenced_ct_series_uid']
            
            if frame_match and series_match:
                matching_clinical.append(clinical)
        
        if verbose:
            print(f"      → Found {len(matching_clinical)} matching clinical RTSTRUCT(s)")
        
        if not matching_clinical:
            chain = {
                'rtplan': None,
                'clinical_rtstruct': None,
                'ct_series': None,
                'limbus_ai_rtstruct': limbus_rtstruct,
                'chain_complete': False,
                'chain_status': 'No matching clinical RTSTRUCT'
            }
            chains.append(chain)
            if verbose:
                print(f"      ✗ No clinical RTSTRUCT matches Frame of Reference + CT Series")
            continue
        
        # Select the correct clinical RTSTRUCT using temporal ordering
        # Chronological order: CT → Limbus AI → Clinical (edited/approved)
        # So we want the clinical RTSTRUCT created AFTER the Limbus RTSTRUCT
        limbus_timestamp = limbus_rtstruct.get('timestamp')
        
        if limbus_timestamp is not None:
            # Filter to clinical RTSTRUCTs created AFTER Limbus
            clinical_after_limbus = [
                c for c in matching_clinical 
                if c.get('timestamp') is not None and c['timestamp'] > limbus_timestamp
            ]
            
            if clinical_after_limbus:
                # Sort by timestamp (earliest first = first edit after Limbus)
                clinical_after_limbus.sort(key=lambda x: x['timestamp'])
                selected_clinical = clinical_after_limbus[0]  # First one created after Limbus
                
                if verbose:
                    print(f"      → Limbus timestamp: {limbus_timestamp}")
                    print(f"      → Found {len(clinical_after_limbus)} clinical RTSTRUCT(s) created AFTER Limbus")
                    print(f"      → Selected: {selected_clinical['filename']} (timestamp: {selected_clinical['timestamp']})")
                
                matching_clinical = [selected_clinical]  # Use only the selected one
            else:
                # No clinical RTSTRUCT found after Limbus - check if any have timestamps
                clinical_with_timestamps = [c for c in matching_clinical if c.get('timestamp') is not None]
                
                if clinical_with_timestamps:
                    if verbose:
                        print(f"      ⚠ No clinical RTSTRUCT found AFTER Limbus timestamp")
                        print(f"      → Limbus: {limbus_timestamp}")
                        for c in clinical_with_timestamps:
                            print(f"      → Clinical: {c['filename']} at {c['timestamp']}")
                        print(f"      → Using most recent clinical RTSTRUCT as fallback")
                    
                    # Fallback: use most recent clinical RTSTRUCT
                    clinical_with_timestamps.sort(key=lambda x: x['timestamp'], reverse=True)
                    matching_clinical = [clinical_with_timestamps[0]]
                else:
                    if verbose:
                        print(f"      ⚠ Clinical RTSTRUCTs have no timestamps, using first match")
                    matching_clinical = [matching_clinical[0]]
        else:
            # Limbus has no timestamp - use clinical with latest timestamp, or first match
            clinical_with_timestamps = [c for c in matching_clinical if c.get('timestamp') is not None]
            
            if clinical_with_timestamps:
                if verbose:
                    print(f"      ⚠ Limbus has no timestamp, using most recent clinical RTSTRUCT")
                clinical_with_timestamps.sort(key=lambda x: x['timestamp'], reverse=True)
                matching_clinical = [clinical_with_timestamps[0]]
            else:
                if verbose:
                    print(f"      ⚠ No timestamps available, using first match")
                matching_clinical = [matching_clinical[0]]
        
        # Process the selected clinical RTSTRUCT (now only one)
        for clinical_rtstruct in matching_clinical:
            chain = {
                'rtplan': None,
                'clinical_rtstruct': clinical_rtstruct,
                'ct_series': None,
                'limbus_ai_rtstruct': limbus_rtstruct,
                'chain_complete': False,
                'chain_status': 'Starting'
            }
            
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
                    print(f"      ✗ CT series not found")
                chains.append(chain)
                continue
            
            chain['ct_series'] = matched_ct
            chain['chain_complete'] = True
            chain['chain_status'] = 'Complete'
            
            if verbose:
                print(f"      ✓ Found CT series: {matched_ct['file_count']} slices")
                print(f"      ✓✓ CHAIN COMPLETE")
            
            chains.append(chain)
    
    return chains


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

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


def get_common_structures(rtstruct1: dict, rtstruct2: dict, excluded_vois: List[str] = None) -> Tuple[List[str], List[int], List[int]]:
    """
    Find common structures between two RTSTRUCTs.
    
    Parameters
    ----------
    rtstruct1 : dict
        First RTSTRUCT data (Limbus AI)
    rtstruct2 : dict
        Second RTSTRUCT data (Clinical)
    excluded_vois : list of str, optional
        List of VOI names to exclude (case-insensitive)
        
    Returns
    -------
    tuple
        (common_voi_names, indices_in_rtstruct1, indices_in_rtstruct2)
    """
    if excluded_vois is None:
        excluded_vois = ['body', 'skin']
    
    # Get structure names
    vois1 = [s['Name'] for s in rtstruct1['Struct']]
    vois2 = [s['Name'] for s in rtstruct2['Struct']]
    
    # Find common VOIs (case-sensitive match)
    common_vois = []
    indices1 = []
    indices2 = []
    
    for idx1, name in enumerate(vois1):
        if name in vois2 and name.lower() not in excluded_vois:
            common_vois.append(name)
            indices1.append(idx1)
            indices2.append(vois2.index(name))
    
    return common_vois, indices1, indices2


# ============================================================================
# MAIN PROCESSING FUNCTION
# ============================================================================

def quantify_contour_differences_no_rtplan(dicom_root_folder: str, calc_all_parameters: int = 1,
                                            max_patients: Optional[int] = None) -> pd.DataFrame:
    """
    Quantify differences between contours WITHOUT using RTPLAN files.
    
    This function identifies DICOM chains by:
    1. Finding Limbus AI RTSTRUCTs (by metadata)
    2. Finding matching clinical RTSTRUCTs (same Frame of Reference + CT Series)
    3. Finding corresponding CT series
    
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
        Table with quantitative results
    """
    # Set tolerances
    apl_tolerance = 0.1
    sdsc_tolerance = 0.1
    
    # Excluded VOIs
    excluded_vois = ['body', 'skin']
    
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
        
        # Identify DICOM chains WITHOUT RTPLAN
        print("  Using DICOM chain identification (NO RTPLAN mode)...")
        chains = identify_dicom_chain_no_rtplan(patient_folder, verbose=True)
        
        if not chains:
            print(f"  ✗ No valid DICOM chains found for this patient")
            skip_result = {
                'pNumber': patient_id,
                'CTSeriesUID': 'N/A',
                'ChainStatus': 'No RTSTRUCT pairs found',
                'Enough_RTSTRUCTs': 'No',
                'RTPLAN_Present': 'N/A (excluded)',
                'Common VOI': 'N/A',
                'VOIName': 'N/A',
                'Dice': None,
                'Status': 'No valid DICOM chains found'
            }
            if calc_all_parameters != 0:
                skip_result['APL'] = None
                skip_result['SDSC'] = None
                skip_result['APL_tol0'] = None
                skip_result['SDSC_tol0'] = None
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
                    'Clinical_RTSTRUCT': chain['clinical_rtstruct']['filename'] if chain['clinical_rtstruct'] else 'N/A',
                    'Limbus_AI_RTSTRUCT': chain['limbus_ai_rtstruct']['filename'] if chain['limbus_ai_rtstruct'] else 'N/A',
                    'Enough_RTSTRUCTs': 'No',
                    'RTPLAN_Present': 'N/A (excluded)',
                    'Common VOI': 'N/A',
                    'VOIName': 'N/A',
                    'Dice': None,
                    'Status': f'Incomplete chain: {chain["chain_status"]}'
                }
                if calc_all_parameters != 0:
                    skip_result['APL'] = None
                    skip_result['SDSC'] = None
                    skip_result['APL_tol0'] = None
                    skip_result['SDSC_tol0'] = None
                all_results.append(skip_result)
                continue
            
            # Extract chain components
            clinical_rtstruct_info = chain['clinical_rtstruct']
            ct_series_info = chain['ct_series']
            limbus_rtstruct_info = chain['limbus_ai_rtstruct']
            
            print(f"    Clinical RTSTRUCT: {clinical_rtstruct_info['filename']}")
            print(f"    Limbus AI RTSTRUCT: {limbus_rtstruct_info['filename']}")
            print(f"    CT Series: {ct_series_info['file_count']} slices")
            
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
            # RTSTRUCT 2 = Clinical (reference)
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
            
            # Find common structures using helper function
            common_vois, indices1, indices2 = get_common_structures(rtstruct1, rtstruct2, excluded_vois)
            
            if not common_vois:
                warnings.warn(f'No valid VOIs found after exclusions. Skipping this chain.')
                skip_result = {
                    'pNumber': patient_id,
                    'CTSeriesUID': ct_series_info['series_uid'][-12:],
                    'ChainStatus': 'Complete',
                    'Clinical_RTSTRUCT': clinical_rtstruct_info['filename'],
                    'Limbus_AI_RTSTRUCT': limbus_rtstruct_info['filename'],
                    'RTSTRUCT1_SeriesDescription': rtstruct1_series_desc,
                    'RTSTRUCT2_SeriesDescription': rtstruct2_series_desc,
                    'Enough_RTSTRUCTs': 'Yes',
                    'RTPLAN_Present': 'N/A (excluded)',
                    'Common VOI': 'No',
                    'VOIName': 'N/A',
                    'Dice': None,
                    'Status': 'No common VOIs after exclusions'
                }
                if calc_all_parameters != 0:
                    skip_result['APL'] = None
                    skip_result['SDSC'] = None
                    skip_result['APL_tol0'] = None
                    skip_result['SDSC_tol0'] = None
                all_results.append(skip_result)
                continue
            
            print(f"\n    Common structures ({len(common_vois)}): {', '.join(common_vois)}")
            print(f"    Comparing {len(common_vois)} structure(s)")
            
            # Compose structure matrices (COMMON STRUCTURES ONLY)
            print("\n    Composing structure matrices (COMMON STRUCTURES ONLY)...")
            print(f"    → Limbus AI: composing {len(indices1)} of {len(vois1)} structures")
            print(f"    → Clinical: composing {len(indices2)} of {len(vois2)} structures")
            
            try:
                # Only compose the common structures - avoids 64-structure limit!
                voi1 = compose_struct_matrix_filtered(imaging_data, rtstruct1, indices1)
                voi2 = compose_struct_matrix_filtered(imaging_data, rtstruct2, indices2)
            except Exception as e:
                print(f"    ✗ Error composing structure matrices: {str(e)}")
                continue
            
            # Calculate metrics for each structure
            print("    Calculating metrics...")
            for struct_position, (voi_name, orig_idx1, orig_idx2) in enumerate(zip(common_vois, indices1, indices2)):
                print(f"      Processing: {voi_name}")
                
                # Check if VOIs are empty
                is_empty1 = not has_contour_points_local(rtstruct1['Struct'][orig_idx1])
                is_empty2 = not has_contour_points_local(rtstruct2['Struct'][orig_idx2])
                
                if is_empty1 or is_empty2:
                    which_side = 'both' if is_empty1 and is_empty2 else ('Limbus AI' if is_empty1 else 'Clinical')
                    warnings.warn(f'Skipping VOI "{voi_name}": empty contour in {which_side}.')
                    continue
                
                # Initialize result
                result = {
                    'pNumber': patient_id,
                    'CTSeriesUID': ct_series_info['series_uid'][-12:],
                    'ChainStatus': 'Complete',
                    'Clinical_RTSTRUCT': clinical_rtstruct_info['filename'],
                    'Limbus_AI_RTSTRUCT': limbus_rtstruct_info['filename'],
                    'RTSTRUCT1_SeriesDescription': rtstruct1_series_desc,
                    'RTSTRUCT2_SeriesDescription': rtstruct2_series_desc,
                    'Enough_RTSTRUCTs': 'Yes',
                    'RTPLAN_Present': 'N/A (excluded)',
                    'Common VOI': 'Yes',
                    'VOIName': voi_name
                }
                
                try:
                    # Calculate volumetric DICE
                    dice_idx = struct_position + 1
                    result['Dice'] = calculate_dice_logical(voi1, voi2, dice_idx, dice_idx)
                    
                    # Calculate APL and Surface DSC if requested
                    if calc_all_parameters != 0:
                        # Calculate with tolerance 0.1
                        temp_path_length = calculate_path_length(
                            imaging_data, rtstruct1, rtstruct2, 
                            orig_idx1, orig_idx2, apl_tolerance
                        )
                        result['APL'] = np.sum(temp_path_length)
                        
                        result['SDSC'] = calculate_surface_dsc(
                            imaging_data, rtstruct1, rtstruct2,
                            orig_idx1, orig_idx2, sdsc_tolerance
                        )
                        
                        # Calculate with tolerance 0.0 (strict matching)
                        temp_path_length_0 = calculate_path_length(
                            imaging_data, rtstruct1, rtstruct2, 
                            orig_idx1, orig_idx2, 0.0
                        )
                        result['APL_tol0'] = np.sum(temp_path_length_0)
                        
                        result['SDSC_tol0'] = calculate_surface_dsc(
                            imaging_data, rtstruct1, rtstruct2,
                            orig_idx1, orig_idx2, 0.0
                        )
                    
                    all_results.append(result)
                    print(f"        DICE: {result['Dice']:.4f}")
                    if calc_all_parameters != 0:
                        print(f"        APL (tol=0.1):  {result['APL']:.4f}")
                        print(f"        SDSC (tol=0.1): {result['SDSC']:.4f}")
                        print(f"        APL (tol=0.0):  {result['APL_tol0']:.4f}")
                        print(f"        SDSC (tol=0.0): {result['SDSC_tol0']:.4f}")
                
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
# EXCEL FILE HANDLING (APPEND/UPDATE)
# ============================================================================

def save_results_to_excel(results: pd.DataFrame, output_file: str = 'contour_comparison_results_excl_RTPLAN.xlsx'):
    """
    Save contour comparison results to Excel file.
    
    Logic:
    - If file doesn't exist: create new file with results
    - If file exists:
        - For NEW patients: append their results
        - For EXISTING patients: override/update their results
    
    Patient identification is based on 'pNumber' column.
    
    Parameters
    ----------
    results : pd.DataFrame
        Results DataFrame from quantify_contour_differences_no_rtplan
    output_file : str
        Path to Excel file
    """
    if results is None or results.empty:
        print("No results to save.")
        return
    
    # Add timestamp to results
    results = results.copy()
    results['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Get unique patient IDs in new results
    new_patients = set(results['pNumber'].unique())
    
    if os.path.exists(output_file):
        try:
            # Load existing data
            existing_df = pd.read_excel(output_file, engine='openpyxl')
            print(f"\nLoaded existing file with {len(existing_df)} record(s)")
            
            # Get existing patient IDs
            existing_patients = set(existing_df['pNumber'].unique())
            
            # Determine which patients to update vs append
            patients_to_update = new_patients & existing_patients
            patients_to_append = new_patients - existing_patients
            
            if patients_to_update:
                print(f"Updating results for {len(patients_to_update)} existing patient(s)")
                existing_df = existing_df[~existing_df['pNumber'].isin(patients_to_update)]
            
            if patients_to_append:
                print(f"Appending results for {len(patients_to_append)} new patient(s)")
            
            # Combine: existing (without updated patients) + all new results
            combined_df = pd.concat([existing_df, results], ignore_index=True)
            
            # Sort by patient and VOI name
            combined_df = combined_df.sort_values(['pNumber', 'CTSeriesUID', 'VOIName'])
            
            # Save combined results
            combined_df.to_excel(output_file, index=False, engine='openpyxl')
            print(f"Saved {len(combined_df)} total record(s) to {output_file}")
            print(f"  - Total unique patients: {len(combined_df['pNumber'].unique())}")
            
        except Exception as e:
            print(f"Error reading existing file: {e}")
            print("Creating new file instead...")
            results.to_excel(output_file, index=False, engine='openpyxl')
            print(f"Saved {len(results)} record(s) to {output_file}")
    else:
        # Create new file
        results.to_excel(output_file, index=False, engine='openpyxl')
        print(f"\nCreated new file with {len(results)} record(s): {output_file}")
        print(f"  - Total unique patients: {len(new_patients)}")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == '__main__':
    # Configuration
    DICOM_ROOT_FOLDER = "Z:\\ICoNEA\\DICOM\\P0728C0006I13351751"  # Update this path
    MAX_PATIENTS = None  # Limit for sample test (set to None for all patients)
    
    # Parse command-line arguments if provided
    if len(sys.argv) > 1:
        DICOM_ROOT_FOLDER = sys.argv[1]
    if len(sys.argv) > 2:
        MAX_PATIENTS = int(sys.argv[2]) if sys.argv[2].lower() != 'none' else None
    
    print("=" * 80)
    print("Quantify Contour Differences - WITHOUT RTPLAN")
    print("=" * 80)
    print(f"DICOM Root Folder: {DICOM_ROOT_FOLDER}")
    print(f"Max Patients: {MAX_PATIENTS if MAX_PATIENTS is not None else 'All'}")
    print("=" * 80)
    print("\nIdentification Method (NO RTPLAN):")
    print("  1. Find Limbus AI RTSTRUCT(s) by metadata verification")
    print("     - SeriesDescription == 'Limbus RTSS v1.8.0'")
    print("     - StructureSetLabel == 'Limbus RTStruct'")
    print("  2. Find clinical RTSTRUCT(s) matching:")
    print("     - Same Frame of Reference UID")
    print("     - Same Referenced CT Series UID")
    print("  3. Find matching CT series")
    print("  4. Compare Limbus AI vs Clinical RTSTRUCT contours")
    print("\nNote: Without RTPLAN, approval status cannot be verified.")
    print("      All non-Limbus RTSTRUCTs are treated as clinical candidates.")
    print("=" * 80)
    
    # Run analysis
    results = quantify_contour_differences_no_rtplan(
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
        print("\n" + "=" * 80)
        print("SAVING RESULTS TO EXCEL")
        print("=" * 80)
        output_file = 'contour_comparison_results_excl_RTPLAN.xlsx'
        save_results_to_excel(results, output_file)
    else:
        print("\nNo results generated.")
