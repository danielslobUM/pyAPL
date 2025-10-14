"""
calculateVoxelDiffCounts - Calculate voxel difference counts

Counts the number of voxels outside tolerance between two contours.
"""

import numpy as np
from scipy.ndimage import distance_transform_edt
from resample_contour_slices import resample_contour_slices


def calculate_voxel_diff_counts(ct, struct_ref, struct_new, struct_num_1, struct_num_2, tolerance):
    """
    Calculate voxel difference counts between two contours.
    
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
        Tolerance value(s) in cm
        
    Returns
    -------
    ndarray
        Number of voxels outside tolerance for each tolerance value
    """
    # Resample contours
    contour1, mm_oc = resample_contour_slices(
        struct_ref['Struct'][struct_num_1]['Slice'], 
        ct, 
        struct_ref['Struct'][struct_num_1]['Name']
    )
    contour2, mm_nc = resample_contour_slices(
        struct_new['Struct'][struct_num_2]['Slice'], 
        ct, 
        struct_new['Struct'][struct_num_2]['Name']
    )
    
    # Determine range
    range_margin = 20
    min_x = min(mm_oc['minX'], mm_nc['minX']) - range_margin
    max_x = max(mm_oc['maxX'], mm_nc['maxX']) + range_margin
    min_z = min(mm_oc['minZ'], mm_nc['minZ']) - range_margin
    max_z = max(mm_oc['maxZ'], mm_nc['maxZ']) + range_margin
    
    # Clamp to valid range (MATLAB uses 1-indexing, Python uses 0-indexing)
    min_x = max(0, min_x)
    max_x = min(ct['PixelNumXi'], max_x)
    min_z = max(0, min_z)
    max_z = min(ct['PixelNumZi'], max_z)
    
    if min_x >= max_x or min_z >= max_z:
        print('Warning: Empty crop after clamping; returning zeros.')
        if not isinstance(tolerance, (list, np.ndarray)):
            tolerance = [tolerance]
        return np.zeros(len(tolerance))
    
    # Crop contours
    bw_ref_crop = contour1[min_x:max_x, :, min_z:max_z]
    bw_new_crop = contour2[min_x:max_x, :, min_z:max_z]
    
    # Convert to (Z, Y, X) for distance transform
    bw_ref_zyx = np.transpose(bw_ref_crop, (2, 1, 0))
    bw_new_zyx = np.transpose(bw_new_crop, (2, 1, 0))
    
    # Calculate distance transform
    spacing = [ct['PixelSpacingZi'], ct['PixelSpacingYi'], ct['PixelSpacingXi']]
    dt = distance_transform_edt(~bw_ref_zyx, sampling=spacing)
    
    # Ensure tolerance is array
    if not isinstance(tolerance, (list, np.ndarray)):
        tolerance = [tolerance]
    tolerance = np.array(tolerance)
    
    # Calculate voxel counts
    n_voxels_outside = np.zeros(len(tolerance))
    for t_idx, tol in enumerate(tolerance):
        ref_tol = dt <= tol
        diff_c = ref_tol.astype(int) - bw_new_zyx.astype(int)
        n_voxels_outside[t_idx] = np.sum(diff_c == -1)
    
    return n_voxels_outside
