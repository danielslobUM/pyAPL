"""
remove_duplicates.py - Remove duplicate rows from failed_chain_ct_filepaths output

Reads the failed_chain_ct_filepaths.xlsx file and removes duplicate rows,
keeping only unique pNumber + CTSeriesUID combinations.

Usage:
    python remove_duplicates.py [input_file] [output_file]
"""

import sys
import pandas as pd
from pathlib import Path

# ============================================================================
# CONFIGURATION
# ============================================================================

SCRIPT_DIR = Path(__file__).parent
DEFAULT_INPUT_FILE = str(SCRIPT_DIR.parent / 'failed_chain_ct_filepaths.xlsx')
DEFAULT_OUTPUT_FILE = str(SCRIPT_DIR.parent / 'failed_chain_ct_filepaths_deduped.xlsx')

# Columns to consider for identifying duplicates
# For CT filepaths, we want unique pNumber + CTSeriesUID combinations
SUBSET_COLUMNS = ['pNumber', 'CTSeriesUID']


# ============================================================================
# MAIN LOGIC
# ============================================================================

def remove_duplicates(input_file: str, output_file: str, subset: list = None):
    """
    Remove duplicate rows from an Excel file.

    Parameters
    ----------
    input_file : str
        Path to the input Excel file
    output_file : str
        Path for the output Excel file
    subset : list, optional
        List of column names to consider for identifying duplicates.
        If None, all columns are considered.
    """
    print(f"Loading: {input_file}")
    df = pd.read_excel(input_file, engine='openpyxl')
    
    original_count = len(df)
    print(f"Original rows: {original_count}")
    
    if subset:
        print(f"Identifying duplicates based on columns: {subset}")
    else:
        print("Identifying duplicates based on all columns")
    
    # Remove duplicates, keeping first occurrence
    df_deduped = df.drop_duplicates(subset=subset, keep='first')
    
    deduped_count = len(df_deduped)
    removed_count = original_count - deduped_count
    
    print(f"Rows after deduplication: {deduped_count}")
    print(f"Duplicates removed: {removed_count}")
    
    # Save to output file
    df_deduped.to_excel(output_file, index=False, engine='openpyxl')
    print(f"Saved to: {output_file}")
    
    return df_deduped


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == '__main__':
    input_file = DEFAULT_INPUT_FILE
    output_file = DEFAULT_OUTPUT_FILE
    
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    
    print("=" * 70)
    print("Remove Duplicate Rows from Excel File")
    print("=" * 70)
    print(f"Input file:  {input_file}")
    print(f"Output file: {output_file}")
    print("=" * 70)
    
    remove_duplicates(input_file, output_file, subset=SUBSET_COLUMNS)
