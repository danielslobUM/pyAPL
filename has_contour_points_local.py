"""
hasContourPointsLocal - Check if structure has contour points

True if the structure has at least one slice with points.
Works with either .ContourData (flat [x y z ...]) or .X/.Y/.Z triplets.
"""

def has_contour_points_local(struct_entry):
    """
    Check if a structure entry has at least one slice with contour points.
    
    Parameters
    ----------
    struct_entry : dict
        Structure entry containing 'Slice' field with contour data
        
    Returns
    -------
    bool
        True if structure has contour points, False otherwise
    """
    if 'Slice' not in struct_entry or not struct_entry['Slice']:
        return False
    
    slices = struct_entry['Slice']
    
    # Case 1: DICOM-typical flat vector
    if any('ContourData' in s for s in slices):
        return any(s.get('ContourData') is not None and len(s.get('ContourData', [])) > 0 
                   for s in slices)
    
    # Case 2: separate X/Y/Z vectors
    if all(all(k in s for k in ['X', 'Y', 'Z']) for s in slices if s):
        return any(s.get('X') is not None and len(s.get('X', [])) > 0 and
                   s.get('Y') is not None and len(s.get('Y', [])) > 0 and
                   s.get('Z') is not None and len(s.get('Z', [])) > 0
                   for s in slices)
    
    return False
