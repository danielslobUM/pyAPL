# Synthetic RTSTRUCT File Generation for Testing

## Overview

This document explains how to create synthetic RTSTRUCT files that are compatible with `quantifyContourDifferences.m` for testing contour comparison functionality.

## The Problem

When creating synthetic RTSTRUCT files for testing, you need to ensure that:
1. Both RTSTRUCT files contain structures with **matching names**
2. The structures have different geometries to enable meaningful comparisons

The original approach created files with different structure names:
- File 1: "Square Contour"
- File 2: "Rectangle Contour"

This caused the MATLAB script to report: "No common VOIs found for patient"

## The Solution

The `zelf maken.py` script now creates two RTSTRUCT files with:
- **Matching structure names**: Both files contain a structure named "Test Contour"
- **Different geometries**: 
  - File 1: Square-shaped contour
  - File 2: Rectangle-shaped contour (same x-dimension, 2x y-dimension)

This allows `quantifyContourDifferences.m` to:
1. Find the common structure name in both files
2. Compare the geometrically different contours
3. Calculate DICE, APL, and Surface DICE metrics

## Usage

### Prerequisites

Install the required Python package:
```bash
pip install rt-utils
```

### Running the Script

1. **Edit the DICOM series path** in `zelf maken.py`:
   ```python
   dicom_series_path = "C:\\path\\to\\your\\DICOM\\series"
   ```

2. **Run the script**:
   ```bash
   python "zelf maken.py"
   ```

3. **Output**: Two DICOM RTSTRUCT files will be created:
   - `RTStructfile1_allslices_synth.dcm` - Contains square contour
   - `RTStructfile2_allslices_synth.dcm` - Contains rectangle contour

### Using with quantifyContourDifferences.m

1. Place the generated RTSTRUCT files in appropriate folders:
   - File 1 in the "Method 1" or "Reference" folder
   - File 2 in the "Method 2" or "Comparison" folder

2. Run the MATLAB script:
   ```matlab
   quantifyContourDifferences(1, rootFolder)
   ```

3. When prompted to select structures, you should see "Test Contour" as a common structure in both files.

## Technical Details

### Structure Name Matching

The MATLAB function `quantifyContourDifferences.m` (line 184-187) uses:
```matlab
toCompare = find(ismember(VOIs1,VOIs2));
```

This checks if structure names from the first RTSTRUCT exist in the second RTSTRUCT. For comparison to work:
- Structure names must match **exactly**
- At least one common structure name must exist in both files

### Contour Geometry

Both contours are:
- Applied to **all slices** in the DICOM series
- Centered at the image isocenter
- Scaled based on image dimensions

The geometries differ in the y-dimension:
- Square: Base size in both x and y directions
- Rectangle: Same x-dimension as square, but 2x the y-dimension

This creates a measurable difference that will be reflected in the DICE, APL, and Surface DICE metrics.

## Troubleshooting

### "No common VOIs found"
- Ensure both RTSTRUCT files use the **same structure name**
- Check that structure names don't have trailing spaces or different capitalization

### "DICOM series path does not exist"
- Update the `dicom_series_path` variable in the script to point to a valid DICOM CT series folder

### MATLAB cannot read the files
- Ensure the RTSTRUCT files are saved with `.dcm` extension
- Verify the files are valid DICOM files using a DICOM viewer
- Check that the RTSTRUCT files reference the same CT series

## Example Output

When the script runs successfully, you should see:
```
Looking for DICOM series at: C:\path\to\DICOM\series
Saved RTStruct file 1 (Square) to: C:\path\RTStructfile1_allslices_synth.dcm
  Structure name: 'Test Contour'
Saved RTStruct file 2 (Rectangle) to: C:\path\RTStructfile2_allslices_synth.dcm
  Structure name: 'Test Contour'

================================================================================
SUCCESS!
================================================================================

Both RTSTRUCT files have been created with matching structure name: 'Test Contour'
This allows quantifyContourDifferences.m to find common VOIs and perform comparisons.
```

## References

- RT-Utils library: https://github.com/qurit/rt-utils
- DICOM Standard: https://www.dicomstandard.org/
