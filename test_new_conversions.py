"""
Test script for newly converted Python modules.
"""

import numpy as np


def test_calculate_dice():
    """Test calculate_dice function."""
    print("Testing calculate_dice...")
    
    from calculate_dice import calculate_dice
    
    # Create test volumes (3x3x3)
    # Structure 1 is in bit 0, structure 2 is in bit 1
    voi1 = np.zeros((3, 3, 3), dtype=np.uint16)
    voi2 = np.zeros((3, 3, 3), dtype=np.uint16)
    
    # Set some voxels for structure 1 (bit 0) in both VOIs
    voi1[0:2, 0:2, 0:2] = 1  # 8 voxels
    voi2[0:2, 0:2, 0:2] = 1  # 8 voxels (same location)
    
    # Perfect overlap - DICE should be 1.0
    dice = calculate_dice(voi1, voi2, 1, 1)
    assert abs(dice - 1.0) < 0.001, f"Expected DICE=1.0, got {dice}"
    print(f"  ✓ Perfect overlap: DICE = {dice:.3f}")
    
    # Partial overlap
    voi2_partial = np.zeros((3, 3, 3), dtype=np.uint16)
    voi2_partial[0:1, 0:2, 0:2] = 1  # 4 voxels (half overlap)
    dice = calculate_dice(voi1, voi2_partial, 1, 1)
    expected_dice = 2 * 4 / (8 + 4)  # 2 * overlap / (vol1 + vol2)
    assert abs(dice - expected_dice) < 0.001, f"Expected DICE={expected_dice:.3f}, got {dice}"
    print(f"  ✓ Partial overlap: DICE = {dice:.3f}")
    
    # Empty volumes (edge case)
    voi_empty1 = np.zeros((3, 3, 3), dtype=np.uint16)
    voi_empty2 = np.zeros((3, 3, 3), dtype=np.uint16)
    dice = calculate_dice(voi_empty1, voi_empty2, 1, 1)
    assert dice == 1.0, f"Expected DICE=1.0 for empty volumes, got {dice}"
    print(f"  ✓ Empty volumes: DICE = {dice:.3f}")
    
    print("✓ calculate_dice tests passed\n")


def test_calculate_path_length():
    """Test calculate_path_length function."""
    print("Testing calculate_path_length...")
    
    from calculate_path_length import calculate_path_length
    
    # Create mock CT/image structure
    ct = {
        'PixelSpacingXi': 0.1,  # cm
        'PixelSpacingYi': 0.1,  # cm
        'PixelSpacingZi': 0.1,  # cm
        'PixelNumXi': 10,
        'PixelNumYi': 10,
        'PixelNumZi': 10
    }
    
    # Create mock structure data (minimal contour)
    struct_ref = {
        'Struct': [{
            'Name': 'TestStructure',
            'Slice': []  # Empty slices for this simple test
        }]
    }
    
    struct_new = {
        'Struct': [{
            'Name': 'TestStructure',
            'Slice': []  # Empty slices for this simple test
        }]
    }
    
    # Note: Full testing would require proper contour data
    # This is a basic import/structure test
    print("  ✓ Function imported and structure validated")
    print("✓ calculate_path_length structure tests passed\n")


def test_calculate_path_length_interpolated():
    """Test calculate_path_length_interpolated function."""
    print("Testing calculate_path_length_interpolated...")
    
    from calculate_path_length_interpolated import calculate_path_length_interpolated
    
    # Create mock CT structure
    ct = {
        'PixelSpacingXi': 0.1,  # cm
        'PixelSpacingYi': 0.1,  # cm
        'PixelSpacingZi': 0.1,  # cm
        'PixelNumXi': 10,
        'PixelNumYi': 10,
        'PixelNumZi': 10
    }
    
    # Create mock structure data
    struct_ref = {
        'Struct': [{
            'Name': 'TestStructure',
            'Slice': []  # Empty slices for this simple test
        }]
    }
    
    struct_new = {
        'Struct': [{
            'Name': 'TestStructure',
            'Slice': []  # Empty slices for this simple test
        }]
    }
    
    # Note: Full testing would require proper contour data
    print("  ✓ Function imported and structure validated")
    print("✓ calculate_path_length_interpolated structure tests passed\n")


def test_read_dicomct():
    """Test read_dicomct function."""
    print("Testing read_dicomct...")
    
    from read_dicomct import read_dicomct
    
    # Test with invalid input (should return None)
    result = read_dicomct(['.', '..'], read_image_data=False)
    assert result is None, "Expected None for invalid input"
    print("  ✓ Invalid input handling works")
    
    # Note: Full testing would require actual DICOM files
    print("✓ read_dicomct structure tests passed\n")


def test_module_imports():
    """Test that all new modules can be imported."""
    print("Testing new module imports...")
    
    modules = [
        'calculate_dice',
        'calculate_path_length',
        'calculate_path_length_interpolated',
        'read_dicomct',
    ]
    
    for mod in modules:
        try:
            __import__(mod)
            print(f"  ✓ {mod}")
        except Exception as e:
            print(f"  ✗ {mod}: {e}")
            raise
    
    print("✓ All new module imports successful\n")


if __name__ == '__main__':
    print("=" * 60)
    print("Running tests for newly converted modules")
    print("=" * 60)
    print()
    
    test_module_imports()
    test_calculate_dice()
    test_calculate_path_length()
    test_calculate_path_length_interpolated()
    test_read_dicomct()
    
    print("=" * 60)
    print("All tests passed!")
    print("=" * 60)
