"""
Script to recursively read DICOM files and create an Excel inventory.
Designed to help compare manual vs AI-based RT STRUCT files for each CT series.
"""

import os
import pydicom
from pydicom.errors import InvalidDicomError
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def extract_dicom_info(dicom_path: str) -> Optional[Dict]:
    """
    Extract relevant DICOM tags from a file.
    
    Args:
        dicom_path: Path to DICOM file
        
    Returns:
        Dictionary with extracted information or None if not a valid DICOM
    """
    try:
        ds = pydicom.dcmread(dicom_path, force=True)
        
        # Basic information for all modalities
        info = {
            'filepath': str(Path(dicom_path).parent),
            'filename': Path(dicom_path).name,
            'modality': getattr(ds, 'Modality', 'UNKNOWN'),
            'sop_instance_uid': getattr(ds, 'SOPInstanceUID', ''),
            'series_instance_uid': getattr(ds, 'SeriesInstanceUID', ''),
            'series_description': getattr(ds, 'SeriesDescription', ''),
            'patient_id': getattr(ds, 'PatientID', ''),
            'study_instance_uid': getattr(ds, 'StudyInstanceUID', ''),
        }
        
        # RT STRUCT specific information
        if info['modality'] == 'RTSTRUCT':
            # Get referenced CT series
            referenced_series = []
            if hasattr(ds, 'ReferencedFrameOfReferenceSequence'):
                for frame_ref in ds.ReferencedFrameOfReferenceSequence:
                    if hasattr(frame_ref, 'RTReferencedStudySequence'):
                        for study_ref in frame_ref.RTReferencedStudySequence:
                            if hasattr(study_ref, 'RTReferencedSeriesSequence'):
                                for series_ref in study_ref.RTReferencedSeriesSequence:
                                    series_uid = getattr(series_ref, 'SeriesInstanceUID', '')
                                    if series_uid:
                                        referenced_series.append(series_uid)
            
            info['referenced_ct_series_uid'] = '; '.join(referenced_series) if referenced_series else ''
            
            # Get creator information
            info['structure_set_label'] = getattr(ds, 'StructureSetLabel', '')
            info['structure_set_name'] = getattr(ds, 'StructureSetName', '')
            info['structure_set_date'] = getattr(ds, 'StructureSetDate', '')
            info['structure_set_time'] = getattr(ds, 'StructureSetTime', '')
            
            # Get operator/creator information
            info['operators_name'] = getattr(ds, 'OperatorsName', '')
            info['manufacturer'] = getattr(ds, 'Manufacturer', '')
            info['manufacturer_model_name'] = getattr(ds, 'ManufacturerModelName', '')
            info['software_versions'] = getattr(ds, 'SoftwareVersions', '')
            
            # Try to identify if it's manual or AI-based
            label = info['structure_set_label'].lower()
            name = info['structure_set_name'].lower()
            manufacturer = info['manufacturer'].lower()
            
            if any(keyword in label or keyword in name or keyword in manufacturer 
                   for keyword in ['ai', 'auto', 'automatic', 'dl', 'deep', 'learning', 'neural']):
                info['rtstruct_type'] = 'AI'
            elif any(keyword in label or keyword in name 
                     for keyword in ['manual', 'physician', 'clinician']):
                info['rtstruct_type'] = 'MANUAL'
            else:
                info['rtstruct_type'] = 'UNKNOWN'
                
        else:
            # Set RT STRUCT columns to empty for non-RTSTRUCT files
            info['referenced_ct_series_uid'] = ''
            info['structure_set_label'] = ''
            info['structure_set_name'] = ''
            info['structure_set_date'] = ''
            info['structure_set_time'] = ''
            info['operators_name'] = ''
            info['manufacturer'] = ''
            info['manufacturer_model_name'] = ''
            info['software_versions'] = ''
            info['rtstruct_type'] = ''
        
        return info
        
    except InvalidDicomError:
        logger.debug(f"Not a valid DICOM file: {dicom_path}")
        return None
    except Exception as e:
        logger.warning(f"Error reading {dicom_path}: {str(e)}")
        return None


def discover_patient_folders(root_folder: str) -> List[str]:
    """
    Discover patient folders at the top level of the DICOM directory.
    Patient folders typically start with 'P'.
    
    Args:
        root_folder: Root directory containing patient folders
        
    Returns:
        List of patient folder paths
    """
    patient_folders = []
    
    try:
        for item in os.listdir(root_folder):
            item_path = os.path.join(root_folder, item)
            if os.path.isdir(item_path) and item.startswith('P'):
                patient_folders.append(item_path)
    except PermissionError as e:
        logger.warning(f"Permission denied accessing {root_folder}: {e}")
    
    return sorted(patient_folders)


def scan_dicom_folder(root_folder: str, max_patients: int = None) -> List[Dict]:
    """
    Scan DICOM folder organized by patient directories.
    Stops completely after processing max_patients.
    
    Args:
        root_folder: Root directory containing patient folders (e.g., Z:\\ICoNEA\\DICOM)
        max_patients: Maximum number of patients to process (None = all)
        
    Returns:
        List of dictionaries containing DICOM information
    """
    dicom_data = []
    file_count = 0
    error_count = 0
    
    logger.info(f"Scanning folder: {root_folder}")
    
    # First, discover patient folders
    patient_folders = discover_patient_folders(root_folder)
    total_patients = len(patient_folders)
    
    if total_patients == 0:
        logger.warning(f"No patient folders (starting with 'P') found in {root_folder}")
        logger.info("Falling back to recursive scan...")
        # Fallback to simple recursive scan if no patient folders found
        return scan_dicom_folder_recursive(root_folder, max_patients)
    
    logger.info(f"Found {total_patients} patient folder(s)")
    
    # Limit patients if specified
    if max_patients and max_patients > 0:
        patient_folders = patient_folders[:max_patients]
        logger.info(f"Processing first {len(patient_folders)} patient(s)")
    
    # Process each patient folder
    for patient_idx, patient_folder in enumerate(patient_folders):
        patient_id = os.path.basename(patient_folder)
        logger.info(f"[{patient_idx + 1}/{len(patient_folders)}] Processing patient: {patient_id}")
        
        # Scan all files within this patient folder
        for root, dirs, files in os.walk(patient_folder):
            current_subfolder = os.path.relpath(root, patient_folder)
            
            for filename in files:
                # Skip common non-DICOM files
                if filename.lower().endswith(('.xml', '.txt', '.pdf', '.jpg', '.png', '.exe', '.ttl')):
                    continue
                    
                filepath = os.path.join(root, filename)
                file_count += 1
                
                # Progress update every 100 files
                if file_count % 100 == 0:
                    logger.info(f"  Progress: {file_count} files | {len(dicom_data)} DICOM | Current: {current_subfolder}")
                
                info = extract_dicom_info(filepath)
                if info:
                    dicom_data.append(info)
                else:
                    error_count += 1
        
        logger.info(f"  Patient {patient_id} done: {len(dicom_data)} total DICOM files so far")
    
    logger.info(f"Scan complete: {len(patient_folders)} patients, {file_count} files processed, "
               f"{len(dicom_data)} DICOM files found, {error_count} errors/non-DICOM")
    return dicom_data


def scan_dicom_folder_recursive(root_folder: str, max_patients: int = None) -> List[Dict]:
    """
    Fallback: Recursively scan folder for DICOM files (when no patient folder structure).
    
    Args:
        root_folder: Root directory to start scanning
        max_patients: Maximum number of unique patient IDs to include (None = all)
        
    Returns:
        List of dictionaries containing DICOM information
    """
    dicom_data = []
    file_count = 0
    error_count = 0
    unique_patients = set()
    
    logger.info(f"Recursive scan of: {root_folder}")
    if max_patients:
        logger.info(f"Will stop after {max_patients} unique patient(s)")
    
    for root, dirs, files in os.walk(root_folder):
        # Check if we've reached patient limit - stop completely
        if max_patients and len(unique_patients) >= max_patients:
            logger.info(f"Reached {max_patients} patients. Stopping scan.")
            break
        
        current_folder = os.path.basename(root) if os.path.basename(root) else root
        
        for filename in files:
            if filename.lower().endswith(('.xml', '.txt', '.pdf', '.jpg', '.png', '.exe', '.ttl')):
                continue
                
            filepath = os.path.join(root, filename)
            file_count += 1
            
            if file_count % 100 == 0:
                logger.info(f"Progress: {file_count} files | {len(dicom_data)} DICOM | "
                          f"{len(unique_patients)} patients | Current: {current_folder}")
            
            info = extract_dicom_info(filepath)
            if info:
                patient_id = info.get('patient_id', '')
                if patient_id:
                    if max_patients and patient_id not in unique_patients and len(unique_patients) >= max_patients:
                        continue  # Skip this file, patient limit reached
                    unique_patients.add(patient_id)
                
                dicom_data.append(info)
            else:
                error_count += 1
    
    logger.info(f"Scan complete: {file_count} files, {len(dicom_data)} DICOM, "
               f"{len(unique_patients)} patients, {error_count} errors")
    return dicom_data


def create_excel_report(dicom_data: List[Dict], output_file: str):
    """
    Create Excel file with DICOM inventory.
    Organizes data to make manual vs AI RT STRUCT comparison easy.
    
    Args:
        dicom_data: List of DICOM information dictionaries
        output_file: Path to output Excel file
    """
    if not dicom_data:
        logger.warning("No DICOM data to export")
        return
    
    df = pd.DataFrame(dicom_data)
    
    # Define column order for clarity
    columns_order = [
        'patient_id',
        'study_instance_uid',
        'modality',
        'series_instance_uid',
        'series_description',
        'sop_instance_uid',
        'referenced_ct_series_uid',
        'rtstruct_type',
        'structure_set_label',
        'structure_set_name',
        'structure_set_date',
        'structure_set_time',
        'operators_name',
        'manufacturer',
        'manufacturer_model_name',
        'software_versions',
        'filepath',
        'filename',
    ]
    
    # Reorder columns (only include existing columns)
    existing_columns = [col for col in columns_order if col in df.columns]
    df = df[existing_columns]
    
    # Sort: by patient, study, modality (CT first, then RTSTRUCT), then series
    df = df.sort_values(
        by=['patient_id', 'study_instance_uid', 'modality', 'series_instance_uid'],
        ascending=[True, True, True, True]
    )
    
    # Create Excel writer with multiple sheets
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        # Sheet 1: All DICOM files
        df.to_excel(writer, sheet_name='All_DICOM_Files', index=False)
        
        # Sheet 2: Only RT STRUCTs grouped by CT series
        rtstruct_df = df[df['modality'] == 'RTSTRUCT'].copy()
        if not rtstruct_df.empty:
            rtstruct_df = rtstruct_df.sort_values(
                by=['patient_id', 'referenced_ct_series_uid', 'rtstruct_type', 'structure_set_label']
            )
            rtstruct_df.to_excel(writer, sheet_name='RTSTRUCT_Comparison', index=False)
        
        # Sheet 3: Only CT series
        ct_df = df[df['modality'] == 'CT'].copy()
        if not ct_df.empty:
            # Get unique CT series (not individual slices)
            ct_series = ct_df.groupby('series_instance_uid').first().reset_index()
            ct_series.to_excel(writer, sheet_name='CT_Series', index=False)
        
        # Sheet 4: Summary statistics
        summary_data = {
            'Metric': [
                'Total DICOM Files',
                'Total CT Slices',
                'Unique CT Series',
                'Total RT STRUCT Files',
                'Manual RT STRUCTs',
                'AI RT STRUCTs',
                'Unknown RT STRUCTs',
                'Unique Patients',
                'Unique Studies'
            ],
            'Count': [
                len(df),
                len(df[df['modality'] == 'CT']),
                df[df['modality'] == 'CT']['series_instance_uid'].nunique() if 'CT' in df['modality'].values else 0,
                len(df[df['modality'] == 'RTSTRUCT']),
                len(rtstruct_df[rtstruct_df['rtstruct_type'] == 'MANUAL']) if not rtstruct_df.empty else 0,
                len(rtstruct_df[rtstruct_df['rtstruct_type'] == 'AI']) if not rtstruct_df.empty else 0,
                len(rtstruct_df[rtstruct_df['rtstruct_type'] == 'UNKNOWN']) if not rtstruct_df.empty else 0,
                df['patient_id'].nunique(),
                df['study_instance_uid'].nunique()
            ]
        }
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
        
        # Auto-adjust column widths
        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if cell.value:
                            max_length = max(max_length, len(str(cell.value)))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)  # Cap at 50 characters
                worksheet.column_dimensions[column_letter].width = adjusted_width
    
    logger.info(f"Excel report created: {output_file}")
    logger.info(f"Total records: {len(df)}")
    if not rtstruct_df.empty:
        logger.info(f"RT STRUCTs: {len(rtstruct_df)} (Manual: {len(rtstruct_df[rtstruct_df['rtstruct_type'] == 'MANUAL'])}, "
                   f"AI: {len(rtstruct_df[rtstruct_df['rtstruct_type'] == 'AI'])}, "
                   f"Unknown: {len(rtstruct_df[rtstruct_df['rtstruct_type'] == 'UNKNOWN'])})")


def main():
    """Main execution function."""
    # Configuration
    root_folder = input("Enter the root DICOM folder path: ").strip('"').strip("'")
    
    if not os.path.exists(root_folder):
        logger.error(f"Folder does not exist: {root_folder}")
        return
    
    # Ask for maximum number of unique patients
    max_patients_input = input("Maximum number of unique patient IDs to process (press Enter for all): ").strip()
    max_patients = None
    if max_patients_input:
        try:
            max_patients = int(max_patients_input)
            if max_patients <= 0:
                logger.warning("Invalid number, processing all patients")
                max_patients = None
        except ValueError:
            logger.warning("Invalid input, processing all patients")
            max_patients = None
    
    # Default output file in the same directory as the script
    script_dir = Path(__file__).parent
    output_file = script_dir / "dicom_inventory.xlsx"
    
    custom_output = input(f"Output Excel file (press Enter for '{output_file}'): ").strip('"').strip("'")
    if custom_output:
        output_file = Path(custom_output)
    
    logger.info("Starting DICOM scan...")
    dicom_data = scan_dicom_folder(root_folder, max_patients)
    
    if dicom_data:
        logger.info("Creating Excel report...")
        create_excel_report(dicom_data, str(output_file))
        logger.info("Done!")
    else:
        logger.warning("No DICOM files found!")


if __name__ == "__main__":
    main()
