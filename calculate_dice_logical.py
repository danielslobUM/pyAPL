"""
calculateDiceLogical - Calculate Dice coefficient between two contours

Calculates the Dice coefficient between two contours in terms of overlapping volume.

dice = 2 |X ∩ Y|      using the volumes
       ----------
       |X| + |Y|

Femke Vaassen @ MAASTRO
"""

import numpy as np


def calculate_dice_logical(voi1, voi2, struct_num_1, struct_num_2):
    """
    Calculate the Dice similarity coefficient between two structures.
    
    Parameters
    ----------
    voi1 : ndarray
        First volume of interest (contains all structures)
    voi2 : ndarray
        Second volume of interest (contains all structures)
    struct_num_1 : int
        Structure number (1-indexed) within VOI1
    struct_num_2 : int
        Structure number (1-indexed) within VOI2
        
    Returns
    -------
    float
        Dice similarity coefficient (0 to 1)
    """
    # Extract the specific structure using bit operations
    # MATLAB bitget is 1-indexed, we need to adjust for 0-indexed Python
    # bitget(voi1, struct_num_1) extracts bit at position struct_num_1
    voi1_struct = ((voi1 >> (struct_num_1 - 1)) & 1).astype(bool)
    voi2_struct = ((voi2 >> (struct_num_2 - 1)) & 1).astype(bool)
    
    # Calculate overlapping pixels
    overlap = voi1_struct & voi2_struct
    summed_vol = np.sum(voi1_struct) + np.sum(voi2_struct)
    
    if summed_vol == 0:
        dice = 1.0
    else:
        dice = (2.0 * np.sum(overlap)) / summed_vol
    
    return dice
