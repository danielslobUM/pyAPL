"""
Inspect RTSTRUCT DICOM files to identify distinguishing metadata
between Limbus AI and ARIA RADonc structures
"""
import os
import sys
import pydicom
from pathlib import Path

def inspect_rtstruct(rtstruct_path):
    """
    Read and display key metadata from an RTSTRUCT file.
    
    Parameters
    ----------
    rtstruct_path : str
        Path to RTSTRUCT DICOM file
    """
    print(f"\n{'='*80}")
    print(f"File: {rtstruct_path}")
    print(f"{'='*80}")
    
    try:
        ds = pydicom.dcmread(rtstruct_path, stop_before_pixels=True)
        
        # Basic identification
        print(f"\n--- BASIC IDENTIFICATION ---")
        print(f"SOP Instance UID: {ds.get('SOPInstanceUID', 'N/A')}")
        print(f"Series Instance UID: {ds.get('SeriesInstanceUID', 'N/A')}")
        print(f"Study Instance UID: {ds.get('StudyInstanceUID', 'N/A')}")
        
        # Descriptive fields that might distinguish source
        print(f"\n--- DESCRIPTIVE FIELDS ---")
        print(f"Patient Name: {ds.get('PatientName', 'N/A')}")
        print(f"Patient ID: {ds.get('PatientID', 'N/A')}")
        print(f"Study Description: {ds.get('StudyDescription', 'N/A')}")
        print(f"Series Description: {ds.get('SeriesDescription', 'N/A')}")
        print(f"Structure Set Label: {ds.get('StructureSetLabel', 'N/A')}")
        print(f"Structure Set Name: {ds.get('StructureSetName', 'N/A')}")
        print(f"Structure Set Description: {ds.get('StructureSetDescription', 'N/A')}")
        
        # Date/Time information
        print(f"\n--- DATE/TIME ---")
        print(f"Structure Set Date: {ds.get('StructureSetDate', 'N/A')}")
        print(f"Structure Set Time: {ds.get('StructureSetTime', 'N/A')}")
        print(f"Series Date: {ds.get('SeriesDate', 'N/A')}")
        print(f"Series Time: {ds.get('SeriesTime', 'N/A')}")
        print(f"Study Date: {ds.get('StudyDate', 'N/A')}")
        print(f"Study Time: {ds.get('StudyTime', 'N/A')}")
        
        # Manufacturer/Software information
        print(f"\n--- MANUFACTURER/SOFTWARE ---")
        print(f"Manufacturer: {ds.get('Manufacturer', 'N/A')}")
        print(f"Manufacturer's Model Name: {ds.get('ManufacturerModelName', 'N/A')}")
        print(f"Software Versions: {ds.get('SoftwareVersions', 'N/A')}")
        print(f"Station Name: {ds.get('StationName', 'N/A')}")
        print(f"Institutional Department Name: {ds.get('InstitutionalDepartmentName', 'N/A')}")
        
        # Approval status
        print(f"\n--- APPROVAL STATUS ---")
        print(f"Approval Status: {ds.get('ApprovalStatus', 'N/A')}")
        
        # Structure Set ROI Sequence (first few structures)
        print(f"\n--- STRUCTURE NAMES (first 5) ---")
        if hasattr(ds, 'StructureSetROISequence') and ds.StructureSetROISequence:
            for idx, roi in enumerate(ds.StructureSetROISequence[:5]):
                roi_name = roi.get('ROIName', 'N/A')
                roi_number = roi.get('ROINumber', 'N/A')
                roi_generation_algorithm = roi.get('ROIGenerationAlgorithm', 'N/A')
                print(f"  [{idx+1}] ROI #{roi_number}: {roi_name} (Algorithm: {roi_generation_algorithm})")
        
        # Private tags that might contain vendor-specific info
        print(f"\n--- CHECKING FOR PRIVATE TAGS ---")
        private_tags = []
        for tag in ds.keys():
            if tag.group % 2 == 1:  # Odd group numbers are private
                try:
                    value = str(ds[tag].value)[:100]  # Limit length
                    private_tags.append((tag, value))
                except:
                    pass
        
        if private_tags:
            print(f"Found {len(private_tags)} private tags")
            for tag, value in private_tags[:10]:  # Show first 10
                print(f"  {tag}: {value}")
        else:
            print("No private tags found")
            
    except Exception as e:
        print(f"Error reading file: {str(e)}")
        import traceback
        traceback.print_exc()


def find_rtstruct_files(patient_folder):
    """
    Find all RTSTRUCT files in a patient folder.
    
    Parameters
    ----------
    patient_folder : str
        Path to patient folder
        
    Returns
    -------
    list
        List of paths to RTSTRUCT files
    """
    rtstruct_files = []
    rtstruct_folder = os.path.join(patient_folder, 'RTSTRUCT')
    
    if not os.path.isdir(rtstruct_folder):
        print(f"No RTSTRUCT folder found at {rtstruct_folder}")
        return rtstruct_files
    
    for root, dirs, files in os.walk(rtstruct_folder):
        for file in files:
            if file.lower().endswith('.dcm'):
                rtstruct_files.append(os.path.join(root, file))
    
    return rtstruct_files


if __name__ == '__main__':
    # You can provide a patient folder path as an argument
    if len(sys.argv) > 1:
        patient_folder = sys.argv[1]
    else:
        # Default: find first patient in DICOM root
        dicom_root = "Z:\\ICoNEA\\DICOM\\P0728C0006I13393418"
        
        if not os.path.exists(dicom_root):
            print(f"DICOM root not found: {dicom_root}")
            print("Please provide a patient folder path as an argument")
            sys.exit(1)
        
        # Find first patient folder
        patient_folders = [os.path.join(dicom_root, f) for f in os.listdir(dicom_root) 
                          if f.startswith('P') and os.path.isdir(os.path.join(dicom_root, f))]
        
        if not patient_folders:
            print("No patient folders found")
            sys.exit(1)
        
        patient_folder = patient_folders[0]
    
    print(f"Inspecting patient folder: {patient_folder}")
    
    # Find all RTSTRUCT files
    rtstruct_files = find_rtstruct_files(patient_folder)
    
    if not rtstruct_files:
        print("No RTSTRUCT files found")
    else:
        print(f"\nFound {len(rtstruct_files)} RTSTRUCT file(s)")
        
        # Inspect each file
        for rtstruct_file in rtstruct_files:
            inspect_rtstruct(rtstruct_file)
        
        # Summary comparison
        if len(rtstruct_files) >= 2:
            print(f"\n\n{'='*80}")
            print("COMPARISON SUMMARY")
            print(f"{'='*80}")
            print("\nTo determine which is Limbus AI vs ARIA RADonc, look for:")
            print("  - Manufacturer field (might say 'Limbus AI' or 'Varian')")
            print("  - Software Versions")
            print("  - Series Description or Structure Set Label")
            print("  - Station Name")
            print("  - Date/Time differences (which is older/newer)")
            print("  - ROI Generation Algorithm")
