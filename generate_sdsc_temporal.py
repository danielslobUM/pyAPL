"""
Quick script to generate SDSC temporal line plot only.
"""
import sys
sys.path.insert(0, r'c:\Users\daniel.slob\Documents\pyAPL\pyAPL')

from explore_results import create_sdsc_temporal_lineplot

if __name__ == '__main__':
    import os
    output_dir = r'c:\Users\daniel.slob\Documents\pyAPL\explore_results\Overall'
    os.makedirs(output_dir, exist_ok=True)
    
    create_sdsc_temporal_lineplot(
        results_file=r'c:\Users\daniel.slob\Documents\pyAPL\contour_comparison_results_P0728_v7.xlsx',
        output_file=os.path.join(output_dir, 'sdsc_temporal_lineplot.png')
    )
    print("\n✓ Done! Plot saved to: explore_results/Overall/sdsc_temporal_lineplot.png")
