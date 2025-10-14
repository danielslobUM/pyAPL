"""
Example usage of the pyAPL Python modules.

This script demonstrates how to use the converted Python modules
for calculating contour differences.
"""

import os
from quantify_contour_differences import quantify_contour_differences


def example_1_full_calculation():
    """
    Example 1: Run full calculation with all parameters (DICE, APL, Surface DSC).
    
    This will prompt you to select folders containing:
    - Imaging data (CT scans)
    - RTSTRUCT files for method/person 1 (reference)
    - RTSTRUCT files for method/person 2 (comparison)
    """
    print("="*80)
    print("Example 1: Full calculation with all parameters")
    print("="*80)
    
    # Run with all parameters calculated
    results = quantify_contour_differences(
        calc_all_parameters=1,  # Calculate DICE, APL, and Surface DSC
        root_folder=os.getcwd()  # Start folder selection from current directory
    )
    
    if results is not None and not results.empty:
        print("\nResults:")
        print(results)
        
        # Save results to CSV
        output_file = 'contour_comparison_results_full.csv'
        results.to_csv(output_file, index=False)
        print(f"\nResults saved to {output_file}")
    else:
        print("No results generated.")


def example_2_dice_only():
    """
    Example 2: Calculate only volumetric DICE (faster).
    
    This skips APL and Surface DSC calculations for faster processing.
    """
    print("="*80)
    print("Example 2: Calculate DICE only (faster)")
    print("="*80)
    
    # Run with only DICE calculation
    results = quantify_contour_differences(
        calc_all_parameters=0,  # Only calculate DICE
        root_folder=os.getcwd()
    )
    
    if results is not None and not results.empty:
        print("\nResults:")
        print(results)
        
        # Save results to CSV
        output_file = 'contour_comparison_results_dice_only.csv'
        results.to_csv(output_file, index=False)
        print(f"\nResults saved to {output_file}")
    else:
        print("No results generated.")


def example_3_programmatic():
    """
    Example 3: Programmatic usage with direct folder paths.
    
    For automated workflows, you can provide folder paths directly
    instead of using the GUI dialog.
    """
    print("="*80)
    print("Example 3: Programmatic usage")
    print("="*80)
    
    # Define your folder paths here
    # imaging_folder = "/path/to/imaging/data"
    # rtstruct1_folder = "/path/to/rtstruct/method1"
    # rtstruct2_folder = "/path/to/rtstruct/method2"
    
    print("Note: This example requires you to modify the script")
    print("      with actual folder paths for automated processing.")
    print("\nExample code:")
    print("""
    from quantify_contour_differences import quantify_contour_differences
    
    # Set folder paths
    imaging_folder = "/path/to/imaging/data"
    rtstruct1_folder = "/path/to/rtstruct/method1"
    rtstruct2_folder = "/path/to/rtstruct/method2"
    
    # Run comparison
    results = quantify_contour_differences(
        calc_all_parameters=1,
        root_folder="/path/to/root"
    )
    
    # Process results
    if results is not None:
        print(results)
        results.to_csv('results.csv', index=False)
    """)


def main():
    """Main function to run examples."""
    print("\n" + "="*80)
    print("pyAPL Python Examples")
    print("="*80)
    print("\nAvailable examples:")
    print("1. Full calculation (DICE + APL + Surface DSC)")
    print("2. DICE only (faster)")
    print("3. Programmatic usage example")
    print("0. Exit")
    
    choice = input("\nSelect an example to run (0-3): ").strip()
    
    if choice == '1':
        example_1_full_calculation()
    elif choice == '2':
        example_2_dice_only()
    elif choice == '3':
        example_3_programmatic()
    elif choice == '0':
        print("Exiting.")
    else:
        print("Invalid choice. Please select 0-3.")


if __name__ == '__main__':
    main()
