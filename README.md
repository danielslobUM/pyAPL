# pyAPL

Python scripts for calculating the Added Path Length (APL) and other contour comparison metrics for medical imaging (DICOM RTSTRUCT).

## Overview

This repository contains Python scripts converted from MATLAB for quantifying differences between contours delineated by different methods or persons. The main batch file `quantify_contour_differences.py` orchestrates all other modules to compute:

- **Volumetric DICE**: Dice similarity coefficient based on volume overlap
- **Added Path Length (APL)**: Path length differences between contours
- **Surface DICE**: Dice coefficient based on surface overlap

## Installation

### Requirements

- Python 3.7+
- NumPy
- SciPy
- PyDICOM
- scikit-image
- pandas

### Setup

1. Clone this repository:
```bash
git clone https://github.com/danielslobUM/pyAPL.git
cd pyAPL
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

Run the main script:
```bash
python quantify_contour_differences.py
```

This will:
1. Prompt you to select a folder containing imaging data (CT scans)
2. Prompt you to select RTSTRUCT files for method/person 1 (reference)
3. Prompt you to select RTSTRUCT files for method/person 2 (comparison)
4. Ask you to select which structures (OARs) to compare
5. Calculate metrics and save results to CSV

### Python API

You can also use the function programmatically:

```python
from quantify_contour_differences import quantify_contour_differences

# Calculate all parameters (DICE, APL, Surface DSC)
results = quantify_contour_differences(calc_all_parameters=1, root_folder='/path/to/data')

# Calculate only DICE (faster)
results = quantify_contour_differences(calc_all_parameters=0, root_folder='/path/to/data')
```

## Module Description

### Main Module
- **quantify_contour_differences.py**: Main batch processing script

### Utility Modules
- **read_dicomct_light.py**: Lightweight DICOM CT reader (metadata only)
- **read_dicomrtstruct.py**: DICOM RTSTRUCT reader
- **resample_contour_slices.py**: Contour resampling and binary volume creation
- **compose_struct_matrix.py**: Matrix representation of structures
- **has_contour_points_local.py**: Check for empty contours

### Calculation Modules
- **calculate_dice_logical.py**: Volumetric DICE calculation
- **calculate_surface_dsc.py**: Surface DICE calculation
- **calculate_different_path_length_v2.py**: Added path length calculation
- **calculate_voxel_diff_counts.py**: Voxel difference counting

## MATLAB Scripts

The original MATLAB scripts are also included in this repository for reference and can be used with MATLAB if preferred.

## Credits

Original MATLAB scripts by:
- Rik Hansen (17/02/2025)
- Daniël Slob (25/08/2025)
- Femke Vaassen @ MAASTRO
- Jose A. Baeza @ MAASTRO

Python conversion: 2025

## License

Please refer to the repository license for usage terms. 
