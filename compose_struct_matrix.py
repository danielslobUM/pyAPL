"""
compose_struct_matrix - Build matrix representation of contours

Builds a matrix of zeros and adds to all voxels within the nth contour
the value 2^(n-1). So if a voxel lies within the first, third and 5th
contour its value is 2^0 + 2^2 + 2^4 = 21.

Steven Petit, Ralph Leijenaar @ MAASTRO
"""

import numpy as np
from skimage.draw import polygon


def compose_struct_matrix(scan, rtstruct_file):
    """
    Compose a matrix representation of structures from RTSTRUCT.
    
    Parameters
    ----------
    scan : dict
        CT/PET scan data
    rtstruct_file : dict or str
        RTSTRUCT file or structure read with read_dicomrtstruct
        
    Returns
    -------
    ndarray
        Matrix containing contours in binary representation.
        Each structure occupies one bit position.
    """
    print('Composing VOI of structures')
    
    # Read structure file if needed
    if isinstance(rtstruct_file, str):
        from read_dicomrtstruct import read_dicomrtstruct
        struct_in = read_dicomrtstruct(rtstruct_file)
    else:
        struct_in = rtstruct_file
    
    # Calculate Y coordinate grid
    yct = scan['PixelFirstYi'] + np.arange(scan['PixelNumYi']) * scan['PixelSpacingYi']
    
    # Determine matrix data type based on number of structures
    struct_num = struct_in['StructNum']
    if struct_num <= 16:
        matrix = np.zeros(scan['Image'].shape, dtype=np.uint16)
    elif struct_num <= 32:
        matrix = np.zeros(scan['Image'].shape, dtype=np.uint32)
    elif struct_num <= 64:
        matrix = np.zeros(scan['Image'].shape, dtype=np.uint64)
    else:
        print('-   Too many structs Only doing first 64 -')
        matrix = np.zeros(scan['Image'].shape, dtype=np.uint64)
        struct_num = 64
    
    # Process each structure
    for i in range(struct_num):
        struct = struct_in['Struct'][i]
        
        if len(struct['Slice']) > 1:
            warning1 = False
            warning2 = False
            
            for j, slice_data in enumerate(struct['Slice']):
                do_process = False
                
                if slice_data['Y'] is not None and len(slice_data['Y']) > 0:
                    # Convert structure coordinates to grid indices
                    x_samp = (slice_data['X'] - scan['PixelFirstXi']) / scan['PixelSpacingXi']
                    z_samp = (slice_data['Z'] - scan['PixelFirstZi']) / scan['PixelSpacingZi']
                    y_samp = (slice_data['Y'][0] - scan['PixelFirstYi']) / scan['PixelSpacingYi']
                    
                    # Check if Y position matches a CT slice
                    y_diff = np.abs(yct - slice_data['Y'][0])
                    
                    if np.any(y_diff < 0.0001):
                        do_process = True
                    elif slice_data['Y'][0] < np.min(yct) or slice_data['Y'][0] > np.max(yct):
                        warning1 = True
                    elif np.any(y_diff <= 0.11):
                        warning2 = True
                        do_process = True
                    else:
                        print('-   Discrepancy between y-position slice and contour')
                        break
                    
                    if do_process:
                        # Use polygon to fill the contour
                        y_idx = int(np.round(y_samp))
                        
                        if 0 <= y_idx < scan['PixelNumYi']:
                            try:
                                # Create polygon mask
                                rr, cc = polygon(z_samp, x_samp, 
                                               shape=(scan['PixelNumXi'], scan['PixelNumZi']))
                                
                                # Get linear indices and set bit
                                for r, c in zip(rr, cc):
                                    if (0 <= r < scan['PixelNumXi'] and 
                                        0 <= c < scan['PixelNumZi']):
                                        matrix[r, y_idx, c] |= (1 << i)
                            except:
                                # If polygon fails, skip this slice
                                pass
            
            if warning1:
                print('-   Warning: span y-pos contour is larger than image')
            if warning2:
                print('-   Warning: 1 mm discrepancy is allowed between slice and contour y-position!')
    
    return matrix
