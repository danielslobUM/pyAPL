"""
calculateSurfaceDSC - Calculate surface DSC between two contours

Calculates surface DSC between two contours in terms of overlapping surfaces.

surface dsc = 2 |X ∩ Y|   using the contours/surfaces
              ----------
              |X| + |Y|

Femke Vaassen @ MAASTRO
"""

import numpy as np
from scipy.ndimage import distance_transform_edt
from resample_contour_slices import resample_contour_slices


def calculate_surface_dsc(ct, struct_ref, struct_new, struct_num_1, struct_num_2, tolerance):
    """
    Calculate surface DSC between two contours.
    
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
        Tolerance margin in cm for acceptable contour overlap
        
    Returns
    -------
    float or ndarray
        Surface DSC value(s) for each tolerance value
    """
    print('-   Calculating: Surface DSC')
    
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
    
    # Determine range with margin
    range_margin = 20
    min_x = max(0, min(minmax_oc['minX'], minmax_nc['minX']) - range_margin)
    max_x = min(ct['PixelNumXi'], max(minmax_oc['maxX'], minmax_nc['maxX']) + range_margin)
    min_z = max(0, min(minmax_oc['minZ'], minmax_nc['minZ']) - range_margin)
    max_z = min(ct['PixelNumZi'], max(minmax_oc['maxZ'], minmax_nc['maxZ']) + range_margin)
    
    # Extract relevant regions
    contour1_crop = contour1[min_x:max_x, :, min_z:max_z]
    contour2_crop = contour2[min_x:max_x, :, min_z:max_z]
    
    # Ensure tolerance is array
    if not isinstance(tolerance, (list, np.ndarray)):
        tolerance = [tolerance]
    tolerance = np.array(tolerance)
    
    # Convert to (Z, Y, X) for distance transform (scipy convention)
    contour1_zyx = np.transpose(contour1_crop, (2, 1, 0))
    contour2_zyx = np.transpose(contour2_crop, (2, 1, 0))
    
    # Calculate distance transforms with proper spacing
    # Spacing order: (Z, Y, X) matching the transposed array
    spacing = [ct['PixelSpacingZi'], ct['PixelSpacingYi'], ct['PixelSpacingXi']]
    distance_c1 = distance_transform_edt(~contour1_zyx, sampling=spacing)
    distance_c2 = distance_transform_edt(~contour2_zyx, sampling=spacing)
    
    # Calculate surface DSC for each tolerance
    surface_dsc = np.zeros(len(tolerance))
    
    for tol_idx, tol in enumerate(tolerance):
        # Find pixels within tolerance
        diff1 = distance_c1 <= tol
        diff2 = distance_c2 <= tol
        
        # Calculate overlapping pixels
        pixel_data_overlap1 = contour1_zyx & diff2
        pixel_data_overlap2 = contour2_zyx & diff1
        
        c1b2 = np.sum(pixel_data_overlap1)
        c2b1 = np.sum(pixel_data_overlap2)
        
        c1 = np.sum(contour1)
        c2 = np.sum(contour2)
        
        if c1 + c2 > 0:
            surface_dsc[tol_idx] = (2.0 * c2b1) / (c1 + c2)
        else:
            surface_dsc[tol_idx] = 0.0
    
    # Return scalar if single tolerance, otherwise array
    if len(surface_dsc) == 1:
        return surface_dsc[0]
    return surface_dsc
