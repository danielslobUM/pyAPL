"""
Create synthetic RTSTRUCT files for testing contour comparison.

This script creates two RTSTRUCT files with geometrically different contours
but with MATCHING structure names so they can be compared by quantifyContourDifferences.m

The key difference from the original approach:
- BOTH files contain a structure named "Test Contour"
- File 1: Contains a smaller rectangular contour (x = half base, y = base)
- File 2: Contains a larger rectangular contour (x = half base, y = 2x base)

This allows the MATLAB script to find common VOIs and perform comparisons.
"""

from rt_utils import RTStructBuilder
from rt_utils.rtstruct import RTStruct
from numpy.typing import NDArray
import numpy as np
import os


def create_square_mask(rtstruct: RTStruct) -> NDArray[np.bool_]:
    """
    Create a rectangular contour applied to ALL slices.
    The contour has x-dimension = half of base size and y-dimension = base size.
    """
    if not rtstruct.series_data:
        raise RuntimeError("No DICOM images were loaded from the provided series path.")

    ref = rtstruct.series_data[0]
    width = int(ref.Columns)   # x (Columns)
    height = int(ref.Rows)     # y (Rows)
    depth = len(rtstruct.series_data)  # z (Slices)

    # Initialize empty mask (all False)
    mask: NDArray[np.bool_] = np.zeros((width, height, depth), dtype=bool)

    # Define a centered rectangle with x-dimension = half of base size
    min_dim = min(width, height)
    square_size = max(10, min_dim // 16)  # Base size
    square_size_x = square_size // 2  # X dimension: half of base size
    square_size_y = square_size  # Y dimension: full base size
    
    # Center the contour at isocenter (exact center of image)
    x_center = width // 2
    y_center = height // 2
    x1 = x_center - square_size_x // 2
    x2 = x_center + square_size_x // 2
    y1 = y_center - square_size_y // 2
    y2 = y_center + square_size_y // 2

    # Apply contour to ALL slices
    for k in range(depth):
        mask[x1:x2, y1:y2, k] = True

    return mask


def create_rectangle_mask(rtstruct: RTStruct) -> NDArray[np.bool_]:
    """
    Create a rectangle with the same x-dimension as the square but 2x the y-dimension.
    Applied to ALL slices.
    """
    if not rtstruct.series_data:
        raise RuntimeError("No DICOM images were loaded from the provided series path.")

    ref = rtstruct.series_data[0]
    width = int(ref.Columns)
    height = int(ref.Rows)
    depth = len(rtstruct.series_data)

    mask: NDArray[np.bool_] = np.zeros((width, height, depth), dtype=bool)

    # Create RECTANGLE with same X as square (half of base), but 2x Y dimension
    min_dim = min(width, height)
    square_size = max(10, min_dim // 16)  # Same base size as square
    square_size_x = square_size // 2  # X dimension reduced to half (same as square)
    
    # Center the rectangle at isocenter (exact center of image)
    x_center = width // 2
    y_center = height // 2
    
    # Same x-dimension as square (half of base size)
    x1 = x_center - square_size_x // 2
    x2 = x_center + square_size_x // 2
    
    # Y-dimension: 2x the square's Y dimension
    rect_height = square_size * 2  # Double the base square size for height
    y1 = y_center - rect_height // 2
    y2 = y_center + rect_height // 2

    # Apply rectangle to ALL slices
    for k in range(depth):
        mask[x1:x2, y1:y2, k] = True

    return mask


def main():
    # Update this path to match your actual DICOM series location
    # Example: dicom_series_path = "C:\\path\\to\\your\\DICOM\\series\\CT\\Patient001"
    dicom_series_path = (
        "C:\\Users\\USERNAME\\Path\\To\\DICOM\\CT\\P0001C"
    )
    
    print(f"Looking for DICOM series at: {dicom_series_path}")
    if not os.path.exists(dicom_series_path):
        print(f"ERROR: DICOM series path does not exist!")
        print("Please update the dicom_series_path in the script to match your actual path.")
        return

    # IMPORTANT: Use MATCHING structure names so quantifyContourDifferences.m can find common VOIs
    # Both files will have a structure named "Test Contour" but with different geometries
    structure_name = "Test Contour"
    
    # Create RTStruct file 1 with smaller rectangular contour
    # This represents "method 1" or "reference" contour
    rtstruct1 = RTStructBuilder.create_new(dicom_series_path=dicom_series_path)
    square_mask = create_square_mask(rtstruct1)
    rtstruct1.add_roi(mask=square_mask, color=[255, 0, 0], name=structure_name)
    
    output_path1 = "RTStructfile1_allslices_synth"
    rtstruct1.save(output_path1)
    print(f"Saved RTStruct file 1 (Smaller Rectangle) to: {os.path.abspath(output_path1 if output_path1.endswith('.dcm') else output_path1 + '.dcm')}")
    print(f"  Structure name: '{structure_name}'")

    # Create RTStruct file 2 with larger rectangular contour (same x-dim, 2x y-dim)
    # This represents "method 2" or "comparison" contour
    rtstruct2 = RTStructBuilder.create_new(dicom_series_path=dicom_series_path)
    rectangle_mask = create_rectangle_mask(rtstruct2)
    rtstruct2.add_roi(mask=rectangle_mask, color=[0, 255, 0], name=structure_name)
    
    output_path2 = "RTStructfile2_allslices_synth"
    rtstruct2.save(output_path2)
    print(f"Saved RTStruct file 2 (Larger Rectangle) to: {os.path.abspath(output_path2 if output_path2.endswith('.dcm') else output_path2 + '.dcm')}")
    print(f"  Structure name: '{structure_name}'")
    
    print("\n" + "="*80)
    print("SUCCESS!")
    print("="*80)
    print(f"\nBoth RTSTRUCT files have been created with matching structure name: '{structure_name}'")
    print("This allows quantifyContourDifferences.m to find common VOIs and perform comparisons.")
    print("\nThe two files contain geometrically different contours:")
    print("  - File 1: Smaller rectangular contour (x = half base, y = base)")
    print("  - File 2: Larger rectangular contour (x = half base, y = 2x base)")
    print("\nYou can now use these files with the MATLAB quantifyContourDifferences.m script.")


if __name__ == "__main__":
    main()
