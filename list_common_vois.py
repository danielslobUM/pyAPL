"""
list_common_vois.py - List VOIs present in both clinical and Limbus AI structure sets

Uses the same DICOM chain identification logic as quantifycontourdifferences_P0728_v5.py.
For each patient and each complete chain, prints the VOIs found in both RTSTRUCTs,
as well as VOIs exclusive to each side.

Usage:
    python list_common_vois.py [dicom_root_folder] [max_patients]

Examples:
    python list_common_vois.py Z:\\ICoNEA\\DICOM
    python list_common_vois.py Z:\\ICoNEA\\DICOM 10
"""

import os
import sys
import random
import pydicom

from quantifycontourdifferences_P0728_v5 import (
    discover_patient_folders,
    identify_dicom_chain,
)

# VOIs to exclude from comparison (case-insensitive)
EXCLUDED_VOIS = ['body', 'skin']


def get_rtstruct_roi_names(rtstruct_path: str) -> list:
    """
    Read ROI names from an RTSTRUCT file without full contour parsing.

    Parameters
    ----------
    rtstruct_path : str
        Path to the RTSTRUCT .dcm file

    Returns
    -------
    list of str
        Ordered list of ROI names as stored in StructureSetROISequence
    """
    ds = pydicom.dcmread(rtstruct_path, stop_before_pixels=True)
    names = []
    if (0x3006, 0x0020) in ds:  # StructureSetROISequence
        for roi in ds[0x3006, 0x0020]:
            name = str(roi.get('ROIName', '')).strip()
            if name:
                names.append(name)
    return names


def list_common_vois(folder: str, max_patients: int = None):
    """
    For each patient and complete DICOM chain, print VOIs present in both
    the clinical RTSTRUCT and Limbus AI RTSTRUCT.

    The folder argument can be either:
    - A root folder containing multiple patient subdirectories (P*), OR
    - A single patient folder directly (e.g. Z:\\ICoNEA\\DICOM\\P0728xxxx)

    Parameters
    ----------
    folder : str
        Root folder with patient subdirectories, or a single patient folder.
    max_patients : int, optional
        If provided, randomly sample this many patients. Default is None (all patients).
        Only used when folder is a root folder.
    """
    # Auto-detect: try to find patient subfolders first
    patients = discover_patient_folders(folder)

    if patients:
        # folder is a root folder containing multiple patients
        print(f"\nRoot folder detected. Found {len(patients)} patient folder(s) in: {folder}")
        if max_patients is not None:
            patients = random.sample(patients, min(max_patients, len(patients)))
            print(f"Randomly selected {len(patients)} patient(s) for inspection")
    else:
        # Treat folder itself as a single patient folder
        patient_id = os.path.basename(folder.rstrip("/\\\\"))
        print(f"\nSingle patient folder detected: {patient_id}")
        patients = [{'patient_id': patient_id, 'patient_folder': folder}]

    summary_rows = []
    
    # Track PTV variations across all clinical RTSTRUCTs
    ptv_variations = {}  # key: PTV name, value: count
    patients_with_exact_ptv = 0
    patients_with_any_ptv = 0
    total_complete_chains = 0
    
    print()

    for patient_data in patients:
        patient_id = patient_data['patient_id']
        patient_folder = patient_data['patient_folder']

        print(f"\n{'='*70}")
        print(f"Patient: {patient_id}")
        print(f"{'='*70}")

        chains = identify_dicom_chain(patient_folder, verbose=False)

        if not chains:
            print("  No approved RTPLANs found.")
            summary_rows.append({
                'patient': patient_id,
                'chain': '-',
                'status': 'No approved RTPLANs',
                'common_count': 0
            })
            continue

        for chain_idx, chain in enumerate(chains):
            chain_label = f"Chain {chain_idx + 1}"
            print(f"\n  {chain_label}: {chain['chain_status']}")

            if not chain['chain_complete']:
                print(f"  → Skipping incomplete chain")
                summary_rows.append({
                    'patient': patient_id,
                    'chain': chain_label,
                    'status': chain['chain_status'],
                    'common_count': 0
                })
                continue

            clinical_info = chain['clinical_rtstruct']
            limbus_info = chain['limbus_ai_rtstruct']

            try:
                clinical_names = get_rtstruct_roi_names(clinical_info['path'])
                limbus_names = get_rtstruct_roi_names(limbus_info['path'])
            except Exception as e:
                print(f"  → Error reading RTSTRUCT: {e}")
                summary_rows.append({
                    'patient': patient_id,
                    'chain': chain_label,
                    'status': f'Read error: {e}',
                    'common_count': 0
                })
                continue

            # Track PTV variations in clinical RTSTRUCT
            total_complete_chains += 1
            ptv_names_in_clinical = [n for n in clinical_names if 'ptv' in n.lower()]
            has_exact_ptv = 'PTV' in clinical_names
            
            if has_exact_ptv:
                patients_with_exact_ptv += 1
            if ptv_names_in_clinical:
                patients_with_any_ptv += 1
                for ptv_name in ptv_names_in_clinical:
                    ptv_variations[ptv_name] = ptv_variations.get(ptv_name, 0) + 1
            limbus_set = set(limbus_names)
            clinical_set = set(clinical_names)

            # Common VOIs (order preserved from clinical, exclusions applied)
            common = [
                name for name in clinical_names
                if name in limbus_set and name.lower() not in EXCLUDED_VOIS
            ]

            # VOIs only on one side (excluding body/skin)
            only_clinical = [
                name for name in clinical_names
                if name not in limbus_set and name.lower() not in EXCLUDED_VOIS
            ]
            only_limbus = [
                name for name in limbus_names
                if name not in clinical_set and name.lower() not in EXCLUDED_VOIS
            ]

            print(f"\n  Clinical RTSTRUCT : {len(clinical_names)} ROIs  [{clinical_info['filename']}]")
            print(f"  Limbus AI RTSTRUCT: {len(limbus_names)} ROIs  [{limbus_info['filename']}]")

            print(f"\n  ✓ Common VOIs ({len(common)})  [excluded: {EXCLUDED_VOIS}]:")
            if common:
                for name in common:
                    print(f"      {name}")
            else:
                print("      (none)")

            if only_clinical:
                print(f"\n  ← Only in Clinical ({len(only_clinical)}):")
                for name in only_clinical:
                    print(f"      {name}")

            if only_limbus:
                print(f"\n  → Only in Limbus AI ({len(only_limbus)}):")
                for name in only_limbus:
                    print(f"      {name}")

            summary_rows.append({
                'patient': patient_id,
                'chain': chain_label,
                'status': 'Complete',
                'common_count': len(common)
            })

    # Print summary table
    print(f"\n\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"  {'Patient':<30} {'Chain':<10} {'Common VOIs':>12}  Status")
    print(f"  {'-'*65}")
    for row in summary_rows:
        status_str = row['status'] if row['status'] != 'Complete' else ''
        count_str = str(row['common_count']) if row['status'] == 'Complete' else '-'
        print(f"  {row['patient']:<30} {row['chain']:<10} {count_str:>12}  {status_str}")
    print(f"{'='*70}")
    
    # Print PTV variations summary
    print(f"\n\n{'='*70}")
    print("PTV VARIATIONS IN CLINICAL RTSTRUCT")
    print(f"{'='*70}")
    print(f"  Total complete chains analyzed: {total_complete_chains}")
    print(f"  Chains with exact 'PTV':        {patients_with_exact_ptv}" + (f" ({100*patients_with_exact_ptv/total_complete_chains:.1f}%)" if total_complete_chains > 0 else ""))
    print(f"  Chains with any PTV variation:  {patients_with_any_ptv}" + (f" ({100*patients_with_any_ptv/total_complete_chains:.1f}%)" if total_complete_chains > 0 else ""))
    
    # Sort by count (descending)
    sorted_ptv = sorted(ptv_variations.items(), key=lambda x: x[1], reverse=True)
    total_ptv_mentions = sum(ptv_variations.values())
    
    print(f"\n  Total PTV structure mentions:   {total_ptv_mentions}")
    print(f"  Unique PTV names found:         {len(ptv_variations)}")
    print(f"\n  {'PTV Structure Name':<40} {'Count':>8}")
    print(f"  {'-'*50}")
    
    for ptv_name, count in sorted_ptv:
        print(f"  {ptv_name:<40} {count:>8}")
    
    if not sorted_ptv:
        print("  (no PTV variations found)")
    
    print(f"  {'-'*50}")
    print(f"  {'TOTAL':<40} {total_ptv_mentions:>8}")
    print(f"{'='*70}")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == '__main__':
    # Can be a root folder (Z:\ICoNEA\DICOM) OR a single patient folder
    # (e.g. Z:\ICoNEA\DICOM\P0728xxxxxxxxxxxxxxxx)
    FOLDER = r"Z:\ICoNEA\DICOM"
    MAX_PATIENTS = 200  # Only used when FOLDER is a root folder

    if len(sys.argv) > 1:
        FOLDER = sys.argv[1]
    if len(sys.argv) > 2:
        MAX_PATIENTS = int(sys.argv[2]) if sys.argv[2].lower() != 'none' else None

    print("=" * 70)
    print("List Common VOIs — Clinical RTSTRUCT vs Limbus AI RTSTRUCT")
    print("=" * 70)
    print(f"Folder      : {FOLDER}")
    print(f"Max Patients: {MAX_PATIENTS if MAX_PATIENTS is not None else 'All (or N/A for single patient)'}")
    print("Uses chain identification from quantifycontourdifferences_P0728_v5")
    print("=" * 70)

    list_common_vois(FOLDER, MAX_PATIENTS)
