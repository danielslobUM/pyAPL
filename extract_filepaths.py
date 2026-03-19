"""
extract_filepaths.py - Extract CT series file paths for failed-chain patients

Reads contour_comparison_results_P0728_v6.xlsx, filters patients with:
  - 'Limbus AI RTSTRUCT not found (no verified match)'

For these patients, we already have the CTSeriesUID from the v6 file (from the
partial chain that was found). This script simply scans the patient folder for
all CT DICOM files, matches by CTSeriesUID, and extracts the CT folder path.

Output: Excel file with one row per CT series found:
  - pNumber, ChainStatus, CTSeriesUID, CT_Folder, CT_FileCount

Usage:
    python extract_filepaths.py [dicom_root_folder]
"""

import os
import sys
import pydicom
import pandas as pd
from pathlib import Path

from quantifycontourdifferences_P0728_v5 import discover_patient_folders

# ============================================================================
# CONFIGURATION
# ============================================================================

# Results file (relative to workspace root = script's parent directory)
SCRIPT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
RESULTS_FILE = str(SCRIPT_DIR.parent / 'contour_comparison_results_P0728_v6.xlsx')

# DICOM root folder
DICOM_ROOT_FOLDER = r"Z:\ICoNEA\DICOM"

# Output file
OUTPUT_FILE = str(SCRIPT_DIR.parent / 'failed_chain_ct_filepaths.xlsx')

# Statuses to filter (only patients missing Limbus AI)
FILTER_STATUSES = [
    'Limbus AI RTSTRUCT not found (no verified match)',
]


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def scan_ct_files_in_patient(patient_folder: str) -> dict:
    """
    Scan all .dcm files in a patient folder and identify CT series.
    
    Parameters
    ----------
    patient_folder : str
        Path to patient folder
        
    Returns
    -------
    dict
        Dictionary mapping CT Series UID to info dict with:
        - series_uid: full Series Instance UID
        - folder: folder containing the CT files
        - file_count: number of CT files in this series
        - files: list of file paths
    """
    ct_series_dict = {}
    
    # Walk entire patient folder to find all .dcm files
    for root, dirs, files in os.walk(patient_folder):
        for file in files:
            if file.lower().endswith('.dcm'):
                filepath = os.path.join(root, file)
                try:
                    ds = pydicom.dcmread(filepath, stop_before_pixels=True)
                    if ds.get('Modality', '') == 'CT':
                        series_uid = str(ds.get('SeriesInstanceUID', ''))
                        
                        if series_uid not in ct_series_dict:
                            ct_series_dict[series_uid] = {
                                'series_uid': series_uid,
                                'folder': root,
                                'file_count': 0,
                                'files': []
                            }
                        ct_series_dict[series_uid]['file_count'] += 1
                        ct_series_dict[series_uid]['files'].append(filepath)
                except:
                    pass
    
    return ct_series_dict


# ============================================================================
# MAIN LOGIC
# ============================================================================

def extract_ct_filepaths(results_file: str, dicom_root: str, output_file: str):
    """
    For each patient with 'Limbus AI RTSTRUCT not found', locate the CT series.

    The v6 file already contains CTSeriesUID (last 12 chars) for these patients.
    We scan the patient folder for CT files and match by series UID suffix.

    Parameters
    ----------
    results_file : str
        Path to the v6 results Excel file
    dicom_root : str
        Root folder containing patient subdirectories (e.g. Z:\\ICoNEA\\DICOM)
    output_file : str
        Path for the output Excel file
    """
    # ------------------------------------------------------------------
    # 1. Load and filter the results file
    # ------------------------------------------------------------------
    print(f"Loading results from: {results_file}")
    df = pd.read_excel(results_file, engine='openpyxl')
    filtered = df[df['ChainStatus'].isin(FILTER_STATUSES)]

    # Keep all rows - a patient can have multiple rows with missing Limbus AI
    # Each row may correspond to a different CT series / RTPLAN chain
    patient_ct_info = filtered[['pNumber', 'ChainStatus', 'CTSeriesUID']].sort_values('pNumber')
    print(f"Found {len(patient_ct_info)} rows with missing Limbus AI "
          f"({patient_ct_info['pNumber'].nunique()} unique patients)")

    # ------------------------------------------------------------------
    # 2. Build a lookup from patient ID → patient folder on disk
    # ------------------------------------------------------------------
    print(f"\nDiscovering patient folders in: {dicom_root}")
    all_patients = discover_patient_folders(dicom_root)
    folder_lookup = {p['patient_id']: p['patient_folder'] for p in all_patients}
    print(f"Found {len(folder_lookup)} patient folders on disk")

    # ------------------------------------------------------------------
    # 3. For each filtered patient, locate CT series by matching UID
    # ------------------------------------------------------------------
    results = []
    not_found_on_disk = []

    for _, row in patient_ct_info.iterrows():
        patient_id = row['pNumber']
        chain_status = row['ChainStatus']
        ct_series_uid_suffix = str(row['CTSeriesUID'])  # Last 12 chars from v6
        
        # Remove trailing ".0" if present (Excel float conversion artifact)
        if ct_series_uid_suffix.endswith('.0'):
            ct_series_uid_suffix = ct_series_uid_suffix[:-2]

        patient_folder = folder_lookup.get(patient_id)
        if not patient_folder:
            print(f"  ✗ {patient_id}: folder not found on disk")
            not_found_on_disk.append(patient_id)
            results.append({
                'pNumber': patient_id,
                'ChainStatus': chain_status,
                'CTSeriesUID': ct_series_uid_suffix,
                'CT_Folder': 'Patient folder not found on disk',
                'CT_FileCount': 0,
            })
            continue

        # Scan all CT files in patient folder
        ct_series_dict = scan_ct_files_in_patient(patient_folder)
        
        if not ct_series_dict:
            print(f"  ✗ {patient_id}: no CT files found in folder")
            results.append({
                'pNumber': patient_id,
                'ChainStatus': chain_status,
                'CTSeriesUID': ct_series_uid_suffix,
                'CT_Folder': 'No CT files found in patient folder',
                'CT_FileCount': 0,
            })
            continue

        # Match CT series by UID suffix (last 12 chars)
        matched_ct = None
        for series_uid, ct_info in ct_series_dict.items():
            if series_uid.endswith(ct_series_uid_suffix):
                matched_ct = ct_info
                break

        if matched_ct:
            results.append({
                'pNumber': patient_id,
                'ChainStatus': chain_status,
                'CTSeriesUID': matched_ct['series_uid'],
                'CT_Folder': matched_ct['folder'],
                'CT_FileCount': matched_ct['file_count'],
            })
            print(f"  ✓ {patient_id}: found CT series ({matched_ct['file_count']} files)")
        else:
            # List available CT series for debugging
            available_uids = [uid[-12:] for uid in ct_series_dict.keys()]
            print(f"  ✗ {patient_id}: CT series '{ct_series_uid_suffix}' not found")
            print(f"      Available: {available_uids}")
            results.append({
                'pNumber': patient_id,
                'ChainStatus': chain_status,
                'CTSeriesUID': ct_series_uid_suffix,
                'CT_Folder': f'CT series not found. Available: {available_uids}',
                'CT_FileCount': 0,
            })

    # ------------------------------------------------------------------
    # 4. Save to Excel
    # ------------------------------------------------------------------
    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values(['pNumber', 'CTSeriesUID'])
    results_df.to_excel(output_file, index=False, engine='openpyxl')

    print(f"\n{'='*70}")
    print(f"RESULTS")
    print(f"{'='*70}")
    print(f"Total rows written:       {len(results_df)}")
    print(f"Unique patients:          {results_df['pNumber'].nunique()}")
    print(f"CT series found:          {len(results_df[results_df['CT_FileCount'] > 0])}")
    print(f"Patients not on disk:     {len(not_found_on_disk)}")
    print(f"Output saved to:          {output_file}")
    print(f"{'='*70}")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == '__main__':
    dicom_root = DICOM_ROOT_FOLDER
    if len(sys.argv) > 1:
        dicom_root = sys.argv[1]

    print("=" * 70)
    print("Extract CT Series File Paths for Failed-Chain Patients")
    print("=" * 70)
    print(f"Results file : {RESULTS_FILE}")
    print(f"DICOM root   : {dicom_root}")
    print(f"Output file  : {OUTPUT_FILE}")
    print(f"Filter       : {FILTER_STATUSES}")
    print("=" * 70)

    extract_ct_filepaths(RESULTS_FILE, dicom_root, OUTPUT_FILE)
