"""
Basic functionality tests for converted Python modules.
"""

import numpy as np
from has_contour_points_local import has_contour_points_local
from calculate_dice_logical import calculate_dice_logical


def test_has_contour_points_local():
    """Test has_contour_points_local function."""
    print("Testing has_contour_points_local...")
    
    # Test empty structure
    empty_struct = {'Slice': []}
    assert has_contour_points_local(empty_struct) == False, "Empty structure should return False"
    
    # Test structure with X/Y/Z data
    struct_with_data = {
        'Slice': [
            {'X': [1, 2, 3], 'Y': [1, 2, 3], 'Z': [1, 2, 3]}
        ]
    }
    assert has_contour_points_local(struct_with_data) == True, "Structure with data should return True"
    
    # Test structure with empty X/Y/Z
    struct_empty_xyz = {
        'Slice': [
            {'X': [], 'Y': [], 'Z': []}
        ]
    }
    assert has_contour_points_local(struct_empty_xyz) == False, "Structure with empty arrays should return False"
    
    print("✓ has_contour_points_local tests passed")


def test_calculate_dice_logical():
    """Test calculate_dice_logical function."""
    print("Testing calculate_dice_logical...")
    
    # Create test volumes (3x3x3)
    # Structure 1 is in bit 0, structure 2 is in bit 1
    voi1 = np.zeros((3, 3, 3), dtype=np.uint16)
    voi2 = np.zeros((3, 3, 3), dtype=np.uint16)
    
    # Set some voxels for structure 1 (bit 0) in both VOIs
    voi1[0:2, 0:2, 0:2] = 1  # 8 voxels
    voi2[0:2, 0:2, 0:2] = 1  # 8 voxels (same location)
    
    # Perfect overlap - DICE should be 1.0
    dice = calculate_dice_logical(voi1, voi2, 1, 1)
    assert abs(dice - 1.0) < 0.001, f"Perfect overlap should give DICE=1.0, got {dice}"
    
    # Partial overlap
    voi3 = np.zeros((3, 3, 3), dtype=np.uint16)
    voi3[1:3, 1:3, 1:3] = 1  # 8 voxels, different location (1 voxel overlap)
    
    dice_partial = calculate_dice_logical(voi1, voi3, 1, 1)
    expected_dice = 2.0 * 1 / (8 + 8)  # 2 * overlap / (vol1 + vol2)
    assert abs(dice_partial - expected_dice) < 0.001, f"Expected DICE={expected_dice}, got {dice_partial}"
    
    # No overlap
    voi4 = np.zeros((3, 3, 3), dtype=np.uint16)
    voi4[2, 2, 2] = 1  # 1 voxel, no overlap
    
    dice_none = calculate_dice_logical(voi1, voi4, 1, 1)
    assert dice_none == 0.0, f"No overlap should give DICE=0.0, got {dice_none}"
    
    # Both empty (edge case)
    voi5 = np.zeros((3, 3, 3), dtype=np.uint16)
    voi6 = np.zeros((3, 3, 3), dtype=np.uint16)
    
    dice_empty = calculate_dice_logical(voi5, voi6, 1, 1)
    assert dice_empty == 1.0, f"Both empty should give DICE=1.0, got {dice_empty}"
    
    print("✓ calculate_dice_logical tests passed")


def test_module_imports():
    """Test that all modules can be imported."""
    print("Testing module imports...")
    
    modules = [
        'read_dicomct_light',
        'read_dicomrtstruct',
        'resample_contour_slices',
        'compose_struct_matrix',
        'calculate_surface_dsc',
        'calculate_different_path_length_v2',
        'calculate_voxel_diff_counts',
        'quantify_contour_differences',
    ]
    
    for mod in modules:
        try:
            __import__(mod)
            print(f"  ✓ {mod}")
        except Exception as e:
            print(f"  ✗ {mod}: {e}")
            raise
    
    print("✓ All module imports successful")


if __name__ == '__main__':
    print("="*60)
    print("Running basic functionality tests")
    print("="*60)
    
    test_module_imports()
    print()
    test_has_contour_points_local()
    print()
    test_calculate_dice_logical()
    print()
    
    print("="*60)
    print("All tests passed!")
    print("="*60)
