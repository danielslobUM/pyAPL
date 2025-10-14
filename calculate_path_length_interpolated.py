"""
calculatePathLength_interpolated - Calculate path lengths with interpolation handling

Calculates path lengths of the contours and path length that were added or adjusted 
between two contours, handling interpolated slices.

Femke Vaassen @ MAASTRO
"""

import numpy as np
from resample_contour_slices import resample_contour_slices


def calculate_path_length_interpolated(ct, struct_ref, struct_new, struct_num_1, struct_num_2):
    """
    Calculate path length that was added when comparing contours, handling interpolation.
    
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
        
    Returns
    -------
    path_length_added_new : float
        Path length that was added when comparing the adjusted with the original contour (mm)
    path_length_original : float
        Path length of the original contour (automatic contour) (mm)
    path_length_new_contour : float
        Path length of the new contour (user-adjusted contour) (mm)
    compare_deleted_from_automatic : int
        Number of slices deleted from automatic contour
    compare_added_to_adjusted : int
        Number of slices added to adjusted contour
    every_slice_contoured : int
        Whether every slice was contoured (1) or not (0)
    slices_automatic : int
        Number of slices in automatic contour
    """
    print('-   Calculating: Added path length')
    
    # Resample contours
    contour1, _ = resample_contour_slices(
        struct_ref['Struct'][struct_num_1]['Slice'], 
        ct, 
        struct_ref['Struct'][struct_num_1]['Name']
    )
    contour2, _ = resample_contour_slices(
        struct_new['Struct'][struct_num_2]['Slice'], 
        ct, 
        struct_new['Struct'][struct_num_2]['Name']
    )
    
    # Find unique slices with contours
    indices = np.where(contour1)
    unique_slices_c1 = np.unique(indices[1])
    
    indices = np.where(contour2)
    unique_slices_c2 = np.unique(indices[1])
    
    # Create adapted contour2 (excluding interpolated slices)
    contour2_adapted = np.zeros_like(contour2)
    
    for slice_idx in range(contour2.shape[1]):
        # If contour1 has data in this slice, include contour2 data
        if np.any(contour1[:, slice_idx, :]):
            contour2_adapted[:, slice_idx, :] = contour2[:, slice_idx, :]
        # If slice is before first or after last slice of contour1
        elif slice_idx < unique_slices_c1[0] or slice_idx > unique_slices_c1[-1]:
            contour2_adapted[:, slice_idx, :] = contour2[:, slice_idx, :]
        
        # Always include first and last slices of contour2
        if slice_idx == unique_slices_c2[0] or slice_idx == unique_slices_c2[-1]:
            contour2_adapted[:, slice_idx, :] = contour2[:, slice_idx, :]
    
    # Check if interpolated slices were removed
    if np.any(contour2 - contour2_adapted):
        # Get unique slices in adapted contour
        indices = np.where(contour2_adapted)
        unique_slices_c2_adapted = np.unique(indices[1])
        
        # Compare slices
        compare_same = np.intersect1d(unique_slices_c1, unique_slices_c2_adapted)
        compare_deleted_from_automatic = len(np.setdiff1d(unique_slices_c1, compare_same))
        compare_added_to_adjusted = len(np.setdiff1d(unique_slices_c2_adapted, compare_same))
        
        every_slice_contoured = 0
    else:
        # No interpolated slices removed
        compare_same = np.intersect1d(unique_slices_c1, unique_slices_c2)
        compare_deleted_from_automatic = len(np.setdiff1d(unique_slices_c1, compare_same))
        compare_added_to_adjusted = len(np.setdiff1d(unique_slices_c2, compare_same))
        
        every_slice_contoured = 1
    
    slices_automatic = len(unique_slices_c1)
    
    # Calculate differences
    diff_contours = contour1.astype(int) - contour2_adapted.astype(int)
    
    # Calculate path lengths (pixel size in X and Z direction)
    # Convert cm to mm by multiplying by 10
    path_length_original = np.sum(contour1 == 1) * (ct['PixelSpacingXi'] * 10)  # mm
    path_length_new_contour = np.sum(contour2 == 1) * (ct['PixelSpacingXi'] * 10)  # mm
    path_length_added_new = np.sum(diff_contours == -1) * (ct['PixelSpacingXi'] * 10)  # mm
    
    return (path_length_added_new, path_length_original, path_length_new_contour,
            compare_deleted_from_automatic, compare_added_to_adjusted, 
            every_slice_contoured, slices_automatic)
