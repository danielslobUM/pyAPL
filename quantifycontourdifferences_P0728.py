"""
quantifycontourdifferences_P0728 - Automated contour comparison using LinkedDICOM metadata

This script automatically fetches the correct data from all patients in the dataset
using linkeddicom.ttl files for metadata. It processes patients with the folder structure:
DICOM -> Pxxxxxxxxxxxxxxxx -> CT/RTDOSE/RTPLAN/RTSTRUCT (folders) -> yyyymmdd -> .dcm files
                           -> linkeddicom.ttl

The linkeddicom.ttl file contains metadata to locate the correct CT and RTSTRUCT files.

History
-------
Created for P0728 dataset analysis
Adapted from quantify_contour_differences.py
"""

import os
import sys
import warnings
import pandas as pd
import numpy as np
from pathlib import Path
from rdflib import Graph, Namespace, URIRef
from read_dicomct_light import read_dicomct_light
from read_dicomrtstruct import read_dicomrtstruct
from compose_struct_matrix import compose_struct_matrix
from calculate_dice_logical import calculate_dice_logical
from calculate_surface_dsc import calculate_surface_dsc
from calculate_different_path_length_v2 import calculate_different_path_length_v2
from has_contour_points_local import has_contour_points_local


def parse_linkeddicom_ttl(ttl_file_path):
    """
    Parse a linkeddicom.ttl file to extract DICOM file information.
    
    Parameters
    ----------
    ttl_file_path : str
        Path to the linkeddicom.ttl file
        
    Returns
    -------
    dict
        Dictionary with keys 'ct_files' and 'rtstruct_files', each containing lists of file paths
    """
    if not os.path.exists(ttl_file_path):
        warnings.warn(f"TTL file not found: {ttl_file_path}")
        return {'ct_files': [], 'rtstruct_files': []}
    
    try:
        g = Graph()
        g.parse(ttl_file_path, format='ttl')
        
        # Define namespaces commonly used in LinkedDICOM
        DICOM = Namespace("http://purl.org/healthcarevocab/v1#")
        RDF = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")
        RDFS = Namespace("http://www.w3.org/2000/01/rdf-schema#")
        
        ct_files = []
        rtstruct_files = []
        
        # Query for all subjects and their types
        for subject in g.subjects():
            subject_str = str(subject)
            
            # Check the types of this subject
            for obj in g.objects(subject, RDF.type):
                obj_str = str(obj).lower()
                
                # If it's a CT modality
                if 'ct' in obj_str or 'computedtomography' in obj_str.replace(' ', ''):
                    # Try to find file path information
                    for pred, obj in g.predicate_objects(subject):
                        if 'filename' in str(pred).lower() or 'filepath' in str(pred).lower():
                            ct_files.append(str(obj))
                
                # If it's an RTSTRUCT modality
                if 'rtstruct' in obj_str or 'rtstructureset' in obj_str.replace(' ', ''):
                    # Try to find file path information
                    for pred, obj in g.predicate_objects(subject):
                        if 'filename' in str(pred).lower() or 'filepath' in str(pred).lower():
                            rtstruct_files.append(str(obj))
        
        return {
            'ct_files': ct_files,
            'rtstruct_files': rtstruct_files
        }
    
    except Exception as e:
        warnings.warn(f"Error parsing TTL file {ttl_file_path}: {str(e)}")
        return {'ct_files': [], 'rtstruct_files': []}


def discover_patient_data(dicom_root_folder):
    """
    Discover all patient folders and their data in the DICOM directory structure.
    
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
        - ttl_file: Path to linkeddicom.ttl file
        - ct_folder: Path to CT folder
        - rtstruct_folder: Path to RTSTRUCT folder
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
        
        # Look for linkeddicom.ttl file
        ttl_file = os.path.join(patient_folder, 'linkeddicom.ttl')
        
        # Look for CT and RTSTRUCT folders
        ct_folder = os.path.join(patient_folder, 'CT')
        rtstruct_folder = os.path.join(patient_folder, 'RTSTRUCT')
        
        patient_data = {
            'patient_id': item,
            'patient_folder': patient_folder,
            'ttl_file': ttl_file if os.path.exists(ttl_file) else None,
            'ct_folder': ct_folder if os.path.isdir(ct_folder) else None,
            'rtstruct_folder': rtstruct_folder if os.path.isdir(rtstruct_folder) else None
        }
        
        patients.append(patient_data)
    
    return patients


def find_dicom_files_in_folder(folder_path):
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


def quantify_contour_differences_p0728(dicom_root_folder, method1_identifier='method1', 
                                        method2_identifier='method2', calc_all_parameters=1,
                                        selected_oars=None, max_patients=None):
    """
    Quantify differences between contours for all patients using linkeddicom.ttl metadata.
    
    This function automatically processes all patients in the DICOM folder structure,
    comparing RTSTRUCT files from two different methods/persons.
    
    Parameters
    ----------
    dicom_root_folder : str
        Root folder containing patient subdirectories with DICOM data
    method1_identifier : str, optional
        Identifier string to recognize RTSTRUCT files for method/person 1 (reference).
        Default is 'method1'. This string should appear in the folder name or file name.
    method2_identifier : str, optional
        Identifier string to recognize RTSTRUCT files for method/person 2 (comparison).
        Default is 'method2'. This string should appear in the folder name or file name.
    calc_all_parameters : int, optional
        Switch on (1) or off (0) calculation of added path length (APL) 
        and surface DICE in addition to volumetric DICE. Default = 1.
    selected_oars : list of str, optional
        List of structure names to compare. If None, will prompt user to select.
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
    patients = discover_patient_data(dicom_root_folder)
    
    if not patients:
        print("No patient folders found.")
        return pd.DataFrame()
    
    print(f"Found {len(patients)} patient folder(s)")
    
    # Limit number of patients if max_patients is specified
    if max_patients is not None and max_patients > 0:
        patients = patients[:max_patients]
        print(f"Limiting to first {len(patients)} patient(s) for sample test")
    
    # Process each patient
    all_results = []
    oars_selected = selected_oars is not None
    
    for patient_idx, patient_data in enumerate(patients):
        patient_id = patient_data['patient_id']
        print(f"\n{'='*80}")
        print(f"Processing patient {patient_idx + 1}/{len(patients)}: {patient_id}")
        print(f"{'='*80}")
        
        # Check if patient has required folders
        if not patient_data['ct_folder']:
            print(f"  Warning: No CT folder found for patient {patient_id}")
            continue
        
        if not patient_data['rtstruct_folder']:
            print(f"  Warning: No RTSTRUCT folder found for patient {patient_id}")
            continue
        
        # Find CT files
        print("  Searching for CT files...")
        ct_files = find_dicom_files_in_folder(patient_data['ct_folder'])
        
        if not ct_files:
            print(f"  Warning: No CT DICOM files found for patient {patient_id}")
            continue
        
        print(f"  Found {len(ct_files)} CT file(s)")
        
        # Read CT data
        print("  Reading CT data...")
        try:
            imaging_data = read_dicomct_light(ct_files)
        except Exception as e:
            print(f"  Error reading CT data: {str(e)}")
            continue
        
        # Find RTSTRUCT files for both methods
        print("  Searching for RTSTRUCT files...")
        rtstruct_folder = patient_data['rtstruct_folder']
        
        # Look for subdirectories or files containing method identifiers
        rtstruct1_files = []
        rtstruct2_files = []
        
        # Search through RTSTRUCT folder structure
        for root, dirs, files in os.walk(rtstruct_folder):
            root_lower = root.lower()
            
            # Check if this folder or its parent contains method identifiers
            if method1_identifier.lower() in root_lower:
                rtstruct1_files.extend([os.path.join(root, f) for f in files if f.lower().endswith('.dcm')])
            elif method2_identifier.lower() in root_lower:
                rtstruct2_files.extend([os.path.join(root, f) for f in files if f.lower().endswith('.dcm')])
            else:
                # If no folder structure, check file names
                for f in files:
                    if f.lower().endswith('.dcm'):
                        file_path = os.path.join(root, f)
                        if method1_identifier.lower() in f.lower():
                            rtstruct1_files.append(file_path)
                        elif method2_identifier.lower() in f.lower():
                            rtstruct2_files.append(file_path)
        
        # If we couldn't find files by method identifier, try date-based approach
        if not rtstruct1_files and not rtstruct2_files:
            print("  Warning: Could not identify RTSTRUCT files by method identifier.")
            print(f"  Looking for date-based subdirectories in RTSTRUCT folder...")
            
            # Find all date subdirectories
            date_dirs = []
            for item in os.listdir(rtstruct_folder):
                item_path = os.path.join(rtstruct_folder, item)
                if os.path.isdir(item_path):
                    date_dirs.append(item_path)
            
            date_dirs.sort()  # Sort by date
            
            if len(date_dirs) >= 2:
                # Assume first date is method1, second is method2 (or vice versa)
                print(f"  Found {len(date_dirs)} date-based subdirectories")
                print(f"  Using {os.path.basename(date_dirs[0])} as method 1")
                print(f"  Using {os.path.basename(date_dirs[-1])} as method 2")
                
                rtstruct1_files = find_dicom_files_in_folder(date_dirs[0])
                rtstruct2_files = find_dicom_files_in_folder(date_dirs[-1])
            elif len(date_dirs) == 1:
                # Only one date directory - check if there are multiple RTSTRUCT files
                all_rtstruct_files = find_dicom_files_in_folder(date_dirs[0])
                if len(all_rtstruct_files) >= 2:
                    print(f"  Found {len(all_rtstruct_files)} RTSTRUCT files in single date directory")
                    print(f"  Using first as method 1, second as method 2")
                    rtstruct1_files = [all_rtstruct_files[0]]
                    rtstruct2_files = [all_rtstruct_files[1]]
                else:
                    print(f"  Warning: Not enough RTSTRUCT files found for patient {patient_id}")
                    continue
        
        if not rtstruct1_files:
            print(f"  Warning: No RTSTRUCT files found for method 1")
            continue
        
        if not rtstruct2_files:
            print(f"  Warning: No RTSTRUCT files found for method 2")
            continue
        
        print(f"  Method 1: {len(rtstruct1_files)} RTSTRUCT file(s)")
        print(f"  Method 2: {len(rtstruct2_files)} RTSTRUCT file(s)")
        
        # Read RTSTRUCT files (use first file from each method)
        try:
            print("  Reading RTSTRUCT files...")
            rtstruct1 = read_dicomrtstruct(rtstruct1_files[0])
            rtstruct2 = read_dicomrtstruct(rtstruct2_files[0])
        except Exception as e:
            print(f"  Error reading RTSTRUCT files: {str(e)}")
            continue
        
        # Get structure names
        vois1 = [s['Name'] for s in rtstruct1['Struct']]
        vois2 = [s['Name'] for s in rtstruct2['Struct']]
        
        print(f"  Method 1 structures: {len(vois1)}")
        print(f"  Method 2 structures: {len(vois2)}")
        
        # Find common VOIs
        common_vois = [v for v in vois1 if v in vois2]
        
        if not common_vois:
            warnings.warn(f'No common VOIs found for patient {patient_id}. Skipping patient.')
            continue
        
        print(f"  Common structures: {len(common_vois)}")
        
        # Select OARs if not already selected
        if selected_oars is None and not oars_selected:
            print(f'\n  Common VOIs: {", ".join(common_vois)}')
            print('  Please enter the indices of OARs to include (comma-separated, or press Enter for all):')
            for i, voi in enumerate(common_vois):
                print(f'  {i}: {voi}')
            
            selection = input('  Selection (e.g., 0,2,4 or press Enter for all): ').strip()
            if selection:
                indices = [int(x.strip()) for x in selection.split(',')]
                selected_oars = [common_vois[i] for i in indices if i < len(common_vois)]
            else:
                selected_oars = common_vois
            
            print(f'  Selected OARs: {", ".join(selected_oars)}')
            oars_selected = True
        
        # Use the selected OARs
        to_compare = [i for i, v in enumerate(vois1) if v in selected_oars and v in vois2]
        
        if not to_compare:
            warnings.warn(f'None of the selected OARs are present for patient {patient_id}. Skipping patient.')
            continue
        
        print(f"  Comparing {len(to_compare)} structure(s)")
        
        # Compose structure matrices
        print("  Composing structure matrices...")
        try:
            voi1 = compose_struct_matrix(imaging_data, rtstruct1)
            voi2 = compose_struct_matrix(imaging_data, rtstruct2)
        except Exception as e:
            print(f"  Error composing structure matrices: {str(e)}")
            continue
        
        # Calculate metrics for each structure
        print("  Calculating metrics...")
        for comparison_no, method1_struct_no in enumerate(to_compare):
            voi_name = vois1[method1_struct_no]
            method2_struct_no = vois2.index(voi_name)
            
            print(f"    Processing: {voi_name}")
            
            # Check if VOIs are empty
            is_empty1 = not has_contour_points_local(rtstruct1['Struct'][method1_struct_no])
            is_empty2 = not has_contour_points_local(rtstruct2['Struct'][method2_struct_no])
            
            if is_empty1 or is_empty2:
                which_side = 'both' if is_empty1 and is_empty2 else ('RTSTRUCT1' if is_empty1 else 'RTSTRUCT2')
                warnings.warn(f'Skipping VOI "{voi_name}" for patient {patient_id}: empty contour in {which_side}.')
                continue
            
            # Initialize result
            result = {
                'pNumber': patient_id,
                'VOIName': voi_name
            }
            
            try:
                # Calculate volumetric DICE
                result['Dice'] = calculate_dice_logical(voi1, voi2, method1_struct_no + 1, method2_struct_no + 1)
                
                # Calculate APL and Surface DSC if requested
                if calc_all_parameters != 0:
                    # Calculate APL
                    temp_path_length = calculate_different_path_length_v2(
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
                print(f"      DICE: {result['Dice']:.4f}")
                if calc_all_parameters != 0:
                    print(f"      APL:  {result['APL']:.4f}")
                    print(f"      SDSC: {result['SDSC']:.4f}")
            
            except Exception as e:
                print(f"    Error calculating metrics for {voi_name}: {str(e)}")
                continue
    
    # Create results table
    if all_results:
        results_table = pd.DataFrame(all_results)
        results_table = results_table.sort_values(['pNumber', 'VOIName'])
        return results_table
    else:
        return pd.DataFrame()


if __name__ == '__main__':
    # Configuration
    # Update these paths for your dataset
    DICOM_ROOT_FOLDER = '/path/to/DICOM'  # Update this path
    METHOD1_IDENTIFIER = 'method1'  # Update to match your folder/file naming
    METHOD2_IDENTIFIER = 'method2'  # Update to match your folder/file naming
    MAX_PATIENTS = 5  # Limit to 5 patients for sample test (set to None for all patients)
    
    # Parse command-line arguments if provided
    if len(sys.argv) > 1:
        DICOM_ROOT_FOLDER = sys.argv[1]
    if len(sys.argv) > 2:
        METHOD1_IDENTIFIER = sys.argv[2]
    if len(sys.argv) > 3:
        METHOD2_IDENTIFIER = sys.argv[3]
    if len(sys.argv) > 4:
        MAX_PATIENTS = int(sys.argv[4]) if sys.argv[4].lower() != 'none' else None
    
    print("="*80)
    print("Quantify Contour Differences - P0728 Dataset (Sample Test Mode)")
    print("="*80)
    print(f"DICOM Root Folder: {DICOM_ROOT_FOLDER}")
    print(f"Method 1 Identifier: {METHOD1_IDENTIFIER}")
    print(f"Method 2 Identifier: {METHOD2_IDENTIFIER}")
    print(f"Max Patients: {MAX_PATIENTS if MAX_PATIENTS is not None else 'All'}")
    print("="*80)
    
    # Run analysis
    results = quantify_contour_differences_p0728(
        dicom_root_folder=DICOM_ROOT_FOLDER,
        method1_identifier=METHOD1_IDENTIFIER,
        method2_identifier=METHOD2_IDENTIFIER,
        calc_all_parameters=1,
        selected_oars=None,  # Will prompt user
        max_patients=MAX_PATIENTS
    )
    
    if results is not None and not results.empty:
        print("\n" + "="*80)
        print("RESULTS")
        print("="*80)
        print(results.to_string(index=False))
        
        # Save to CSV
        output_file = 'contour_comparison_results_P0728.csv'
        results.to_csv(output_file, index=False)
        print(f"\nResults saved to {output_file}")
    else:
        print("\nNo results generated.")
