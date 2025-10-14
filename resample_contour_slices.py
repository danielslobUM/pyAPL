"""
resampleContourSlices - Resample contour using RTSTRUCT coordinates and CT

The coordinates are upsampled to prevent open contours and then used to
create a binary image of the contour.

Jose A. Baeza & Femke Vaassen @ MAASTRO
"""

import numpy as np
from scipy.interpolate import interp1d
from skimage.draw import polygon


def resample_contour_slices(rts_cs, ct, st_name):
    """
    Resample a contour using the RTSTRUCT coordinates and the CT.
    
    Parameters
    ----------
    rts_cs : list of dict
        ContourSequence values (slices) with 'X', 'Y', 'Z' keys
    ct : dict
        CT information dictionary
    st_name : str
        Structure name
        
    Returns
    -------
    ndarray
        Binary image of the upsampled coordinates of the structure
    dict
        Dictionary with minimal and maximal pixel values:
        - minX : int
        - maxX : int
        - minZ : int
        - maxZ : int
    """
    # Upsample the ContourSequence values to prevent open contours
    rts_cs_aux = []
    for i in range(len(rts_cs)):
        if rts_cs[i]['X'] is not None and len(rts_cs[i]['X']) > 0:
            current_sampling = np.arange(len(rts_cs[i]['X']))
            new_sampling = np.arange(0, len(rts_cs[i]['X']), 0.1)
            
            # Interpolate X, Y, Z coordinates
            f_x = interp1d(current_sampling, rts_cs[i]['X'], kind='linear')
            f_y = interp1d(current_sampling, rts_cs[i]['Y'], kind='linear')
            f_z = interp1d(current_sampling, rts_cs[i]['Z'], kind='linear')
            
            rts_cs_upsamp_x = f_x(new_sampling)
            rts_cs_upsamp_y = f_y(new_sampling)
            rts_cs_upsamp_z = f_z(new_sampling)
            
            # Stack and append
            upsampled = np.column_stack([rts_cs_upsamp_x, rts_cs_upsamp_y, rts_cs_upsamp_z])
            rts_cs_aux.append(upsampled)
    
    if not rts_cs_aux:
        # Return empty volume and default minmax
        rts_vol = np.zeros((ct['PixelNumXi'], ct['PixelNumYi'], ct['PixelNumZi']), dtype=bool)
        minmax = {'minX': 0, 'maxX': 0, 'minZ': 0, 'maxZ': 0}
        return rts_vol, minmax
    
    # Concatenate all upsampled contours
    rts_cs_aux = np.vstack(rts_cs_aux)
    
    # Convert spatial positions to pixel values
    rts_cs_grid = np.zeros((len(rts_cs_aux), 3), dtype=int)
    rts_cs_grid[:, 0] = np.round((rts_cs_aux[:, 0] - ct['PixelFirstXi']) / ct['PixelSpacingXi']).astype(int)
    rts_cs_grid[:, 1] = np.round((rts_cs_aux[:, 1] - ct['PixelFirstYi']) / ct['PixelSpacingYi']).astype(int)
    rts_cs_grid[:, 2] = np.round((rts_cs_aux[:, 2] - ct['PixelFirstZi']) / ct['PixelSpacingZi']).astype(int)
    
    # Check if points are outside the grid
    if (np.any(rts_cs_grid < 0) or 
        np.any(rts_cs_grid[:, 0] > ct['PixelNumXi'] - 1) or
        np.any(rts_cs_grid[:, 1] > ct['PixelNumYi'] - 1) or
        np.any(rts_cs_grid[:, 2] > ct['PixelNumZi'] - 1)):
        
        # Clip values to valid range
        rts_cs_grid[rts_cs_grid < 0] = 0
        rts_cs_grid[rts_cs_grid[:, 0] > ct['PixelNumXi'] - 1, 0] = ct['PixelNumXi'] - 1
        rts_cs_grid[rts_cs_grid[:, 1] > ct['PixelNumYi'] - 1, 1] = ct['PixelNumYi'] - 1
        rts_cs_grid[rts_cs_grid[:, 2] > ct['PixelNumZi'] - 1, 2] = ct['PixelNumZi'] - 1
        
        print(f'\n PAS OP! RTSTRUCT "{st_name}" includes points outside the current GRID \n')
    
    # Calculate min/max values
    minmax = {
        'minX': np.min(rts_cs_grid[:, 0]),
        'maxX': np.max(rts_cs_grid[:, 0]),
        'minZ': np.min(rts_cs_grid[:, 2]),
        'maxZ': np.max(rts_cs_grid[:, 2])
    }
    
    # Create binary volume
    rts_vol = np.zeros((ct['PixelNumXi'], ct['PixelNumYi'], ct['PixelNumZi']), dtype=bool)
    
    # Group points by Y slice
    unique_y = np.unique(rts_cs_grid[:, 1])
    for y_slice in unique_y:
        slice_points = rts_cs_grid[rts_cs_grid[:, 1] == y_slice]
        
        if len(slice_points) > 2:
            # Use polygon to fill the contour
            x_coords = slice_points[:, 0]
            z_coords = slice_points[:, 2]
            
            try:
                rr, cc = polygon(x_coords, z_coords, shape=(ct['PixelNumXi'], ct['PixelNumZi']))
                rts_vol[rr, y_slice, cc] = True
            except:
                # If polygon fails, just mark the boundary points
                for point in slice_points:
                    if (0 <= point[0] < ct['PixelNumXi'] and 
                        0 <= point[2] < ct['PixelNumZi']):
                        rts_vol[point[0], point[1], point[2]] = True
    
    return rts_vol, minmax
