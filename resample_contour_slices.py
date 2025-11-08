"""
resampleContourSlices - Resample contour using RTSTRUCT coordinates and CT

The coordinates are upsampled to prevent open contours and then used to
create a binary image of the contour.

This version closely matches the MATLAB implementation in resampleContourSlices.m

Jose A. Baeza & Femke Vaassen @ MAASTRO
"""

import numpy as np


def resample_contour_slices(rts_cs, ct, st_name):
    """
    Resample a contour using the RTSTRUCT coordinates and the CT.
    
    Parameters
    ----------
    rts_cs : list of dict
        ContourSequence values (slices) with 'X', 'Y', 'Z' keys
    ct : dict
        CT information dictionary with keys:
        - Image : ndarray or shape info
        - PixelFirstXi, PixelFirstYi, PixelFirstZi : float
        - PixelSpacingXi, PixelSpacingYi, PixelSpacingZi : float
        - PixelNumXi, PixelNumYi, PixelNumZi : int
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
    # Upsampling the ContourSequence values to prevent open contours and
    # regrouping them in one single matrix for performance.
    rts_cs_aux = []
    
    for i in range(len(rts_cs)):
        # Check if slice has contour points (matching MATLAB's ~isempty check)
        if rts_cs[i]['X'] is not None and len(rts_cs[i]['X']) > 0:
            # MATLAB: current_sampling = 1:length(RTS_cs(i).X)
            # MATLAB is 1-indexed, so 1:N means indices 1,2,3,...,N
            # In Python (0-indexed), we use 0:N-1, which is 0,1,2,...,N-1
            # But for interpolation, we need the same range [0, N-1] to [0, N-1]
            current_sampling = np.arange(1, len(rts_cs[i]['X']) + 1)
            
            # MATLAB: new_sampling = 1:0.1:length(RTS_cs(i).X)
            # This creates [1, 1.1, 1.2, ..., N]
            # We need to match this exactly
            new_sampling = np.arange(1, len(rts_cs[i]['X']) + 1, 0.1)
            
            # Interpolate X, Y, Z coordinates
            # MATLAB's interp1 with default 'linear' method
            rts_cs_upsamp_x = np.interp(new_sampling, current_sampling, rts_cs[i]['X'])
            rts_cs_upsamp_y = np.interp(new_sampling, current_sampling, rts_cs[i]['Y'])
            rts_cs_upsamp_z = np.interp(new_sampling, current_sampling, rts_cs[i]['Z'])
            
            # MATLAB: vertcat(RTS_cs_aux, [RTS_cs_upsamp_X' RTS_cs_upsamp_Y' RTS_cs_upsamp_Z'])
            # Stack as columns and append to list
            upsampled = np.column_stack([rts_cs_upsamp_x, rts_cs_upsamp_y, rts_cs_upsamp_z])
            rts_cs_aux.append(upsampled)
    
    # Concatenate all upsampled contours
    # MATLAB starts with empty array and uses vertcat
    if len(rts_cs_aux) == 0:
        # No valid contours - return empty volume
        # MATLAB would continue with empty array, but we should handle this
        if 'Image' in ct and hasattr(ct['Image'], 'shape'):
            rts_vol = np.zeros(ct['Image'].shape)
        else:
            rts_vol = np.zeros((ct['PixelNumXi'], ct['PixelNumYi'], ct['PixelNumZi']))
        minmax = {'minX': 1, 'maxX': 1, 'minZ': 1, 'maxZ': 1}
        return rts_vol, minmax
    
    rts_cs_aux = np.vstack(rts_cs_aux)
    
    # Convert spatial positions in pixel values
    # MATLAB: round((RTS_cs_aux(:,1)-CT.PixelFirstXi)./CT.PixelSpacingXi)+1
    # The +1 converts from 0-based to 1-based indexing (MATLAB convention)
    rts_cs_grid = np.zeros((len(rts_cs_aux), 3), dtype=int)
    rts_cs_grid[:, 0] = np.round((rts_cs_aux[:, 0] - ct['PixelFirstXi']) / ct['PixelSpacingXi']).astype(int) + 1
    rts_cs_grid[:, 1] = np.round((rts_cs_aux[:, 1] - ct['PixelFirstYi']) / ct['PixelSpacingYi']).astype(int) + 1
    rts_cs_grid[:, 2] = np.round((rts_cs_aux[:, 2] - ct['PixelFirstZi']) / ct['PixelSpacingZi']).astype(int) + 1
    
    # It may occur that RTSTRUCTs are far off the GRID. This is probably due to
    # an error, then pixels are considered invalid
    outside_grid_limit = 5  # in pixels
    
    # MATLAB: non_valid = (RTS_cs_grid(:,1)<-outside_grid_limit) | ...
    non_valid = ((rts_cs_grid[:, 0] < -outside_grid_limit) | 
                 (rts_cs_grid[:, 1] < -outside_grid_limit) | 
                 (rts_cs_grid[:, 2] < -outside_grid_limit) |
                 (rts_cs_grid[:, 0] > ct['PixelNumXi'] + outside_grid_limit) |
                 (rts_cs_grid[:, 1] > ct['PixelNumYi'] + outside_grid_limit) |
                 (rts_cs_grid[:, 2] > ct['PixelNumZi'] + outside_grid_limit))
    
    # MATLAB: RTS_cs_grid = RTS_cs_grid(~non_valid,:)
    rts_cs_grid = rts_cs_grid[~non_valid, :]
    
    # Check if we have any valid points left
    if len(rts_cs_grid) == 0:
        # No valid points after filtering - return empty volume
        if 'Image' in ct and hasattr(ct['Image'], 'shape'):
            rts_vol = np.zeros(ct['Image'].shape)
        else:
            rts_vol = np.zeros((ct['PixelNumXi'], ct['PixelNumYi'], ct['PixelNumZi']))
        minmax = {'minX': 1, 'maxX': 1, 'minZ': 1, 'maxZ': 1}
        return rts_vol, minmax
    
    # Sometimes the RTSTRUCT is outside the CT grid (i.e. in BODY).
    # Pixels are forced to be between [1...PixelNum]
    # MATLAB: if (min(RTS_cs_grid(:))<1) | (max(RTS_cs_grid(:,1)) > (CT.PixelNumXi-1)) | ...
    if (np.min(rts_cs_grid) < 1 or 
        np.max(rts_cs_grid[:, 0]) > (ct['PixelNumXi'] - 1) or
        np.max(rts_cs_grid[:, 1]) > (ct['PixelNumYi'] - 1) or
        np.max(rts_cs_grid[:, 2]) > (ct['PixelNumZi'] - 1)):
        
        # MATLAB: RTS_cs_grid(RTS_cs_grid<1) = 1
        rts_cs_grid[rts_cs_grid < 1] = 1
        
        # MATLAB: RTS_cs_grid(RTS_cs_grid(:,1)>(CT.PixelNumXi-1),1) = CT.PixelNumXi-1
        rts_cs_grid[rts_cs_grid[:, 0] > (ct['PixelNumXi'] - 1), 0] = ct['PixelNumXi'] - 1
        rts_cs_grid[rts_cs_grid[:, 1] > (ct['PixelNumYi'] - 1), 1] = ct['PixelNumYi'] - 1
        rts_cs_grid[rts_cs_grid[:, 2] > (ct['PixelNumZi'] - 1), 2] = ct['PixelNumZi'] - 1
        
        # MATLAB: fprintf(['\n PAS OP! RTSTRUCT "', st_name, '" includes points outside the current GRID \n'])
        print(f'\n PAS OP! RTSTRUCT "{st_name}" includes points outside the current GRID \n')
    
    # MATLAB: minmax.minX = min(RTS_cs_grid(:,1))
    minmax = {
        'minX': int(np.min(rts_cs_grid[:, 0])),
        'maxX': int(np.max(rts_cs_grid[:, 0])),
        'minZ': int(np.min(rts_cs_grid[:, 2])),
        'maxZ': int(np.max(rts_cs_grid[:, 2]))
    }
    
    # Generate a zero-filled VOI and set the 1's at the boundary of the contour
    # MATLAB: RTS_cs_grid_idxs = sub2ind(size(CT.Image), RTS_cs_grid(:,1), RTS_cs_grid(:,2), RTS_cs_grid(:,3))
    # MATLAB: RTS_vol = zeros(size(CT.Image))
    # MATLAB: RTS_vol(RTS_cs_grid_idxs) = 1
    
    # Get the shape of CT.Image
    if 'Image' in ct and hasattr(ct['Image'], 'shape'):
        vol_shape = ct['Image'].shape
    else:
        vol_shape = (ct['PixelNumXi'], ct['PixelNumYi'], ct['PixelNumZi'])
    
    rts_vol = np.zeros(vol_shape)
    
    # Convert MATLAB 1-based indices to Python 0-based indices for sub2ind equivalent
    # MATLAB sub2ind with 1-based indexing: sub2ind(size, row, col, page)
    # Python equivalent with 0-based indexing: np.ravel_multi_index((row-1, col-1, page-1), shape)
    # Since MATLAB indices are 1-based, we subtract 1
    rts_cs_grid_0based = rts_cs_grid - 1
    
    # Use ravel_multi_index to convert subscripts to linear indices
    # This is the Python equivalent of MATLAB's sub2ind
    try:
        rts_cs_grid_idxs = np.ravel_multi_index(
            (rts_cs_grid_0based[:, 0], rts_cs_grid_0based[:, 1], rts_cs_grid_0based[:, 2]),
            vol_shape
        )
        # Set the boundary points to 1
        rts_vol.flat[rts_cs_grid_idxs] = 1
    except ValueError as e:
        # If there's still an indexing error, print warning
        print(f"Warning: Could not set some contour points for {st_name}: {e}")
    
    return rts_vol, minmax
