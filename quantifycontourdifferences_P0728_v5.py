"""
quantifycontourdifferences_P0728_v5 - Automated contour comparison using DICOM chain identification

This script automatically fetches the correct data from all patients in the dataset
using the DICOM chain identification method:
1. Find all approved RTPLANs in patient folder
2. For each approved RTPLAN → find referenced clinical ARIA RTSTRUCT (via SOP Instance UID)
3. From clinical RTSTRUCT → find CT series (Frame of Reference + CT Series UID match)
4. From clinical RTSTRUCT → find Limbus AI RTSTRUCT:
   a. Process from StudyDate: after 17-11-2025 the new (script) process, otherwise the old one
   b. Candidates on the same CT (Frame of Reference + CT Series UID)
   c. 'Limbus RTS Pall' on this CT → chain excluded (palliative)
   d. New process: R1 Label 'Limbus RTStruct' + StructureSetName == CT SeriesDescription (the
      unedited Limbus output); R2 clinical StructureSetName == CT SeriesDescription?
        yes: edited Limbus import → script copy first, then closest SeriesDate/Time
        no (empty / own label): made by hand in ARIA → closest SeriesDate/Time
      old process: select among 'Limbus RTStruct' candidates (metadata only, no contour similarity)
5. Find RTDOSE, compare clinical ARIA RTSTRUCT with Limbus AI RTSTRUCT
Output: StatusCategory per chain (proper / no script use / RayStation / excluded / failed) and
Status notes (origin of the clinical set, time gaps, several Limbus sets, saved after approval)

v6 Changes:
- Old/new process decided by StudyDate (cutoff 17-11-2025). New process: the Limbus set is the
  ARIA copy made by the script, the clinical set is the imported original
- Palliative chains ('Limbus RTS Pall') are excluded per chain
- New output columns: StudyDate, Process, ScriptFootprint, Limbus_MatchMethod,
  Clinical_RTSTRUCT_Source (Manufacturer / model of the clinical set, e.g. RayStation)
- RTSTRUCT Frame of Reference falls back to ReferencedFrameOfReferenceSequence;
  the first referenced CT series is used
- Several Limbus candidates in a tier: SeriesDate/Time closest to the clinical set wins
  (was: earliest). New column Limbus_SeriesGap_h = Limbus minus clinical, in hours
- Limbus sets exported at a later stage carry SeriesDescription 'Limbus RTSS v1.8.3-B1';
  accepted next to 'Limbus RTSS v1.8.0' (SD_LIMBUS_IMPORTS)

v5 Changes:
- IMPROVED Limbus identification: First match by geometry (Frame of Reference + CT Series UID),
  then verify metadata (SeriesDescription + StructureSetLabel)
- This ensures we find the Limbus RTSTRUCT that references the SAME CT as the clinical RTSTRUCT
- Avoids false positives from Limbus files referencing different CT scans

v3/v4 Changes (inherited):
- compose_struct_matrix_filtered() - Only composes COMMON structures
- Avoids 64-structure limit by only processing structures needed for comparison
- Limbus detection uses SeriesDescription + StructureSetLabel (not ManufacturerModelName)

Folder structure:
DICOM -> Pxxxxxxxxxxxxxxxx -> CT/RTDOSE/RTPLAN/RTSTRUCT (folders) -> yyyymmdd -> .dcm files

History
-------
Created for P0728 dataset analysis
v2: Refactored to use new DICOM chain identification
v3: Optimized to only compose common structures (avoids 64-struct limit)
v4: Fixed Limbus detection using SeriesDescription + StructureSetLabel
v5: Match by geometry first, then verify Limbus metadata
v6: Old/new process by StudyDate, palliative exclusion, selection columns in output
"""

import os
import sys
import warnings
import random
import pydicom
import pandas as pd
import numpy as np
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Tuple, Optional
from skimage.draw import polygon

from read_dicomct_light import read_dicomct_light
from read_dicomrtstruct import read_dicomrtstruct
from read_dicomrtplan import read_dicomrtplan
from calculate_dice_logical import calculate_dice_logical
from calculate_surface_dsc import calculate_surface_dsc
from calculate_path_length import calculate_path_length
from has_contour_points_local import has_contour_points_local
from calculate_dvh_parameters import read_rtdose, find_matching_rtdose, calculate_dvh_parameters
from calculate_distance_3d import calculate_distance_3d, find_structure_by_name, TUMOUR_STRUCTURES


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
        
    Example
    -------
    If structure_indices = [5, 12, 23] (3 structures):
    - Structure at index 5 gets bit position 0 (value 2^0 = 1)
    - Structure at index 12 gets bit position 1 (value 2^1 = 2)
    - Structure at index 23 gets bit position 2 (value 2^2 = 4)
    
    To check with calculate_dice_logical, use the 1-indexed position in the list:
    - calculate_dice_logical(voi1, voi2, 1, 1) for first structure in list
    - calculate_dice_logical(voi1, voi2, 2, 2) for second structure in list
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
# LIMBUS SELECTION (v6 - OLD/NEW PROCESS BY STUDY DATE)
# ============================================================================

# Studies after this date follow the new process: a script copies the imported Limbus
# set (copy = 'Limbus RTStruct', new ARIA series) and the imported original becomes the
# clinical set (relabelled <date><modality><meta>). Up to and including this date the
# imported original itself is the Limbus set and the clinical set is a separate set.
PROCESS_CUTOFF_DATE = '20251117'
LIMBUS_LABEL = 'Limbus RTStruct'
LIMBUS_PALLIATIVE_LABEL = 'Limbus RTS Pall'
# SeriesDescriptions written by Limbus; v1.8.3-B1 for Limbus sets exported at a later stage
SD_LIMBUS_IMPORTS = ('Limbus RTSS v1.8.0', 'Limbus RTSS v1.8.3-B1')
SD_ARIA_COPY = 'ARIA RadOnc Structure Sets'      # SeriesDescription of a set copied in ARIA
LIMBUS_DESCRIPTION = 'Limbus Contour'            # StructureSetDescription (3006,0006) written by Limbus
SD_RAYSTATION = 'RS: Approved Structure Set'     # SeriesDescription of a RayStation export (proton plans)
SD_CONTOURING = 'Contouring'                     # SeriesDescription of a set made in ARIA Contouring
MAX_SERIES_GAP_H = 24                            # larger Limbus-clinical SeriesDate/Time gap is noted in Status
MAX_CLINICAL_AFTER_APPROVAL_DAYS = 7             # clinical set saved later than this after plan approval is noted
# R1 also requires the Limbus StructureSetName (3006,0004) to equal the CT SeriesDescription
# (0008,103E), as Limbus writes it. Excludes hand-made sets that carry the Limbus label.
REQUIRE_LIMBUS_NAME_IS_CT = True


def clinical_from_limbus_import(clinical_rtstruct: dict, ct_series: Optional[dict]) -> bool:
    """
    R2: the clinical set is the edited Limbus import. Limbus names the set after the CT,
    so its StructureSetName (3006,0004) equals the CT SeriesDescription (0008,103E).
    An empty or other name (e.g. its own label '20251126CT') means a set made in ARIA.
    """
    name = clinical_rtstruct['structure_set_name'].strip()
    return bool(name) and name == (ct_series or {}).get('series_description', '').strip()


def clinical_origin_note(clinical_rtstruct: dict, ct_series: Optional[dict], process: str) -> Optional[str]:
    """
    Status note when the clinical set was not made by editing the Limbus import:
    a RayStation export, or a set made by hand in ARIA (new process: not from the import
    by R2; old process: SeriesDescription 'Contouring'). None for the expected workflow.
    """
    if clinical_rtstruct['series_description'] == SD_RAYSTATION:
        return 'Note: clinical set from RayStation'
    if process == 'new' and not clinical_from_limbus_import(clinical_rtstruct, ct_series):
        return (f"Note: clinical set made by hand in ARIA, not from Limbus import "
                f"(SD '{clinical_rtstruct['series_description']}')")
    if process == 'old' and clinical_rtstruct['series_description'] == SD_CONTOURING:
        return "Note: clinical set made by hand in ARIA (SD 'Contouring')"
    return None


def clinical_after_approval_note(clinical_rtstruct: dict, rtplan: dict) -> Optional[str]:
    """
    Status note when the clinical SeriesDate/Time is more than MAX_CLINICAL_AFTER_APPROVAL_DAYS
    after the plan's approval (ReviewDate, else RTPlanDate): the set was saved again after
    approval and may differ from the approved version.
    """
    clinical_dt = series_datetime(clinical_rtstruct)
    approval_dt = series_datetime({'series_date': rtplan.get('approval_date', ''),
                                   'series_time': rtplan.get('approval_time', '')})
    if clinical_dt is None or approval_dt is None:
        return None
    days = (clinical_dt - approval_dt).total_seconds() / 86400
    if days <= MAX_CLINICAL_AFTER_APPROVAL_DAYS:
        return None
    return f'Note: clinical set saved {days:.0f} days after plan approval (may differ from approved version)'


def add_chain_note(chain: dict, note: Optional[str]):
    """Append note to the chain's Status notes."""
    if note:
        chain['chain_note'] = '; '.join(filter(None, [chain.get('chain_note'), note]))


def with_chain_note(status: str, chain: dict) -> str:
    """status, followed by the chain's notes if it has any."""
    return f"{status}; {chain['chain_note']}" if chain.get('chain_note') else status


def status_category(chain: dict) -> str:
    """One category per chain, for counting: proper / no script use / RayStation / excluded / failed."""
    clinical, limbus = chain.get('clinical_rtstruct'), chain.get('limbus_ai_rtstruct')
    raystation = bool(clinical) and clinical['series_description'] == SD_RAYSTATION
    if not chain.get('chain_complete'):
        if chain['chain_status'].startswith('Excluded'):
            return 'Excluded: palliative'
        if raystation:
            return 'RayStation: failed'
        if limbus is None and chain.get('limbus_match_method'):
            return f"Failed: {chain['limbus_match_method']}"
        return f"Failed: {chain['chain_status']}"
    if raystation:
        return 'RayStation clinical set'
    if chain['process'] == 'new':
        if not clinical_from_limbus_import(clinical, chain['ct_series']):
            return 'New: clinical set made by hand in ARIA'
        if limbus['series_description'] == SD_ARIA_COPY:
            return 'New: proper (script copy)'
        return 'New: no script copy used'
    if chain['process'] == 'old':
        return 'Old: proper (original import)' if chain['limbus_match_method'].startswith('original import') \
            else 'Old: label only'
    return 'Unknown process'


def description_matches(rtstruct: dict) -> bool:
    """StructureSetDescription (3006,0006) is the one Limbus writes."""
    return rtstruct['structure_set_description'].strip() == LIMBUS_DESCRIPTION


def name_matches(rtstruct: dict, ct_series: Optional[dict], clinical_rtstruct: dict,
                 process: str) -> bool:
    """
    StructureSetName (3006,0004) check. New process: equals the clinical set's
    StructureSetName (the clinical set is the edited Limbus import and keeps its name).
    Otherwise: equals the CT's SeriesDescription (Limbus names the set after the CT;
    old-process clinical sets have no StructureSetName). False if either value is empty.
    """
    name = rtstruct['structure_set_name'].strip()
    if process == 'new':
        reference = clinical_rtstruct['structure_set_name'].strip()
    else:
        reference = (ct_series or {}).get('series_description', '').strip()
    return bool(name) and name == reference


def determine_process(clinical_rtstruct: dict, ct_series: dict) -> Tuple[str, str]:
    """
    Return (study_date, process) for a chain.

    StudyDate is taken from the clinical RTSTRUCT, falling back to the CT series.
    process is 'new' if StudyDate > PROCESS_CUTOFF_DATE, 'old' otherwise, and
    'unknown' if no StudyDate is available.
    """
    study_date = clinical_rtstruct.get('study_date') or (ct_series or {}).get('study_date', '')
    if not study_date:
        return '', 'unknown'
    return study_date, 'new' if study_date > PROCESS_CUTOFF_DATE else 'old'


def determine_script_footprint(process: str, clinical_rtstruct: dict, candidates: List[Dict]) -> str:
    """
    Report whether the new-process script left its footprint on this CT.

    present : a Limbus copy in a new ARIA series exists on the same CT and the clinical
              set is the imported original (a SeriesDescription in SD_LIMBUS_IMPORTS)
    present (clinical set is not the imported original) : the copy exists, but the clinical
              set referenced by the plan was made separately (e.g. a later re-plan set)
    missing : new process by date, but no Limbus copy in an ARIA series on this CT
    n/a (old process) / n/a (unknown process)
    """
    if process != 'new':
        return f'n/a ({process} process)'
    copy_present = any(
        c['structure_set_label'] in (LIMBUS_LABEL, LIMBUS_PALLIATIVE_LABEL)
        and c['series_description'] == SD_ARIA_COPY
        for c in candidates
    )
    if not copy_present:
        return 'missing'
    if clinical_rtstruct['series_description'] in SD_LIMBUS_IMPORTS:
        return 'present'
    return 'present (clinical set is not the imported original)'


def series_datetime(rtstruct: dict) -> Optional[datetime]:
    """SeriesDate + SeriesTime of an RTSTRUCT as a datetime, or None if SeriesDate is missing."""
    date = rtstruct.get('series_date', '').strip()
    time = rtstruct.get('series_time', '').strip().replace(':', '').split('.')[0]
    try:
        return datetime.strptime(date + (time + '000000')[:6], '%Y%m%d%H%M%S')
    except ValueError:
        return None


def series_gap_hours(limbus_rtstruct: dict, clinical_rtstruct: dict) -> Optional[float]:
    """Limbus minus clinical SeriesDate/Time in hours (positive = Limbus series is later)."""
    limbus_dt = series_datetime(limbus_rtstruct)
    clinical_dt = series_datetime(clinical_rtstruct)
    if limbus_dt is None or clinical_dt is None:
        return None
    return round((limbus_dt - clinical_dt).total_seconds() / 3600, 2)


def series_gap_note(gap_hours: Optional[float]) -> Optional[str]:
    """Status note when the Limbus and clinical SeriesDate/Time are more than MAX_SERIES_GAP_H apart."""
    if gap_hours is None or abs(gap_hours) <= MAX_SERIES_GAP_H:
        return None
    side = 'earlier' if gap_hours < 0 else 'later'
    return f'Note: Limbus set {abs(gap_hours) / 24:.1f} days {side} than clinical set (> 1 day)'


def sort_closest_to_clinical(matches: List[Dict], clinical_rtstruct: dict) -> str:
    """
    Sort matches in place: SeriesDate/Time closest to the clinical set first, or earliest
    first if the clinical set has no SeriesDate. Returns the ordering used, for match_method.
    """
    # Earliest first, so equally close candidates resolve to the earlier series
    matches.sort(key=lambda c: (c['series_date'], c['series_time']))
    if series_datetime(clinical_rtstruct) is None:
        return 'earliest SeriesDate/Time'
    # Candidates without a SeriesDate sort last
    matches.sort(key=lambda c: abs(series_gap_hours(c, clinical_rtstruct))
                 if series_datetime(c) is not None else float('inf'))
    return 'closest SeriesDate/Time to clinical'


def limbus_name_is_ct(rtstruct: dict, ct_series: Optional[dict]) -> bool:
    """StructureSetName (3006,0004) equals the CT SeriesDescription, as Limbus writes it.
    True when the CT has no SeriesDescription (nothing to compare)."""
    ct_name = (ct_series or {}).get('series_description', '').strip()
    return not ct_name or rtstruct['structure_set_name'].strip() == ct_name


def select_limbus_new_process(labelled: List[Dict], clinical_rtstruct: dict,
                              ct_series: Optional[dict]) -> Tuple[Optional[Dict], str]:
    """
    New process. labelled holds the R1 sets on this CT: StructureSetLabel (3006,0002)
    'Limbus RTStruct' and (REQUIRE_LIMBUS_NAME_IS_CT) StructureSetName == CT SeriesDescription.
    R1 selects the unedited Limbus output; the edited import is relabelled and drops out.

    R2 classifies the clinical set (clinical_from_limbus_import), it does not filter:
    every R1 set carries the CT name.
      edited Limbus import : several R1 sets → script copy first, then closest SeriesDate/Time
      made by hand in ARIA : the R1 set with the SeriesDate/Time closest to the clinical set
    """
    if not labelled:
        return None, 'no Limbus RTStruct label'
    matches = list(labelled)
    order = sort_closest_to_clinical(matches, clinical_rtstruct)
    if not clinical_from_limbus_import(clinical_rtstruct, ct_series):
        method = f'label + {order} (clinical set not from Limbus import)'
        if len(matches) > 1:
            method += f' ({len(matches)} candidates)'
        return matches[0], method

    method = 'label + name (edited Limbus import)'
    if len(matches) > 1:
        matches.sort(key=lambda c: c['series_description'] != SD_ARIA_COPY)  # stable
        method += f' (ambiguous: {len(matches)} candidates, script copy first, then {order})'
    return matches[0], method


def limbus_r1_candidates(candidates: List[Dict], ct_series: Optional[dict]) -> List[Dict]:
    """R1 sets: Label 'Limbus RTStruct' and (REQUIRE_LIMBUS_NAME_IS_CT) named after the CT."""
    return [c for c in candidates if c['structure_set_label'] == LIMBUS_LABEL
            and (not REQUIRE_LIMBUS_NAME_IS_CT or limbus_name_is_ct(c, ct_series))]


def select_limbus_rtstruct(candidates: List[Dict], process: str,
                           clinical_rtstruct: dict,
                           ct_series: Optional[dict] = None) -> Tuple[Optional[Dict], str]:
    """
    Select the Limbus RTSTRUCT on which the clinical RTSTRUCT was based.

    Selection uses metadata only (never contour similarity, which would bias the
    AI-vs-clinical comparison). candidates are the other RTSTRUCTs on the same CT.

    New process: R1 (label + CT name) and R2 (clinical origin), see select_limbus_new_process.
    Old / unknown process: tiers by SeriesDescription among the labelled sets; when several
    match a tier, candidates whose StructureSetDescription (3006,0006) and StructureSetName
    (3006,0004) match go first, then the SeriesDate/Time closest to the clinical set.

    Returns
    -------
    (limbus_rtstruct or None, match_method)
        match_method describes how the set was chosen, or why none was:
        - 'Excluded: palliative'      a 'Limbus RTS Pall' set exists on this CT
        - 'label + name (edited Limbus import)'
                                      new process: clinical set is the edited Limbus import
        - 'label + closest SeriesDate/Time to clinical (clinical set not from Limbus import)'
                                      new process: clinical set made in ARIA, paired on time
        - 'no Limbus RTStruct with CT name'
                                      new process: labelled sets exist, none named after the CT
        - 'original import'           old process: label + Limbus SeriesDescription
        - 'label only'                old process: only the label matched
        - ' (ambiguous: n candidates, ...)' appended when several match
        - 'no Limbus RTStruct label'  no candidate carries the Limbus label
    """
    if any(c['structure_set_label'] == LIMBUS_PALLIATIVE_LABEL for c in candidates):
        return None, 'Excluded: palliative'

    labelled = [c for c in candidates if c['structure_set_label'] == LIMBUS_LABEL]
    if process == 'new':
        r1 = limbus_r1_candidates(candidates, ct_series)
        if labelled and not r1:
            return None, 'no Limbus RTStruct with CT name'
        return select_limbus_new_process(r1, clinical_rtstruct, ct_series)
    if not labelled:
        return None, 'no Limbus RTStruct label'

    tiers = [('original import', lambda c: c['series_description'] in SD_LIMBUS_IMPORTS),
             ('label only', lambda c: True)]

    for method, condition in tiers:
        matches = [c for c in labelled if condition(c)]
        if not matches:
            continue
        if len(matches) > 1:
            method += f' (ambiguous: {len(matches)} candidates, {sort_closest_to_clinical(matches, clinical_rtstruct)})'
            # Stable sort: Description and Name matches first, time order kept among equals
            matches.sort(key=lambda c: (not description_matches(c),
                                        not name_matches(c, ct_series, clinical_rtstruct, process)))
        return matches[0], method

    return None, 'no Limbus RTStruct label'  # not reached: 'label only' accepts every labelled set


# ============================================================================
# DICOM CHAIN IDENTIFICATION FUNCTIONS (v5 - Updated)
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
                # Approval moment: ReviewDate/Time (300E,0004/0005), else RTPlanDate/Time
                'approval_date': str(ds.get('ReviewDate', '') or ds.get('RTPlanDate', '')),
                'approval_time': str(ds.get('ReviewTime', '') if ds.get('ReviewDate', '')
                                     else ds.get('RTPlanTime', '')),
                'referenced_rtstruct_sop_uid': ref_rtstruct_sop_uid
            }
            
            all_rtplans.append(rtplan_info)
            
            if approval_status == 'APPROVED':
                approved_rtplans.append(rtplan_info)
                
        except Exception as e:
            pass
    
    return all_rtplans, approved_rtplans


def scan_rtstruct_files(patient_folder: str) -> List[Dict]:
    """
    Scan patient folder for all RTSTRUCT files.
    
    v5: Returns ALL RTSTRUCTs with metadata. Limbus verification is done separately
    during chain matching (geometry first, then verify metadata).
    
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

                    # Extract the first referenced CT series UID (and its Frame of Reference)
                    # from ReferencedFrameOfReferenceSequence
                    referenced_ct_series_uid = ''
                    sequence_frame_ref_uid = ''
                    for frame_ref in ds.get('ReferencedFrameOfReferenceSequence', []):  # (3006,0010)
                        sequence_frame_ref_uid = sequence_frame_ref_uid or str(frame_ref.get('FrameOfReferenceUID', ''))
                        for study_ref in frame_ref.get('RTReferencedStudySequence', []):  # (3006,0012)
                            for series_ref in study_ref.get('RTReferencedSeriesSequence', []):  # (3006,0014)
                                referenced_ct_series_uid = (referenced_ct_series_uid
                                                            or str(series_ref.get('SeriesInstanceUID', '')))

                    # The top-level FrameOfReferenceUID is optional in an RT Structure Set;
                    # fall back to the one in ReferencedFrameOfReferenceSequence
                    frame_ref_uid = frame_ref_uid or sequence_frame_ref_uid

                    info = {
                        'path': filepath,
                        'filename': os.path.basename(filepath),
                        'model_name': model_name,  # kept for backward compatibility
                        'manufacturer_model': model_name,  # consistent with check_metadata.py
                        'manufacturer': manufacturer,
                        'sop_instance_uid': sop_uid,
                        'series_instance_uid': series_uid,
                        'frame_of_reference_uid': frame_ref_uid,
                        'referenced_ct_series_uid': referenced_ct_series_uid,
                        'structure_set_label': struct_label,
                        'structure_set_name': str(ds.get('StructureSetName', '')),
                        'structure_set_description': str(ds.get('StructureSetDescription', '')),
                        'series_description': series_desc,
                        'study_date': str(ds.get('StudyDate', '')),
                        'series_date': str(ds.get('SeriesDate', '')),
                        'series_time': str(ds.get('SeriesTime', ''))
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
                                'series_description': series_desc,  # consistent with check_metadata.py
                                'study_date': str(ds.get('StudyDate', '')),
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
    
    Chain: Approved RTPLAN → Clinical RTSTRUCT → CT Series → Limbus AI RTSTRUCT → RTDOSE

    v6 Limbus Identification (metadata only, see select_limbus_rtstruct):
    1. Process from StudyDate: > PROCESS_CUTOFF_DATE is the new process, otherwise old
    2. Candidates: RTSTRUCTs matching Frame of Reference + CT Series UID of the clinical set
    3. A 'Limbus RTS Pall' candidate excludes the chain (palliative)
    4. New process: R1 Label 'Limbus RTStruct' and StructureSetName (3006,0004) == CT
                    SeriesDescription (0008,103E); R2 clinical StructureSetName == CT
                    SeriesDescription → edited import: script copy first, then closest
                    SeriesDate/Time; otherwise made by hand in ARIA (or RayStation):
                    closest SeriesDate/Time
       Status notes: RayStation, made by hand in ARIA, saved after plan approval,
                    several Limbus sets, Limbus-clinical gap > 1 day, no RTDOSE
       Old process: among 'Limbus RTStruct' candidates the original Limbus import, else any
                    ('label only'); several in a tier: SeriesDate/Time closest to the clinical set's

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
        - study_date, process: StudyDate and 'old' / 'new' / 'unknown'
        - script_footprint: 'present' / 'missing' / 'n/a (... process)'
        - limbus_match_method: how the Limbus set was selected (or why not)
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
    
    # Step 2: Scan all RTSTRUCT files (v5: get ALL, verify Limbus later)
    all_rtstructs = scan_rtstruct_files(patient_folder)
    
    if verbose:
        print(f"    Found {len(all_rtstructs)} RTSTRUCT(s)")
    
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
            'rtdose_path': None,
            'rtdose_status': '',
            'study_date': '',
            'process': '',
            'script_footprint': '',
            'limbus_match_method': '',
            'limbus_series_gap_h': None,
            'chain_note': None,
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
        
        # ====================================================================
        # v6: Find Limbus AI RTSTRUCT - SAME CT, THEN SELECT BY PROCESS
        # ====================================================================
        study_date, process = determine_process(clinical_rtstruct, matched_ct)
        chain['study_date'] = study_date
        chain['process'] = process
        add_chain_note(chain, clinical_origin_note(clinical_rtstruct, matched_ct, process))
        add_chain_note(chain, clinical_after_approval_note(clinical_rtstruct, rtplan))

        if verbose:
            print(f"      → StudyDate {study_date or '-'} → {process.upper()} process")
            if chain['chain_note']:
                print(f"      → {chain['chain_note']}")

        # Find RTSTRUCTs matching Frame of Reference + CT Series UID
        geometry_matched_candidates = []
        for rtstruct in all_rtstructs:
            # Skip the clinical RTSTRUCT itself
            if rtstruct['sop_instance_uid'] == clinical_rtstruct['sop_instance_uid']:
                continue
                
            frame_match = rtstruct['frame_of_reference_uid'] == clinical_rtstruct['frame_of_reference_uid']
            series_match = rtstruct['referenced_ct_series_uid'] == clinical_rtstruct['referenced_ct_series_uid']
            
            if frame_match and series_match:
                geometry_matched_candidates.append(rtstruct)
        
        if verbose:
            print(f"      → Found {len(geometry_matched_candidates)} RTSTRUCT(s) matching same CT")
        
        chain['script_footprint'] = determine_script_footprint(
            process, clinical_rtstruct, geometry_matched_candidates)

        # Select the Limbus set by metadata (never by contour similarity)
        matched_limbus, match_method = select_limbus_rtstruct(
            geometry_matched_candidates, process, clinical_rtstruct, matched_ct)
        chain['limbus_match_method'] = match_method
        n_limbus = len(limbus_r1_candidates(geometry_matched_candidates, matched_ct) if process == 'new'
                       else [c for c in geometry_matched_candidates if c['structure_set_label'] == LIMBUS_LABEL])
        if n_limbus > 1 and match_method != 'Excluded: palliative':
            add_chain_note(chain, f'Note: {n_limbus} Limbus RTStruct sets on this CT')

        if verbose:
            print(f"      → Script footprint: {chain['script_footprint']}")
            for candidate in geometry_matched_candidates:
                print(f"        - {candidate['filename']}: Label '{candidate['structure_set_label']}', "
                      f"SeriesDescription '{candidate['series_description']}'")

        if match_method == 'Excluded: palliative':
            chain['chain_status'] = 'Excluded: palliative'
            if verbose:
                print(f"      ✗ Palliative ('{LIMBUS_PALLIATIVE_LABEL}' on this CT) — chain excluded")
            chains.append(chain)
            continue

        if not matched_limbus:
            chain['chain_status'] = f'Limbus AI RTSTRUCT not found ({match_method})'
            if verbose:
                print(f"      ✗ No Limbus AI RTSTRUCT found ({match_method})")
            chains.append(chain)
            continue

        if verbose:
            print(f"      ✓ Limbus AI: {matched_limbus['filename']} [{match_method}]")

        chain['limbus_ai_rtstruct'] = matched_limbus
        chain['limbus_series_gap_h'] = series_gap_hours(matched_limbus, clinical_rtstruct)
        add_chain_note(chain, series_gap_note(chain['limbus_series_gap_h']))
        chain['limbus_description_match'] = description_matches(matched_limbus)
        chain['limbus_name_match'] = name_matches(matched_limbus, matched_ct, clinical_rtstruct, process)
        chain['chain_complete'] = True
        chain['chain_status'] = 'Complete'

        # Find matching RTDOSE for this chain
        # Uses: CT Frame of Reference UID + approved RTPLAN SOP Instance UID
        rtdose_path, rtdose_status = find_matching_rtdose(
            patient_folder,
            rtplan['sop_instance_uid'],
            matched_ct['frame_ref_uid']
        )
        chain['rtdose_path'] = rtdose_path
        chain['rtdose_status'] = rtdose_status
        if not rtdose_path:
            add_chain_note(chain, 'Note: no matching RTDOSE')

        if verbose:
            if rtdose_path:
                print(f"      ✓ RTDOSE: {os.path.basename(rtdose_path)} [{rtdose_status}]")
            else:
                print(f"      ⚠ No matching RTDOSE found — dose metrics will be skipped")
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


def extract_folder_date(filepath: str) -> Optional[str]:
    """
    Extract the date from the folder containing a DICOM file.

    Assumes folder structure: .../yyyymmdd/file.dcm
    Returns the immediate parent folder name (expected to be a date string),
    or None if filepath is None or empty.
    """
    if not filepath:
        return None
    return os.path.basename(os.path.dirname(filepath))


def chain_selection_columns(chain: dict) -> Dict[str, str]:
    """Result columns describing how the chain's process and Limbus set were determined."""
    clinical, limbus, ct = chain.get('clinical_rtstruct'), chain.get('limbus_ai_rtstruct'), chain.get('ct_series')
    return {
        'StatusCategory': status_category(chain),
        'Plan_ApprovalDate': (chain.get('rtplan') or {}).get('approval_date') or None,
        'CT_SeriesDescription': ct['series_description'] if ct else None,
        'Clinical_SeriesDescription': clinical['series_description'] if clinical else None,
        'Clinical_Label': clinical['structure_set_label'] if clinical else None,
        'Clinical_Name': clinical['structure_set_name'] if clinical else None,
        'Limbus_SeriesDescription': limbus['series_description'] if limbus else None,
        'Limbus_Label': limbus['structure_set_label'] if limbus else None,
        'Limbus_Name': limbus['structure_set_name'] if limbus else None,
        'StudyDate': chain.get('study_date') or None,
        'Process': chain.get('process') or None,
        'ScriptFootprint': chain.get('script_footprint') or None,
        'Limbus_MatchMethod': chain.get('limbus_match_method') or None,
        'Limbus_SeriesGap_h': chain.get('limbus_series_gap_h'),
        'Limbus_DescriptionMatch': chain.get('limbus_description_match'),
        'Limbus_NameMatch': chain.get('limbus_name_match'),
        'Status': chain.get('chain_note'),  # rows with a status of their own use with_chain_note
        'Clinical_RTSTRUCT_Source': clinical_rtstruct_source(chain.get('clinical_rtstruct')),
    }


def clinical_rtstruct_source(clinical_rtstruct: Optional[dict]) -> Optional[str]:
    """Manufacturer / ManufacturerModelName of the clinical RTSTRUCT, e.g. a RayStation export."""
    if not clinical_rtstruct:
        return None
    return f"{clinical_rtstruct['manufacturer']} / {clinical_rtstruct['manufacturer_model']}"


def discover_patient_folders(dicom_root_folder: str) -> List[Dict]:
    """
    Discover all patient folders in the DICOM directory structure.
    
    Parameters
    ----------
    dicom_root_folder : str
        Root folder containing patient subdirectories, named either
        P... or all digits

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
    
    # Patient folders are either pseudonymised (P0728C0006I...) or a plain
    # patient number (e.g. 1000237); the folder name is used as pNumber
    for item in os.listdir(dicom_root_folder):
        patient_folder = os.path.join(dicom_root_folder, item)

        if not os.path.isdir(patient_folder):
            continue

        # Check if this looks like a patient folder
        if not (item.startswith('P') or item.isdigit()):
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
# DOSE CALCULATION HELPERS (integrated from calculate_dose_per_contour)
# ============================================================================

def resample_contour_filled(struct_slices: list, dose_ct: dict) -> np.ndarray:
    """
    Rasterise a structure as a filled 3D binary mask on the dose grid.

    Uses skimage.draw.polygon to produce a solid binary volume per slice,
    matching the filled-polygon methodology of calculate_dose_per_contour.

    Parameters
    ----------
    struct_slices : list of dict
        ContourSequence slice list with 'X', 'Y', 'Z' keys (cm).
    dose_ct : dict
        Dose-grid descriptor from read_rtdose (PixelFirst*/PixelSpacing*/PixelNum*).

    Returns
    -------
    ndarray of bool
        3D binary mask, shape (PixelNumXi, PixelNumYi, PixelNumZi).
    """
    nx = dose_ct['PixelNumXi']
    ny = dose_ct['PixelNumYi']
    nz = dose_ct['PixelNumZi']
    mask = np.zeros((nx, ny, nz), dtype=bool)

    for sl in struct_slices:
        if sl['X'] is None or len(sl['X']) == 0:
            continue
        yi = int(round((sl['Y'][0] - dose_ct['PixelFirstYi']) / dose_ct['PixelSpacingYi']))
        if yi < 0 or yi >= ny:
            continue
        xi = np.round((sl['X'] - dose_ct['PixelFirstXi']) / dose_ct['PixelSpacingXi']).astype(int)
        zi = np.round((sl['Z'] - dose_ct['PixelFirstZi']) / dose_ct['PixelSpacingZi']).astype(int)
        try:
            rr, cc = polygon(xi, zi, shape=(nx, nz))
            valid = (rr >= 0) & (rr < nx) & (cc >= 0) & (cc < nz)
            mask[rr[valid], yi, cc[valid]] = True
        except Exception:
            pass

    return mask


def dose_stats(dose_cube: np.ndarray, struct_slices: list, dose_ct: dict) -> dict:
    """
    Compute Dmean and D0.03cc for one structure on the dose grid.

    Methodology matches calculate_dose_per_contour:
      - Structure rasterised as filled binary mask (resample_contour_filled)
      - Dmean: mean dose over all voxels inside the structure
      - Dmax: D0.03cc — dose to the hottest 0.03 cc volume

    Parameters
    ----------
    dose_cube : ndarray
        3D dose array (Gy) from read_rtdose, shape (Xi, Yi, Zi).
    struct_slices : list of dict
        ContourSequence slice list with 'X', 'Y', 'Z' keys (cm).
    dose_ct : dict
        Dose-grid descriptor from read_rtdose.

    Returns
    -------
    dict with keys 'Dmean' and 'Dmax' (float, Gy), or NaN if mask is empty.
    """
    mask = resample_contour_filled(struct_slices, dose_ct)
    vals = dose_cube[mask]
    if vals.size == 0:
        return {'Dmean': float('nan'), 'Dmax': float('nan')}

    # Voxel volume in cc (pixel spacing in cm → cm³ = cc, divided by 1000
    # to match calculate_dose_per_contour unit convention)
    voxel_vol_cc = (
        dose_ct['PixelSpacingXi'] * dose_ct['PixelSpacingYi'] * dose_ct['PixelSpacingZi']
    ) / 1000.0

    # D0.03cc: dose to the hottest 0.03 cc
    target_cc = 0.03
    n_voxels_needed = max(1, int(np.ceil(target_cc / voxel_vol_cc)))
    sorted_vals = np.sort(vals)[::-1]  # descending
    d_near_max = float(sorted_vals[min(n_voxels_needed - 1, len(sorted_vals) - 1)])

    return {'Dmean': float(np.mean(vals)), 'Dmax': d_near_max}


# ============================================================================
# CHECKPOINTING (SAVE AFTER EVERY PATIENT)
# ============================================================================

# Column order of the results table (also used for the checkpoint CSV header)
RESULT_COLUMNS = [
    'pNumber', 'CTSeriesUID',
    'Clinical_RTSTRUCT_Date', 'RTDOSE_Date',
    'ChainStatus', 'StatusCategory',
    'StudyDate', 'Process', 'ScriptFootprint', 'Limbus_MatchMethod', 'Limbus_SeriesGap_h',
    'Plan_ApprovalDate', 'CT_SeriesDescription',
    'Clinical_SeriesDescription', 'Clinical_Label', 'Clinical_Name',
    'Limbus_SeriesDescription', 'Limbus_Label', 'Limbus_Name',
    'Clinical_RTSTRUCT_Source',
    'RTPLAN_Name', 'RTPLAN_File', 'RTDOSE_File',
    'Clinical_RTSTRUCT', 'Limbus_AI_RTSTRUCT',
    'RTSTRUCT1_SeriesDescription', 'RTSTRUCT2_SeriesDescription',
    'Enough_RTSTRUCTs', 'RTPLAN_Present', 'Common VOI', 'VOIName',
    'Dice',
    'APL', 'SDSC',
    'APL_tol05', 'SDSC_tol05',
    'APL_tol1', 'SDSC_tol1',
    'APL_tol3', 'SDSC_tol3',
    'AI_Dmean', 'AI_Dmax', 'Clin_Dmean', 'Clin_Dmax',
    'Delta_Dmean', 'Delta_Dmax', 'DoseStatus',
    'dist_to_ptv', 'DistStatus',
    'RTPLAN_StudyDescription', 'RTPLAN_RTPlanName',
    'RTPLAN_NumberOfFractions', 'RTPLAN_TargetPrescriptionDose',
    'RTPLAN_DoseReferenceDescription', 'RTPLAN_SetupTechniqueDescription',
    'Status', 'timestamp',
]

# Chain-level duplicates are skipped before the expensive contour work.
# Row-level duplicates are removed only when saving VOI rows.
CHAIN_DUPLICATE_KEY_COLUMNS = ['pNumber', 'CTSeriesUID', 'RTPLAN_Name']
ROW_DUPLICATE_KEY_COLUMNS = ['pNumber', 'CTSeriesUID', 'RTPLAN_Name', 'VOIName']

# Columns converted back to numbers when reading the checkpoint (all others stay text)
NUMERIC_COLUMNS = [
    'Dice', 'APL', 'SDSC', 'APL_tol05', 'SDSC_tol05', 'APL_tol1', 'SDSC_tol1',
    'APL_tol3', 'SDSC_tol3', 'AI_Dmean', 'AI_Dmax', 'Clin_Dmean', 'Clin_Dmax',
    'Delta_Dmean', 'Delta_Dmax', 'dist_to_ptv',
    'RTPLAN_NumberOfFractions', 'RTPLAN_TargetPrescriptionDose',
]


def _normalise_key_value(value) -> str:
    """
    Normalise one chain-key value so keys from DICOM, the checkpoint CSV and the
    Excel file compare equal.

    The CTSeriesUID column holds the last 12 characters of the UID. Excel stores
    an all-digit value as a number, so it is read back as e.g. '289048612345.0'
    or without its leading zeros. Numeric strings are therefore reduced to their
    canonical form ('012345.0' -> '12345'); everything else is only stripped.
    """
    s = str(value).strip()
    try:
        d = Decimal(s)
    except InvalidOperation:
        return s
    if not d.is_finite():
        return s
    return format(d.normalize(), 'f')


def chain_keys_from_frame(df: pd.DataFrame) -> set:
    """
    Return the normalised (pNumber, CTSeriesUID, RTPLAN_Name) keys of chains in df
    that produced at least one VOI result row.

    Placeholder rows (incomplete chain, no common VOIs) are ignored, so such a chain
    is evaluated again on the next run, e.g. once its Limbus RTSTRUCT is available.
    """
    if df.empty or not set(CHAIN_DUPLICATE_KEY_COLUMNS).issubset(df.columns):
        return set()
    if 'ChainStatus' in df.columns:
        df = df[df['ChainStatus'].astype(str).str.strip() == 'Complete']
    if 'VOIName' in df.columns:
        df = df[df['VOIName'].notna() & (df['VOIName'].astype(str).str.strip() != 'N/A')]
    return {
        tuple(_normalise_key_value(v) for v in row)
        for row in df[CHAIN_DUPLICATE_KEY_COLUMNS].dropna().itertuples(index=False, name=None)
    }


def checkpoint_paths(output_file: str) -> Tuple[str, str]:
    """
    Return the checkpoint file paths belonging to an output Excel file.

    - <stem>_checkpoint.csv       : result rows, appended after every patient
    - <stem>_checkpoint_done.txt  : one patient ID per line, written after that
                                    patient's rows are safely on disk
    """
    stem = os.path.splitext(output_file)[0]
    return f'{stem}_checkpoint.csv', f'{stem}_checkpoint_done.txt'


def load_checkpoint(output_file: str) -> Tuple[set, pd.DataFrame]:
    """
    Load completed patients and their result rows from the checkpoint.

    Only patients listed in the done-file count as completed. Rows of a patient
    that was interrupted mid-write (rows present, done-marker missing) are
    dropped from the CSV, so that patient is processed again cleanly.

    Returns
    -------
    done : set
        Patient IDs that were fully processed
    rows : pd.DataFrame
        Result rows of the completed patients
    """
    csv_file, done_file = checkpoint_paths(output_file)

    done = set()
    if os.path.exists(done_file):
        with open(done_file, encoding='utf-8') as f:
            done = {line.strip() for line in f if line.strip()}

    if not os.path.exists(csv_file):
        return done, pd.DataFrame(columns=RESULT_COLUMNS)

    # Read everything as text ('N/A' must stay 'N/A'), then restore numeric columns
    rows = pd.read_csv(csv_file, dtype=str, keep_default_na=False, na_values=[''],
                       encoding='utf-8')
    for col in NUMERIC_COLUMNS:
        if col in rows.columns:
            numbers = pd.to_numeric(rows[col], errors='coerce')
            rows[col] = numbers.where(numbers.notna() | rows[col].isna(), rows[col])

    needs_rewrite = False

    # A checkpoint written by an older version has a different header; rows appended
    # with the current RESULT_COLUMNS would end up in the wrong columns
    if list(rows.columns) != RESULT_COLUMNS:
        print("Checkpoint: upgrading CSV header to the current result columns")
        rows = rows.reindex(columns=RESULT_COLUMNS)
        needs_rewrite = True

    incomplete = ~rows['pNumber'].isin(done)
    if incomplete.any():
        print(f"Checkpoint: discarding {incomplete.sum()} row(s) of interrupted patient(s): "
              f"{', '.join(sorted(rows.loc[incomplete, 'pNumber'].unique()))}")
        rows = rows[~incomplete]
        needs_rewrite = True

    if needs_rewrite:
        rows.to_csv(csv_file, index=False, encoding='utf-8')

    rows = rows.drop_duplicates(subset=ROW_DUPLICATE_KEY_COLUMNS, keep='last')

    return done, rows


def append_to_checkpoint(output_file: str, patient_id: str, patient_rows: List[Dict]):
    """
    Append one patient's result rows to the checkpoint and mark the patient done.

    A patient without any result rows (e.g. unreadable CT) is still marked done,
    so it is not reprocessed after every restart.
    """
    csv_file, done_file = checkpoint_paths(output_file)

    if patient_rows:
        unknown = set().union(*patient_rows) - set(RESULT_COLUMNS)
        if unknown:
            warnings.warn(f"Columns not in RESULT_COLUMNS are not checkpointed: {sorted(unknown)}")
        df = pd.DataFrame(patient_rows).reindex(columns=RESULT_COLUMNS)
        write_header = not os.path.exists(csv_file)
        with open(csv_file, 'a', newline='', encoding='utf-8') as f:
            df.to_csv(f, header=write_header, index=False)
            f.flush()
            os.fsync(f.fileno())

    with open(done_file, 'a', encoding='utf-8') as f:
        f.write(f'{patient_id}\n')
        f.flush()
        os.fsync(f.fileno())


# ============================================================================
# MAIN PROCESSING FUNCTION
# ============================================================================

def quantify_contour_differences_p0728(dicom_root_folder: str, calc_all_parameters: int = 1,
                                        max_patients: Optional[int] = None,
                                        output_file: str = 'contour_comparison_results_P0728_v8.xlsx',
                                        patient_ids: Optional[set] = None) -> pd.DataFrame:
    """
    Quantify differences between contours for all patients using DICOM chain identification.

    patient_ids : set of str, optional
        If given, only patient folders whose name matches one of these IDs (compared in
        normalised form, so leading zeros / '.0' do not matter) are processed.
    
    This function automatically processes all patients in the DICOM folder structure,
    comparing Limbus AI RTSTRUCT with clinical ARIA RTSTRUCT using the approved RTPLAN
    as the entry point for chain identification.
    
    v5: Geometry-first Limbus matching (Frame of Reference + CT Series UID),
        then verify metadata (SeriesDescription + StructureSetLabel).
    
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
    output_file : str, optional
        Excel output file. Chains whose (pNumber, CTSeriesUID, RTPLAN_Name) already
        occur in this file or in the checkpoint are skipped; there is no
        patient-level skip, so new chains of known patients are still processed. Results are
        checkpointed after every patient to <stem>_checkpoint.csv, so an interrupted
        run continues where it stopped when started again.

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
    
    # Excluded VOIs
    excluded_vois = ['body', 'skin']
    
    # Discover all patients
    print(f"Scanning for patients in: {dicom_root_folder}")
    patients = discover_patient_folders(dicom_root_folder)
    
    if not patients:
        print("No patient folders found.")
        return pd.DataFrame()
    
    print(f"Found {len(patients)} patient folder(s)")

    if patient_ids is not None:
        wanted = {_normalise_key_value(p) for p in patient_ids}
        patients = [p for p in patients if _normalise_key_value(p['patient_id']) in wanted]
        print(f"Restricted to {len(patients)} of {len(wanted)} requested patient ID(s)")
        if not patients:
            print("None of the requested patients were found in the DICOM root folder.")
            return pd.DataFrame()

    # Limit number of patients if max_patients is specified
    if max_patients is not None and max_patients > 0:
        patients = random.sample(patients, min(max_patients, len(patients)))
        print(f"Randomly selected {len(patients)} patient(s) for sample test")
    
    # Process each patient
    all_results = []

    # Load any existing checkpoint rows so an interrupted previous run can be
    # merged back in at the end. Exact duplicates are removed by row identity.
    checkpoint_done, checkpoint_rows = load_checkpoint(output_file)
    if checkpoint_done:
        print(f"Found {len(checkpoint_done)} completed patient marker(s) in checkpoint {checkpoint_paths(output_file)[0]}")

    existing_chain_keys = set()
    if os.path.exists(output_file):
        try:
            key_source_columns = CHAIN_DUPLICATE_KEY_COLUMNS + ['ChainStatus', 'VOIName']
            existing_df = pd.read_excel(output_file, engine='openpyxl',
                                        usecols=lambda c: c in key_source_columns, dtype=str)
            existing_chain_keys.update(chain_keys_from_frame(existing_df))
            print(f"Found {len(existing_chain_keys)} existing chain key(s) in {output_file}")
        except Exception as e:
            print(f"Warning: could not read existing output file for duplicate detection: {e}")

    checkpoint_keys = chain_keys_from_frame(checkpoint_rows)
    if checkpoint_keys:
        print(f"Found {len(checkpoint_keys)} chain key(s) in checkpoint")
    existing_chain_keys.update(checkpoint_keys)

    # Rows of the patient currently being processed start at this index in all_results;
    # they are written to the checkpoint once the next patient starts (or the loop ends)
    current_patient = None
    current_start = 0

    for patient_idx, patient_data in enumerate(patients):
        if current_patient is not None:
            append_to_checkpoint(output_file, current_patient, all_results[current_start:])
            current_patient = None

        patient_id = patient_data['patient_id']
        patient_folder = patient_data['patient_folder']

        print(f"\n{'='*80}")
        print(f"Processing patient {patient_idx + 1}/{len(patients)}: {patient_id}")
        print(f"{'='*80}")
        current_patient = patient_id
        current_start = len(all_results)

        # Identify DICOM chains using the v5 method
        print("  Using DICOM chain identification (v5 - geometry first)...")
        chains = identify_dicom_chain(patient_folder, verbose=True)
        
        if not chains:
            print(f"  ✗ No valid DICOM chains found for this patient")
            skip_result = {
                'pNumber': patient_id,
                'CTSeriesUID': 'N/A',
                'ChainStatus': 'No approved RTPLANs',
                'StatusCategory': 'Failed: no approved RTPLAN',
                'Enough_RTSTRUCTs': 'No',
                'RTPLAN_Present': 'No',
                'Common VOI': 'N/A',
                'VOIName': 'N/A',
                'Dice': None,
                'Clinical_RTSTRUCT_Date': None,
                'RTDOSE_Date': None,
                'Status': 'No valid DICOM chains found'
            }
            if calc_all_parameters != 0:
                skip_result['APL'] = None
                skip_result['SDSC'] = None
                skip_result['APL_tol05'] = None
                skip_result['SDSC_tol05'] = None
                skip_result['APL_tol1'] = None
                skip_result['SDSC_tol1'] = None
                skip_result['APL_tol3'] = None
                skip_result['SDSC_tol3'] = None
            skip_result['AI_Dmean'] = None
            skip_result['AI_Dmax'] = None
            skip_result['Clin_Dmean'] = None
            skip_result['Clin_Dmax'] = None
            skip_result['Delta_Dmean'] = None
            skip_result['Delta_Dmax'] = None
            skip_result['DoseStatus'] = 'Skipped'
            skip_result['dist_to_ptv'] = None
            skip_result['DistStatus'] = 'Skipped'
            all_results.append(skip_result)
            continue
        
        # Process each complete chain
        print(f"\n  Found {len(chains)} chain(s) to process")
        
        for chain_idx, chain in enumerate(chains):
            print(f"\n  {'-'*76}")
            print(f"  Processing chain {chain_idx + 1}/{len(chains)}: {chain['chain_status']}")
            print(f"  {'-'*76}")

            chain_key = tuple(_normalise_key_value(v) for v in (
                patient_id,
                chain['ct_series']['series_uid'][-12:] if chain['ct_series'] else 'N/A',
                chain['rtplan']['plan_name'] if chain['rtplan'] else 'N/A',
            ))
            chain_saved = False

            if chain_key in existing_chain_keys:
                print(f"  ↷ Skipping duplicate chain: pNumber={chain_key[0]}, CTSeriesUID={chain_key[1]}, RTPLAN_Name={chain_key[2]}")
                continue
            
            if not chain['chain_complete']:
                print(f"  ✗ Incomplete chain: {chain['chain_status']}")
                skip_result = {
                    'pNumber': patient_id,
                    'CTSeriesUID': chain['ct_series']['series_uid'][-12:] if chain['ct_series'] else 'N/A',
                    'ChainStatus': chain['chain_status'],
                    **chain_selection_columns(chain),
                    'RTPLAN_Name': chain['rtplan']['plan_name'],
                    'RTPLAN_File': chain['rtplan']['filename'],
                    'RTDOSE_File': os.path.basename(chain.get('rtdose_path') or '') or None,
                    'Clinical_RTSTRUCT': chain['clinical_rtstruct']['filename'] if chain['clinical_rtstruct'] else 'N/A',
                    'Limbus_AI_RTSTRUCT': chain['limbus_ai_rtstruct']['filename'] if chain['limbus_ai_rtstruct'] else 'N/A',
                    'Enough_RTSTRUCTs': 'No',
                    'RTPLAN_Present': 'Yes',
                    'Common VOI': 'N/A',
                    'VOIName': 'N/A',
                    'Dice': None,
                    'Clinical_RTSTRUCT_Date': extract_folder_date(chain['clinical_rtstruct']['path']) if chain['clinical_rtstruct'] else None,
                    'RTDOSE_Date': extract_folder_date(chain.get('rtdose_path')),
                    'Status': with_chain_note(chain['chain_status'] if chain['chain_status'].startswith('Excluded')
                                              else f'Incomplete chain: {chain["chain_status"]}', chain)
                }
                if calc_all_parameters != 0:
                    skip_result['APL'] = None
                    skip_result['SDSC'] = None
                    skip_result['APL_tol05'] = None
                    skip_result['SDSC_tol05'] = None
                    skip_result['APL_tol1'] = None
                    skip_result['SDSC_tol1'] = None
                    skip_result['APL_tol3'] = None
                    skip_result['SDSC_tol3'] = None
                skip_result['AI_Dmean'] = None
                skip_result['AI_Dmax'] = None
                skip_result['Clin_Dmean'] = None
                skip_result['Clin_Dmax'] = None
                skip_result['Delta_Dmean'] = None
                skip_result['Delta_Dmax'] = None
                skip_result['DoseStatus'] = 'Skipped'
                skip_result['dist_to_ptv'] = None
                skip_result['DistStatus'] = 'Skipped'
                all_results.append(skip_result)
                continue
            
            # Extract chain components
            rtplan_info = chain['rtplan']
            clinical_rtstruct_info = chain['clinical_rtstruct']
            ct_series_info = chain['ct_series']
            limbus_rtstruct_info = chain['limbus_ai_rtstruct']

            # Extract generation dates from folder names (yyyymmdd parent folder)
            clinical_rtstruct_date = extract_folder_date(clinical_rtstruct_info['path'])
            rtdose_date = extract_folder_date(chain.get('rtdose_path'))
            rtdose_file_basename = os.path.basename(chain.get('rtdose_path') or '') or None
            
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
            # RTSTRUCT 1 = Limbus AI  → used as the baseline/reference
            # RTSTRUCT 2 = Clinical ARIA → the corrected version, assessed against AI
            # APL counts surface pixels of the clinical contour that lie outside the
            # AI contour expanded by the tolerance band, i.e. the corrections made
            # by the clinician that exceed the accepted tolerance.
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

            # Load RTDOSE if the chain identified one
            print("\n    Loading RTDOSE...")
            dose_cube = None
            dose_ct_grid = None
            rtdose_data = None
            rtdose_file = chain.get('rtdose_path')
            if rtdose_file:
                try:
                    rtdose_data = read_rtdose(rtdose_file)
                    dose_cube = rtdose_data['cube']
                    dose_ct_grid = rtdose_data['ct']
                    print(f"    ✓ RTDOSE loaded: {os.path.basename(rtdose_file)} "
                          f"[{chain.get('rtdose_status', '')}]")
                except Exception as e:
                    print(f"    ⚠ Could not load RTDOSE: {str(e)} — dose metrics will be skipped")
            else:
                print("    ⚠ No RTDOSE in chain — dose metrics will be skipped")

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
                    **chain_selection_columns(chain),
                    'RTPLAN_Name': rtplan_info['plan_name'],
                    'RTPLAN_File': rtplan_info['filename'],
                    'RTDOSE_File': rtdose_file_basename,
                    'Clinical_RTSTRUCT': clinical_rtstruct_info['filename'],
                    'Limbus_AI_RTSTRUCT': limbus_rtstruct_info['filename'],
                    'RTSTRUCT1_SeriesDescription': rtstruct1_series_desc,
                    'RTSTRUCT2_SeriesDescription': rtstruct2_series_desc,
                    'Enough_RTSTRUCTs': 'Yes',
                    'RTPLAN_Present': 'Yes',
                    'Common VOI': 'No',
                    'VOIName': 'N/A',
                    'Dice': None,
                    'Clinical_RTSTRUCT_Date': clinical_rtstruct_date,
                    'RTDOSE_Date': rtdose_date,
                    'Status': with_chain_note('No common VOIs after exclusions', chain)
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
                    skip_result['APL_tol05'] = None
                    skip_result['SDSC_tol05'] = None
                    skip_result['APL_tol1'] = None
                    skip_result['SDSC_tol1'] = None
                    skip_result['APL_tol3'] = None
                    skip_result['SDSC_tol3'] = None
                skip_result['AI_Dmean'] = None
                skip_result['AI_Dmax'] = None
                skip_result['Clin_Dmean'] = None
                skip_result['Clin_Dmax'] = None
                skip_result['Delta_Dmean'] = None
                skip_result['Delta_Dmax'] = None
                skip_result['DoseStatus'] = 'Skipped'
                skip_result['dist_to_ptv'] = None
                skip_result['DistStatus'] = 'Skipped'
                all_results.append(skip_result)
                continue
            
            print(f"    Comparing {len(common_vois)} structure(s)")
            
            # ================================================================
            # v3 OPTIMIZATION: Only compose COMMON structures
            # ================================================================
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

            # Find tumour (PTV) structure indices in clinical RTSTRUCT for distance calculation
            tumour_indices_for_dist = {}
            for _tname in TUMOUR_STRUCTURES:
                _tidx = find_structure_by_name(rtstruct2, _tname)
                if _tidx is not None:
                    tumour_indices_for_dist[_tname] = _tidx
            if tumour_indices_for_dist:
                print(f"    Distance reference structures: {list(tumour_indices_for_dist.keys())}")
            else:
                print("    ⚠ No tumour structures found — dist_to_ptv will be None")

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
                    **chain_selection_columns(chain),
                    'RTPLAN_Name': rtplan_info['plan_name'],
                    'RTPLAN_File': rtplan_info['filename'],
                    'RTDOSE_File': rtdose_file_basename,
                    'Clinical_RTSTRUCT': clinical_rtstruct_info['filename'],
                    'Limbus_AI_RTSTRUCT': limbus_rtstruct_info['filename'],
                    'RTSTRUCT1_SeriesDescription': rtstruct1_series_desc,
                    'RTSTRUCT2_SeriesDescription': rtstruct2_series_desc,
                    'Enough_RTSTRUCTs': 'Yes',
                    'RTPLAN_Present': 'Yes',
                    'Common VOI': 'Yes',
                    'VOIName': voi_name,
                    'Clinical_RTSTRUCT_Date': clinical_rtstruct_date,
                    'RTDOSE_Date': rtdose_date
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
                    # In the filtered matrix, structures are at positions 1, 2, 3, ... (1-indexed)
                    # struct_position is 0-indexed, so we use struct_position + 1
                    dice_idx = struct_position + 1
                    result['Dice'] = calculate_dice_logical(voi1, voi2, dice_idx, dice_idx)
                    
                    # Calculate APL and Surface DSC if requested
                    if calc_all_parameters != 0:
                        # APL and SDSC use ORIGINAL structure indices from the RTSTRUCT
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
                        
                        # Calculate with tolerance 0.05 cm (0.5 mm)
                        temp_path_length_05 = calculate_path_length(
                            imaging_data, rtstruct1, rtstruct2,
                            orig_idx1, orig_idx2, 0.05
                        )
                        result['APL_tol05'] = np.sum(temp_path_length_05)

                        result['SDSC_tol05'] = calculate_surface_dsc(
                            imaging_data, rtstruct1, rtstruct2,
                            orig_idx1, orig_idx2, 0.05
                        )

                        # Calculate with tolerance 0.1 cm (1 mm)
                        temp_path_length_1 = calculate_path_length(
                            imaging_data, rtstruct1, rtstruct2,
                            orig_idx1, orig_idx2, 0.1
                        )
                        result['APL_tol1'] = np.sum(temp_path_length_1)

                        result['SDSC_tol1'] = calculate_surface_dsc(
                            imaging_data, rtstruct1, rtstruct2,
                            orig_idx1, orig_idx2, 0.1
                        )

                        # Calculate with tolerance 0.3 cm (3 mm)
                        temp_path_length_3 = calculate_path_length(
                            imaging_data, rtstruct1, rtstruct2,
                            orig_idx1, orig_idx2, 0.3
                        )
                        result['APL_tol3'] = np.sum(temp_path_length_3)
                        
                        result['SDSC_tol3'] = calculate_surface_dsc(
                            imaging_data, rtstruct1, rtstruct2,
                            orig_idx1, orig_idx2, 0.3
                        )

                    # Calculate dose statistics
                    if rtdose_data is not None:
                        try:
                            def _r(v): return round(v, 4) if not np.isnan(v) else float('nan')
                            dvh_parm, _, _, _ = calculate_dvh_parameters(
                                rtdose_data, orig_idx1, orig_idx2,
                                rtstruct1, rtstruct2, imaging_data)
                            result['AI_Dmean']    = _r(dvh_parm['AutomaticDmean'])
                            result['AI_Dmax']     = _r(dvh_parm['AutomaticD0.03cc'])
                            result['Clin_Dmean']  = _r(dvh_parm['AdjustedDmean'])
                            result['Clin_Dmax']   = _r(dvh_parm['AdjustedD0.03cc'])
                            result['Delta_Dmean'] = _r(dvh_parm['DeltaDmean'])
                            result['Delta_Dmax']  = _r(dvh_parm['DeltaD0.03cc'])
                            result['DoseStatus']  = 'OK'
                        except Exception as de:
                            result['AI_Dmean'] = result['AI_Dmax'] = None
                            result['Clin_Dmean'] = result['Clin_Dmax'] = None
                            result['Delta_Dmean'] = result['Delta_Dmax'] = None
                            result['DoseStatus'] = f'Error: {de}'
                    else:
                        result['AI_Dmean'] = result['AI_Dmax'] = None
                        result['Clin_Dmean'] = result['Clin_Dmax'] = None
                        result['Delta_Dmean'] = result['Delta_Dmax'] = None
                        result['DoseStatus'] = 'No RTDOSE'

                    # Calculate 3D distance to nearest tumour structure (clinical RTSTRUCT)
                    if tumour_indices_for_dist:
                        try:
                            _row_dists = {}
                            for _tname, _tidx in tumour_indices_for_dist.items():
                                if voi_name == _tname:
                                    _row_dists[_tname] = 0.0
                                else:
                                    _row_dists[_tname] = calculate_distance_3d(
                                        imaging_data, rtstruct2, _tidx, orig_idx2)
                            result['dist_to_ptv'] = round(min(_row_dists.values()), 2)
                            result['DistStatus'] = 'OK'
                        except Exception as _de:
                            result['dist_to_ptv'] = None
                            result['DistStatus'] = f'Error: {_de}'
                    else:
                        result['dist_to_ptv'] = None
                        result['DistStatus'] = 'No tumour structure'

                    all_results.append(result)
                    chain_saved = True
                    print(f"        DICE: {result['Dice']:.4f}")
                    if calc_all_parameters != 0:
                        print(f"        APL (tol=0.1):  {result['APL']:.4f}")
                        print(f"        SDSC (tol=0.1): {result['SDSC']:.4f}")
                        print(f"        APL (tol=0.05): {result['APL_tol05']:.4f}")
                        print(f"        SDSC (tol=0.05):{result['SDSC_tol05']:.4f}")
                        print(f"        APL (tol=0.1):  {result['APL_tol1']:.4f}")
                        print(f"        SDSC (tol=0.1): {result['SDSC_tol1']:.4f}")
                        print(f"        APL (tol=0.3):  {result['APL_tol3']:.4f}")
                        print(f"        SDSC (tol=0.3): {result['SDSC_tol3']:.4f}")
                    if result['DoseStatus'] == 'OK':
                        print(f"        Dmean AI/Clin:  {result['AI_Dmean']:.4f} / {result['Clin_Dmean']:.4f} Gy")
                        print(f"        D0.03cc AI/Clin:{result['AI_Dmax']:.4f} / {result['Clin_Dmax']:.4f} Gy")
                    else:
                        print(f"        Dose: {result['DoseStatus']}")

                except Exception as e:
                    print(f"      ✗ Error calculating metrics for {voi_name}: {str(e)}")
                    continue

            if chain_saved:
                existing_chain_keys.add(chain_key)
    
    if current_patient is not None:
        append_to_checkpoint(output_file, current_patient, all_results[current_start:])

    # Create results table from the checkpoint: this run plus earlier interrupted runs
    _, results_table = load_checkpoint(output_file)
    if not results_table.empty:
        results_table = results_table.drop(columns='timestamp')  # set when saving to Excel
        results_table = results_table.drop_duplicates(subset=ROW_DUPLICATE_KEY_COLUMNS, keep='last')
        results_table = results_table.sort_values(['pNumber', 'CTSeriesUID', 'VOIName'])
        return results_table
    else:
        return pd.DataFrame()


# ============================================================================
# EXCEL FILE HANDLING (APPEND/UPDATE)
# ============================================================================

def save_results_to_excel(results: pd.DataFrame, output_file: str = 'contour_comparison_results_P0728_v8.xlsx'):
    """
    Save contour comparison results to Excel file.
    
    Logic:
    - If file doesn't exist: create new file with results
    - If file exists:
        - Append new rows
        - Drop exact duplicates using pNumber + CTSeriesUID + VOIName

    Repeat patients are kept when their image/VOI key changes.
    
    Parameters
    ----------
    results : pd.DataFrame
        Results DataFrame from quantify_contour_differences_p0728
    output_file : str
        Path to Excel file (default: contour_comparison_results_P0728_v5.xlsx)
    """
    if results is None or results.empty:
        print("No results to save.")
        return

    # Add timestamp to results
    results = results.copy()
    results['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Apply desired column order (unknown columns land at the end)
    existing_preferred = [c for c in RESULT_COLUMNS if c in results.columns]
    extra_cols = [c for c in results.columns if c not in RESULT_COLUMNS]
    results = results[existing_preferred + extra_cols]
    
    # Get unique patient IDs in new results
    new_patients = set(results['pNumber'].unique())
    
    if os.path.exists(output_file):
        try:
            # Load existing data
            # Key columns as text: Excel turns all-digit values into numbers,
            # which cannot be sorted together with the text values of new rows
            existing_df = pd.read_excel(output_file, engine='openpyxl',
                                        dtype={c: str for c in ROW_DUPLICATE_KEY_COLUMNS})
            print(f"\nLoaded existing file with {len(existing_df)} record(s)")

            # Combine everything, then remove only exact duplicate analysis rows.
            # Compare on normalised keys, but keep the stored values as they are
            combined_df = pd.concat([existing_df, results], ignore_index=True)
            norm_keys = combined_df[ROW_DUPLICATE_KEY_COLUMNS].apply(
                lambda s: s.map(lambda v: _normalise_key_value(v) if pd.notna(v) else v))
            combined_df = combined_df[~norm_keys.duplicated(keep='last')]
            for col in ROW_DUPLICATE_KEY_COLUMNS:
                combined_df[col] = combined_df[col].astype(str).where(combined_df[col].notna())
            
            # Sort by patient and VOI name
            combined_df = combined_df.sort_values(['pNumber', 'CTSeriesUID', 'VOIName'])
            
            # Save combined results
            combined_df.to_excel(output_file, index=False, engine='openpyxl')
            print(f"Saved {len(combined_df)} total record(s) to {output_file}")
            print(f"  - Total unique patients: {len(combined_df['pNumber'].unique())}")
            
        except Exception as e:
            # Never overwrite the existing results; write this run to a separate file
            fallback_file = f"{os.path.splitext(output_file)[0]}_new_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
            print(f"Error merging into existing file: {e}")
            print(f"Existing file left untouched; writing this run to {fallback_file}")
            results.to_excel(fallback_file, index=False, engine='openpyxl')
            print(f"Saved {len(results)} record(s) to {fallback_file}")
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
    DICOM_ROOT_FOLDER = r"\\smb.isilon01.ad.maastro.nl\Research\Projects\phys\p0728-automation\ICoNEA\Addendum\DICOManon"  # Update this path
    MAX_PATIENTS = None  # Limit for sample test (set to None for all patients)
    OUTPUT_FILE = 'contour_comparison_results_P0728_v8.xlsx'
    
    # Parse command-line arguments if provided
    if len(sys.argv) > 1:
        DICOM_ROOT_FOLDER = sys.argv[1]
    if len(sys.argv) > 2:
        MAX_PATIENTS = int(sys.argv[2]) if sys.argv[2].lower() != 'none' else None
    # Optional: text file with one patient ID per line -> only these patients are processed
    PATIENT_IDS = None
    if len(sys.argv) > 3 and sys.argv[3].lower() != 'none':
        with open(sys.argv[3], encoding='utf-8') as f:
            PATIENT_IDS = {line.strip() for line in f if line.strip()}
    # Optional: separate output file (also gives a separate checkpoint), so a concurrent
    # run with the default output file is not disturbed
    if len(sys.argv) > 4:
        OUTPUT_FILE = sys.argv[4]

    print("=" * 80)
    print("Quantify Contour Differences - P0728 Dataset (v5 - Geometry-First Matching)")
    print("=" * 80)
    print(f"DICOM Root Folder: {DICOM_ROOT_FOLDER}")
    print(f"Max Patients: {MAX_PATIENTS if MAX_PATIENTS is not None else 'All'}")
    print("=" * 80)
    print("\nv5 Identification Method:")
    print("  1. Find approved RTPLAN(s) in patient folder")
    print("  2. Get referenced clinical RTSTRUCT from RTPLAN (SOP Instance UID)")
    print("  3. Find matching CT series (Frame of Reference + Series UID)")
    print("  4. Find Limbus AI RTSTRUCT:")
    print("     a. FIRST: Match by Frame of Reference + CT Series UID (same CT)")
    print(f"     b. THEN: Verify SeriesDescription in {SD_LIMBUS_IMPORTS}")
    print("             AND StructureSetLabel == 'Limbus RTStruct'")
    print("  5. Compare Limbus AI vs Clinical RTSTRUCT contours")
    print("\nInherited Optimizations:")
    print("  - Only composes COMMON structures (avoids 64-structure limit)")
    print("  - Faster processing")
    print("=" * 80)
    
    # Run analysis
    results = quantify_contour_differences_p0728(
        dicom_root_folder=DICOM_ROOT_FOLDER,
        calc_all_parameters=1,
        max_patients=MAX_PATIENTS,
        output_file=OUTPUT_FILE,
        patient_ids=PATIENT_IDS
    )
    
    if results is not None and not results.empty:
        print("\n" + "=" * 80)
        print("RESULTS")
        print("=" * 80)
        print(results.to_string(index=False))
        
        # Save to Excel (append new patients, update existing ones)
        print("\n" + "=" * 80)
        print("SAVING RESULTS TO EXCEL")
        print("=" * 80)
        save_results_to_excel(results, OUTPUT_FILE)
    else:
        print("\nNo results generated.")
