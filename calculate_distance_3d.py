"""
calculateDistance_3D - Calculate the minimum 3D distance between PTV1 and each OAR.

Uses resample_contour_slices to create binary contour images from RTSTRUCT
coordinates and the CT, then computes the Euclidean distance transform to
find the minimum distance from one contour surface to another.

For each row in the v6 results Excel, the script:
1. Loads the clinical RTSTRUCT and CT via the DICOM chain
2. Finds 'PTV1' (exact match) and the row's VOI in the clinical RTSTRUCT
3. Computes the minimum 3D distance from PTV1 to the OAR
4. Saves results to a new Excel file with '_with_dist' suffix

Translated from calculateDistance_3D.m
Jose A. Baeza & Femke Vaassen @ MAASTRO

Usage
-----
1. Set INPUT_FILE, DICOM_ROOT_FOLDER below.
2. Run:  python calculate_distance_3d.py
"""

import os
import sys
import numpy as np
import pandas as pd
import pydicom
from pathlib import Path
from typing import Optional
from scipy.ndimage import distance_transform_edt

from resample_contour_slices import resample_contour_slices
from read_dicomct_light import read_dicomct_light
from read_dicomrtstruct import read_dicomrtstruct


# ============================================================================
# CONFIGURATION
# ============================================================================

SCRIPT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
INPUT_FILE = str(SCRIPT_DIR.parent / 'contour_comparison_results_P0728_v6.xlsx')
OUTPUT_FILE = str(SCRIPT_DIR.parent / 'contour_comparison_results_P0728_v6_with_dist.xlsx')

DICOM_ROOT_FOLDER = r"Z:\ICoNEA\DICOM"

# Tumour structures to measure distance from (all found structures are used)
TUMOUR_STRUCTURES = ['PTV1', 'PTVp1_5', 'PTVp1_8', 'PTVnsum_5']


# ============================================================================
# CORE DISTANCE FUNCTION
# ============================================================================


def calculate_distance_3d(ct, struct, struct_num_1, struct_num_2):
    """
    Calculate the minimum 3D distance between two structures.

    Mirrors calculateDistance_3D.m (Jose A. Baeza & Femke Vaassen @ MAASTRO).

    The MATLAB implementation:
      1. Crops only X and Z to the combined bounding box (all Y slices kept).
      2. Applies shiftdim(..., 2): (X, Y, Z) -> (Z, X, Y).
      3. Runs bwdistsc with spacing [PixelSpacingXi, PixelSpacingZi, PixelSpacingYi].
      4. Samples the distance map at Contour2 voxels; returns the minimum.

    Here we match that logic using scipy's distance_transform_edt, with an
    additional Y-axis crop (to the combined bounding box) to avoid allocating
    the full CT-height distance array. Slices outside both structures are empty
    and do not affect the result.

    Parameters
    ----------
    ct : dict
        CT information dictionary with pixel spacing and grid info.
    struct : dict
        Structure set dictionary with 'Struct' list, each element having
        'Slice' (contour data) and 'Name'.
    struct_num_1 : int
        Index of the first structure (reference, e.g. PTV1).
    struct_num_2 : int
        Index of the second structure (e.g. OAR).

    Returns
    -------
    float
        minDist2PTV: minimum distance from structure 2 surface voxels to
        structure 1 (in cm).
    """
    contour1, minmax_oc = resample_contour_slices(
        struct['Struct'][struct_num_1]['Slice'], ct,
        struct['Struct'][struct_num_1]['Name']
    )
    contour2, minmax_nc = resample_contour_slices(
        struct['Struct'][struct_num_2]['Slice'], ct,
        struct['Struct'][struct_num_2]['Name']
    )

    # Crop X and Z to the combined bounding box (matching MATLAB).
    # Also crop Y to the combined bounding box as a memory optimisation;
    # slices outside both structures are all-zero and do not change the result.
    margin = 20
    min_x = max(0, min(minmax_oc['minX'], minmax_nc['minX']) - margin)
    max_x = min(contour1.shape[0], max(minmax_oc['maxX'], minmax_nc['maxX']) + margin)
    min_y = max(0, min(minmax_oc['minY'], minmax_nc['minY']) - margin)
    max_y = min(contour1.shape[1], max(minmax_oc['maxY'], minmax_nc['maxY']) + margin)
    min_z = max(0, min(minmax_oc['minZ'], minmax_nc['minZ']) - margin)
    max_z = min(contour1.shape[2], max(minmax_oc['maxZ'], minmax_nc['maxZ']) + margin)

    # Crop to (X_range, Y_range, Z_range) and free full-grid arrays.
    contour1_crop = contour1[min_x:max_x, min_y:max_y, min_z:max_z].astype(bool)
    contour2_crop = contour2[min_x:max_x, min_y:max_y, min_z:max_z].astype(bool)
    del contour1, contour2

    # MATLAB shiftdim(A, 2) on (X, Y, Z) -> (Z, X, Y).
    # numpy equivalent: transpose with axes (2, 0, 1).
    contour1_shifted = np.ascontiguousarray(np.transpose(contour1_crop, (2, 0, 1)))
    contour2_shifted = np.ascontiguousarray(np.transpose(contour2_crop, (2, 0, 1)))
    del contour1_crop, contour2_crop

    # spacing for axes (Z, X, Y) after the transpose, matching MATLAB's
    # bwdistsc(..., [PixelSpacingXi, PixelSpacingZi, PixelSpacingYi]).
    # (PixelSpacingXi == PixelSpacingZi for CT so the first two are interchangeable.)
    spacing_3d = [ct['PixelSpacingXi'], ct['PixelSpacingZi'], ct['PixelSpacingYi']]

    # 3D Euclidean distance transform: distance from every voxel to the nearest
    # True voxel in contour1_shifted (equivalent to MATLAB's bwdistsc).
    grtruth_dist1 = distance_transform_edt(~contour1_shifted, sampling=spacing_3d)
    del contour1_shifted

    # Sample the distance map at Contour2 surface voxels and take the minimum.
    dist1 = grtruth_dist1[contour2_shifted]
    del grtruth_dist1, contour2_shifted

    if dist1.size == 0:
        return np.inf
    return float(np.min(dist1))


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def find_structure_by_name(rtstruct: dict, name: str) -> Optional[int]:
    """Find structure index by exact name match. Returns None if not found."""
    for idx, s in enumerate(rtstruct['Struct']):
        if s.get('Name', '').strip() == name:
            return idx
    return None


def find_file_in_folder(root_folder: str, filename: str) -> Optional[str]:
    """Walk a folder tree and return the full path of the first file matching filename."""
    for dirpath, _, filenames in os.walk(root_folder):
        if filename in filenames:
            return os.path.join(dirpath, filename)
    return None


def find_ct_files_for_rtstruct(rtstruct_path: str, ct_folder: str) -> list:
    """
    Read the referenced CT Series UID from an RTSTRUCT file,
    then collect all CT .dcm files belonging to that series.

    Returns
    -------
    list of str
        Paths to CT .dcm files, or empty list on failure.
    """
    try:
        ds = pydicom.dcmread(rtstruct_path, stop_before_pixels=True)
    except Exception:
        return []

    # Extract referenced CT series UID
    ref_ct_uid = ''
    if (0x3006, 0x0010) in ds:  # ReferencedFrameOfReferenceSequence
        for frame_ref in ds[0x3006, 0x0010]:
            if (0x3006, 0x0012) in frame_ref:  # RTReferencedStudySequence
                for study_ref in frame_ref[0x3006, 0x0012]:
                    if (0x3006, 0x0014) in study_ref:  # RTReferencedSeriesSequence
                        for series_ref in study_ref[0x3006, 0x0014]:
                            uid = str(series_ref.get('SeriesInstanceUID', ''))
                            if uid:
                                ref_ct_uid = uid
                                break

    if not ref_ct_uid:
        return []

    # Collect CT files matching that series UID
    ct_files = []
    for dirpath, _, filenames in os.walk(ct_folder):
        for fn in filenames:
            if not fn.lower().endswith('.dcm'):
                continue
            fpath = os.path.join(dirpath, fn)
            try:
                ct_ds = pydicom.dcmread(fpath, stop_before_pixels=True)
                if (ct_ds.get('Modality', '') == 'CT' and
                        str(ct_ds.get('SeriesInstanceUID', '')) == ref_ct_uid):
                    ct_files.append(fpath)
            except Exception:
                pass

    return ct_files


# ============================================================================
# MAIN PROCESSING
# ============================================================================

def calculate_all_distances(input_file: str, dicom_root: str, output_file: str,
                            max_rows: Optional[int] = None):
    """
    Calculate minimum 3D PTV1-to-OAR distance for every row in the v6 dataset.

    Parameters
    ----------
    input_file : str
        Path to the v6 results Excel file.
    dicom_root : str
        Root folder containing patient DICOM subdirectories.
    output_file : str
        Path for the output Excel file.
    max_rows : int, optional
        Limit processing to this many rows (for testing).
    """
    # ------------------------------------------------------------------
    # 1. Load the full v6 dataset as the baseline
    # ------------------------------------------------------------------
    print(f"Loading dataset from: {input_file}")
    df = pd.read_excel(input_file, engine='openpyxl')
    print(f"Loaded {len(df)} rows")

    if max_rows is not None and max_rows > 0:
        df = df.head(max_rows).copy()
        print(f"Limited to first {max_rows} rows for testing")

    # ------------------------------------------------------------------
    # 1b. Initialise result columns (always recompute from scratch)
    # ------------------------------------------------------------------
    df['dist_to_ptv'] = None
    df['DistStatus'] = None

    # ------------------------------------------------------------------
    # 2. Patient folder helper (constructed directly from pNumber)
    # ------------------------------------------------------------------
    def get_patient_folder(patient_id: str) -> Optional[str]:
        folder = os.path.join(dicom_root, patient_id)
        return folder if os.path.isdir(folder) else None

    # ------------------------------------------------------------------
    # 3. Process rows grouped by (pNumber, Clinical_RTSTRUCT)
    # ------------------------------------------------------------------
    total_rows = len(df)
    processed = 0
    errors = 0
    no_ptv = 0

    # Helper: derive next versioned filename (e.g. output_v1.xlsx, output_v2.xlsx, ...)
    output_path = Path(output_file)
    stem = output_path.stem   # e.g. 'contour_comparison_results_P0728_v6_with_dist'
    suffix = output_path.suffix  # '.xlsx'
    parent = output_path.parent

    def next_versioned_file() -> str:
        """Return the next *_snap_vN.xlsx path that does not exist yet."""
        v = 1
        while True:
            candidate = parent / f"{stem}_snap_v{v}{suffix}"
            if not candidate.exists():
                return str(candidate)
            v += 1

    save_version = 0  # tracks how many intermediate saves have been done

    # Collect pending rows and group them by (pNumber, Clinical_RTSTRUCT) so
    # each CT + RTSTRUCT is loaded exactly once, then freed before the next group.
    pending_mask = (
        df['dist_to_ptv'].isna()
        & (df.get('ChainStatus') == 'Complete')
        & df.get('VOIName').notna()
        & (df.get('VOIName') != 'N/A')
        & df.get('Clinical_RTSTRUCT').notna()
        & (df.get('Clinical_RTSTRUCT') != 'N/A')
    )
    pending_df = df[pending_mask]
    pending_count = len(pending_df)
    print(f"{pending_count} rows pending processing")

    groups = pending_df.groupby(['pNumber', 'Clinical_RTSTRUCT'], sort=False)
    n_groups = len(groups)
    group_num = 0

    for (patient_id, clinical_rtstruct_file), group in groups:
        group_num += 1
        group_indices = group.index.tolist()
        print(f"  Group {group_num}/{n_groups}: {patient_id} | {clinical_rtstruct_file} "
              f"({len(group_indices)} rows)")

        rtstruct = None
        ct = None

        try:
            # --- Patient folder ---
            patient_folder = get_patient_folder(patient_id)
            if not patient_folder:
                for idx in group_indices:
                    df.at[idx, 'DistStatus'] = 'Error: Patient folder not found'
                errors += len(group_indices)
                continue

            # --- Load RTSTRUCT ---
            rtstruct_folder = os.path.join(patient_folder, 'RTSTRUCT')
            rtstruct_path = find_file_in_folder(rtstruct_folder, clinical_rtstruct_file)
            if not rtstruct_path:
                print(f"    {patient_id}: RTSTRUCT file not found: {clinical_rtstruct_file}")
                for idx in group_indices:
                    df.at[idx, 'DistStatus'] = 'Error: RTSTRUCT file not found on disk'
                errors += len(group_indices)
                continue
            rtstruct = read_dicomrtstruct(rtstruct_path, verbose=False)

            # --- Find tumour structures once for the whole group ---
            tumour_indices = {}
            for tname in TUMOUR_STRUCTURES:
                tidx = find_structure_by_name(rtstruct, tname)
                if tidx is not None:
                    tumour_indices[tname] = tidx

            if not tumour_indices:
                avail = [s.get('Name', '') for s in rtstruct['Struct']]
                ptv_like = [n for n in avail if 'ptv' in n.lower()]
                print(f"    {patient_id}: No tumour structures found. PTV-like: {ptv_like}")
                for idx in group_indices:
                    df.at[idx, 'dist_to_ptv'] = -1
                    df.at[idx, 'DistStatus'] = 'No tumour structures found in RTSTRUCT'
                no_ptv += len(group_indices)
                continue
            else:
                print(f"    {patient_id}: found tumour structure(s): {list(tumour_indices.keys())}")

            # --- Load CT once for the whole group ---
            ct_folder = os.path.join(patient_folder, 'CT')
            ct_files = find_ct_files_for_rtstruct(rtstruct_path, ct_folder)
            if not ct_files:
                print(f"    {patient_id}: No CT files found for {clinical_rtstruct_file}")
                for idx in group_indices:
                    df.at[idx, 'DistStatus'] = 'Error: No CT files found for RTSTRUCT'
                errors += len(group_indices)
                continue
            ct = read_dicomct_light(ct_files)

            # --- Process each row (VOI) in the group ---
            for idx in group_indices:
                voi_name = df.at[idx, 'VOIName']
                processed += 1

                try:
                    # Find the OAR structure index
                    oar_idx = find_structure_by_name(rtstruct, voi_name)

                    # Compute distance from VOI to each found tumour structure
                    row_dists = {}
                    for tname, tidx in tumour_indices.items():
                        if voi_name == tname:
                            row_dists[tname] = 0.0  # VOI is this tumour — distance = 0
                        elif oar_idx is not None:
                            row_dists[tname] = calculate_distance_3d(ct, rtstruct, tidx, oar_idx)

                    if not row_dists:
                        df.at[idx, 'DistStatus'] = f'Error: VOI "{voi_name}" not found in RTSTRUCT'
                        errors += 1
                        continue

                    df.at[idx, 'dist_to_ptv'] = round(min(row_dists.values()), 2)
                    df.at[idx, 'DistStatus'] = 'OK'

                except Exception as e:
                    print(f"    Error row {idx} ({patient_id}, {voi_name}): {e}")
                    df.at[idx, 'DistStatus'] = f'Error: {e}'
                    errors += 1

        except Exception as e:
            print(f"  Error group ({patient_id}, {clinical_rtstruct_file}): {e}")
            for idx in group_indices:
                if pd.isna(df.at[idx, 'DistStatus']):
                    df.at[idx, 'DistStatus'] = f'Error: {e}'
            errors += len(group_indices)

        finally:
            # Explicitly free CT and RTSTRUCT memory before loading the next group
            del ct, rtstruct

        # Intermediate save every 500 processed rows (new versioned file each time)
        if processed > 0 and processed % 500 == 0:
            snap_path = next_versioned_file()
            save_version += 1
            print(f"  ** Intermediate save (snap_v{save_version}) at {processed} processed rows -> {snap_path} **")
            df.to_excel(snap_path, index=False, engine='openpyxl')

    # ------------------------------------------------------------------
    # 5. Save results
    # ------------------------------------------------------------------
    df.to_excel(output_file, index=False, engine='openpyxl')

    valid = df['dist_to_ptv'].dropna()
    valid = valid[valid >= 0]

    print(f"\n{'='*70}")
    print("RESULTS")
    print(f"{'='*70}")
    already_done = total_rows - pending_count
    print(f"Total rows:                    {total_rows}")
    print(f"Skipped (already calculated):  {already_done}")
    print(f"Processed this run:            {processed}")
    print(f"Valid distances:               {len(valid)}")
    print(f"No tumour structure found (-1):{no_ptv}")
    print(f"Errors:                        {errors}")
    if len(valid) > 0:
        print(f"\nDistance stats (cm):")
        print(f"  Mean:   {valid.mean():.2f}")
        print(f"  Median: {valid.median():.2f}")
        print(f"  Min:    {valid.min():.2f}")
        print(f"  Max:    {valid.max():.2f}")
        std_val = valid.std() if len(valid) > 1 else float('nan')
        print(f"  Std:    {std_val:.2f}" if not np.isnan(std_val) else "  Std:    N/A (only 1 value)")
    print(f"\nOutput saved to: {output_file}")
    print(f"{'='*70}")

    return df


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    dicom_root = DICOM_ROOT_FOLDER
    max_rows = None  # Set to an integer for testing with a limited number of rows

    if len(sys.argv) > 1:
        dicom_root = sys.argv[1]
    if len(sys.argv) > 2:
        max_rows = int(sys.argv[2]) if sys.argv[2].lower() != 'none' else None

    print("=" * 70)
    print("Calculate Minimum 3D Distance: PTV1 -> OAR")
    print("=" * 70)
    print(f"Input file:  {INPUT_FILE}")
    print(f"Output file: {OUTPUT_FILE}")
    print(f"DICOM root:  {dicom_root}")
    print(f"Tumour structures: {TUMOUR_STRUCTURES}")
    print(f"Max rows:    {max_rows if max_rows else 'All'}")
    print("=" * 70)

    calculate_all_distances(INPUT_FILE, dicom_root, OUTPUT_FILE, max_rows)
