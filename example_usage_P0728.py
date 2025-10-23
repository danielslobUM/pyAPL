"""
Example usage of quantifycontourdifferences_P0728.py

This script demonstrates how to use the automated contour comparison
functionality for the P0728 dataset (or similar folder structures).
"""

from quantifycontourdifferences_P0728 import quantify_contour_differences_p0728
import pandas as pd


def example_basic_usage():
    """
    Example 1: Basic usage with user prompts for OAR selection.
    
    This will prompt the user to select which structures to compare.
    Processes only first 5 patients for sample testing.
    """
    print("="*80)
    print("Example 1: Basic Usage (Sample Test - 5 Patients)")
    print("="*80)
    
    results = quantify_contour_differences_p0728(
        # Update this path - should contain patient folders (e.g., P123456789012345/)
        # See README_P0728.md for expected folder structure
        dicom_root_folder='/path/to/your/DICOM',
        method1_identifier='method1',              # Update to match your naming
        method2_identifier='method2',              # Update to match your naming
        calc_all_parameters=1,                     # Calculate all metrics
        max_patients=5                             # Limit to 5 patients for sample test
    )
    
    if results is not None and not results.empty:
        print("\nResults:")
        print(results.to_string(index=False))
        results.to_csv('example_results_basic.csv', index=False)
        print("\nResults saved to example_results_basic.csv")
    else:
        print("\nNo results generated")


def example_preselected_oars():
    """
    Example 2: Batch processing with pre-selected structures.
    
    This avoids user prompts by pre-specifying which structures to compare.
    Useful for automated pipelines. Processes only 5 patients for sample test.
    """
    print("="*80)
    print("Example 2: Pre-selected OARs (Sample Test - 5 Patients)")
    print("="*80)
    
    # Define structures you want to compare
    structures_to_compare = [
        'Lung_L',
        'Lung_R', 
        'Heart',
        'Esophagus',
        'SpinalCord'
    ]
    
    results = quantify_contour_differences_p0728(
        dicom_root_folder='/path/to/your/DICOM',  # Update this path
        method1_identifier='manual',               # Update to match your naming
        method2_identifier='automatic',            # Update to match your naming
        calc_all_parameters=1,
        selected_oars=structures_to_compare,       # Pre-select structures
        max_patients=5                             # Limit to 5 patients
    )
    
    if results is not None and not results.empty:
        print("\nResults:")
        print(results.to_string(index=False))
        
        # Save results
        results.to_csv('example_results_preselected.csv', index=False)
        print("\nResults saved to example_results_preselected.csv")
        
        # Print summary statistics
        print("\n" + "="*80)
        print("Summary Statistics")
        print("="*80)
        print(f"Patients processed: {results['pNumber'].nunique()}")
        print(f"Structures compared: {results['VOIName'].nunique()}")
        print(f"\nAverage DICE by structure:")
        print(results.groupby('VOIName')['Dice'].mean().sort_values(ascending=False))
        
        if 'APL' in results.columns:
            print(f"\nAverage APL by structure:")
            print(results.groupby('VOIName')['APL'].mean().sort_values())
        
        if 'SDSC' in results.columns:
            print(f"\nAverage Surface DSC by structure:")
            print(results.groupby('VOIName')['SDSC'].mean().sort_values(ascending=False))
    else:
        print("\nNo results generated")


def example_dice_only():
    """
    Example 3: Calculate only DICE (faster processing).
    
    This skips APL and Surface DSC calculations for faster processing.
    Processes only 5 patients for sample test.
    """
    print("="*80)
    print("Example 3: DICE Only (Fast Mode - 5 Patients)")
    print("="*80)
    
    results = quantify_contour_differences_p0728(
        dicom_root_folder='/path/to/your/DICOM',
        method1_identifier='v1',
        method2_identifier='v2',
        calc_all_parameters=0,  # Only calculate DICE
        selected_oars=['Lung_L', 'Lung_R'],
        max_patients=5          # Limit to 5 patients
    )
    
    if results is not None and not results.empty:
        print("\nResults:")
        print(results.to_string(index=False))
        results.to_csv('example_results_dice_only.csv', index=False)
        print("\nResults saved to example_results_dice_only.csv")
    else:
        print("\nNo results generated")


def example_date_based_comparison():
    """
    Example 4: Using date-based folder structure.
    
    If your RTSTRUCT folders are organized by date rather than method identifier,
    the script will automatically use date-based matching as a fallback.
    To explicitly use date-based matching, provide identifiers that won't match
    your actual folder/file names, and the script will automatically fall back
    to sorting by date subdirectories.
    Processes only 5 patients for sample test.
    """
    print("="*80)
    print("Example 4: Date-based Comparison (5 Patients)")
    print("="*80)
    
    # Note: Using identifiers that don't match actual folder names triggers
    # automatic fallback to date-based comparison (earliest vs latest date)
    results = quantify_contour_differences_p0728(
        dicom_root_folder='/path/to/your/DICOM',
        method1_identifier='_no_match_1_',  # Placeholder - triggers date fallback
        method2_identifier='_no_match_2_',  # Placeholder - triggers date fallback
        calc_all_parameters=1,
        selected_oars=None,  # Will prompt
        max_patients=5       # Limit to 5 patients
    )
    
    if results is not None and not results.empty:
        print("\nResults:")
        print(results.to_string(index=False))
        results.to_csv('example_results_date_based.csv', index=False)
        print("\nResults saved to example_results_date_based.csv")
    else:
        print("\nNo results generated")


def example_custom_analysis():
    """
    Example 5: Custom analysis and filtering of results.
    
    Demonstrates how to filter and analyze results programmatically.
    Processes only 5 patients for sample test.
    """
    print("="*80)
    print("Example 5: Custom Analysis (5 Patients)")
    print("="*80)
    
    results = quantify_contour_differences_p0728(
        dicom_root_folder='/path/to/your/DICOM',
        method1_identifier='method1',
        method2_identifier='method2',
        calc_all_parameters=1,
        selected_oars=['Lung_L', 'Lung_R', 'Heart', 'Esophagus'],
        max_patients=5  # Limit to 5 patients
    )
    
    if results is not None and not results.empty:
        print("\nFull Results:")
        print(results.to_string(index=False))
        
        # Filter for high-quality matches (DICE > 0.9)
        high_quality = results[results['Dice'] > 0.9]
        print(f"\n{len(high_quality)} / {len(results)} comparisons have DICE > 0.9")
        
        # Filter for low-quality matches (DICE < 0.7)
        low_quality = results[results['Dice'] < 0.7]
        if not low_quality.empty:
            print(f"\nLow quality matches (DICE < 0.7):")
            print(low_quality[['pNumber', 'VOIName', 'Dice']].to_string(index=False))
        
        # Find structures with large APL values
        if 'APL' in results.columns:
            large_apl = results[results['APL'] > results['APL'].quantile(0.9)]
            if not large_apl.empty:
                print(f"\nStructures with large APL (top 10%):")
                print(large_apl[['pNumber', 'VOIName', 'APL']].to_string(index=False))
        
        # Patient-wise summary
        print("\nPatient-wise average DICE:")
        patient_summary = results.groupby('pNumber')['Dice'].agg(['mean', 'std', 'min', 'max'])
        print(patient_summary)
        
        # Structure-wise summary
        print("\nStructure-wise average DICE:")
        structure_summary = results.groupby('VOIName')['Dice'].agg(['mean', 'std', 'min', 'max'])
        print(structure_summary)
        
        # Save filtered results
        high_quality.to_csv('high_quality_matches.csv', index=False)
        if not low_quality.empty:
            low_quality.to_csv('low_quality_matches.csv', index=False)
        
        print("\nFiltered results saved")
    else:
        print("\nNo results generated")


if __name__ == '__main__':
    print("\n" + "="*80)
    print("quantifycontourdifferences_P0728.py - Example Usage")
    print("="*80)
    print()
    print("Before running these examples, update the DICOM folder paths")
    print("and method identifiers to match your dataset structure.")
    print()
    print("Available examples:")
    print("  1. Basic usage with user prompts")
    print("  2. Pre-selected OARs (batch processing)")
    print("  3. DICE only (fast mode)")
    print("  4. Date-based comparison")
    print("  5. Custom analysis and filtering")
    print()
    print("Uncomment the example you want to run below.")
    print("="*80 + "\n")
    
    # Uncomment one of the following to run an example:
    
    # example_basic_usage()
    # example_preselected_oars()
    # example_dice_only()
    # example_date_based_comparison()
    # example_custom_analysis()
    
    print("\nTo run an example, uncomment it in the code and update the paths.")
