"""
read_dicomct_light - Lightweight DICOM CT reader

This is a lightweight version of read_dicomct. Compared to that function it does not 
read out the actual imaging data and also skips header information for all slices 
except the slice with the lowest Y value.

History
-------
17/02/2025, Rik Hansen - Creation
Converted to Python
"""

import numpy as np
import pydicom


def read_dicomct_light(filenames_in, read_image_data=True):
    """
    Read DICOM CT metadata (lightweight version without full image data).
    
    Parameters
    ----------
    filenames_in : list of str
        Full filenames of the CT DICOM files
    read_image_data : bool, optional
        If True, create empty image placeholder. Default is True.
        
    Returns
    -------
    dict
        Dictionary containing CT metadata:
        - Filenames : list of str - Sorted filenames
        - DicomHeader : pydicom.Dataset - DICOM header of first slice
        - PixelSpacingXi : float - Pixel spacing in cm/pixel X
        - PixelSpacingYi : float - Pixel spacing in cm/pixel Y  
        - PixelSpacingZi : float - Pixel spacing in cm/pixel Z
        - PixelNumXi : int - Number of pixels X
        - PixelNumYi : int - Number of pixels Y
        - PixelNumZi : int - Number of pixels Z
        - PixelFirstXi : float - X value of pixel 1 in cm
        - PixelFirstYi : float - Y value of pixel 1 in cm
        - PixelFirstZi : float - Z value of pixel 1 in cm
        - Image : ndarray - Empty placeholder array (if read_image_data=True)
    """
    slice_num = len(filenames_in)
    
    # Check for valid input
    if slice_num == 2 and '.' in filenames_in[0] and '..' in filenames_in[1]:
        return None
    
    # Read first two slices for slice-spacing derivation
    yi = []
    for slice_cur in range(slice_num):
        dcm = pydicom.dcmread(filenames_in[slice_cur], stop_before_pixels=True)
        image_position_patient = dcm.ImagePositionPatient
        yi.append([slice_cur, float(image_position_patient[2])])
    
    # Get unique Y positions and sort
    yi = np.array(yi)
    _, unique_indices = np.unique(yi[:, 1], return_index=True)
    yi = yi[unique_indices]
    slice_num = len(yi)
    
    # Sort by Y position
    sorted_indices = np.argsort(yi[:, 1])
    slice_value_y_sorted = yi[sorted_indices]
    
    # Create output structure
    ctout = {}
    ctout['Filenames'] = [filenames_in[int(idx)] for idx in slice_value_y_sorted[:, 0]]
    
    # Read the first DICOM header
    ctout['DicomHeader'] = pydicom.dcmread(ctout['Filenames'][0], stop_before_pixels=True)
    
    # Store pixel spacing information (convert mm to cm)
    ctout['PixelSpacingXi'] = float(ctout['DicomHeader'].PixelSpacing[0]) / 10.0
    
    # Calculate Y spacing from slice positions
    if len(yi) > 1:
        y_slice_thicknesses = np.abs(np.unique(np.round((yi[:-1, 1] - yi[1:, 1]) * 1000) / 1000))
        if len(y_slice_thicknesses) > 0:
            ctout['PixelSpacingYi'] = y_slice_thicknesses[0] / 10.0
        else:
            ctout['PixelSpacingYi'] = float(ctout['DicomHeader'].SliceThickness) / 10.0
    else:
        ctout['PixelSpacingYi'] = float(ctout['DicomHeader'].SliceThickness) / 10.0
    
    ctout['PixelSpacingZi'] = float(ctout['DicomHeader'].PixelSpacing[1]) / 10.0
    
    # Store image dimensions
    ctout['PixelNumXi'] = int(ctout['DicomHeader'].Columns)
    ctout['PixelNumYi'] = len(ctout['Filenames'])
    ctout['PixelNumZi'] = int(ctout['DicomHeader'].Rows)
    
    # Calculate first pixel positions
    image_orientation = np.array(ctout['DicomHeader'].ImageOrientationPatient)
    reference_orientation = np.array([1, 0, 0, 0, 1, 0])
    
    if np.sum(np.abs(image_orientation - reference_orientation) > 0.025) == 0:
        image_position = np.array(ctout['DicomHeader'].ImagePositionPatient)
        
        ctout['PixelFirstXi'] = (image_position[0] / 10.0) - \
                                (1 if image_orientation[0] == -1 else 0) * \
                                (ctout['PixelSpacingXi'] * ctout['PixelNumXi'])
        
        ctout['PixelFirstYi'] = image_position[2] / 10.0
        
        ctout['PixelFirstZi'] = (-image_position[1] / 10.0) - \
                                image_orientation[4] * \
                                (ctout['PixelSpacingZi'] * (ctout['PixelNumZi'] - 1))
    else:
        ctout['PixelFirstXi'] = None
        ctout['PixelFirstYi'] = None
        ctout['PixelFirstZi'] = None
    
    # Create empty image placeholder if requested
    if read_image_data:
        ctout['Image'] = np.zeros((ctout['PixelNumXi'], 
                                   ctout['PixelNumYi'], 
                                   ctout['PixelNumZi']))
    
    return ctout
