# quantifycontourdifferences_P0728.py

## Overview

This script is designed to automatically process all patients in the P0728 dataset (or similar datasets) and compare RTSTRUCT contours between two methods/persons. It uses the LinkedDICOM TTL files for metadata and automatically discovers the correct DICOM files for each patient.

## Folder Structure

The script expects the following folder structure:

```
DICOM/
├── P123456789012345/           # Patient folder (starts with 'P')
│   ├── linkeddicom.ttl         # LinkedDICOM metadata file (optional)
│   ├── CT/                     # CT images folder
│   │   └── 20230101/           # Date-based subfolder
│   │       ├── image001.dcm
│   │       ├── image002.dcm
│   │       └── ...
│   ├── RTDOSE/                 # RT Dose folder (not used by this script)
│   ├── RTPLAN/                 # RT Plan folder (not used by this script)
│   └── RTSTRUCT/               # RT Structure Set folder
│       ├── method1/            # Method 1 RTSTRUCT files (or date folder)
│       │   └── struct.dcm
│       └── method2/            # Method 2 RTSTRUCT files (or date folder)
│           └── struct.dcm
└── P987654321098765/           # Another patient folder
    └── ...
```

## Usage

### Basic Usage (Command Line)

```bash
python quantifycontourdifferences_P0728.py
```

The script will prompt you to:
1. Use the default DICOM root folder or specify a custom path
2. Select which structures (OARs) to compare

**Note:** By default, the script is configured to process only the first 5 patients as a sample test. To process all patients, modify the `MAX_PATIENTS` variable in the script or use command-line arguments.

### Usage with Command-Line Arguments

```bash
python quantifycontourdifferences_P0728.py /path/to/DICOM method1 method2 5
```

Arguments:
1. Path to DICOM root folder
2. Method 1 identifier (string that appears in folder/file names)
3. Method 2 identifier (string that appears in folder/file names)
4. Maximum number of patients to process (optional, use 'none' for all patients)

### Python API Usage

```python
from quantifycontourdifferences_P0728 import quantify_contour_differences_p0728

# Sample test mode - process only 5 patients
results = quantify_contour_differences_p0728(
    dicom_root_folder='/path/to/DICOM',
    method1_identifier='method1',
    method2_identifier='method2',
    calc_all_parameters=1,  # Calculate DICE, APL, and Surface DSC
    selected_oars=None,     # Will prompt for selection
    max_patients=5          # Limit to 5 patients
)

# Process all patients
results = quantify_contour_differences_p0728(
    dicom_root_folder='/path/to/DICOM',
    method1_identifier='method1',
    method2_identifier='method2',
    calc_all_parameters=1,
    selected_oars=None,
    max_patients=None       # Process all patients
)

# With pre-selected OARs
results = quantify_contour_differences_p0728(
    dicom_root_folder='/path/to/DICOM',
    method1_identifier='method1',
    method2_identifier='method2',
    calc_all_parameters=1,
    selected_oars=['Lung_L', 'Lung_R', 'Heart'],  # Pre-select structures
    max_patients=5          # Limit to 5 patients
)

# Results are returned as a pandas DataFrame
print(results)
results.to_csv('results.csv', index=False)
```

## Method Identifiers

The script identifies RTSTRUCT files for each method using string matching. The method identifiers should appear in either:
- Folder names (e.g., `RTSTRUCT/method1/`, `RTSTRUCT/method2/`)
- File names (e.g., `struct_method1.dcm`, `struct_method2.dcm`)

### Common Identifier Patterns

- `method1`, `method2`
- `manual`, `automatic`
- `observer1`, `observer2`
- `original`, `revised`
- Date-based: If no identifier is found, the script will fall back to using date-based subdirectories

## Fallback Behavior

If the script cannot identify RTSTRUCT files using method identifiers, it will:

1. Look for date-based subdirectories in the RTSTRUCT folder
2. Use the earliest date as method 1 and the latest date as method 2
3. If only one date folder exists, use the first two RTSTRUCT files found

## Output

The script generates a pandas DataFrame with the following columns:

- **pNumber**: Patient identifier
- **VOIName**: Structure name
- **Dice**: Volumetric DICE coefficient (0-1, higher is better)
- **APL**: Added Path Length in cm (lower is better)
- **SDSC**: Surface DICE coefficient (0-1, higher is better)

Results are automatically saved to `contour_comparison_results_P0728.csv`.

## Requirements

Make sure all dependencies are installed:

```bash
pip install -r requirements.txt
```

Key dependencies:
- numpy
- scipy
- pydicom
- scikit-image
- pandas
- rdflib (for parsing LinkedDICOM TTL files)

## Configuration

Before running the script, update the configuration section in the `__main__` block:

```python
# Update these paths for your dataset
DICOM_ROOT_FOLDER = '/path/to/DICOM'  # Path to your DICOM root folder
METHOD1_IDENTIFIER = 'method1'        # String to identify method 1 files
METHOD2_IDENTIFIER = 'method2'        # String to identify method 2 files
```

## Troubleshooting

### "No patient folders found"
- Check that your DICOM root folder path is correct
- Ensure patient folders start with 'P'

### "No CT DICOM files found"
- Verify that CT files have `.dcm` extension
- Check that the CT folder exists and contains date-based subdirectories

### "Could not identify RTSTRUCT files by method identifier"
- Verify method identifiers match your folder/file naming
- Check that RTSTRUCT folder contains subdirectories or files with method identifiers
- The script will fall back to date-based matching if identifiers are not found

### "No common VOIs found"
- Ensure both RTSTRUCT files contain structures with matching names
- Structure names are case-sensitive

## LinkedDICOM Integration

The script is designed to work with LinkedDICOM metadata files (`linkeddicom.ttl`). While the current implementation includes a TTL parser, it primarily relies on the folder structure for file discovery. The TTL parsing functionality can be extended if your LinkedDICOM files contain specific file path information.

For more information about LinkedDICOM, see: https://github.com/MaastrichtU-CDS/LinkedDicom

## Examples

### Example 1: Process All Patients with Manual Selection

```python
from quantifycontourdifferences_P0728 import quantify_contour_differences_p0728

results = quantify_contour_differences_p0728(
    dicom_root_folder='/data/P0728/DICOM',
    method1_identifier='manual',
    method2_identifier='automatic'
)
```

The script will:
1. Scan for all patient folders in `/data/P0728/DICOM`
2. For each patient, find CT files and RTSTRUCT files for both methods
3. Prompt you to select which structures to compare (only once)
4. Calculate metrics for all patients and selected structures
5. Save results to CSV

### Example 2: Batch Processing with Pre-selected Structures

```python
from quantifycontourdifferences_P0728 import quantify_contour_differences_p0728

# Define structures to compare
oars_to_compare = [
    'Lung_L', 'Lung_R', 'Heart', 
    'Esophagus', 'SpinalCord'
]

results = quantify_contour_differences_p0728(
    dicom_root_folder='/data/P0728/DICOM',
    method1_identifier='v1',
    method2_identifier='v2',
    calc_all_parameters=1,
    selected_oars=oars_to_compare
)

# Save with custom filename
results.to_csv('comparison_v1_vs_v2.csv', index=False)

# Print summary statistics
print(f"\nProcessed {results['pNumber'].nunique()} patients")
print(f"Compared {results['VOIName'].nunique()} structures")
print(f"\nAverage DICE by structure:")
print(results.groupby('VOIName')['Dice'].mean().sort_values(ascending=False))
```

## Differences from quantify_contour_differences.py

The main differences from the original script are:

1. **Automatic patient discovery**: No need to manually select folders
2. **Built-in file search**: Automatically finds CT and RTSTRUCT files
3. **Method-based identification**: Identifies RTSTRUCT files by method identifier
4. **Batch processing**: Processes all patients in one run
5. **LinkedDICOM support**: Can parse TTL files for metadata (extensible)
6. **Fallback mechanisms**: Handles various folder structures automatically

## Support

For issues or questions, please refer to the main repository README or contact the maintainer.
