"""
calculateDifferentPathLength_v2 - Calculate different path length between contours

Calculates path lengths of the contours and path length that were added or adjusted
between two contours.

Femke Vaassen @ MAASTRO
"""

import numpy as np
from scipy.ndimage import distance_transform_edt
from resample_contour_slices import resample_contour_slices


def calculate_different_path_length_v2(ct, struct_ref, struct_new, struct_num_1, struct_num_2, tolerance):
    """
    Calculate different path length between two contours.
    
    Parameters
    ----------
    ct : dict
        CT information dictionary
    struct_ref : dict
        RTSTRUCT of the first/reference dataset
    struct_new : dict
        RTSTRUCT of the second/new dataset
    struct_num_1 : int
        Structure number (0-indexed) within STRUCT_ref
    struct_num_2 : int
        Structure number (0-indexed) within STRUCT_new
    tolerance : float or array-like
        Tolerance between the two contours that is accepted (in cm)
        
    Returns
    -------
    ndarray
        Path length per slice that is different in the second contour 
        compared to the first contour (shape: [PixelNumYi, len(tolerance)])
    """
    print(f"Analyzing Structure: {struct_ref['Struct'][struct_num_1]['Name']}")
    print('-   Calculating: Different Path Length')
    
    # Resample contours
    contour1, minmax_oc = resample_contour_slices(
        struct_ref['Struct'][struct_num_1]['Slice'], 
        ct, 
        struct_ref['Struct'][struct_num_1]['Name']
    )
    contour2, minmax_nc = resample_contour_slices(
        struct_new['Struct'][struct_num_2]['Slice'], 
        ct, 
        struct_new['Struct'][struct_num_2]['Name']
    )
    
    # Determine range
    range_margin = 0
    min_x = min(minmax_oc['minX'], minmax_nc['minX']) - range_margin
    max_x = max(minmax_oc['maxX'], minmax_nc['maxX']) + range_margin
    min_z = min(minmax_oc['minZ'], minmax_nc['minZ']) - range_margin
    max_z = max(minmax_oc['maxZ'], minmax_nc['maxZ']) + range_margin
    
    # Clip to valid range
    min_x = max(0, min_x)
    max_x = min(ct['PixelNumXi'], max_x)
    min_z = max(0, min_z)
    max_z = min(ct['PixelNumZi'], max_z)
    
    # Extract relevant regions
    contour1_crop = contour1[min_x:max_x, :, min_z:max_z]
    contour2_crop = contour2[min_x:max_x, :, min_z:max_z]
    
    # Convert to (Z, Y, X) for distance transform
    contour1_zyx = np.transpose(contour1_crop, (2, 1, 0))
    
    # Calculate distance transform with proper spacing
    spacing = [ct['PixelSpacingZi'], ct['PixelSpacingYi'], ct['PixelSpacingXi']]
    distance_c1 = distance_transform_edt(~contour1_zyx.astype(bool), sampling=spacing)
    
    # Ensure tolerance is array
    if not isinstance(tolerance, (list, np.ndarray)):
        tolerance = [tolerance]
    tolerance = np.array(tolerance)
    
    # Initialize output
    path_length_outside = np.zeros((ct['PixelNumYi'], len(tolerance)))
    
    # Calculate path length for each tolerance
    for tol_idx, tol in enumerate(tolerance):
        # Create tolerance-expanded contour1
        contour1_tol = distance_c1 <= tol
        
        # Calculate difference (pixels in tolerance region but not in contour2)
        # Note: contour2 is already in correct orientation from resample
        contour2_zyx = np.transpose(contour2_crop, (2, 1, 0))
        diff_contours = contour1_tol.astype(int) - contour2_zyx.astype(int)
        
        # Calculate path length per slice
        # Pixel size factor: average of diagonal and straight distance
        pixel_size_factor = ((np.sqrt(2) * ct['PixelSpacingXi'] * 10) / 2 + 
                           (ct['PixelSpacingXi'] * 10) / 2)
        
        for ii in range(ct['PixelNumYi']):
            # Extract slice (Y is middle dimension in ZYX)
            diff_slice_contour = diff_contours[:, ii, :]
            slice_contour1 = contour1_crop[:, ii, :]
            slice_contour2 = contour2_crop[:, ii, :]
            
            # Count pixels where automatic is outside the GT+tolerance contour
            path_length_outside[ii, tol_idx] = np.sum(diff_slice_contour == -1) * pixel_size_factor
            
            # Check for slices with missing contours
            if tol_idx == 0:  # Only display for first tolerance
                if np.sum(slice_contour1) == 0 and np.sum(slice_contour2) != 0:
                    print(f'    -- Slice {ii} contains a GT contour but no automatic contour: '
                          'all pixels are added to total')
                
                if np.sum(slice_contour1) != 0 and np.sum(slice_contour2) == 0:
                    print(f'    -- Slice {ii} contains no GT contour but does contain an '
                          'automatic contour')
    
    return path_length_outside
