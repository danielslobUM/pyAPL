import pandas as pd
import os

data = pd.read_excel("contour_comparison_results_P0728_v5.xlsx")

# Filter out rows where SDSC_tol0 is None/NaN
data_valid = data[data['SDSC_tol0'].notna()].copy()

print(f"Total records with valid SDSC_tol0: {len(data_valid)}")

# Get unique VOI names
unique_vois = data_valid['VOIName'].unique()
print(f"Number of unique VOI names: {len(unique_vois)}")

# Create summary for each VOI
summary_data = []
for voi in unique_vois:
    voi_data = data_valid[data_valid['VOIName'] == voi]
    
    # Count where SDSC_tol0 = 1 (perfect match)
    count_perfect_sdsc = len(voi_data[voi_data['SDSC_tol0'] == 1.0])
    
    # Count SDSC_tol0 in various ranges
    count_sdsc_above_0_9 = len(voi_data[voi_data['SDSC_tol0'] > 0.9])
    count_sdsc_above_0_8 = len(voi_data[voi_data['SDSC_tol0'] > 0.8])
    count_sdsc_below_0_4 = len(voi_data[voi_data['SDSC_tol0'] < 0.4])
    count_sdsc_below_0_3 = len(voi_data[voi_data['SDSC_tol0'] < 0.3])
    count_sdsc_below_0_2 = len(voi_data[voi_data['SDSC_tol0'] < 0.2])
    count_sdsc_equals_0 = len(voi_data[voi_data['SDSC_tol0'] == 0.0])
    
    # Count where APL_tol0 = 0 (perfect match)
    count_perfect_apl = len(voi_data[voi_data['APL_tol0'] == 0.0])
    
    total = len(voi_data)
    pct_perfect_sdsc = (count_perfect_sdsc / total * 100) if total > 0 else 0
    pct_sdsc_above_0_9 = (count_sdsc_above_0_9 / total * 100) if total > 0 else 0
    pct_sdsc_above_0_8 = (count_sdsc_above_0_8 / total * 100) if total > 0 else 0
    pct_sdsc_below_0_4 = (count_sdsc_below_0_4 / total * 100) if total > 0 else 0
    pct_sdsc_below_0_3 = (count_sdsc_below_0_3 / total * 100) if total > 0 else 0
    pct_sdsc_below_0_2 = (count_sdsc_below_0_2 / total * 100) if total > 0 else 0
    pct_sdsc_equals_0 = (count_sdsc_equals_0 / total * 100) if total > 0 else 0
    pct_perfect_apl = (count_perfect_apl / total * 100) if total > 0 else 0
    
    summary_data.append({
        'VOIName': voi,
        'Total_Count': total,
        'SDSC_tol0_Equals_1': count_perfect_sdsc,
        'Percent_Perfect_SDSC': round(pct_perfect_sdsc, 2),
        'SDSC_tol0_Above_0.9': count_sdsc_above_0_9,
        'Percent_Above_0.9': round(pct_sdsc_above_0_9, 2),
        'SDSC_tol0_Above_0.8': count_sdsc_above_0_8,
        'Percent_Above_0.8': round(pct_sdsc_above_0_8, 2),
        'SDSC_tol0_Below_0.4': count_sdsc_below_0_4,
        'Percent_Below_0.4': round(pct_sdsc_below_0_4, 2),
        'SDSC_tol0_Below_0.3': count_sdsc_below_0_3,
        'Percent_Below_0.3': round(pct_sdsc_below_0_3, 2),
        'SDSC_tol0_Below_0.2': count_sdsc_below_0_2,
        'Percent_Below_0.2': round(pct_sdsc_below_0_2, 2),
        'APL_tol0_Equals_0': count_perfect_apl,
        'Percent_Perfect_APL': round(pct_perfect_apl, 2)
    })

summary = pd.DataFrame(summary_data)

# Explicitly set column order
column_order = [
    'VOIName',
    'Total_Count',
    'SDSC_tol0_Equals_1',
    'Percent_Perfect_SDSC',
    'SDSC_tol0_Above_0.9',
    'Percent_Above_0.9',
    'SDSC_tol0_Above_0.8',
    'Percent_Above_0.8',
    'SDSC_tol0_Below_0.4',
    'Percent_Below_0.4',
    'SDSC_tol0_Below_0.3',
    'Percent_Below_0.3',
    'SDSC_tol0_Below_0.2',
    'Percent_Below_0.2',
    'APL_tol0_Equals_0',
    'Percent_Perfect_APL'
]
summary = summary[column_order]
summary = summary.sort_values('VOIName')

# Display summary
print("\n" + "="*80)
print("SDSC_tol0 Analysis by VOI Name")
print("="*80)
print(summary.to_string(index=False))

# Save to Excel with append/update logic
output_file = 'investigate_output.xlsx'

if os.path.exists(output_file):
    try:
        # Load existing data
        existing_df = pd.read_excel(output_file, engine='openpyxl')
        print(f"\nLoaded existing file with {len(existing_df)} record(s)")
        
        # Get VOI names to update vs append
        existing_vois = set(existing_df['VOIName'].unique())
        new_vois = set(summary['VOIName'].unique())
        
        vois_to_update = new_vois & existing_vois
        vois_to_append = new_vois - existing_vois
        
        if vois_to_update:
            print(f"Updating {len(vois_to_update)} existing VOI(s)")
            # Remove old records for VOIs being updated
            existing_df = existing_df[~existing_df['VOIName'].isin(vois_to_update)]
        
        if vois_to_append:
            print(f"Appending {len(vois_to_append)} new VOI(s)")
        
        # Combine: existing (without updated) + all new
        combined_df = pd.concat([existing_df, summary], ignore_index=True)
        combined_df = combined_df.sort_values('VOIName')
        
        # Ensure column order matches
        combined_df = combined_df[column_order]
        
        combined_df.to_excel(output_file, index=False, engine='openpyxl')
        print(f"Saved {len(combined_df)} total record(s) to {output_file}")
        
    except Exception as e:
        print(f"Error reading existing file: {e}")
        print("Creating new file instead...")
        summary.to_excel(output_file, index=False, engine='openpyxl')
        print(f"Results saved to {output_file}")
else:
    # Create new file
    summary.to_excel(output_file, index=False, engine='openpyxl')
    print(f"Created new file: {output_file}")