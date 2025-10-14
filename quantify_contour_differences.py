"""
quantify_contour_differences - Quantify differences between contours

This function can be used to quickly quantify differences between 
contours delineated by two different methods/persons for one or more
patients. The user is asked to select a (sub)folder with imaging data, a
(sub)folder containing RTSTRUCTS for method/person 1 and a (sub)folder 
containing RTSTRUCTS for method/person 2.

History
-------
17/02/2025, Rik Hansen - Creation
25/08/2025, Daniël Slob - created hasContourPointsLocal
Converted to Python
"""

import os
import re
import warnings
import pandas as pd
import numpy as np
from read_dicomct_light import read_dicomct_light
from read_dicomrtstruct import read_dicomrtstruct
from compose_struct_matrix import compose_struct_matrix
from calculate_dice_logical import calculate_dice_logical
from calculate_surface_dsc import calculate_surface_dsc
from calculate_different_path_length_v2 import calculate_different_path_length_v2
from has_contour_points_local import has_contour_points_local

# Try to import tkinter for GUI, fall back to CLI if not available
try:
    import tkinter as tk
    from tkinter import filedialog
    HAS_TKINTER = True
except ImportError:
    HAS_TKINTER = False


def quantify_contour_differences(calc_all_parameters=1, root_folder=None):
    """
    Quantify differences between contours delineated by two methods/persons.
    
    Parameters
    ----------
    calc_all_parameters : int, optional
        Switch on (1) or off (0) calculation of added path length (APL) 
        and surface DICE in addition to volumetric DICE. Default = 1.
    root_folder : str, optional
        Start folder for subfolder selection. Default is current directory.
        
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
    # Set defaults
    if calc_all_parameters is None:
        calc_all_parameters = 1
    
    if root_folder is None or not os.path.isdir(root_folder):
        root_folder = os.getcwd()
    
    apl_tolerance = 0.1
    sdsc_tolerance = 0.1
    
    # Select folders (GUI or CLI)
    if HAS_TKINTER:
        # Initialize tkinter for folder selection
        root = tk.Tk()
        root.withdraw()
        
        # Select imaging data folder
        imaging_data_folder = filedialog.askdirectory(
            initialdir=root_folder,
            title='Select folder with imaging data'
        )
        if not imaging_data_folder:
            print("No imaging data folder selected. Exiting.")
            return None
        
        # Select RTSTRUCT folder for method/person 1
        struct_folder_method1 = filedialog.askdirectory(
            initialdir=root_folder,
            title='Select folder with RTSTRUCT data of method/person 1 (reference data)'
        )
        if not struct_folder_method1:
            print("No method 1 folder selected. Exiting.")
            return None
        
        # Select RTSTRUCT folder for method/person 2
        struct_folder_method2 = filedialog.askdirectory(
            initialdir=root_folder,
            title='Select folder with RTSTRUCT data of method/person 2 (new data)'
        )
        if not struct_folder_method2:
            print("No method 2 folder selected. Exiting.")
            return None
    else:
        # CLI input
        print("GUI not available. Using command-line input.")
        imaging_data_folder = input("Enter path to imaging data folder: ").strip()
        if not os.path.isdir(imaging_data_folder):
            print(f"Invalid folder: {imaging_data_folder}")
            return None
        
        struct_folder_method1 = input("Enter path to RTSTRUCT folder for method/person 1: ").strip()
        if not os.path.isdir(struct_folder_method1):
            print(f"Invalid folder: {struct_folder_method1}")
            return None
        
        struct_folder_method2 = input("Enter path to RTSTRUCT folder for method/person 2: ").strip()
        if not os.path.isdir(struct_folder_method2):
            print(f"Invalid folder: {struct_folder_method2}")
            return None
    
    dirnames_imaging_data = [d for d in os.listdir(imaging_data_folder) 
                            if os.path.isdir(os.path.join(imaging_data_folder, d))]
    
    rtstruct_files_method1 = [f for f in os.listdir(struct_folder_method1) 
                             if os.path.isfile(os.path.join(struct_folder_method1, f))]
    
    rtstruct_files_method2 = [f for f in os.listdir(struct_folder_method2) 
                             if os.path.isfile(os.path.join(struct_folder_method2, f))]
    
    # Perform contour differences quantification
    n_imaging_sets = len(dirnames_imaging_data)
    selected_oars = None
    all_results = []
    
    print(f"Processing {n_imaging_sets} imaging sets...")
    
    for imaging_set_no, dirname in enumerate(dirnames_imaging_data):
        print(f"\nProcessing imaging set {imaging_set_no + 1}/{n_imaging_sets}")
        
        # Read imaging data
        print('Reading imaging data')
        folder_imaging_data = os.path.join(imaging_data_folder, dirname)
        imaging_files = [os.path.join(folder_imaging_data, f) 
                        for f in os.listdir(folder_imaging_data)
                        if os.path.isfile(os.path.join(folder_imaging_data, f))]
        
        if not imaging_files:
            print(f"No imaging files found in {folder_imaging_data}")
            continue
        
        imaging_data = read_dicomct_light(imaging_files)
        
        # Extract patient number
        match = re.search(r'P\d{4}C', folder_imaging_data)
        if match:
            p_number_start = match.start()
            p_number = folder_imaging_data[p_number_start:].split('_')[0]
        else:
            print(f"Could not extract patient number from {folder_imaging_data}")
            continue
        
        print(f'Calculating metrics for patient {p_number}')
        print('Reading struct files')
        
        # Find RTSTRUCT files for this patient
        rtstruct1_files = [f for f in rtstruct_files_method1 if p_number in f]
        rtstruct2_files = [f for f in rtstruct_files_method2 if p_number in f]
        
        if not rtstruct1_files or not rtstruct2_files:
            print(f"RTSTRUCT files not found for patient {p_number}")
            continue
        
        # Read RTSTRUCT files
        rtstruct1_filename = os.path.join(struct_folder_method1, rtstruct1_files[0])
        rtstruct1 = read_dicomrtstruct(rtstruct1_filename)
        
        rtstruct2_filename = os.path.join(struct_folder_method2, rtstruct2_files[0])
        rtstruct2 = read_dicomrtstruct(rtstruct2_filename)
        
        # Get structure names
        vois1 = [s['Name'] for s in rtstruct1['Struct']]
        vois2 = [s['Name'] for s in rtstruct2['Struct']]
        n_vois1 = len(vois1)
        n_vois2 = len(vois2)
        
        # Find common VOIs
        common_vois = [v for v in vois1 if v in vois2]
        
        if not common_vois:
            warnings.warn(f'No common VOIs found for patient {p_number}. Skipping patient.')
            continue
        
        if n_vois2 < n_vois1:
            warnings.warn(f'There are less structures in the new RTSTRUCT set for patient: {p_number}')
        
        missing_vois = [v for v in vois1 if v not in vois2]
        if missing_vois:
            warnings.warn(f'The following structure(s) is/are missing in the new RTSTRUCT for patient {p_number}: {", ".join(missing_vois)}')
        
        # Select OARs once per run
        if selected_oars is None:
            print(f'\nCommon VOIs for patient {p_number}: {", ".join(common_vois)}')
            print('Please enter the indices of OARs to include (comma-separated, or press Enter for all):')
            for i, voi in enumerate(common_vois):
                print(f'{i}: {voi}')
            
            selection = input('Selection (e.g., 0,2,4 or press Enter for all): ').strip()
            if selection:
                indices = [int(x.strip()) for x in selection.split(',')]
                selected_oars = [common_vois[i] for i in indices if i < len(common_vois)]
            else:
                selected_oars = common_vois
            
            print(f'Selected OARs: {", ".join(selected_oars)}')
        
        # Filter to selected OARs
        to_compare = [i for i, v in enumerate(vois1) if v in selected_oars and v in vois2]
        
        if not to_compare:
            warnings.warn(f'None of the selected OARs are present for patient {p_number}. Skipping patient.')
            continue
        
        # Compose structure matrices
        voi1 = compose_struct_matrix(imaging_data, rtstruct1)
        voi2 = compose_struct_matrix(imaging_data, rtstruct2)
        
        print('Calculating metrics')
        
        # Calculate metrics for each structure
        for comparison_no, method1_struct_no in enumerate(to_compare):
            voi_name = vois1[method1_struct_no]
            method2_struct_no = vois2.index(voi_name)
            
            # Check if VOIs are empty
            is_empty1 = not has_contour_points_local(rtstruct1['Struct'][method1_struct_no])
            is_empty2 = not has_contour_points_local(rtstruct2['Struct'][method2_struct_no])
            
            if is_empty1 or is_empty2:
                which_side = 'both' if is_empty1 and is_empty2 else ('RTSTRUCT1' if is_empty1 else 'RTSTRUCT2')
                warnings.warn(f'Skipping VOI "{voi_name}" for patient {p_number}: empty contour in {which_side}.')
                continue
            
            # Initialize result
            result = {
                'pNumber': p_number,
                'VOIName': voi_name
            }
            
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
    
    # Create results table
    if all_results:
        results_table = pd.DataFrame(all_results)
        results_table = results_table.sort_values('VOIName')
        return results_table
    else:
        return pd.DataFrame()


if __name__ == '__main__':
    # Sample call
    results = quantify_contour_differences(calc_all_parameters=1)
    
    if results is not None and not results.empty:
        print("\n" + "="*80)
        print("RESULTS")
        print("="*80)
        print(results.to_string(index=False))
        
        # Optionally save to CSV
        output_file = 'contour_comparison_results.csv'
        results.to_csv(output_file, index=False)
        print(f"\nResults saved to {output_file}")
    else:
        print("\nNo results generated.")
