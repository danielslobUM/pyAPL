"""
read_dicomct - Read DICOM CT and apply IEC convention

Reads DICOM CT images from low to high Y and fills the structure with images 
according to the IEC convention.

This CT is given in the image coordinate system:
              -----------         IEC
             /|         /|         Z
            / |        / |        /|
           /  |       /  |         |   /| Y
          /   |      /   |         |   /
         /    ------/----          |  /
         ----/------    /          | /
        |   /      |   /           |/
        |  /       |  /     X------|----------------->
        | /        | /            /|
        |/         |/            / |
        ------------

PixelFirst coordinates will be the bottom-left-corner. The CT cube will
be addressed in the following way CT.Image(1:Width,1:Depth,1:Height) or
CT.Image(X,Y,Z)

History
-------
Original MATLAB version by Andre Dekker, Lucas Persoon, Wouter van Elmpt, 
Bas Nijsten @ MAASTRO (2005-2012)
Converted to Python
"""

import numpy as np
import pydicom


def read_dicomct(filenames_in, read_image_data=True):
    """
    Read DICOM CT and apply IEC convention.
    
    Parameters
    ----------
    filenames_in : list of str
        Full filenames of the CT DICOM files
    read_image_data : bool, optional
        If True, read the actual CT image data. Default is True.
        
    Returns
    -------
    dict or None
        Dictionary containing CT information:
        - Filenames : list of str - Sorted filenames
        - UIDs : list of str - SOP instance UIDs
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
        - RescaleIntercept : float - Offset to convert to Hounsfield units
        - RescaleSlope : float - Slope to convert to Hounsfield units
        - Model : str - Manufacturer model name
        - Manufacturer : str - Manufacturer
        - Institute : str - Institution name
        - TableHeight : float - Table height
        - PrivTableHeight : float - Private table height
        - MachineName : str - Machine name (if available)
        - HUToRED : ndarray - HU to RED conversion (if available)
        - Image : ndarray - CT image (if read_image_data=True)
        
        Returns None if invalid input is provided.
    """
    slice_num = len(filenames_in)
    
    # Check for valid input
    if slice_num == 2 and '.' in filenames_in[0] and '..' in filenames_in[1]:
        return None
    
    # Sort the DICOM files from low to high slice Y value
    yi = []
    uids = []
    
    for slice_cur in range(slice_num):
        dicom_header = pydicom.dcmread(filenames_in[slice_cur], stop_before_pixels=True)
        yi.append([slice_cur, float(dicom_header.ImagePositionPatient[2])])
        uids.append(dicom_header.SOPInstanceUID)
    
    # Get unique Y positions
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
    ctout['UIDs'] = [uids[int(idx)] for idx in slice_value_y_sorted[:, 0]]
    
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
    
    # Calculate first pixel positions using IEC convention
    image_orientation = np.array(ctout['DicomHeader'].ImageOrientationPatient)
    reference_orientation = np.array([1, 0, 0, 0, 1, 0])
    
    if np.sum(np.abs(image_orientation - reference_orientation) > 0.025) == 0:
        image_position = np.array(ctout['DicomHeader'].ImagePositionPatient)
        
        ctout['PixelFirstXi'] = (image_position[0] / 10.0) - \
                                (image_orientation[0] == -1) * \
                                (ctout['PixelSpacingXi'] * ctout['PixelNumXi'])
        
        ctout['PixelFirstYi'] = image_position[2] / 10.0
        
        ctout['PixelFirstZi'] = (-image_position[1] / 10.0) - \
                                image_orientation[4] * \
                                (ctout['PixelSpacingZi'] * (ctout['PixelNumZi'] - 1))
    else:
        ctout['PixelFirstXi'] = None
        ctout['PixelFirstYi'] = None
        ctout['PixelFirstZi'] = None
    
    # Store rescale parameters
    ctout['RescaleIntercept'] = float(ctout['DicomHeader'].RescaleIntercept)
    ctout['RescaleSlope'] = float(ctout['DicomHeader'].RescaleSlope)
    
    # Store manufacturer information
    if hasattr(ctout['DicomHeader'], 'ManufacturerModelName'):
        ctout['Model'] = ctout['DicomHeader'].ManufacturerModelName
    else:
        ctout['Model'] = None
    
    ctout['Manufacturer'] = ctout['DicomHeader'].Manufacturer
    
    # Store institution information
    ctout['Institute'] = ''
    if hasattr(ctout['DicomHeader'], 'InstitutionName'):
        if 'Maastro' in ctout['DicomHeader'].InstitutionName:
            ctout['Institute'] = 'Maastro'
    
    # Store table height
    if hasattr(ctout['DicomHeader'], 'TableHeight'):
        ctout['TableHeight'] = float(ctout['DicomHeader'].TableHeight)
    else:
        ctout['TableHeight'] = 0.0
    
    # Store private table height from various private tags
    ctout['PrivTableHeight'] = 0.0
    
    private_tags = [
        ('Private_1099_10xx_Creator', 'Private_1099_1099'),
        ('Private_1199_11xx_Creator', 'Private_1199_1199'),
        ('Private_1299_12xx_Creator', 'Private_1299_1299'),
        ('Private_1399_13xx_Creator', 'Private_1399_1399'),
    ]
    
    for creator_tag, data_tag in private_tags:
        if hasattr(ctout['DicomHeader'], creator_tag) and hasattr(ctout['DicomHeader'], data_tag):
            value = getattr(ctout['DicomHeader'], data_tag)
            if isinstance(value, str):
                ctout['PrivTableHeight'] = float(value)
            else:
                ctout['PrivTableHeight'] = float(str(value))
            break
    
    # Store machine name
    if hasattr(ctout['DicomHeader'], 'Private_1499_14xx_Creator') and \
       hasattr(ctout['DicomHeader'], 'Private_1499_1499'):
        value = ctout['DicomHeader'].Private_1499_1499
        if isinstance(value, str):
            ctout['MachineName'] = value.strip()
        else:
            ctout['MachineName'] = str(value).strip()
    else:
        ctout['MachineName'] = None
    
    # Store HU to RED conversion if available
    if hasattr(ctout['DicomHeader'], 'Private_1599_15xx_Creator') and \
       hasattr(ctout['DicomHeader'], 'Private_1599_1599'):
        try:
            hu_to_red_string = ctout['DicomHeader'].Private_1599_1599
            if isinstance(hu_to_red_string, bytes):
                # Convert bytes to array of doubles
                hu_to_red = []
                for i in range(0, len(hu_to_red_string), 8):
                    if i + 8 <= len(hu_to_red_string):
                        value = np.frombuffer(hu_to_red_string[i:i+8], dtype=np.float64)[0]
                        hu_to_red.append(value)
                ctout['HUToRED'] = np.array(hu_to_red)
            else:
                ctout['HUToRED'] = None
        except:
            ctout['HUToRED'] = None
    else:
        ctout['HUToRED'] = None
    
    # Read all slices if requested
    if read_image_data:
        # Initialize image array (Z, X, Y) initially
        ctout['Image'] = np.zeros((ctout['PixelNumZi'], 
                                   ctout['PixelNumXi'], 
                                   ctout['PixelNumYi']))
        
        # Read and apply RescaleSlope and RescaleIntercept
        for slice_cur in range(slice_num):
            pixel_array = pydicom.dcmread(ctout['Filenames'][slice_cur]).pixel_array
            ctout['Image'][:, :, slice_cur] = (pixel_array.astype(float) * 
                                               ctout['RescaleSlope'] + 
                                               ctout['RescaleIntercept'])
        
        # Clip values below -1024 to -1024
        ctout['Image'][ctout['Image'] < -1024] = -1024
        
        # Apply IEC format transformations
        # Flip Z axis (reverse first dimension)
        ctout['Image'] = ctout['Image'][::-1, :, :]
        
        # Permute to (X, Y, Z) format
        # From (Z, X, Y) to (X, Z, Y)
        ctout['Image'] = np.transpose(ctout['Image'], (1, 0, 2))
        # From (X, Z, Y) to (X, Y, Z)
        ctout['Image'] = np.transpose(ctout['Image'], (0, 2, 1))
    
    return ctout
