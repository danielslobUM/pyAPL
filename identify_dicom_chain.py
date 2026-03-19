"""
identify_dicom_chain.py - Identify the complete DICOM reference chain for radiotherapy data.

This script establishes the correct linkage between DICOM files in a patient folder using:
1. Find approved RTPLAN (using Approval Status tag 300E,0002)
2. From RTPLAN -> identify the clinically approved ARIA RTStruct it references
3. From ARIA RTStruct -> identify what Limbus AI structure set was used (if linked)
4. From RTStructs -> identify the referenced CT series
5. Locate the CT series files in the patient folder

Designed for integration with quantifycontourdifferences_P0728.py

Author: Generated for P0728 dataset analysis
"""

import os
import sys
import random
import pydicom
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class RTStructInfo:
    """Information about an RTSTRUCT file."""
    path: str
    sop_instance_uid: str
    series_instance_uid: str
    frame_of_reference_uid: str
    manufacturer_model_name: str
    structure_set_label: str = ''
    structure_set_name: str = ''
    referenced_ct_series_uid: str = ''
    referenced_sop_uids: List[str] = field(default_factory=list)
    is_limbus_ai: bool = False
    is_aria_radonc: bool = False


@dataclass
class RTPlanInfo:
    """Information about an RTPLAN file."""
    path: str
    sop_instance_uid: str
    series_instance_uid: str
    approval_status: str
    plan_name: str = ''
    plan_label: str = ''
    referenced_rtstruct_sop_uid: str = ''
    referenced_rtstruct_series_uid: str = ''
    frame_of_reference_uid: str = ''


@dataclass
class CTSeriesInfo:
    """Information about a CT series."""
    series_instance_uid: str
    frame_of_reference_uid: str
    folder_path: str
    file_paths: List[str] = field(default_factory=list)
    num_slices: int = 0


@dataclass 
class DicomChain:
    """Complete chain of linked DICOM objects for a patient."""
    patient_id: str
    approved_rtplan: Optional[RTPlanInfo] = None
    clinical_rtstruct: Optional[RTStructInfo] = None  # ARIA RADonc
    ai_rtstruct: Optional[RTStructInfo] = None  # Limbus AI
    ct_series: Optional[CTSeriesInfo] = None
    chain_complete: bool = False
    chain_status: str = ''
    identification_method: Dict = field(default_factory=dict)


def find_dicom_files_recursive(folder_path: str, modality_filter: str = None) -> List[str]:
    """
    Recursively find all DICOM files in a folder.
    
    Parameters
    ----------
    folder_path : str
        Path to folder to search
    modality_filter : str, optional
        If provided, only return files with this modality (e.g., 'CT', 'RTPLAN', 'RTSTRUCT')
        
    Returns
    -------
    List[str]
        List of full paths to DICOM files
    """
    dicom_files = []
    
    if not os.path.isdir(folder_path):
        return dicom_files
    
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith('.dcm'):
                filepath = os.path.join(root, file)
                if modality_filter:
                    try:
                        ds = pydicom.dcmread(filepath, stop_before_pixels=True)
                        if ds.get('Modality', '') == modality_filter:
                            dicom_files.append(filepath)
                    except:
                        pass
                else:
                    dicom_files.append(filepath)
    
    return dicom_files


def read_rtplan_info(rtplan_path: str) -> Optional[RTPlanInfo]:
    """
    Read RTPLAN file and extract relevant information.
    
    Parameters
    ----------
    rtplan_path : str
        Path to RTPLAN DICOM file
        
    Returns
    -------
    RTPlanInfo or None
        Extracted information, or None if not a valid RTPLAN
    """
    try:
        ds = pydicom.dcmread(rtplan_path, stop_before_pixels=True)
        
        if ds.get('Modality', '') != 'RTPLAN':
            return None
        
        # Get approval status - handle both keyword and tag access
        approval_status = ''
        if (0x300E, 0x0002) in ds:
            approval_elem = ds[0x300E, 0x0002]
            approval_status = str(approval_elem.value) if approval_elem.value else ''
        elif hasattr(ds, 'ApprovalStatus'):
            approval_status = str(ds.ApprovalStatus)
        
        info = RTPlanInfo(
            path=rtplan_path,
            sop_instance_uid=str(ds.get('SOPInstanceUID', '')),
            series_instance_uid=str(ds.get('SeriesInstanceUID', '')),
            approval_status=approval_status,
            plan_name=str(ds.get('RTPlanName', '')),
            plan_label=str(ds.get('RTPlanLabel', '')),
            frame_of_reference_uid=str(ds.get('FrameOfReferenceUID', ''))
        )
        
        # Get referenced RTSTRUCT from ReferencedStructureSetSequence (300C,0060)
        if (0x300C, 0x0060) in ds:
            ref_struct_seq = ds[0x300C, 0x0060]
            if ref_struct_seq.value and len(ref_struct_seq.value) > 0:
                item = ref_struct_seq[0]
                if (0x0008, 0x1155) in item:  # Referenced SOP Instance UID
                    info.referenced_rtstruct_sop_uid = str(item[0x0008, 0x1155].value)
                if (0x0020, 0x000E) in item:  # Referenced Series Instance UID (if present)
                    info.referenced_rtstruct_series_uid = str(item[0x0020, 0x000E].value)
        
        return info
        
    except Exception as e:
        print(f"    Warning: Error reading RTPLAN {rtplan_path}: {e}")
        return None


def read_rtstruct_info(rtstruct_path: str) -> Optional[RTStructInfo]:
    """
    Read RTSTRUCT file and extract relevant information.
    
    Parameters
    ----------
    rtstruct_path : str
        Path to RTSTRUCT DICOM file
        
    Returns
    -------
    RTStructInfo or None
        Extracted information, or None if not a valid RTSTRUCT
    """
    try:
        ds = pydicom.dcmread(rtstruct_path, stop_before_pixels=True)
        
        if ds.get('Modality', '') != 'RTSTRUCT':
            return None
        
        model_name = str(ds.get('ManufacturerModelName', ''))
        
        info = RTStructInfo(
            path=rtstruct_path,
            sop_instance_uid=str(ds.get('SOPInstanceUID', '')),
            series_instance_uid=str(ds.get('SeriesInstanceUID', '')),
            frame_of_reference_uid=str(ds.get('FrameOfReferenceUID', '')),
            manufacturer_model_name=model_name,
            structure_set_label=str(ds.get('StructureSetLabel', '')),
            structure_set_name=str(ds.get('StructureSetName', '')),
            is_limbus_ai=(model_name == 'ARIA RTM'),
            is_aria_radonc=(model_name == 'ARIA RadOnc')
        )
        
        # Get referenced CT series from ReferencedFrameOfReferenceSequence
        if (0x3006, 0x0010) in ds:  # ReferencedFrameOfReferenceSequence
            for frame_ref in ds[0x3006, 0x0010]:
                if (0x3006, 0x0012) in frame_ref:  # RTReferencedStudySequence
                    for study_ref in frame_ref[0x3006, 0x0012]:
                        if (0x3006, 0x0014) in study_ref:  # RTReferencedSeriesSequence
                            for series_ref in study_ref[0x3006, 0x0014]:
                                series_uid = str(series_ref.get('SeriesInstanceUID', ''))
                                if series_uid:
                                    info.referenced_ct_series_uid = series_uid
                                    break
        
        # Collect all Referenced SOP Instance UIDs (for finding links to other RTSTRUCTs)
        info.referenced_sop_uids = collect_all_referenced_sop_uids(ds)
        
        return info
        
    except Exception as e:
        print(f"    Warning: Error reading RTSTRUCT {rtstruct_path}: {e}")
        return None


def collect_all_referenced_sop_uids(dataset) -> List[str]:
    """
    Recursively collect all Referenced SOP Instance UIDs from a dataset.
    
    Parameters
    ----------
    dataset : pydicom.Dataset
        DICOM dataset to search
        
    Returns
    -------
    List[str]
        List of all Referenced SOP Instance UIDs found
    """
    uids = []
    
    def search_recursive(ds, depth=0):
        if depth > 20:
            return
        
        for elem in ds:
            try:
                # Check for Referenced SOP Instance UID tag
                if elem.tag == (0x0008, 0x1155):
                    uids.append(str(elem.value))
                # Recurse into sequences
                elif elem.VR == 'SQ' and elem.value:
                    for item in elem.value:
                        search_recursive(item, depth + 1)
            except:
                pass
    
    search_recursive(dataset)
    return uids


def find_ct_series_info(patient_folder: str, target_series_uid: str) -> Optional[CTSeriesInfo]:
    """
    Find CT series files matching the target Series Instance UID.
    
    Parameters
    ----------
    patient_folder : str
        Path to patient folder
    target_series_uid : str
        Series Instance UID to find
        
    Returns
    -------
    CTSeriesInfo or None
        Information about the CT series, or None if not found
    """
    ct_folder = os.path.join(patient_folder, 'CT')
    
    if not os.path.isdir(ct_folder):
        # Try searching entire patient folder
        ct_folder = patient_folder
    
    matching_files = []
    frame_of_ref = None
    folder_path = None
    
    for root, dirs, files in os.walk(ct_folder):
        for file in files:
            if file.lower().endswith('.dcm'):
                filepath = os.path.join(root, file)
                try:
                    ds = pydicom.dcmread(filepath, stop_before_pixels=True)
                    if ds.get('Modality', '') == 'CT':
                        series_uid = str(ds.get('SeriesInstanceUID', ''))
                        if series_uid == target_series_uid:
                            matching_files.append(filepath)
                            if frame_of_ref is None:
                                frame_of_ref = str(ds.get('FrameOfReferenceUID', ''))
                            if folder_path is None:
                                folder_path = root
                except:
                    pass
    
    if matching_files:
        return CTSeriesInfo(
            series_instance_uid=target_series_uid,
            frame_of_reference_uid=frame_of_ref or '',
            folder_path=folder_path or '',
            file_paths=sorted(matching_files),
            num_slices=len(matching_files)
        )
    
    return None


def search_for_limbus_reference_in_aria(aria_info: RTStructInfo, all_rtstructs: List[RTStructInfo]) -> Tuple[Optional[RTStructInfo], str]:
    """
    Search for a reference to a Limbus AI RTSTRUCT in the ARIA RTSTRUCT.
    
    This function looks for any possible link between the clinical ARIA RTSTRUCT
    and a Limbus AI RTSTRUCT.
    
    Parameters
    ----------
    aria_info : RTStructInfo
        The ARIA RADonc RTSTRUCT information
    all_rtstructs : List[RTStructInfo]
        All available RTSTRUCTs in the patient folder
        
    Returns
    -------
    Tuple[Optional[RTStructInfo], str]
        The linked Limbus AI RTSTRUCT (if found) and the method used to identify it
    """
    limbus_rtstructs = [rs for rs in all_rtstructs if rs.is_limbus_ai]
    
    if not limbus_rtstructs:
        return None, "No Limbus AI RTSTRUCTs found in patient folder"
    
    # Method 1: Check if ARIA RTSTRUCT references Limbus AI SOP Instance UID
    for limbus in limbus_rtstructs:
        if limbus.sop_instance_uid in aria_info.referenced_sop_uids:
            return limbus, f"ARIA RTSTRUCT references Limbus AI SOP Instance UID ({limbus.sop_instance_uid[:20]}...)"
    
    # Method 2: Check if Series Instance UIDs match
    for limbus in limbus_rtstructs:
        if limbus.series_instance_uid and limbus.series_instance_uid == aria_info.series_instance_uid:
            return limbus, f"Series Instance UID match ({limbus.series_instance_uid[:20]}...)"
    
    # Method 3: Check if Frame of Reference UIDs match AND referenced CT series match
    for limbus in limbus_rtstructs:
        if (limbus.frame_of_reference_uid and 
            limbus.frame_of_reference_uid == aria_info.frame_of_reference_uid and
            limbus.referenced_ct_series_uid and
            limbus.referenced_ct_series_uid == aria_info.referenced_ct_series_uid):
            return limbus, f"Frame of Reference + Referenced CT Series match"
    
    # Method 4: Frame of Reference UID match only (weaker link)
    for limbus in limbus_rtstructs:
        if limbus.frame_of_reference_uid and limbus.frame_of_reference_uid == aria_info.frame_of_reference_uid:
            return limbus, f"Frame of Reference UID match only ({limbus.frame_of_reference_uid[:20]}...)"
    
    # Method 5: Referenced CT Series UID match only (weaker link)
    for limbus in limbus_rtstructs:
        if limbus.referenced_ct_series_uid and limbus.referenced_ct_series_uid == aria_info.referenced_ct_series_uid:
            return limbus, f"Referenced CT Series UID match only ({limbus.referenced_ct_series_uid[:20]}...)"
    
    # No link found
    if len(limbus_rtstructs) == 1:
        return limbus_rtstructs[0], "Single Limbus AI RTSTRUCT available (assumed match - NO DIRECT LINK FOUND)"
    
    return None, f"Multiple Limbus AI RTSTRUCTs ({len(limbus_rtstructs)}) but no definitive link found"


def identify_dicom_chain(patient_folder: str, patient_id: str, verbose: bool = True) -> DicomChain:
    """
    Identify the complete DICOM reference chain for a patient.
    
    Process:
    1. Find approved RTPLAN
    2. From RTPLAN -> find referenced ARIA RTSTRUCT
    3. From ARIA RTSTRUCT -> find linked Limbus AI RTSTRUCT
    4. From RTSTRUCTs -> find referenced CT series
    
    Parameters
    ----------
    patient_folder : str
        Path to patient folder
    patient_id : str
        Patient identifier
    verbose : bool
        Print detailed progress information
        
    Returns
    -------
    DicomChain
        Complete chain of linked DICOM objects
    """
    chain = DicomChain(patient_id=patient_id)
    
    if verbose:
        print(f"\n{'='*80}")
        print(f"Identifying DICOM chain for patient: {patient_id}")
        print(f"{'='*80}")
    
    # Step 1: Find all RTPLANs and identify the approved one
    if verbose:
        print(f"\n  [Step 1] Finding approved RTPLAN...")
    
    rtplan_folder = os.path.join(patient_folder, 'RTPLAN')
    if not os.path.isdir(rtplan_folder):
        rtplan_folder = patient_folder
    
    rtplan_files = find_dicom_files_recursive(rtplan_folder, modality_filter='RTPLAN')
    
    if verbose:
        print(f"    Found {len(rtplan_files)} RTPLAN file(s)")
    
    all_rtplans = []
    approved_rtplan = None
    
    for rtplan_path in rtplan_files:
        info = read_rtplan_info(rtplan_path)
        if info:
            all_rtplans.append(info)
            if verbose:
                status = info.approval_status
                print(f"    - {os.path.basename(rtplan_path)}: Status='{status}', Name='{info.plan_name}'")
            
            # Check for APPROVED status (tag 300E,0002)
            if info.approval_status.upper() == 'APPROVED':
                if approved_rtplan is None:
                    approved_rtplan = info
                    if verbose:
                        print(f"      ✓ This is the APPROVED RTPLAN")
                else:
                    if verbose:
                        print(f"      ⚠ Multiple approved RTPLANs found!")
    
    if not approved_rtplan:
        chain.chain_status = "No approved RTPLAN found"
        if verbose:
            print(f"    ✗ No approved RTPLAN found")
        return chain
    
    chain.approved_rtplan = approved_rtplan
    chain.identification_method['rtplan'] = f"Approval Status (300E,0002) = 'APPROVED'"
    
    # Step 2: Find the referenced RTSTRUCT from the approved RTPLAN
    if verbose:
        print(f"\n  [Step 2] Finding clinical RTSTRUCT referenced by approved RTPLAN...")
        print(f"    RTPLAN references RTSTRUCT SOP UID: {approved_rtplan.referenced_rtstruct_sop_uid}")
    
    rtstruct_folder = os.path.join(patient_folder, 'RTSTRUCT')
    if not os.path.isdir(rtstruct_folder):
        rtstruct_folder = patient_folder
    
    rtstruct_files = find_dicom_files_recursive(rtstruct_folder, modality_filter='RTSTRUCT')
    
    if verbose:
        print(f"    Found {len(rtstruct_files)} RTSTRUCT file(s)")
    
    all_rtstructs = []
    clinical_rtstruct = None
    
    for rtstruct_path in rtstruct_files:
        info = read_rtstruct_info(rtstruct_path)
        if info:
            all_rtstructs.append(info)
            type_str = "Limbus AI" if info.is_limbus_ai else ("ARIA RADonc" if info.is_aria_radonc else "Unknown")
            if verbose:
                print(f"    - {os.path.basename(rtstruct_path)}: Type={type_str}, Label='{info.structure_set_label}'")
            
            # Check if this is the RTSTRUCT referenced by the approved RTPLAN
            if info.sop_instance_uid == approved_rtplan.referenced_rtstruct_sop_uid:
                clinical_rtstruct = info
                if verbose:
                    print(f"      ✓ This is the clinical RTSTRUCT referenced by RTPLAN")
    
    if not clinical_rtstruct:
        chain.chain_status = f"Clinical RTSTRUCT (SOP UID: {approved_rtplan.referenced_rtstruct_sop_uid[:20]}...) not found"
        if verbose:
            print(f"    ✗ Clinical RTSTRUCT not found by SOP Instance UID")
        return chain
    
    chain.clinical_rtstruct = clinical_rtstruct
    chain.identification_method['clinical_rtstruct'] = f"Referenced by approved RTPLAN (SOP UID match: {clinical_rtstruct.sop_instance_uid[:20]}...)"
    
    if not clinical_rtstruct.is_aria_radonc:
        if verbose:
            print(f"    ⚠ Warning: Clinical RTSTRUCT is not identified as ARIA RADonc (Model: {clinical_rtstruct.manufacturer_model_name})")
    
    # Step 3: Find the Limbus AI RTSTRUCT linked to the clinical RTSTRUCT
    if verbose:
        print(f"\n  [Step 3] Finding Limbus AI RTSTRUCT linked to clinical RTSTRUCT...")
    
    ai_rtstruct, link_method = search_for_limbus_reference_in_aria(clinical_rtstruct, all_rtstructs)
    
    if ai_rtstruct:
        chain.ai_rtstruct = ai_rtstruct
        chain.identification_method['ai_rtstruct'] = link_method
        if verbose:
            print(f"    ✓ Found Limbus AI RTSTRUCT: {os.path.basename(ai_rtstruct.path)}")
            print(f"      Method: {link_method}")
    else:
        if verbose:
            print(f"    ✗ {link_method}")
        chain.identification_method['ai_rtstruct'] = link_method
    
    # Step 4: Find the CT series referenced by the RTSTRUCTs
    if verbose:
        print(f"\n  [Step 4] Finding referenced CT series...")
    
    # Prefer the CT series referenced by the clinical RTSTRUCT
    ct_series_uid = clinical_rtstruct.referenced_ct_series_uid
    ct_source = "clinical RTSTRUCT"
    
    # If not available, try the AI RTSTRUCT
    if not ct_series_uid and ai_rtstruct:
        ct_series_uid = ai_rtstruct.referenced_ct_series_uid
        ct_source = "AI RTSTRUCT"
    
    if verbose:
        print(f"    Looking for CT Series UID: {ct_series_uid} (from {ct_source})")
    
    if ct_series_uid:
        ct_series = find_ct_series_info(patient_folder, ct_series_uid)
        if ct_series:
            chain.ct_series = ct_series
            chain.identification_method['ct_series'] = f"Referenced by {ct_source} (Series UID: {ct_series_uid[:20]}...)"
            if verbose:
                print(f"    ✓ Found CT series: {ct_series.num_slices} slices in {ct_series.folder_path}")
        else:
            if verbose:
                print(f"    ✗ CT series files not found in patient folder")
    else:
        if verbose:
            print(f"    ✗ No CT series reference found in RTSTRUCTs")
    
    # Step 5: Verify the chain
    if verbose:
        print(f"\n  [Step 5] Verifying chain consistency...")
    
    # Check Frame of Reference UIDs match
    frame_refs = set()
    if chain.approved_rtplan and chain.approved_rtplan.frame_of_reference_uid:
        frame_refs.add(('RTPLAN', chain.approved_rtplan.frame_of_reference_uid))
    if chain.clinical_rtstruct and chain.clinical_rtstruct.frame_of_reference_uid:
        frame_refs.add(('Clinical RTSTRUCT', chain.clinical_rtstruct.frame_of_reference_uid))
    if chain.ai_rtstruct and chain.ai_rtstruct.frame_of_reference_uid:
        frame_refs.add(('AI RTSTRUCT', chain.ai_rtstruct.frame_of_reference_uid))
    if chain.ct_series and chain.ct_series.frame_of_reference_uid:
        frame_refs.add(('CT', chain.ct_series.frame_of_reference_uid))
    
    unique_frame_refs = set(uid for name, uid in frame_refs)
    
    if len(unique_frame_refs) == 1:
        if verbose:
            print(f"    ✓ All objects share the same Frame of Reference UID")
        chain.chain_complete = True
        chain.chain_status = "Complete and verified"
    elif len(unique_frame_refs) > 1:
        if verbose:
            print(f"    ⚠ Warning: Multiple Frame of Reference UIDs found:")
            for name, uid in frame_refs:
                print(f"      - {name}: {uid[:30]}...")
        chain.chain_complete = (chain.approved_rtplan is not None and 
                                chain.clinical_rtstruct is not None and
                                chain.ct_series is not None)
        chain.chain_status = "Complete but Frame of Reference UIDs differ"
    else:
        chain.chain_complete = False
        chain.chain_status = "Incomplete - missing components"
    
    # Final summary
    if verbose:
        print(f"\n  {'='*76}")
        print(f"  CHAIN SUMMARY")
        print(f"  {'='*76}")
        print(f"  Status: {chain.chain_status}")
        print(f"  Approved RTPLAN: {'✓' if chain.approved_rtplan else '✗'}")
        print(f"  Clinical RTSTRUCT (ARIA): {'✓' if chain.clinical_rtstruct else '✗'}")
        print(f"  AI RTSTRUCT (Limbus): {'✓' if chain.ai_rtstruct else '✗'}")
        print(f"  CT Series: {'✓' if chain.ct_series else '✗'}")
        print(f"\n  Identification methods:")
        for key, method in chain.identification_method.items():
            print(f"    - {key}: {method}")
    
    return chain


def analyze_patients(dicom_root_folder: str, num_patients: int = 10, verbose: bool = True) -> pd.DataFrame:
    """
    Analyze multiple patients and identify their DICOM chains.
    
    Parameters
    ----------
    dicom_root_folder : str
        Root folder containing patient subdirectories
    num_patients : int
        Number of random patients to analyze
    verbose : bool
        Print detailed progress information
        
    Returns
    -------
    pd.DataFrame
        Results for all analyzed patients
    """
    print(f"Discovering patient folders in: {dicom_root_folder}")
    
    patient_folders = []
    for item in os.listdir(dicom_root_folder):
        item_path = os.path.join(dicom_root_folder, item)
        if os.path.isdir(item_path) and item.startswith('P'):
            patient_folders.append({'patient_id': item, 'patient_folder': item_path})
    
    if not patient_folders:
        print("No patient folders found.")
        return pd.DataFrame()
    
    print(f"Found {len(patient_folders)} patient folder(s)")
    
    # Randomly select patients
    num_to_analyze = min(num_patients, len(patient_folders))
    selected_patients = random.sample(patient_folders, num_to_analyze)
    print(f"Randomly selected {num_to_analyze} patient(s) for analysis")
    
    results = []
    
    for patient_data in selected_patients:
        chain = identify_dicom_chain(
            patient_data['patient_folder'],
            patient_data['patient_id'],
            verbose=verbose
        )
        
        result = {
            'patient_id': chain.patient_id,
            'chain_complete': chain.chain_complete,
            'chain_status': chain.chain_status,
            'has_approved_rtplan': chain.approved_rtplan is not None,
            'has_clinical_rtstruct': chain.clinical_rtstruct is not None,
            'has_ai_rtstruct': chain.ai_rtstruct is not None,
            'has_ct_series': chain.ct_series is not None,
            'rtplan_file': os.path.basename(chain.approved_rtplan.path) if chain.approved_rtplan else '',
            'clinical_rtstruct_file': os.path.basename(chain.clinical_rtstruct.path) if chain.clinical_rtstruct else '',
            'ai_rtstruct_file': os.path.basename(chain.ai_rtstruct.path) if chain.ai_rtstruct else '',
            'ct_series_uid': chain.ct_series.series_instance_uid if chain.ct_series else '',
            'ct_num_slices': chain.ct_series.num_slices if chain.ct_series else 0,
            'ai_rtstruct_identification_method': chain.identification_method.get('ai_rtstruct', ''),
        }
        
        results.append(result)
    
    return pd.DataFrame(results)


def get_dicom_chain_for_patient(patient_folder: str, patient_id: str) -> Optional[Dict]:
    """
    Get the DICOM chain for a patient in a format suitable for quantifycontourdifferences_P0728.py.
    
    This function is designed for integration into the main analysis script.
    
    Parameters
    ----------
    patient_folder : str
        Path to patient folder
    patient_id : str
        Patient identifier
        
    Returns
    -------
    Dict or None
        Dictionary with paths to all required files, or None if chain is incomplete
    """
    chain = identify_dicom_chain(patient_folder, patient_id, verbose=False)
    
    if not chain.chain_complete or not chain.ct_series or not chain.clinical_rtstruct:
        return None
    
    return {
        'patient_id': patient_id,
        'ct_series_uid': chain.ct_series.series_instance_uid,
        'ct_folder_path': chain.ct_series.folder_path,
        'ct_files': chain.ct_series.file_paths,
        'clinical_rtstruct_path': chain.clinical_rtstruct.path,
        'clinical_rtstruct_sop_uid': chain.clinical_rtstruct.sop_instance_uid,
        'ai_rtstruct_path': chain.ai_rtstruct.path if chain.ai_rtstruct else None,
        'ai_rtstruct_sop_uid': chain.ai_rtstruct.sop_instance_uid if chain.ai_rtstruct else None,
        'rtplan_path': chain.approved_rtplan.path,
        'rtplan_sop_uid': chain.approved_rtplan.sop_instance_uid,
        'frame_of_reference_uid': chain.ct_series.frame_of_reference_uid,
        'identification_methods': chain.identification_method
    }


def main():
    """Main execution function."""
    print("="*80)
    print("DICOM Chain Identification Tool")
    print("Identifies the complete reference chain: RTPLAN -> RTSTRUCT -> CT")
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
    results = analyze_patients(dicom_root_folder, num_patients, verbose=True)
    
    if not results.empty:
        print("\n" + "="*80)
        print("SUMMARY RESULTS")
        print("="*80)
        print(f"\nTotal patients analyzed: {len(results)}")
        print(f"Complete chains: {results['chain_complete'].sum()}")
        print(f"Incomplete chains: {(~results['chain_complete']).sum()}")
        print(f"With approved RTPLAN: {results['has_approved_rtplan'].sum()}")
        print(f"With clinical RTSTRUCT: {results['has_clinical_rtstruct'].sum()}")
        print(f"With AI RTSTRUCT: {results['has_ai_rtstruct'].sum()}")
        print(f"With CT series: {results['has_ct_series'].sum()}")
        
        # AI RTSTRUCT identification methods
        print(f"\nAI RTSTRUCT identification methods:")
        methods = results['ai_rtstruct_identification_method'].value_counts()
        for method, count in methods.items():
            if method:
                print(f"  - {method}: {count}")
        
        print("\n" + "="*80)
        print("DETAILED RESULTS")
        print("="*80)
        # Show key columns
        display_cols = ['patient_id', 'chain_complete', 'chain_status', 'has_ai_rtstruct', 'ai_rtstruct_identification_method']
        print(results[display_cols].to_string(index=False))
        
        # Save to Excel
        output_file = 'dicom_chain_analysis.xlsx'
        results.to_excel(output_file, index=False, engine='openpyxl')
        print(f"\nFull results saved to {output_file}")
    else:
        print("\nNo results generated - no valid patient data found.")


if __name__ == "__main__":
    main()
