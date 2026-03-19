"""
read_dicomrtplan - Read DICOM RTPLAN file

Reads DICOM RT Plan files and extracts plan metadata.

History
-------
30/12/2025 - Created for RTPLAN metadata extraction
"""

import pydicom
import warnings


def read_dicomrtplan(filename_in):
    """
    Read DICOM RTPLAN file and extract plan metadata.
    
    Parameters
    ----------
    filename_in : str
        Filename of the DICOM RTPLAN file including path
        
    Returns
    -------
    dict
        Dictionary containing RTPLAN information with fields:
        - FileName : str - Input filename
        - DicomHeader : pydicom.Dataset - DICOM header
        - StudyUID : str - Study instance UID
        - SOPInstanceUID : str - SOP instance UID
        - PatientID : str - Patient ID
        - PatientName : str - Patient name
        - StudyDescription : str - Study Description (0008,1030)
        - RTPlanName : str - RT Plan Name (300A,0003)
        - NumberOfFractionsPlanned : int - Number of Fractions Planned (300A,0078)
        - TargetPrescriptionDose : float - Target Prescription Dose (300A,0026)
        - DoseReferenceDescription : str - Dose Reference Description (300A,0016)
        - ReferencedDoseSequence : list - Referenced Dose Sequence (300C,0080)
        - SetupTechniqueDescription : str - Setup Technique Description (300A,01B2)
    """
    try:
        # Read DICOM header
        dicom_header = pydicom.dcmread(filename_in, force=True)
        
        # Initialize output structure
        plan_out = {
            'FileName': filename_in,
            'DicomHeader': dicom_header,
        }
        
        # Extract basic identifiers
        plan_out['StudyUID'] = getattr(dicom_header, 'StudyInstanceUID', 'N/A')
        plan_out['SOPInstanceUID'] = getattr(dicom_header, 'SOPInstanceUID', 'N/A')
        
        # Extract patient information
        plan_out['PatientID'] = getattr(dicom_header, 'PatientID', 'N/A')
        
        if hasattr(dicom_header, 'PatientName'):
            patient_name = dicom_header.PatientName
            plan_out['PatientName'] = str(patient_name)
        else:
            plan_out['PatientName'] = 'N/A'
        
        # Extract requested DICOM metadata
        
        # StudyDescription (0008,1030)
        plan_out['StudyDescription'] = getattr(dicom_header, 'StudyDescription', 'N/A')
        
        # RT Plan Name (300A,0003)
        plan_out['RTPlanName'] = getattr(dicom_header, 'RTPlanName', 'N/A')
        
        # Number of Fractions Planned (300A,0078) - from FractionGroupSequence
        plan_out['NumberOfFractionsPlanned'] = 'N/A'
        if hasattr(dicom_header, 'FractionGroupSequence') and len(dicom_header.FractionGroupSequence) > 0:
            first_fraction_group = dicom_header.FractionGroupSequence[0]
            fractions = getattr(first_fraction_group, 'NumberOfFractionsPlanned', None)
            if fractions is not None:
                plan_out['NumberOfFractionsPlanned'] = int(fractions)
        
        # Target Prescription Dose (300A,0026) and Dose Reference Description (300A,0016) - from DoseReferenceSequence
        plan_out['TargetPrescriptionDose'] = 'N/A'
        plan_out['DoseReferenceDescription'] = 'N/A'
        if hasattr(dicom_header, 'DoseReferenceSequence') and len(dicom_header.DoseReferenceSequence) > 0:
            # Try to find target prescription dose and description from first dose reference
            for dose_ref in dicom_header.DoseReferenceSequence:
                target_dose = getattr(dose_ref, 'TargetPrescriptionDose', None)
                if target_dose is not None:
                    plan_out['TargetPrescriptionDose'] = float(target_dose)
                    # Also extract Dose Reference Description
                    dose_ref_desc = getattr(dose_ref, 'DoseReferenceDescription', None)
                    if dose_ref_desc is not None:
                        plan_out['DoseReferenceDescription'] = str(dose_ref_desc)
                    break  # Use first available target prescription dose
        
        # Referenced Dose Sequence (300C,0080) - from FractionGroupSequence
        plan_out['ReferencedDoseSequence'] = []
        if hasattr(dicom_header, 'FractionGroupSequence'):
            for fraction_group in dicom_header.FractionGroupSequence:
                if hasattr(fraction_group, 'ReferencedDoseSequence'):
                    for ref_dose in fraction_group.ReferencedDoseSequence:
                        ref_dose_info = {
                            'ReferencedDoseReferenceUID': getattr(ref_dose, 'ReferencedDoseReferenceUID', 'N/A'),
                            'DoseReferenceStructureType': getattr(ref_dose, 'DoseReferenceStructureType', 'N/A')
                        }
                        plan_out['ReferencedDoseSequence'].append(ref_dose_info)
        
        # Setup Technique Description (300A,01B2) - from PatientSetupSequence
        plan_out['SetupTechniqueDescription'] = 'N/A'
        if hasattr(dicom_header, 'PatientSetupSequence') and len(dicom_header.PatientSetupSequence) > 0:
            first_setup = dicom_header.PatientSetupSequence[0]
            setup_desc = getattr(first_setup, 'SetupTechniqueDescription', None)
            if setup_desc is not None:
                plan_out['SetupTechniqueDescription'] = str(setup_desc)
        
        # Referenced Structure Set Sequence (300C,0060) - Link to RTSTRUCT
        plan_out['ReferencedStructureSetSequence'] = []
        if hasattr(dicom_header, 'ReferencedStructureSetSequence'):
            print(f"    [RTPLAN] ✓ Found tag (300C,0060) - Referenced Structure Set Sequence")
            for idx, ref_struct in enumerate(dicom_header.ReferencedStructureSetSequence):
                if hasattr(ref_struct, 'ReferencedSOPInstanceUID'):
                    referenced_uid = ref_struct.ReferencedSOPInstanceUID
                    print(f"    [RTPLAN] ✓ Found tag (0008,1155) - Referenced SOP Instance UID: {referenced_uid}")
                    plan_out['ReferencedStructureSetSequence'].append({
                        'ReferencedSOPInstanceUID': referenced_uid,
                        'ReferencedSOPClassUID': getattr(ref_struct, 'ReferencedSOPClassUID', 'N/A')
                    })
                else:
                    print(f"    [RTPLAN] ✗ Tag (0008,1155) NOT found in Referenced Structure Set Sequence item {idx}")
        else:
            print(f"    [RTPLAN] ✗ Tag (300C,0060) - Referenced Structure Set Sequence NOT found")
        
        return plan_out
        
    except Exception as e:
        warnings.warn(f"Error reading RTPLAN file {filename_in}: {str(e)}")
        return None


if __name__ == '__main__':
    # Test the function
    import sys
    if len(sys.argv) > 1:
        rtplan_file = sys.argv[1]
        plan_data = read_dicomrtplan(rtplan_file)
        if plan_data:
            print("\nRTPLAN Metadata:")
            print(f"  Patient ID: {plan_data['PatientID']}")
            print(f"  Study Description: {plan_data['StudyDescription']}")
            print(f"  RT Plan Name: {plan_data['RTPlanName']}")
            print(f"  Number of Fractions Planned: {plan_data['NumberOfFractionsPlanned']}")
            print(f"  Target Prescription Dose: {plan_data['TargetPrescriptionDose']}")
            print(f"  Dose Reference Description: {plan_data['DoseReferenceDescription']}")
            print(f"  Setup Technique Description: {plan_data['SetupTechniqueDescription']}")
            print(f"  Referenced Dose Sequence: {plan_data['ReferencedDoseSequence']}")
    else:
        print("Usage: python read_dicomrtplan.py <path_to_rtplan_file.dcm>")
