"""
Quick script to generate OAR summary table with overall averages.
"""
import sys
sys.path.insert(0, r'c:\Users\daniel.slob\Documents\pyAPL\pyAPL')

print("Importing create_oar_summary_table...")
from explore_results import create_oar_summary_table

if __name__ == '__main__':
    import os
    output_dir = r'c:\Users\daniel.slob\Documents\pyAPL\explore_results\Overall'
    os.makedirs(output_dir, exist_ok=True)
    
    print("Starting OAR summary generation...")
    create_oar_summary_table(
        results_file=r'c:\Users\daniel.slob\Documents\pyAPL\contour_comparison_results_P0728_v7.xlsx',
        dicom_root=r'Z:\ICoNEA\DICOM',
        output_file=os.path.join(output_dir, 'oar_summary_table.xlsx')
    )
    print("\n✓ Done! Table saved to: explore_results/Overall/oar_summary_table.xlsx")
