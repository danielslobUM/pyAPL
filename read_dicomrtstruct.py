"""
read_dicomrtstruct - Read DICOM RTSTRUCT file

Reads DICOM RT Structure Set files and extracts contour information.
"""

import pydicom
import numpy as np


def read_dicomrtstruct(filename_in):
    """
    Read DICOM RTSTRUCT file and extract structure information.
    
    Parameters
    ----------
    filename_in : str
        Filename of the DICOM RTSTRUCT file including path
        
    Returns
    -------
    dict
        Dictionary containing RTSTRUCT information with fields:
        - FileName : str - Input filename
        - DicomHeader : pydicom.Dataset - DICOM header
        - StructNum : int - Number of structures
        - Struct : list of dict - List of structure information
        - StudyUID : str - Study instance UID
        - SOPInstanceUID : str - SOP instance UID
        - PlanID : str - Series description
        - ID : str - Patient ID
        - LastName : str - Patient last name
        - FirstName : str - Patient first name
        - StructureSetDate : str - Structure set date
        - StructureSetTime : str - Structure set time
        - FrameOfReference : str - Frame of reference UID
        - ReferencedCTSeriesUID : str - Referenced CT series UID
        - XiO, TrueD, Esoft, MAASTRO_CON : int - Manufacturer flags
        - HasForcedStructures : bool
        - ForcedStructuresList : list
    """
    # Read DICOM header
    dicom_header = pydicom.dcmread(filename_in, force=True)
    
    # Initialize output structure
    struct_out = {
        'FileName': filename_in,
        'DicomHeader': dicom_header,
        'StructNum': len(dicom_header.StructureSetROISequence),
    }
    
    # Extract study and patient information
    struct_out['StudyUID'] = dicom_header.StudyInstanceUID
    struct_out['SOPInstanceUID'] = dicom_header.SOPInstanceUID
    
    if hasattr(dicom_header, 'SeriesDescription'):
        struct_out['PlanID'] = dicom_header.SeriesDescription
    else:
        struct_out['PlanID'] = ''
    
    struct_out['ID'] = dicom_header.PatientID
    
    # Extract patient name
    if hasattr(dicom_header, 'PatientName'):
        patient_name = dicom_header.PatientName
        struct_out['LastName'] = str(patient_name.family_name) if hasattr(patient_name, 'family_name') else ' '
        struct_out['FirstName'] = str(patient_name.given_name) if hasattr(patient_name, 'given_name') else ' '
    else:
        struct_out['LastName'] = ' '
        struct_out['FirstName'] = ' '
    
    # Extract structure set date and time
    struct_out['StructureSetDate'] = getattr(dicom_header, 'StructureSetDate', ' ')
    struct_out['StructureSetTime'] = getattr(dicom_header, 'StructureSetTime', ' ')
    
    # Extract frame of reference
    if hasattr(dicom_header, 'ReferencedFrameOfReferenceSequence'):
        struct_out['FrameOfReference'] = dicom_header.ReferencedFrameOfReferenceSequence[0].FrameOfReferenceUID
        try:
            struct_out['ReferencedCTSeriesUID'] = (
                dicom_header.ReferencedFrameOfReferenceSequence[0]
                .RTReferencedStudySequence[0]
                .RTReferencedSeriesSequence[0]
                .SeriesInstanceUID
            )
        except:
            struct_out['ReferencedCTSeriesUID'] = ''
    else:
        struct_out['FrameOfReference'] = ' '
        struct_out['ReferencedCTSeriesUID'] = ''
    
    # Initialize manufacturer flags
    struct_out['XiO'] = 0
    struct_out['TrueD'] = 0
    struct_out['Esoft'] = 0
    struct_out['MAASTRO_CON'] = 0
    
    # Check manufacturer model
    if hasattr(dicom_header, 'ManufacturerModelName'):
        model = dicom_header.ManufacturerModelName
        if model in ['CMS, Inc.', 'XiO']:
            struct_out['XiO'] = 1
        elif model in ['Syngo MI Applications', 'e.soft']:
            struct_out['Esoft'] = 1
        elif model in ['MAASTRO clinic', 'MAASTRO_CON']:
            struct_out['MAASTRO_CON'] = 1
    
    # Check for TrueD
    try:
        label = getattr(dicom_header, 'StructureSetLabel', '').lower()
        desc = getattr(dicom_header, 'SeriesDescription', '').lower()
        name = getattr(dicom_header, 'StructureSetName', '').lower()
        if 'trued' in label or 'trued' in desc or 'trued' in name:
            struct_out['TrueD'] = 1
    except:
        pass
    
    # Extract structure information
    struct_out['Struct'] = []
    has_forced_structures = False
    forced_structures = []
    
    for struct_cur in range(struct_out['StructNum']):
        struct_info = {}
        roi_seq_item = dicom_header.StructureSetROISequence[struct_cur]
        
        struct_info['Name'] = roi_seq_item.ROIName
        struct_info['Number'] = roi_seq_item.ROINumber
        struct_info['Volume'] = getattr(roi_seq_item, 'ROIVolume', 0)
        struct_info['Type'] = None
        struct_info['Forced'] = 0
        struct_info['RelativeElectronDensity'] = None
        
        # Extract ROI observations
        if hasattr(dicom_header, 'RTROIObservationsSequence'):
            obs_item = dicom_header.RTROIObservationsSequence[struct_cur]
            
            if hasattr(obs_item, 'RTROIInterpretedType'):
                struct_info['Type'] = obs_item.RTROIInterpretedType
            
            if hasattr(obs_item, 'ROIPhysicalPropertiesSequence'):
                for prop_item in obs_item.ROIPhysicalPropertiesSequence:
                    if getattr(prop_item, 'ROIPhysicalProperty', '') == 'REL_ELEC_DENSITY':
                        has_forced_structures = True
                        forced_structures.append(struct_cur)
                        struct_info['Forced'] = 1
                        struct_info['RelativeElectronDensity'] = prop_item.ROIPhysicalPropertyValue
        
        # Extract contour data
        try:
            contour_seq_item = dicom_header.ROIContourSequence[struct_cur]
            
            if hasattr(contour_seq_item, 'ContourSequence'):
                first_contour = contour_seq_item.ContourSequence[0]
                geom_type = getattr(first_contour, 'ContourGeometricType', '')
                struct_info['ClosedPlanar'] = 1 if geom_type == 'CLOSED_PLANAR' else 0
                
                # Extract slice data
                struct_info['Slice'] = []
                for slice_item in contour_seq_item.ContourSequence:
                    contour_data = slice_item.ContourData
                    slice_data = {
                        'X': np.array(contour_data[0::3]) / 10.0,  # Convert mm to cm
                        'Y': np.array(contour_data[2::3]) / 10.0,  # Convert mm to cm (Z in DICOM)
                        'Z': -np.array(contour_data[1::3]) / 10.0  # Convert mm to cm and negate
                    }
                    struct_info['Slice'].append(slice_data)
                
                struct_info['SliceNum'] = len(struct_info['Slice'])
            else:
                struct_info['ClosedPlanar'] = 0
                struct_info['Slice'] = []
                struct_info['SliceNum'] = 0
        except:
            struct_info['ClosedPlanar'] = 0
            struct_info['Slice'] = []
            struct_info['SliceNum'] = 0
        
        struct_out['Struct'].append(struct_info)
    
    struct_out['HasForcedStructures'] = has_forced_structures
    struct_out['ForcedStructuresList'] = forced_structures
    
    return struct_out
