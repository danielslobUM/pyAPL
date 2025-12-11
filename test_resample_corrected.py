"""
Test the corrected resample_contour_slices implementation.
"""

import numpy as np
from resample_contour_slices import resample_contour_slices


def test_basic_functionality():
    """Test basic functionality with simple contour."""
    print("Testing basic functionality...")
    
    # Create a simple CT dictionary
    ct = {
        'PixelFirstXi': 0.0,
        'PixelFirstYi': 0.0,
        'PixelFirstZi': 0.0,
        'PixelSpacingXi': 1.0,
        'PixelSpacingYi': 1.0,
        'PixelSpacingZi': 1.0,
        'PixelNumXi': 10,
        'PixelNumYi': 10,
        'PixelNumZi': 10,
        'Image': np.zeros((10, 10, 10))
    }
    
    # Create a simple square contour in the middle slice
    # Square from (2,2,5) to (6,6,5)
    x_coords = [2.0, 6.0, 6.0, 2.0, 2.0]
    y_coords = [2.0, 2.0, 6.0, 6.0, 2.0]
    z_coords = [5.0, 5.0, 5.0, 5.0, 5.0]
    
    rts_cs = [
        {'X': x_coords, 'Y': y_coords, 'Z': z_coords}
    ]
    
    # Run the function
    rts_vol, minmax = resample_contour_slices(rts_cs, ct, 'test_structure')
    
    # Check that volume has correct shape
    assert rts_vol.shape == (10, 10, 10), f"Volume shape mismatch: {rts_vol.shape}"
    
    # Check that some voxels are marked (boundary points should be set)
    assert np.sum(rts_vol) > 0, "No voxels were marked in the volume"
    
    # Check minmax values are reasonable (1-indexed in our corrected version)
    assert minmax['minX'] >= 1, f"minX should be >= 1, got {minmax['minX']}"
    assert minmax['maxX'] <= 10, f"maxX should be <= 10, got {minmax['maxX']}"
    assert minmax['minZ'] >= 1, f"minZ should be >= 1, got {minmax['minZ']}"
    assert minmax['maxZ'] <= 10, f"maxZ should be <= 10, got {minmax['maxZ']}"
    
    print(f"  Volume shape: {rts_vol.shape}")
    print(f"  Number of marked voxels: {np.sum(rts_vol)}")
    print(f"  minmax: {minmax}")
    print("✓ Basic functionality test passed")


def test_empty_contour():
    """Test with empty contour."""
    print("Testing empty contour...")
    
    ct = {
        'PixelFirstXi': 0.0,
        'PixelFirstYi': 0.0,
        'PixelFirstZi': 0.0,
        'PixelSpacingXi': 1.0,
        'PixelSpacingYi': 1.0,
        'PixelSpacingZi': 1.0,
        'PixelNumXi': 10,
        'PixelNumYi': 10,
        'PixelNumZi': 10,
        'Image': np.zeros((10, 10, 10))
    }
    
    # Empty contour
    rts_cs = [
        {'X': [], 'Y': [], 'Z': []}
    ]
    
    rts_vol, minmax = resample_contour_slices(rts_cs, ct, 'empty_structure')
    
    # Check that volume is all zeros
    assert np.sum(rts_vol) == 0, "Empty contour should produce zero volume"
    
    print("✓ Empty contour test passed")


def test_multiple_slices():
    """Test with multiple slices."""
    print("Testing multiple slices...")
    
    ct = {
        'PixelFirstXi': 0.0,
        'PixelFirstYi': 0.0,
        'PixelFirstZi': 0.0,
        'PixelSpacingXi': 1.0,
        'PixelSpacingYi': 1.0,
        'PixelSpacingZi': 1.0,
        'PixelNumXi': 10,
        'PixelNumYi': 10,
        'PixelNumZi': 10,
        'Image': np.zeros((10, 10, 10))
    }
    
    # Create contours on two different slices
    rts_cs = [
        {
            'X': [3.0, 5.0, 5.0, 3.0, 3.0],
            'Y': [3.0, 3.0, 5.0, 5.0, 3.0],
            'Z': [3.0, 3.0, 3.0, 3.0, 3.0]
        },
        {
            'X': [3.0, 5.0, 5.0, 3.0, 3.0],
            'Y': [3.0, 3.0, 5.0, 5.0, 3.0],
            'Z': [7.0, 7.0, 7.0, 7.0, 7.0]
        }
    ]
    
    rts_vol, minmax = resample_contour_slices(rts_cs, ct, 'multi_slice_structure')
    
    # Check that volume has markings
    assert np.sum(rts_vol) > 0, "No voxels were marked"
    
    # Check that Z range covers both slices
    assert minmax['minZ'] <= 4, f"minZ should cover first slice, got {minmax['minZ']}"
    assert minmax['maxZ'] >= 7, f"maxZ should cover second slice, got {minmax['maxZ']}"
    
    print(f"  Number of marked voxels: {np.sum(rts_vol)}")
    print(f"  minmax: {minmax}")
    print("✓ Multiple slices test passed")


def test_all_points_filtered():
    """Test when all points are filtered out as invalid."""
    print("Testing all points filtered case...")
    
    ct = {
        'PixelFirstXi': 0.0,
        'PixelFirstYi': 0.0,
        'PixelFirstZi': 0.0,
        'PixelSpacingXi': 1.0,
        'PixelSpacingYi': 1.0,
        'PixelSpacingZi': 1.0,
        'PixelNumXi': 10,
        'PixelNumYi': 10,
        'PixelNumZi': 10,
        'Image': np.zeros((10, 10, 10))
    }
    
    # Create contour with all points way outside the grid (> 5 pixels)
    rts_cs = [
        {
            'X': [-100.0, -100.0, -100.0],
            'Y': [-100.0, -100.0, -100.0],
            'Z': [-100.0, -100.0, -100.0]
        }
    ]
    
    # Should handle gracefully and return empty volume
    rts_vol, minmax = resample_contour_slices(rts_cs, ct, 'invalid_structure')
    
    # Volume should be empty
    assert np.sum(rts_vol) == 0, "Volume should be empty when all points filtered"
    assert rts_vol.shape == (10, 10, 10), "Volume shape should still be correct"
    
    print("✓ All points filtered test passed")


def test_outside_grid():
    """Test handling of points outside the grid."""
    print("Testing outside grid handling...")
    
    ct = {
        'PixelFirstXi': 0.0,
        'PixelFirstYi': 0.0,
        'PixelFirstZi': 0.0,
        'PixelSpacingXi': 1.0,
        'PixelSpacingYi': 1.0,
        'PixelSpacingZi': 1.0,
        'PixelNumXi': 10,
        'PixelNumYi': 10,
        'PixelNumZi': 10,
        'Image': np.zeros((10, 10, 10))
    }
    
    # Create contour with some points outside the grid
    rts_cs = [
        {
            'X': [-5.0, 5.0, 15.0, 5.0, -5.0],  # Some points outside
            'Y': [5.0, -5.0, 5.0, 15.0, 5.0],   # Some points outside
            'Z': [5.0, 5.0, 5.0, 5.0, 5.0]
        }
    ]
    
    # This should print a warning but not crash
    rts_vol, minmax = resample_contour_slices(rts_cs, ct, 'outside_structure')
    
    # Volume should still be created
    assert rts_vol.shape == (10, 10, 10), "Volume shape mismatch"
    
    # All indices in minmax should be within valid range [1, 10] (MATLAB 1-indexed)
    assert 1 <= minmax['minX'] <= 10, f"minX out of range: {minmax['minX']}"
    assert 1 <= minmax['maxX'] <= 10, f"maxX out of range: {minmax['maxX']}"
    
    print(f"  minmax: {minmax}")
    print("✓ Outside grid test passed")


def test_interpolation_matches_matlab():
    """Test that interpolation matches MATLAB's behavior."""
    print("Testing interpolation matching...")
    
    # Simple test: interpolate [0, 1, 2] at positions 1, 1.5, 2
    # MATLAB: interp1([1,2,3], [0,1,2], [1, 1.5, 2]) -> [0, 0.5, 1]
    current = np.array([1, 2, 3])
    values = np.array([0.0, 1.0, 2.0])
    new_points = np.array([1, 1.5, 2])
    
    result = np.interp(new_points, current, values)
    expected = np.array([0.0, 0.5, 1.0])
    
    assert np.allclose(result, expected), f"Interpolation mismatch: {result} vs {expected}"
    
    print("✓ Interpolation test passed")


if __name__ == '__main__':
    print("=" * 60)
    print("Testing corrected resample_contour_slices implementation")
    print("=" * 60)
    print()
    
    test_interpolation_matches_matlab()
    print()
    test_basic_functionality()
    print()
    test_empty_contour()
    print()
    test_multiple_slices()
    print()
    test_all_points_filtered()
    print()
    test_outside_grid()
    print()
    
    print("=" * 60)
    print("All tests passed!")
    print("=" * 60)
