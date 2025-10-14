"""
calculatePathLength - Calculate path lengths between contours

Calculates path lengths of the contours and path length that were added or adjusted
between two contours.

Femke Vaassen @ MAASTRO
Daniël Slob: added 'tolerance' to function
"""

import numpy as np
from scipy.ndimage import distance_transform_edt
from resample_contour_slices import resample_contour_slices


def calculate_path_length(image, struct_ref, struct_new, struct_num_1, struct_num_2, tolerance):
    """
    Calculate path length that is different between two contours.
    
    Parameters
    ----------
    image : dict
        CT/image information dictionary
    struct_ref : dict
        RTSTRUCT of the first/reference dataset
    struct_new : dict
        RTSTRUCT of the second/new dataset
    struct_num_1 : int
        Structure number (0-indexed) within STRUCT_ref
    struct_num_2 : int
        Structure number (0-indexed) within STRUCT_new
    tolerance : float
        Tolerance between the two contours that is accepted (in cm)
        
    Returns
    -------
    ndarray
        Path length per slice that is different in the second contour 
        compared to the first contour (shape: [PixelNumYi])
    """
    print(f"Analyzing Structure: {struct_ref['Struct'][struct_num_1]['Name']}")
    print('-   Calculating: Added Path Length')
    
    # Resample contours
    contour1, minmax_oc = resample_contour_slices(
        struct_ref['Struct'][struct_num_1]['Slice'], 
        image, 
        struct_ref['Struct'][struct_num_1]['Name']
    )
    contour2, minmax_nc = resample_contour_slices(
        struct_new['Struct'][struct_num_2]['Slice'], 
        image, 
        struct_new['Struct'][struct_num_2]['Name']
    )
    
    # Determine range with margin
    margin = 15
    min_x = min(minmax_oc['minX'], minmax_nc['minX']) - margin
    max_x = max(minmax_oc['maxX'], minmax_nc['maxX']) + margin
    min_z = min(minmax_oc['minZ'], minmax_nc['minZ']) - margin
    max_z = max(minmax_oc['maxZ'], minmax_nc['maxZ']) + margin
    
    # Clip to valid range
    min_x = max(0, min_x)
    max_x = min(image['PixelNumXi'], max_x)
    min_z = max(0, min_z)
    max_z = min(image['PixelNumZi'], max_z)
    
    # Extract relevant regions
    contour1_crop = contour1[min_x:max_x, :, min_z:max_z]
    contour2_crop = contour2[min_x:max_x, :, min_z:max_z]
    
    # Convert to (Z, Y, X) for distance transform
    contour1_zyx = np.transpose(contour1_crop, (2, 1, 0))
    
    # Calculate distance transform with proper spacing
    spacing = [image['PixelSpacingZi'], image['PixelSpacingYi'], image['PixelSpacingXi']]
    distance_c1 = distance_transform_edt(~contour1_zyx, sampling=spacing)
    
    # Create tolerance-expanded contour1
    contour1_tol = distance_c1 <= tolerance
    
    # Calculate difference
    contour2_zyx = np.transpose(contour2_crop, (2, 1, 0))
    diff_contours = contour1_tol.astype(int) - contour2_zyx.astype(int)
    
    # Initialize output
    path_length_outside = np.zeros(image['PixelNumYi'])
    
    # Calculate path length per slice
    for ii in range(image['PixelNumYi']):
        # Extract slice (Y is middle dimension in ZYX)
        diff_slice_contour = diff_contours[:, ii, :]
        slice_contour1 = contour1_crop[:, ii, :]
        slice_contour2 = contour2_crop[:, ii, :]
        
        # Count pixels where the automatic is outside the GT+tolerance contour
        # Use simple pixel spacing (not the diagonal/straight average)
        path_length_outside[ii] = np.sum(diff_slice_contour == -1) * (image['PixelSpacingXi'] * 10)  # mm
        
        # Check for slices with missing contours
        if np.sum(slice_contour1) == 0 and np.sum(slice_contour2) != 0:
            print(f'    -- Slice {ii} contains a GT contour but no automatic contour: '
                  'all pixels are added to total')
        
        if np.sum(slice_contour1) != 0 and np.sum(slice_contour2) == 0:
            print(f'    -- Slice {ii} contains no GT contour but does contain an automatic contour')
    
    return path_length_outside
