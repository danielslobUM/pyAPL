"""
Explore and visualize contour comparison results

This script loads the results CSV from quantifycontourdifferences_P0728.py
and creates visualizations showing average metrics (APL, DICE, SDSC) for each VOI.
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path


def load_results(results_file='contour_comparison_results_P0728_v6_with_dist.xlsx'):
    """
    Load the results Excel file.
    
    Parameters
    ----------
    results_file : str
        Path to the Excel file
        
    Returns
    -------
    pd.DataFrame
        Loaded results
    """
    if not Path(results_file).exists():
        raise FileNotFoundError(f"File not found: {results_file}")
    
    df = pd.read_excel(results_file)
    print(f"Loaded {len(df)} rows from {results_file}")
    print(f"Columns: {', '.join(df.columns)}")
    return df


def calculate_voi_averages(df):
    """
    Calculate average metrics for each VOI.
    
    Parameters
    ----------
    df : pd.DataFrame
        Results dataframe
        
    Returns
    -------
    pd.DataFrame
        Dataframe with average metrics per VOI
    """
    # Filter out rows with missing values in the metrics
    df_valid = df.dropna(subset=['Dice', 'APL', 'SDSC'])
    
    # Exclude BODY VOI
    df_valid = df_valid[df_valid['VOIName'].str.upper() != 'BODY']
    print(f"Excluded BODY VOI from calculations")
    
    # Group by VOIName and calculate averages and counts
    voi_averages = df_valid.groupby('VOIName').agg({
        'Dice': ['mean', 'count'],
        'APL': 'mean',
        'SDSC': 'mean'
    }).reset_index()
    
    # Flatten column names
    voi_averages.columns = ['VOIName', 'Dice', 'N', 'APL', 'SDSC']
    
    # Sort by VOI name for consistent display
    voi_averages = voi_averages.sort_values('VOIName')
    
    print(f"\nAverage metrics calculated for {len(voi_averages)} VOIs (BODY excluded)")
    return voi_averages


def show_voi_prevalence(df):
    """
    Display all unique VOI names and their prevalence (count).
    
    Parameters
    ----------
    df : pd.DataFrame
        Results dataframe
    """
    print("\n" + "="*80)
    print("VOI PREVALENCE")
    print("="*80)
    
    # Count occurrences of each VOI
    voi_counts = df['VOIName'].value_counts().sort_index()
    
    print(f"\nTotal unique VOIs: {len(voi_counts)}")
    print(f"Total measurements: {len(df)}")
    print("\nVOI Name : Count")
    print("-" * 40)
    
    for voi_name, count in voi_counts.items():
        print(f"{voi_name:30s} : {count:4d}")
    
    print("-" * 40)
    print(f"{'TOTAL':30s} : {voi_counts.sum():4d}")
    print("="*80)


def plot_voi_metrics(voi_averages, max_vois_per_plot=20, figsize=(25, 8)):
    """
    Create two separate bar plots: one for APL, one for DICE/SDSC comparison.
    Splits into multiple figures if there are more than max_vois_per_plot VOIs.
    
    Parameters
    ----------
    voi_averages : pd.DataFrame
        Dataframe with average metrics per VOI
    max_vois_per_plot : int
        Maximum number of VOIs to display per plot (default: 20)
    figsize : tuple
        Figure size (width, height)
    """
    n_vois = len(voi_averages)
    n_chunks = int(np.ceil(n_vois / max_vois_per_plot))
    
    # Split the dataframe into chunks
    voi_chunks = [voi_averages.iloc[i*max_vois_per_plot:(i+1)*max_vois_per_plot] for i in range(n_chunks)]
    
    print(f"\nSplitting {n_vois} VOIs into {n_chunks} bar plot(s) with max {max_vois_per_plot} VOIs each")
    
    # Calculate global y-axis limits for consistency across all plots
    # For DICE/SDSC: already fixed at [0, 1.05]
    dice_sdsc_ylim = [0, 1.05]
    
    # For APL: find the maximum value and add 10% padding
    max_apl = voi_averages['APL'].max()
    apl_ylim = [0, max_apl * 1.1]
    
    # ========== Plot 1: DICE and SDSC Comparison ==========
    for chunk_idx, voi_chunk in enumerate(voi_chunks):
        voi_names = voi_chunk['VOIName'].values
        dice_values = voi_chunk['Dice'].values
        sdsc_values = voi_chunk['SDSC'].values
        n_values = voi_chunk['N'].values
        
        # Set up the bar positions with extra spacing
        x = np.arange(len(voi_names)) * 1.5  # Multiply by 1.5 for extra spacing
        
        # Create labels with N counts
        voi_labels = [f'{name}\n(n={int(n)})' for name, n in zip(voi_names, n_values)]
        
        width = 0.35  # Width of each bar
        
        part_label = f" - Part {chunk_idx + 1}" if n_chunks > 1 else ""
        
        fig1, ax1 = plt.subplots(figsize=figsize)
        
        # Create the bars for DICE and SDSC
        bars1 = ax1.bar(x - width/2, dice_values, width, label='DICE', color='#2ecc71', alpha=0.8)
        bars2 = ax1.bar(x + width/2, sdsc_values, width, label='SDSC', color='#e74c3c', alpha=0.8)
        
        # Customize the plot
        ax1.set_xlabel('VOI Name', fontsize=12, fontweight='bold')
        ax1.set_ylabel('Average Score (0-1 scale)', fontsize=12, fontweight='bold')
        ax1.set_title(f'Average DICE and Surface DICE (SDSC) Scores by VOI{part_label}\n(BODY excluded)', 
                      fontsize=14, fontweight='bold', pad=20)
        ax1.set_xticks(x)
        ax1.set_xticklabels(voi_labels, rotation=45, ha='right')
        ax1.legend(loc='upper right', fontsize=11)
        ax1.grid(axis='y', alpha=0.3, linestyle='--')
        ax1.set_ylim(dice_sdsc_ylim)  # Use consistent y-axis across all plots
        
        # Add value labels on top of bars
        def add_value_labels(bars, ax):
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                        f'{height:.3f}',
                        ha='center', va='bottom', fontsize=8, rotation=0)
        
        add_value_labels(bars1, ax1)
        add_value_labels(bars2, ax1)
        
        plt.tight_layout()
        
        # Save the first figure
        output_file1 = f'voi_dice_sdsc_barplot_part{chunk_idx + 1}.png' if n_chunks > 1 else 'voi_dice_sdsc_barplot.png'
        plt.savefig(output_file1, dpi=300, bbox_inches='tight')
        print(f"\nDICE/SDSC bar plot{part_label} saved to {output_file1}")
        
        plt.show()
    
    # ========== Plot 2: APL ==========
    for chunk_idx, voi_chunk in enumerate(voi_chunks):
        voi_names = voi_chunk['VOIName'].values
        apl_values = voi_chunk['APL'].values
        n_values = voi_chunk['N'].values
        
        # Set up the bar positions with extra spacing
        x = np.arange(len(voi_names)) * 1.5  # Multiply by 1.5 for extra spacing
        
        # Create labels with N counts
        voi_labels = [f'{name}\n(n={int(n)})' for name, n in zip(voi_names, n_values)]
        
        width = 0.35  # Width of each bar
        
        part_label = f" - Part {chunk_idx + 1}" if n_chunks > 1 else ""
        
        fig2, ax2 = plt.subplots(figsize=figsize)
        
        # Create the bars for APL
        bars3 = ax2.bar(x, apl_values, width*2, label='APL', color='#e74c3c', alpha=0.8)
        
        # Customize the plot
        ax2.set_xlabel('VOI Name', fontsize=12, fontweight='bold')
        ax2.set_ylabel('Average Added Path Length (mm)', fontsize=12, fontweight='bold')
        ax2.set_title(f'Average Added Path Length (APL) by VOI{part_label}\n(BODY excluded)', 
                      fontsize=14, fontweight='bold', pad=20)
        ax2.set_xticks(x)
        ax2.set_xticklabels(voi_labels, rotation=45, ha='right')
        ax2.grid(axis='y', alpha=0.3, linestyle='--')
        ax2.set_ylim(apl_ylim)  # Use consistent y-axis across all plots
        
        # Add value labels on top of bars
        for bar in bars3:
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.2f}',
                    ha='center', va='bottom', fontsize=8, rotation=0)
        
        plt.tight_layout()
        
        # Save the second figure
        output_file2 = f'voi_apl_barplot_part{chunk_idx + 1}.png' if n_chunks > 1 else 'voi_apl_barplot.png'
        plt.savefig(output_file2, dpi=300, bbox_inches='tight')
        print(f"APL bar plot{part_label} saved to {output_file2}")
        
        plt.show()


def plot_voi_scatterplots(df, max_plots_per_figure=20):
    """
    Create scatterplots showing the distribution of values for each VOI.
    Creates two separate figures:
    1. DICE and SDSC values for each VOI
    2. APL values for each VOI
    
    Parameters
    ----------
    df : pd.DataFrame
        Full results dataframe
    max_plots_per_figure : int
        Maximum number of VOI plots per figure (default: 20)
    """
    # Filter valid data
    df_valid = df.dropna(subset=['Dice', 'APL', 'SDSC'])
    
    # Exclude BODY VOI
    df_valid = df_valid[df_valid['VOIName'].str.upper() != 'BODY']
    
    # Get unique VOIs
    voi_names = sorted(df_valid['VOIName'].unique())
    n_vois = len(voi_names)
    
    # Split VOIs into chunks of max_plots_per_figure
    n_chunks = int(np.ceil(n_vois / max_plots_per_figure))
    voi_chunks = [voi_names[i*max_plots_per_figure:(i+1)*max_plots_per_figure] for i in range(n_chunks)]
    
    print(f"\nSplitting {n_vois} VOIs into {n_chunks} figure(s) with max {max_plots_per_figure} plots each")
    
    # ========== Figure 1: DICE and SDSC Scatterplots ==========
    for chunk_idx, voi_chunk in enumerate(voi_chunks):
        n_vois_chunk = len(voi_chunk)
        n_cols = int(np.ceil(np.sqrt(n_vois_chunk)))
        n_rows = int(np.ceil(n_vois_chunk / n_cols))
        
        part_label = f"Part {chunk_idx + 1}" if n_chunks > 1 else ""
        title_suffix = f" - {part_label}" if part_label else ""
        
        fig1, axes1 = plt.subplots(n_rows, n_cols, figsize=(n_cols*4, n_rows*3))
        fig1.suptitle(f'Distribution of DICE and SDSC Values by VOI{title_suffix} (BODY excluded)', fontsize=16, fontweight='bold', y=0.995)
        
        # Flatten axes array for easier iteration
        if n_vois_chunk == 1:
            axes1 = [axes1]
        else:
            axes1 = axes1.flatten()
        
        for idx, voi_name in enumerate(voi_chunk):
            ax = axes1[idx]
            voi_data = df_valid[df_valid['VOIName'] == voi_name]
            
            # Create x-coordinates (jittered for visibility)
            n_points = len(voi_data)
            x_dice = np.random.normal(0, 0.02, n_points)
            x_sdsc = np.random.normal(1, 0.02, n_points)
            
            # Plot scatter points
            ax.scatter(x_dice, voi_data['Dice'], alpha=0.6, s=30, color='#2ecc71', label='DICE')
            ax.scatter(x_sdsc, voi_data['SDSC'], alpha=0.6, s=30, color='#3498db', label='SDSC')
            
            # Add mean lines
            ax.axhline(voi_data['Dice'].mean(), color='#2ecc71', linestyle='--', linewidth=2, alpha=0.8, xmin=0, xmax=0.45)
            ax.axhline(voi_data['SDSC'].mean(), color='#3498db', linestyle='--', linewidth=2, alpha=0.8, xmin=0.55, xmax=1)
            
            # Customize subplot
            ax.set_title(f'{voi_name}\n(n={n_points})', fontsize=10, fontweight='bold')
            ax.set_ylabel('Score (0-1)', fontsize=9)
            ax.set_xticks([0, 1])
            ax.set_xticklabels(['DICE', 'SDSC'], fontsize=9)
            ax.set_ylim([-0.05, 1.05])
            ax.grid(axis='y', alpha=0.3, linestyle='--')
            ax.set_xlim([-0.5, 1.5])
            
            # Add statistics text
            dice_mean = voi_data['Dice'].mean()
            dice_std = voi_data['Dice'].std()
            sdsc_mean = voi_data['SDSC'].mean()
            sdsc_std = voi_data['SDSC'].std()
            
            stats_text = f'DICE: {dice_mean:.3f}±{dice_std:.3f}\nSDSC: {sdsc_mean:.3f}±{sdsc_std:.3f}'
            ax.text(0.98, 0.02, stats_text, transform=ax.transAxes, fontsize=8,
                    verticalalignment='bottom', horizontalalignment='right',
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))
        
        # Hide unused subplots
        for idx in range(n_vois_chunk, len(axes1)):
            axes1[idx].axis('off')
        
        plt.tight_layout()
        output_file1 = f'voi_dice_sdsc_scatterplots_part{chunk_idx + 1}.png' if n_chunks > 1 else 'voi_dice_sdsc_scatterplots.png'
        plt.savefig(output_file1, dpi=300, bbox_inches='tight')
        print(f"\nDICE/SDSC scatterplots{title_suffix} saved to {output_file1}")
        plt.show()
    
    # ========== Figure 2: APL Scatterplots ==========
    for chunk_idx, voi_chunk in enumerate(voi_chunks):
        n_vois_chunk = len(voi_chunk)
        n_cols = int(np.ceil(np.sqrt(n_vois_chunk)))
        n_rows = int(np.ceil(n_vois_chunk / n_cols))
        
        part_label = f"Part {chunk_idx + 1}" if n_chunks > 1 else ""
        title_suffix = f" - {part_label}" if part_label else ""
        
        fig2, axes2 = plt.subplots(n_rows, n_cols, figsize=(n_cols*4, n_rows*3))
        fig2.suptitle(f'Distribution of APL Values by VOI{title_suffix} (BODY excluded)', fontsize=16, fontweight='bold', y=0.995)
        
        # Flatten axes array for easier iteration
        if n_vois_chunk == 1:
            axes2 = [axes2]
        else:
            axes2 = axes2.flatten()
        
        for idx, voi_name in enumerate(voi_chunk):
            ax = axes2[idx]
            voi_data = df_valid[df_valid['VOIName'] == voi_name]
            
            # Create x-coordinates (jittered for visibility)
            n_points = len(voi_data)
            x_apl = np.random.normal(0, 0.02, n_points)
            
            # Plot scatter points
            ax.scatter(x_apl, voi_data['APL'], alpha=0.6, s=30, color='#e74c3c')
            
            # Add mean line
            apl_mean = voi_data['APL'].mean()
            ax.axhline(apl_mean, color='#e74c3c', linestyle='--', linewidth=2, alpha=0.8)
            
            # Customize subplot
            ax.set_title(f'{voi_name}\n(n={n_points})', fontsize=10, fontweight='bold')
            ax.set_ylabel('APL (mm)', fontsize=9)
            ax.set_xticks([0])
            ax.set_xticklabels(['APL'], fontsize=9)
            ax.grid(axis='y', alpha=0.3, linestyle='--')
            ax.set_xlim([-0.5, 0.5])
            
            # Add statistics text
            apl_std = voi_data['APL'].std()
            apl_min = voi_data['APL'].min()
            apl_max = voi_data['APL'].max()
            
            stats_text = f'Mean: {apl_mean:.2f}±{apl_std:.2f} mm\nMin: {apl_min:.2f} mm\nMax: {apl_max:.2f} mm'
            ax.text(0.98, 0.98, stats_text, transform=ax.transAxes, fontsize=8,
                    verticalalignment='top', horizontalalignment='right',
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))
        
        # Hide unused subplots
        for idx in range(n_vois_chunk, len(axes2)):
            axes2[idx].axis('off')
        
        plt.tight_layout()
        output_file2 = f'voi_apl_scatterplots_part{chunk_idx + 1}.png' if n_chunks > 1 else 'voi_apl_scatterplots.png'
        plt.savefig(output_file2, dpi=300, bbox_inches='tight')
        print(f"APL scatterplots{title_suffix} saved to {output_file2}")
        plt.show()


def plot_voi_boxplots(df, max_plots_per_figure=20):
    """
    Create boxplots showing the distribution of values for each VOI.
    Split into multiple files to avoid overcrowding, with max 20 plots per figure.
    
    Parameters
    ----------
    df : pd.DataFrame
        Full results dataframe
    max_plots_per_figure : int
        Maximum number of VOI plots per figure (default: 20)
    """
    # Filter valid data
    df_valid = df.dropna(subset=['Dice', 'APL', 'SDSC'])
    
    # Exclude BODY VOI
    df_valid = df_valid[df_valid['VOIName'].str.upper() != 'BODY']
    
    # Get unique VOIs and split into chunks
    voi_names = sorted(df_valid['VOIName'].unique())
    n_vois = len(voi_names)
    n_chunks = int(np.ceil(n_vois / max_plots_per_figure))
    voi_chunks = [voi_names[i*max_plots_per_figure:(i+1)*max_plots_per_figure] for i in range(n_chunks)]
    
    print(f"\nSplitting {n_vois} VOIs into {n_chunks} set(s) with max {max_plots_per_figure} plots each:")
    for i, chunk in enumerate(voi_chunks):
        print(f"  Part {i+1}: {len(chunk)} VOIs")
    
    # Helper function to create boxplots for a subset of VOIs
    def create_dice_sdsc_boxplots(voi_subset, part_label):
        n_vois_subset = len(voi_subset)
        n_cols = int(np.ceil(np.sqrt(n_vois_subset)))
        n_rows = int(np.ceil(n_vois_subset / n_cols))
        
        fig, axes = plt.subplots(n_rows, n_cols, figsize=(n_cols*6, n_rows*5))
        fig.suptitle(f'Distribution of DICE and SDSC Values by VOI - {part_label} (BODY excluded)', 
                     fontsize=16, fontweight='bold', y=0.995)
        
        # Flatten axes array for easier iteration
        if n_vois_subset == 1:
            axes = [axes]
        else:
            axes = axes.flatten()
        
        for idx, voi_name in enumerate(voi_subset):
            ax = axes[idx]
            voi_data = df_valid[df_valid['VOIName'] == voi_name]
            
            n_points = len(voi_data)
            
            # Prepare data for boxplot
            data_to_plot = [voi_data['Dice'].values, voi_data['SDSC'].values]
            
            # Create boxplot
            bp = ax.boxplot(data_to_plot, labels=['DICE', 'SDSC'], patch_artist=True,
                            widths=0.6, showmeans=True,
                            boxprops=dict(alpha=0.7),
                            meanprops=dict(marker='D', markerfacecolor='red', markeredgecolor='red', markersize=6))
            
            # Color the boxes
            colors = ['#2ecc71', '#3498db']
            for patch, color in zip(bp['boxes'], colors):
                patch.set_facecolor(color)
            
            # Customize subplot
            ax.set_title(f'{voi_name}\n(n={n_points})', fontsize=10, fontweight='bold')
            ax.set_ylabel('Score (0-1)', fontsize=9)
            ax.set_ylim([-0.05, 1.05])
            ax.grid(axis='y', alpha=0.3, linestyle='--')
            
            # Add statistics text
            dice_mean = voi_data['Dice'].mean()
            dice_median = voi_data['Dice'].median()
            sdsc_mean = voi_data['SDSC'].mean()
            sdsc_median = voi_data['SDSC'].median()
            
            stats_text = f'DICE: μ={dice_mean:.3f}, m={dice_median:.3f}\nSDSC: μ={sdsc_mean:.3f}, m={sdsc_median:.3f}'
            ax.text(0.98, 0.02, stats_text, transform=ax.transAxes, fontsize=8,
                    verticalalignment='bottom', horizontalalignment='right',
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))
        
        # Hide unused subplots
        for idx in range(n_vois_subset, len(axes)):
            axes[idx].axis('off')
        
        plt.tight_layout(h_pad=3.0, w_pad=3.0)
        return fig
    
    def create_apl_boxplots(voi_subset, part_label):
        n_vois_subset = len(voi_subset)
        n_cols = int(np.ceil(np.sqrt(n_vois_subset)))
        n_rows = int(np.ceil(n_vois_subset / n_cols))
        
        fig, axes = plt.subplots(n_rows, n_cols, figsize=(n_cols*5, n_rows*4))
        fig.suptitle(f'Distribution of APL Values by VOI - {part_label} (BODY excluded)', 
                     fontsize=16, fontweight='bold', y=0.995)
        
        # Flatten axes array for easier iteration
        if n_vois_subset == 1:
            axes = [axes]
        else:
            axes = axes.flatten()
        
        for idx, voi_name in enumerate(voi_subset):
            ax = axes[idx]
            voi_data = df_valid[df_valid['VOIName'] == voi_name]
            
            n_points = len(voi_data)
            
            # Prepare data for boxplot
            data_to_plot = [voi_data['APL'].values]
            
            # Create boxplot
            bp = ax.boxplot(data_to_plot, labels=['APL'], patch_artist=True,
                            widths=0.6, showmeans=True,
                            boxprops=dict(facecolor='#e74c3c', alpha=0.7),
                            meanprops=dict(marker='D', markerfacecolor='darkred', markeredgecolor='darkred', markersize=6))
            
            # Customize subplot
            ax.set_title(f'{voi_name}\n(n={n_points})', fontsize=10, fontweight='bold')
            ax.set_ylabel('APL (mm)', fontsize=9)
            ax.grid(axis='y', alpha=0.3, linestyle='--')
            
            # Add statistics text
            apl_mean = voi_data['APL'].mean()
            apl_median = voi_data['APL'].median()
            apl_q25 = voi_data['APL'].quantile(0.25)
            apl_q75 = voi_data['APL'].quantile(0.75)
            
            stats_text = f'Mean: {apl_mean:.2f} mm\nMedian: {apl_median:.2f} mm\nQ1-Q3: {apl_q25:.2f}-{apl_q75:.2f} mm'
            ax.text(0.98, 0.98, stats_text, transform=ax.transAxes, fontsize=8,
                    verticalalignment='top', horizontalalignment='right',
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))
        
        # Hide unused subplots
        for idx in range(n_vois_subset, len(axes)):
            axes[idx].axis('off')
        
        plt.tight_layout(h_pad=3.0, w_pad=3.0)
        return fig
    
    # ========== Create DICE/SDSC Boxplots ==========
    for chunk_idx, voi_chunk in enumerate(voi_chunks):
        part_label = f"Part {chunk_idx + 1}" if n_chunks > 1 else ""
        fig = create_dice_sdsc_boxplots(voi_chunk, part_label if part_label else "All VOIs")
        output_file = f'voi_dice_sdsc_boxplots_part{chunk_idx + 1}.png' if n_chunks > 1 else 'voi_dice_sdsc_boxplots.png'
        fig.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"\nDICE/SDSC boxplots {part_label} saved to {output_file}" if part_label else f"\nDICE/SDSC boxplots saved to {output_file}")
        plt.show()
    
    # ========== Create APL Boxplots ==========
    for chunk_idx, voi_chunk in enumerate(voi_chunks):
        part_label = f"Part {chunk_idx + 1}" if n_chunks > 1 else ""
        fig = create_apl_boxplots(voi_chunk, part_label if part_label else "All VOIs")
        output_file = f'voi_apl_boxplots_part{chunk_idx + 1}.png' if n_chunks > 1 else 'voi_apl_boxplots.png'
        fig.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"APL boxplots {part_label} saved to {output_file}" if part_label else f"APL boxplots saved to {output_file}")
        plt.show()


def plot_status_distribution(df):
    """
    Create a pie chart showing the distribution of Status values.
    Records with no status value (NaN) are included as 'No Status'.
    
    Parameters
    ----------
    df : pd.DataFrame
        Results dataframe
    """
    print("\n" + "="*80)
    print("STATUS DISTRIBUTION")
    print("="*80)
    
    # Check if Status column exists
    if 'Status' not in df.columns:
        print("\nWarning: 'Status' column not found in dataframe.")
        print(f"Available columns: {', '.join(df.columns)}")
        return
    
    # Count status values, including NaN as a category
    status_counts = df['Status'].fillna('No Status').value_counts().sort_index()
    
    print(f"\nTotal records: {len(df)}")
    print("\nStatus Value : Count : Percentage")
    print("-" * 50)
    
    for status, count in status_counts.items():
        percentage = (count / len(df)) * 100
        print(f"{str(status):20s} : {count:5d} : {percentage:6.2f}%")
    
    print("-" * 50)
    print(f"{'TOTAL':20s} : {status_counts.sum():5d} : 100.00%")
    
    # Create pie chart
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # Generate colors
    colors = plt.cm.Set3(range(len(status_counts)))
    
    # Create the pie chart
    wedges, texts, autotexts = ax.pie(
        status_counts.values,
        labels=status_counts.index,
        autopct='%1.1f%%',
        colors=colors,
        startangle=90,
        textprops={'fontsize': 11, 'weight': 'bold'}
    )
    
    # Enhance the percentage text
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontsize(10)
        autotext.set_weight('bold')
    
    # Add title
    ax.set_title('Distribution of Status Values\n(including records with no status)',
                 fontsize=14, fontweight='bold', pad=20)
    
    # Add a legend with counts
    legend_labels = [f'{status}: {count} ({count/len(df)*100:.1f}%)' 
                     for status, count in status_counts.items()]
    ax.legend(legend_labels, loc='center left', bbox_to_anchor=(1, 0, 0.5, 1),
              fontsize=10)
    
    plt.tight_layout()
    
    # Save the figure
    output_file = 'status_distribution_pie_chart.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"\nStatus distribution pie chart saved to {output_file}")
    
    plt.show()
    print("="*80)


def print_summary_statistics(df, voi_averages):
    """
    Print summary statistics about the results.
    
    Parameters
    ----------
    df : pd.DataFrame
        Full results dataframe
    voi_averages : pd.DataFrame
        VOI averages dataframe
    """
    print("\n" + "="*80)
    print("SUMMARY STATISTICS")
    print("="*80)
    
    # Overall statistics
    df_valid = df.dropna(subset=['Dice', 'APL', 'SDSC'])
    print(f"\nTotal valid measurements: {len(df_valid)}")
    print(f"Number of unique VOIs: {df['VOIName'].nunique()}")
    print(f"Number of unique patients: {df['pNumber'].nunique()}")
    
    # Overall averages
    print(f"\nOverall Average DICE: {df_valid['Dice'].mean():.4f} (±{df_valid['Dice'].std():.4f})")
    print(f"Overall Average APL:  {df_valid['APL'].mean():.4f} mm (±{df_valid['APL'].std():.4f})")
    print(f"Overall Average SDSC: {df_valid['SDSC'].mean():.4f} (±{df_valid['SDSC'].std():.4f})")
    
    # Best and worst performing VOIs
    print("\n" + "-"*80)
    print("VOI Rankings")
    print("-"*80)
    
    print("\nHighest DICE scores:")
    top_dice = voi_averages.nlargest(5, 'Dice')[['VOIName', 'Dice']]
    for idx, row in top_dice.iterrows():
        print(f"  {row['VOIName']}: {row['Dice']:.4f}")
    
    print("\nLowest DICE scores:")
    bottom_dice = voi_averages.nsmallest(5, 'Dice')[['VOIName', 'Dice']]
    for idx, row in bottom_dice.iterrows():
        print(f"  {row['VOIName']}: {row['Dice']:.4f}")
    
    print("\nHighest APL (worse agreement):")
    top_apl = voi_averages.nlargest(5, 'APL')[['VOIName', 'APL']]
    for idx, row in top_apl.iterrows():
        print(f"  {row['VOIName']}: {row['APL']:.4f} mm")
    
    print("\nLowest APL (better agreement):")
    bottom_apl = voi_averages.nsmallest(5, 'APL')[['VOIName', 'APL']]
    for idx, row in bottom_apl.iterrows():
        print(f"  {row['VOIName']}: {row['APL']:.4f} mm")


def create_voi_pie_charts(results_file=None, base_output_dir='explore_results'):
    """
    Create pie charts for each VOI from the raw contour comparison results.
    
    Computes summary statistics (counts and percentages per SDSC_tol0 range)
    directly from the per-patient-per-VOI rows in the results file.
    
    Parameters
    ----------
    results_file : str, optional
        Path to the raw results Excel file (must contain 'VOIName' and 'SDSC_tol0' columns).
        Defaults to contour_comparison_results_P0728_v6.xlsx in the workspace root.
    base_output_dir : str
        Base directory to save the charts (each VOI gets its own subfolder)
    """
    import os
    
    # Default: look for the file relative to the script's parent directory (workspace root)
    if results_file is None:
        script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
        results_file = str(script_dir.parent / 'contour_comparison_results_P0728_v7.xlsx')
    
    # Load raw results
    if not Path(results_file).exists():
        raise FileNotFoundError(f"Results file not found: {results_file}")
    
    df = pd.read_excel(results_file, engine='openpyxl')
    print(f"Loaded {len(df)} rows from {results_file}")
    
    # Check required columns
    if 'VOIName' not in df.columns or 'SDSC' not in df.columns:
        raise ValueError("Results file must contain 'VOIName' and 'SDSC' columns")
    
    # Create base output directory
    base_path = Path(base_output_dir)
    base_path.mkdir(exist_ok=True)
    print(f"Saving charts to: {base_path.absolute()}")
    
    # Get unique VOIs
    unique_vois = df['VOIName'].dropna().unique()
    print(f"Found {len(unique_vois)} unique VOIs")
    
    # Process each VOI
    for voi_name in unique_vois:
        voi_df = df[df['VOIName'] == voi_name].copy()
        valid = voi_df['SDSC'].dropna()
        total_count = len(valid)
        
        # Skip if no data
        if total_count == 0:
            continue
        
        # Compute counts from raw SDSC values
        count_equals_1 = int((valid == 1.0).sum())
        count_above_0_8 = int((valid > 0.8).sum())
        count_below_0_4 = int((valid < 0.4).sum())
        count_below_0_2 = int((valid < 0.2).sum())
        
        # Calculate 5 pie sections
        count_perfect = count_equals_1                          # SDSC = 1.0
        count_good_not_perfect = count_above_0_8 - count_equals_1  # 0.8 < SDSC < 1.0
        count_middle = total_count - count_above_0_8 - count_below_0_4  # 0.4 ≤ SDSC ≤ 0.8
        count_poor_not_very = count_below_0_4 - count_below_0_2  # 0.2 ≤ SDSC < 0.4
        count_very_poor = count_below_0_2                       # SDSC < 0.2
        
        # Calculate percentages
        pct_perfect = 100.0 * count_perfect / total_count
        pct_good_not_perfect = 100.0 * count_good_not_perfect / total_count
        pct_middle = 100.0 * count_middle / total_count
        pct_poor_not_very = 100.0 * count_poor_not_very / total_count
        pct_very_poor = 100.0 * count_very_poor / total_count
        
        # Create pie chart with 5 sections
        fig, ax = plt.subplots(figsize=(12, 10))
        
        # Data for pie chart (5 sections)
        sizes = [count_perfect, count_good_not_perfect, count_middle, count_poor_not_very, count_very_poor]
        legend_labels = [
            f'Perfect (=1.0): {count_perfect} ({pct_perfect:.1f}%)',
            f'Good (0.8-1.0): {count_good_not_perfect} ({pct_good_not_perfect:.1f}%)',
            f'Fair (0.4-0.8): {count_middle} ({pct_middle:.1f}%)',
            f'Poor (0.2-0.4): {count_poor_not_very} ({pct_poor_not_very:.1f}%)',
            f'Very Poor (<0.2): {count_very_poor} ({pct_very_poor:.1f}%)'
        ]
        colors = ['#27ae60', '#2ecc71', '#f39c12', '#e74c3c', '#c0392b']  # Dark green, Light green, Orange, Light red, Dark red
        explode = (0.05, 0, 0, 0, 0.05)  # Slightly separate perfect and very poor sections
        
        # Custom autopct function to hide labels for very small slices
        def make_autopct(values):
            def my_autopct(pct):
                # Only show percentage if slice is >= 3%
                if pct >= 3:
                    return f'{pct:.1f}%'
                return ''
            return my_autopct
        
        # Create pie chart without labels (use legend instead)
        wedges, texts, autotexts = ax.pie(
            sizes,
            colors=colors,
            autopct=make_autopct(sizes),
            startangle=90,
            explode=explode,
            textprops={'fontsize': 11, 'weight': 'bold'},
            pctdistance=0.85,  # Position percentages closer to edge to avoid overlap
            labeldistance=1.1   # Not used when labels=None, but kept for clarity
        )
        
        # Add legend to avoid label overlap
        ax.legend(
            wedges,
            legend_labels,
            title="SDSC Score Ranges",
            loc="center left",
            bbox_to_anchor=(1, 0, 0.5, 1),
            fontsize=10,
            title_fontsize=11
        )
        
        # Set title with total count
        ax.set_title(
            f'{voi_name}\nTotal Count: {total_count}',
            fontsize=14,
            weight='bold',
            pad=20
        )
        
        # Ensure tight layout to prevent clipping
        plt.tight_layout()
        
        # Equal aspect ratio ensures circular pie
        ax.axis('equal')
        
        # Create VOI-specific subdirectory
        safe_voi_name = voi_name.replace('/', '_').replace('\\', '_').replace(':', '_').replace(' ', '_')
        voi_output_path = base_path / safe_voi_name
        voi_output_path.mkdir(exist_ok=True)
        
        # Save figure
        output_file = voi_output_path / 'pie_chart.png'
        plt.tight_layout()
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"  Created chart for: {voi_name}")
    
    print(f"\nSaved {len(unique_vois)} pie charts to {base_path.absolute()}")


def gmm_clustering(data):
    """
    Apply GMM with BIC-based model selection to 1D data.

    Returns
    -------
    labels : np.ndarray
        Cluster label for each element in data (aligned with data's index).
    centroid_dict : dict
        Mapping of cluster id -> mean value of that cluster.
    best_n : int
        Number of components selected.
    """
    from sklearn.mixture import GaussianMixture
    import numpy as np

    if len(data) < 3:
        return np.zeros(len(data), dtype=int), {0: data.mean()}, 1

    # Check if all values are identical
    if data.std() < 1e-10:
        return np.zeros(len(data), dtype=int), {0: data.mean()}, 1

    data_reshaped = data.values.reshape(-1, 1)

    # Try 1 to max_k components, select best by BIC
    max_k = min(6, len(data) // 3)  # Need at least 3 points per component
    max_k = max(1, max_k)

    best_bic = np.inf
    best_gmm = None
    best_n = 1

    for n_components in range(1, max_k + 1):
        try:
            gmm = GaussianMixture(n_components=n_components, random_state=42, n_init=5)
            gmm.fit(data_reshaped)
            bic = gmm.bic(data_reshaped)
            if bic < best_bic:
                best_bic = bic
                best_gmm = gmm
                best_n = n_components
        except Exception:
            continue

    if best_gmm is None:
        return np.zeros(len(data), dtype=int), {0: data.mean()}, 1

    labels = best_gmm.predict(data_reshaped)
    centroid_dict = {}
    for cid in np.unique(labels):
        centroid_dict[cid] = data[labels == cid].mean()

    return labels, centroid_dict, best_n


def gmm_clustering_2d(data_x, data_y):
    """
    Apply 2D GMM with BIC-based model selection.

    Parameters
    ----------
    data_x : pd.Series
        First variable (e.g. MinDist_PTV1_cm).
    data_y : pd.Series
        Second variable (e.g. SDSC_tol0).

    Returns
    -------
    labels : np.ndarray
        Cluster label per sample.
    best_n : int
        Number of components selected.
    gmm : GaussianMixture
        Fitted model (for ellipse drawing).
    """
    from sklearn.mixture import GaussianMixture

    data_2d = np.column_stack([data_x.values, data_y.values])
    n = len(data_2d)

    if n < 4:
        return np.zeros(n, dtype=int), 1, None

    max_k = min(6, n // 3)
    max_k = max(1, max_k)

    best_bic = np.inf
    best_gmm = None
    best_n = 1

    for n_components in range(1, max_k + 1):
        try:
            gmm = GaussianMixture(n_components=n_components, covariance_type='full',
                                  random_state=42, n_init=5)
            gmm.fit(data_2d)
            bic = gmm.bic(data_2d)
            if bic < best_bic:
                best_bic = bic
                best_gmm = gmm
                best_n = n_components
        except Exception:
            continue

    if best_gmm is None:
        return np.zeros(n, dtype=int), 1, None

    labels = best_gmm.predict(data_2d)
    return labels, best_n, best_gmm


def create_voi_scatterplots(results_file='contour_comparison_results_P0728_v7.xlsx', base_output_dir='explore_results'):
    """
    Create visualizations for each VOI showing metric distributions and clustering.
    
    For each VOI, creates:
    - histograms.png: 2x2 grid with histogram + KDE for SDSC (tol=0.5, 1, 3mm), VDSC (Dice), APL (tol=0.5, 1, 3mm), and summary stats
    - gmm_kmeans_clustering.png: 2x4 grid comparing GMM and 1D K-means clustering
    - pie_chart.png: (if create_voi_pie_charts is also called)
    
    Parameters
    ----------
    results_file : str
        Path to the results Excel file
    base_output_dir : str
        Base directory to save the charts (each VOI gets its own subfolder)
    """
    from pathlib import Path
    import matplotlib.pyplot as plt
    import pandas as pd
    from scipy.stats import gaussian_kde
    import numpy as np
    import os

    # Load results
    if not Path(results_file).exists():
        print(f"Error: File not found: {results_file}")
        return

    df = pd.read_excel(results_file)
    print(f"Loaded {len(df)} rows from {results_file}")

    # Check required columns
    required_cols = ['VOIName', 'SDSC', 'Dice', 'APL']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"Error: Missing columns: {missing_cols}")
        return

    # Create base output directory — resolve relative paths from the project root
    _script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    base_path = Path(base_output_dir) if Path(base_output_dir).is_absolute() else _script_dir.parent / base_output_dir
    base_path.mkdir(exist_ok=True)
    print(f"Saving charts to: {base_path.absolute()}")
    
    # Get unique VOIs
    unique_vois = df['VOIName'].unique()
    print(f"Found {len(unique_vois)} unique VOIs")
    
    # Cluster columns for SDSC and Protocol×SDSC
    df['SDSC_GMM_cluster'] = ''
    df['Protocol_SDSC_GMM_cluster'] = ''

    # Process each VOI
    for voi_name in unique_vois:
        voi_df = df[df['VOIName'] == voi_name].copy()
        n_samples = len(voi_df)
        
        if n_samples == 0:
            continue
        
        print(f"Processing {voi_name} ({n_samples} samples)...")
        
        # Create VOI-specific subdirectory
        safe_voi_name = voi_name.replace('/', '_').replace('\\', '_').replace(':', '_').replace(' ', '_')
        voi_output_path = base_path / safe_voi_name
        voi_output_path.mkdir(exist_ok=True)
        
        # Add index for x-axis
        voi_df['index'] = range(1, n_samples + 1)
        
        # ========== Assign SDSC GMM cluster labels back to main DataFrame ==========
        valid_sdsc = voi_df.dropna(subset=['SDSC'])
        if len(valid_sdsc) > 0:
            labels, centroid_dict, _ = gmm_clustering(valid_sdsc['SDSC'])
            rank_map = {
                cid: rank + 1
                for rank, (cid, _) in enumerate(
                    sorted(centroid_dict.items(), key=lambda x: x[1])
                )
            }
            df.loc[valid_sdsc.index, 'SDSC_GMM_cluster'] = [
                f"{voi_name}_{rank_map[lbl]}" for lbl in labels
            ]

        # ========== Assign Protocol_Normalized x SDSC 2D GMM cluster labels ==========
        if 'Protocol_Normalized' in voi_df.columns:
            valid_proto = voi_df.dropna(subset=['Protocol_Normalized', 'SDSC'])
            valid_proto = valid_proto[valid_proto['Protocol_Normalized'].astype(str).str.strip() != '']
            if len(valid_proto) >= 4:
                categories_proto = sorted(valid_proto['Protocol_Normalized'].astype(str).unique())
                cat_map_proto = {cat: i for i, cat in enumerate(categories_proto)}
                encoded_proto = valid_proto['Protocol_Normalized'].astype(str).map(cat_map_proto)
                labels_proto, _, _ = gmm_clustering_2d(encoded_proto, valid_proto['SDSC'])
                cluster_means_proto = {
                    cid: valid_proto['SDSC'].values[labels_proto == cid].mean()
                    for cid in np.unique(labels_proto)
                }
                rank_map_proto = {
                    cid: rank + 1
                    for rank, (cid, _) in enumerate(
                        sorted(cluster_means_proto.items(), key=lambda x: x[1])
                    )
                }
                df.loc[valid_proto.index, 'Protocol_SDSC_GMM_cluster'] = [
                    f"{voi_name}_{rank_map_proto[lbl]}" for lbl in labels_proto
                ]

        # ========== Histograms with KDE (2x2 grid) ==========
        create_histograms_plot(voi_df, voi_name, voi_output_path, n_samples)

        # ========== Dose delta vs distance correlation ==========
        create_dose_distance_correlation_plot(voi_df, voi_name, voi_output_path, n_samples)

        # ========== Distance vs SDSC tol=0.5 correlation ==========
        create_distance_sdsc05_correlation_plot(voi_df, voi_name, voi_output_path, n_samples)

        # ========== Protocol_Normalized x SDSC_tol0 cluster scatter plot ==========
        create_protocol_sdsc_cluster_plot(voi_df, voi_name, voi_output_path, n_samples)

        # ========== Protocol_Normalized x SDSC_tol0 boxplot ==========
        create_protocol_sdsc_boxplot(voi_df, voi_name, voi_output_path, n_samples)

    # Save cluster assignments back into the *_with_dist file
    output_excel = str(Path(results_file))
    df.to_excel(output_excel, index=False)
    print(f"Cluster assignments saved to '{output_excel}'")
    
    print(f"\nVOI visualizations saved successfully to '{base_path}' folder.")


def create_protocol_sdsc_cluster_plot(voi_df, voi_name, output_path, n_samples):
    """
    Scatter plot of SDSC_tol0 (y) vs Protocol_Normalized (x, ordinal-encoded with
    jitter), coloured by Protocol_SDSC_GMM_cluster.

    Parameters
    ----------
    voi_df : pd.DataFrame
        DataFrame for a single VOI.  Must contain Protocol_Normalized,
        SDSC_tol0, and Protocol_SDSC_GMM_cluster columns.
    voi_name : str
        Name of the VOI (used in the title).
    output_path : Path
        Directory to save the plot.
    n_samples : int
        Total number of samples for this VOI.
    """
    import matplotlib.pyplot as plt
    import numpy as np

    if 'Protocol_Normalized' not in voi_df.columns:
        return
    if 'Protocol_SDSC_GMM_cluster' not in voi_df.columns:
        return

    valid = voi_df.dropna(subset=['Protocol_Normalized', 'SDSC']).copy()
    valid = valid[valid['Protocol_Normalized'].astype(str).str.strip() != '']

    if len(valid) < 4:
        return

    # Drop protocols with fewer than 6 samples, then ordinal-encode
    proto_counts = valid['Protocol_Normalized'].astype(str).value_counts()
    categories = sorted(cat for cat in proto_counts.index if proto_counts[cat] >= 6)
    if not categories:
        return
    valid = valid[valid['Protocol_Normalized'].astype(str).isin(categories)]
    cat_map = {cat: i for i, cat in enumerate(categories)}
    valid['_proto_enc'] = valid['Protocol_Normalized'].astype(str).map(cat_map)

    cluster_col = valid['Protocol_SDSC_GMM_cluster'].astype(str)
    unique_clusters = sorted(cluster_col.unique())
    n_clusters = len(unique_clusters)
    cmap = plt.cm.Set1
    color_map = {
        c: cmap(i / max(1, n_clusters - 1))
        for i, c in enumerate(unique_clusters)
    }

    rng = np.random.default_rng(42)
    fig, ax = plt.subplots(figsize=(max(8, len(categories) * 0.7 + 2), 6))

    for cluster in unique_clusters:
        mask = cluster_col == cluster
        jitter = rng.uniform(-0.25, 0.25, int(mask.sum()))
        x_vals = valid.loc[mask, '_proto_enc'].values + jitter
        y_vals = valid.loc[mask, 'SDSC'].values
        ax.scatter(
            x_vals, y_vals,
            c=[color_map[cluster]], alpha=0.7, s=40,
            edgecolors='black', linewidth=0.3,
            label=f'{cluster} (n={int(mask.sum())})'
        )

    ax.set_xticks(range(len(categories)))
    ax.set_xticklabels(categories, rotation=45, ha='right', fontsize=8)
    ax.set_xlabel('Protocol (Normalized)', fontsize=10)
    ax.set_ylabel('SDSC', fontsize=10)
    ax.set_ylim(-0.05, 1.05)
    ax.set_title(
        f'{voi_name} — Protocol \u00d7 SDSC GMM Clustering (N={n_samples})',
        fontsize=11, weight='bold'
    )
    ax.legend(fontsize=8, loc='upper right', bbox_to_anchor=(1.0, 1.0))
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path / 'protocol_sdsc_clustering.png', dpi=150, bbox_inches='tight')
    plt.close()


def create_protocol_sdsc_boxplot(voi_df, voi_name, output_path, n_samples):
    """
    Boxplot of SDSC_tol0 per Protocol_Normalized group, boxes coloured by
    Protocol_SDSC_GMM_cluster (majority cluster of that protocol group).

    Parameters
    ----------
    voi_df : pd.DataFrame
        DataFrame for a single VOI.
    voi_name : str
        Name of the VOI (used in the title).
    output_path : Path
        Directory to save the plot.
    n_samples : int
        Total number of samples for this VOI.
    """
    import matplotlib.pyplot as plt
    import numpy as np

    if 'Protocol_Normalized' not in voi_df.columns:
        return

    valid = voi_df.dropna(subset=['Protocol_Normalized', 'SDSC']).copy()
    valid = valid[valid['Protocol_Normalized'].astype(str).str.strip() != '']

    if len(valid) < 4:
        return

    # Drop protocols with fewer than 6 samples
    proto_counts = valid['Protocol_Normalized'].astype(str).value_counts()
    categories = sorted(cat for cat in proto_counts.index if proto_counts[cat] >= 6)
    if not categories:
        return
    valid = valid[valid['Protocol_Normalized'].astype(str).isin(categories)]

    # Determine majority cluster per category (for colouring)
    cluster_col = 'Protocol_SDSC_GMM_cluster'
    has_clusters = cluster_col in valid.columns and valid[cluster_col].astype(str).str.strip().ne('').any()

    if has_clusters:
        unique_clusters = sorted(valid[cluster_col].astype(str).unique())
        n_cl = len(unique_clusters)
        cmap = plt.cm.Set1
        color_map = {c: cmap(i / max(1, n_cl - 1)) for i, c in enumerate(unique_clusters)}

        def _majority_cluster(group):
            counts = group[cluster_col].astype(str).value_counts()
            return counts.idxmax() if len(counts) else unique_clusters[0]

        cat_colors = [
            color_map[_majority_cluster(valid[valid['Protocol_Normalized'].astype(str) == cat])]
            for cat in categories
        ]
    else:
        cat_colors = ['steelblue'] * len(categories)

    groups = [valid.loc[valid['Protocol_Normalized'].astype(str) == cat, 'SDSC'].values
              for cat in categories]
    n_counts = [len(g) for g in groups]

    fig, ax = plt.subplots(figsize=(max(8, len(categories) * 0.8 + 2), 6))

    bp = ax.boxplot(
        groups,
        positions=range(len(categories)),
        patch_artist=True,
        widths=0.5,
        medianprops=dict(color='black', linewidth=2),
        flierprops=dict(marker='o', markersize=3, alpha=0.5),
    )
    for patch, color in zip(bp['boxes'], cat_colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.75)

    # Overlay individual points (strip)
    rng = np.random.default_rng(42)
    for i, (group, color) in enumerate(zip(groups, cat_colors)):
        if len(group) == 0:
            continue
        jitter = rng.uniform(-0.18, 0.18, len(group))
        ax.scatter(i + jitter, group, c=[color], alpha=0.4, s=20,
                   edgecolors='none', zorder=3)

    # Cluster legend patches
    if has_clusters:
        from matplotlib.patches import Patch
        legend_handles = [Patch(facecolor=color_map[c], alpha=0.75, label=c)
                          for c in unique_clusters]
        ax.legend(handles=legend_handles, fontsize=8, loc='lower right')

    pct_ones = [
        100.0 * (g == 1.0).sum() / len(g) if len(g) > 0 else 0.0
        for g in groups
    ]
    x_labels = [
        f'{cat}\n(n={n}, {p:.0f}% =1)'
        for cat, n, p in zip(categories, n_counts, pct_ones)
    ]
    ax.set_xticks(range(len(categories)))
    ax.set_xticklabels(x_labels, rotation=45, ha='right', fontsize=8)
    ax.set_xlabel('Protocol (Normalized)', fontsize=10)
    ax.set_ylabel('SDSC', fontsize=10)
    ax.set_ylim(-0.05, 1.05)
    ax.set_title(
        f'{voi_name} — SDSC per Protocol (N={n_samples})',
        fontsize=11, weight='bold'
    )
    ax.grid(True, axis='y', alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path / 'protocol_sdsc_boxplot.png', dpi=150, bbox_inches='tight')
    plt.close()


def create_histograms_plot(voi_df, voi_name, output_path, n_samples):
    """
    Create a 2x2 grid of histograms with KDE for all metrics.
    
    Layout:
    - Top-left: SDSC with 3 tolerances (0.5mm, 1mm, 3mm) overlaid
    - Top-right: VDSC (Dice)
    - Bottom-left: APL with 3 tolerances (0.5mm, 1mm, 3mm) overlaid
    - Bottom-right: Summary statistics table
    
    Parameters
    ----------
    voi_df : pd.DataFrame
        DataFrame for a single VOI
    voi_name : str
        Name of the VOI
    output_path : Path
        Directory to save the plot
    n_samples : int
        Number of samples for this VOI
    """
    from scipy.stats import gaussian_kde
    import numpy as np
    import matplotlib.pyplot as plt
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle(f'{voi_name} - Metric Distributions with KDE (N={n_samples})', 
                 fontsize=16, weight='bold', y=0.995)
    
    # Plot 1: SDSC histogram with 3 tolerances (top-left)
    ax = axes[0, 0]
    sdsc_configs = [
        ('SDSC_tol05', 'SDSC (tol=0.5mm)', '#3498db', 2),
        ('SDSC_tol1', 'SDSC (tol=1mm)', '#e67e22', 2),
        ('SDSC_tol3', 'SDSC (tol=3mm)', '#27ae60', 2)
    ]
    
    for col, label, color, linewidth in sdsc_configs:
        if col in voi_df.columns:
            valid = voi_df[col].dropna()
            if len(valid) > 0:
                ax.hist(valid, bins=20, alpha=0.4, color=color, label=label, density=True)
                if len(valid) > 1:
                    try:
                        kde = gaussian_kde(valid)
                        x_range = np.linspace(0, 1, 200)
                        ax.plot(x_range, kde(x_range), color=color, linewidth=linewidth)
                    except np.linalg.LinAlgError:
                        pass
    
    ax.set_xlabel('SDSC Value', fontsize=11)
    ax.set_ylabel('Density', fontsize=11)
    ax.set_title('Distribution: SDSC (Multiple Tolerances)', fontsize=12, weight='bold')
    ax.set_xlim(-0.05, 1.05)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    
    # Plot 2: VDSC (Dice) histogram + KDE (top-right)
    ax = axes[0, 1]
    valid_dice = voi_df.dropna(subset=['Dice'])
    if len(valid_dice) > 0:
        ax.hist(valid_dice['Dice'], bins=20, alpha=0.6, color='#e74c3c', label='VDSC (Dice)', density=True)
        if len(valid_dice) > 1:
            try:
                kde = gaussian_kde(valid_dice['Dice'])
                x_range = np.linspace(0, 1, 200)
                ax.plot(x_range, kde(x_range), color='#c0392b', linewidth=2, label='KDE')
            except np.linalg.LinAlgError:
                pass
    ax.set_xlabel('VDSC Value', fontsize=11)
    ax.set_ylabel('Density', fontsize=11)
    ax.set_title('Distribution: VDSC (Dice)', fontsize=12, weight='bold')
    ax.set_xlim(-0.05, 1.05)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    
    # Plot 3: APL histogram with 3 tolerances (bottom-left)
    ax = axes[1, 0]
    apl_configs = [
        ('APL_tol05', 'APL (tol=0.5mm)', '#9b59b6', 3),
        ('APL_tol1', 'APL (tol=1mm)', '#f39c12', 3),
        ('APL_tol3', 'APL (tol=3mm)', '#16a085', 3)
    ]
    
    # Calculate global x-range for consistent plotting
    all_apl_values = []
    for col, _, _, _ in apl_configs:
        if col in voi_df.columns:
            valid = voi_df[col].dropna()
            if len(valid) > 0:
                all_apl_values.extend(valid.values)
    
    if all_apl_values:
        apl_min, apl_max = np.min(all_apl_values), np.max(all_apl_values)
        x_range_apl = np.linspace(max(0, apl_min - (apl_max - apl_min) * 0.1), 
                                  apl_max + (apl_max - apl_min) * 0.1, 300)
    
    for col, label, color, linewidth in apl_configs:
        if col in voi_df.columns:
            valid = voi_df[col].dropna()
            if len(valid) > 0:
                ax.hist(valid, bins=25, alpha=0.4, color=color, label=label, density=True, edgecolor='black')
                if len(valid) > 1:
                    try:
                        kde = gaussian_kde(valid)
                        ax.plot(x_range_apl, kde(x_range_apl), color=color, linewidth=linewidth, alpha=0.8)
                    except np.linalg.LinAlgError:
                        pass
    
    ax.set_xlabel('APL (mm)', fontsize=11)
    ax.set_ylabel('Density', fontsize=11)
    ax.set_title('Distribution: APL (Multiple Tolerances)', fontsize=12, weight='bold')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    
    # Plot 4: Summary statistics table (bottom-right)
    ax = axes[1, 1]
    ax.axis('off')
    
    # Build statistics table
    stats_data = []
    metrics_config = [
        ('SDSC_tol05', 'SDSC (tol=0.5mm)', '.3f'),
        ('SDSC_tol1', 'SDSC (tol=1mm)', '.3f'),
        ('SDSC_tol3', 'SDSC (tol=3mm)', '.3f'),
        ('Dice', 'VDSC (Dice)', '.3f'),
        ('APL_tol05', 'APL (tol=0.5mm)', '.2f'),
        ('APL_tol1', 'APL (tol=1mm)', '.2f'),
        ('APL_tol3', 'APL (tol=3mm)', '.2f')
    ]
    
    for col, label, fmt in metrics_config:
        if col in voi_df.columns:
            valid = voi_df[col].dropna()
            if len(valid) > 0:
                stats_data.append([
                    label,
                    f'{valid.mean():{fmt}}',
                    f'{valid.median():{fmt}}',
                    f'{valid.std():{fmt}}',
                    f'{valid.min():{fmt}}',
                    f'{valid.max():{fmt}}',
                    f'{len(valid)}'
                ])
    
    if stats_data:
        col_labels = ['Metric', 'Mean', 'Median', 'Std', 'Min', 'Max', 'N']
        table = ax.table(cellText=stats_data, colLabels=col_labels, 
                        loc='center', cellLoc='center')
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1.2, 1.5)
        
        # Style header row
        for j in range(len(col_labels)):
            table[0, j].set_facecolor('#34495e')
            table[0, j].set_text_props(color='white', weight='bold')
        
        # Alternate row colors
        for i in range(len(stats_data)):
            color = '#ecf0f1' if i % 2 == 0 else 'white'
            for j in range(len(col_labels)):
                table[i + 1, j].set_facecolor(color)
    
    ax.set_title('Summary Statistics', fontsize=12, weight='bold', pad=20)
    
    plt.tight_layout()
    plt.savefig(output_path / 'histograms.png', dpi=150, bbox_inches='tight')
    plt.close()


def create_dose_distance_correlation_plot(voi_df, voi_name, output_path, n_samples):
    """
    Side-by-side scatter plots of Delta_Dmax (left) and Delta_Dmean (right)
    versus dist_to_ptv, with linear regression line and Pearson/Spearman
    correlation statistics.  Saved as dose_distance_correlation.png.
    """
    from scipy.stats import pearsonr, spearmanr

    required = ['dist_to_ptv', 'Delta_Dmax', 'Delta_Dmean']
    if not all(c in voi_df.columns for c in required):
        return

    valid = voi_df.dropna(subset=['dist_to_ptv', 'Delta_Dmax', 'Delta_Dmean']).copy()
    valid = valid[valid['dist_to_ptv'] >= 0]
    if len(valid) < 4:
        return

    def _fmt_p(p):
        return 'p < 0.001' if p < 0.001 else f'p = {p:.3f}'

    def _sig(p):
        return '***' if p < 0.001 else ('**' if p < 0.01 else ('*' if p < 0.05 else 'ns'))

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle(
        f'{voi_name} — Dose Delta vs Distance to PTV (N={n_samples})',
        fontsize=13, weight='bold'
    )

    for ax, col, label, color in [
        (axes[0], 'Delta_Dmax',  'ΔDmax (Gy)',  '#3498db'),
        (axes[1], 'Delta_Dmean', 'ΔDmean (Gy)', '#e67e22'),
    ]:
        x = valid['dist_to_ptv'].values
        y = valid[col].values

        r_p, p_p = pearsonr(x, y)
        r_s, p_s = spearmanr(x, y)

        ax.scatter(x, y, c=color, alpha=0.6, s=40, edgecolors='black', linewidth=0.3)

        # Regression line
        m, b = np.polyfit(x, y, 1)
        x_line = np.linspace(x.min(), x.max(), 200)
        ax.plot(x_line, m * x_line + b, color='black', linewidth=1.5, linestyle='--', alpha=0.7)

        ax.axhline(0, color='grey', linestyle=':', linewidth=1, alpha=0.5)

        corr_text = (
            f'Pearson  r = {r_p:+.3f},  {_fmt_p(p_p)}  {_sig(p_p)}\n'
            f'Spearman ρ = {r_s:+.3f},  {_fmt_p(p_s)}  {_sig(p_s)}'
        )
        ax.text(0.03, 0.97, corr_text, transform=ax.transAxes, fontsize=9,
                verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.4))

        ax.set_xlabel('Distance to PTV (cm)', fontsize=10)
        ax.set_ylabel(label, fontsize=10)
        ax.set_title(label, fontsize=11, weight='bold')
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path / 'dose_distance_correlation.png', dpi=150, bbox_inches='tight')
    plt.close()


def create_distance_sdsc05_correlation_plot(voi_df, voi_name, output_path, n_samples):
    """
    Scatter plot of SDSC (y) vs dist_to_ptv (x) with linear regression
    line and Pearson/Spearman correlation statistics.
    Saved as distance_sdsc05_correlation.png.
    """
    from scipy.stats import pearsonr, spearmanr

    if 'dist_to_ptv' not in voi_df.columns or 'SDSC' not in voi_df.columns:
        return

    valid = voi_df.dropna(subset=['dist_to_ptv', 'SDSC']).copy()
    valid = valid[valid['dist_to_ptv'] >= 0]
    if len(valid) < 4:
        return

    def _fmt_p(p):
        return 'p < 0.001' if p < 0.001 else f'p = {p:.3f}'

    def _sig(p):
        return '***' if p < 0.001 else ('**' if p < 0.01 else ('*' if p < 0.05 else 'ns'))

    x = valid['dist_to_ptv'].values
    y = valid['SDSC'].values

    r_p, p_p = pearsonr(x, y)
    r_s, p_s = spearmanr(x, y)

    fig, ax = plt.subplots(figsize=(8, 6))

    ax.scatter(x, y, c='#27ae60', alpha=0.6, s=40, edgecolors='black', linewidth=0.3)

    # Regression line
    m, b = np.polyfit(x, y, 1)
    x_line = np.linspace(x.min(), x.max(), 200)
    ax.plot(x_line, m * x_line + b, color='black', linewidth=1.5, linestyle='--', alpha=0.7)

    corr_text = (
        f'Pearson  r = {r_p:+.3f},  {_fmt_p(p_p)}  {_sig(p_p)}\n'
        f'Spearman ρ = {r_s:+.3f},  {_fmt_p(p_s)}  {_sig(p_s)}'
    )
    ax.text(0.03, 0.97, corr_text, transform=ax.transAxes, fontsize=9,
            verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.4))

    ax.set_xlabel('Distance to PTV (cm)', fontsize=10)
    ax.set_ylabel('SDSC', fontsize=10)
    ax.set_ylim(-0.05, 1.05)
    ax.set_title(
        f'{voi_name} — Distance to PTV vs SDSC (tol=0.5) (N={n_samples})',
        fontsize=11, weight='bold'
    )
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path / 'distance_sdsc05_correlation.png', dpi=150, bbox_inches='tight')
    plt.close()


def _create_2d_cluster_plot_REMOVED(voi_df, voi_name, output_path, n_samples):
    # This function has been replaced by create_dose_distance_correlation_plot
    # and create_distance_sdsc05_correlation_plot.
    pass


def _old_create_2d_cluster_plot(voi_df, voi_name, output_path, n_samples):
    """
    Side-by-side scatter plots of SDSC_tol0 (y) vs MinDist_PTV1_cm (x):
    left panel = 2D GMM (with confidence ellipses),
    right panel = 2D K-means (with silhouette-selected k).
    """
    import matplotlib.pyplot as plt
    from matplotlib.patches import Ellipse
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    import numpy as np

    if 'MinDist_PTV1_cm' not in voi_df.columns:
        return

    valid = voi_df.dropna(subset=['SDSC_tol0', 'MinDist_PTV1_cm']).copy()
    valid = valid[valid['MinDist_PTV1_cm'] >= 0]

    if len(valid) < 4:
        return

    data_2d = np.column_stack([valid['MinDist_PTV1_cm'].values, valid['SDSC_tol0'].values])

    # --- GMM ---
    gmm_labels, gmm_n, gmm = gmm_clustering_2d(valid['MinDist_PTV1_cm'], valid['SDSC_tol0'])

    # Re-rank GMM labels so rank 1 = lowest mean distance (matches DataFrame assignment)
    gmm_rank_map = {
        cid: rank + 1
        for rank, (cid, _) in enumerate(
            sorted(
                {cid: data_2d[gmm_labels == cid, 0].mean() for cid in np.unique(gmm_labels)}.items(),
                key=lambda x: x[1]
            )
        )
    }
    gmm_labels = np.array([gmm_rank_map[lbl] for lbl in gmm_labels])

    # --- K-means with silhouette selection ---
    max_k = min(6, len(data_2d) // 3)
    max_k = max(2, max_k)
    best_score = -1
    best_km_labels = np.zeros(len(data_2d), dtype=int)
    best_km_centers = data_2d.mean(axis=0, keepdims=True)
    best_km_n = 1

    for k in range(2, max_k + 1):
        try:
            km = KMeans(n_clusters=k, random_state=42, n_init=10)
            lbl = km.fit_predict(data_2d)
            if len(np.unique(lbl)) < 2:
                continue
            score = silhouette_score(data_2d, lbl)
            if score > best_score:
                best_score = score
                best_km_labels = lbl
                best_km_centers = km.cluster_centers_
                best_km_n = k
        except Exception:
            continue

    # Use 1 cluster if silhouette never exceeded threshold
    if best_score < 0.2:
        best_km_labels = np.zeros(len(data_2d), dtype=int)
        best_km_centers = data_2d.mean(axis=0, keepdims=True)
        best_km_n = 1

    # Re-rank K-means labels so rank 1 = lowest mean distance
    km_rank_map = {
        cid: rank + 1
        for rank, (cid, _) in enumerate(
            sorted(
                {cid: data_2d[best_km_labels == cid, 0].mean() for cid in np.unique(best_km_labels)}.items(),
                key=lambda x: x[1]
            )
        )
    }
    best_km_labels = np.array([km_rank_map[lbl] for lbl in best_km_labels])
    # Re-order centers to match new rank order
    best_km_centers = np.array([
        best_km_centers[orig_cid]
        for orig_cid, _ in sorted(km_rank_map.items(), key=lambda x: x[1])
    ])

    def _draw_panel(ax, labels, title, centers=None, gmm_model=None):
        unique_labels = np.unique(labels)
        cmap = plt.cm.Set1
        colors = {lbl: cmap((lbl - 1) / max(1, len(unique_labels) - 1))
                  for lbl in unique_labels}

        for lbl in unique_labels:
            mask = labels == lbl
            ax.scatter(
                data_2d[mask, 0], data_2d[mask, 1],
                c=[colors[lbl]], alpha=0.7, s=40,
                edgecolors='black', linewidth=0.3,
                label=f'Cluster {lbl} (n={mask.sum()})'
            )

        # GMM panel: draw confidence ellipses.
        # gmm_model components are in original GMM index order; map back via gmm_rank_map.
        if gmm_model is not None:
            for i, (mean, cov) in enumerate(zip(gmm_model.means_, gmm_model.covariances_)):
                rank = gmm_rank_map.get(i, i + 1)
                if rank not in colors:
                    continue
                vals, vecs = np.linalg.eigh(cov)
                order = vals.argsort()[::-1]
                vals, vecs = vals[order], vecs[:, order]
                angle = np.degrees(np.arctan2(*vecs[:, 0][::-1]))
                width, height = 2 * 2.0 * np.sqrt(vals)
                ellipse = Ellipse(
                    xy=mean, width=width, height=height, angle=angle,
                    edgecolor=colors[rank], facecolor='none', linewidth=1.5, linestyle='--'
                )
                ax.add_patch(ellipse)

        # K-means panel: mark centroids
        if centers is not None:
            for i, center in enumerate(centers):
                lbl = i if i in colors else list(colors.keys())[-1]
                ax.scatter(*center, marker='X', s=150, c=[colors[lbl]],
                           edgecolors='black', linewidth=1, zorder=5)

        ax.set_xlabel('Min Distance PTV1 (cm)', fontsize=10)
        ax.set_ylabel('SDSC (tol=0.0)', fontsize=10)
        ax.set_ylim(-0.05, 1.05)
        ax.set_title(title, fontsize=11, weight='bold')
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)

    # --- Correlation analysis: Pearson and Spearman ---
    from scipy.stats import pearsonr, spearmanr

    r_p, p_p = pearsonr(data_2d[:, 0], data_2d[:, 1])
    r_s, p_s = spearmanr(data_2d[:, 0], data_2d[:, 1])

    def _fmt_p(p):
        if p < 0.001:
            return 'p < 0.001'
        return f'p = {p:.3f}'

    sig_p = '***' if p_p < 0.001 else ('**' if p_p < 0.01 else ('*' if p_p < 0.05 else 'ns'))
    sig_s = '***' if p_s < 0.001 else ('**' if p_s < 0.01 else ('*' if p_s < 0.05 else 'ns'))

    corr_text = (
        f'Pearson  r = {r_p:+.3f},  {_fmt_p(p_p)}  {sig_p}\n'
        f'Spearman ρ = {r_s:+.3f},  {_fmt_p(p_s)}  {sig_s}'
    )

    fig, (ax_gmm, ax_km) = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle(
        f'{voi_name} — 2D Clustering: SDSC tol=0 vs Min Distance PTV1 (N={n_samples})\n{corr_text}',
        fontsize=12, weight='bold'
    )

    _draw_panel(ax_gmm, gmm_labels,
                f'GMM ({gmm_n} component{"s" if gmm_n > 1 else ""})',
                gmm_model=gmm)
    _draw_panel(ax_km, best_km_labels,
                f'K-means ({best_km_n} cluster{"s" if best_km_n > 1 else ""})',
                centers=best_km_centers)

    plt.tight_layout()
    plt.savefig(output_path / 'gmm_2d_clustering.png', dpi=150, bbox_inches='tight')
    plt.close()


# ============================================================================
# MANUAL PATH LENGTH (translated from calculatePathLengthManual.m)
# ============================================================================

def calculate_path_length_manual(ct: dict, rtstruct: dict, struct_num: int) -> float:
    """
    Calculate the total perimeter (in mm) of a contour by counting border
    pixels in the resampled contour image.

    Translated from calculatePathLengthManual.m (MAASTRO).

    Parameters
    ----------
    ct : dict
        CT dictionary as returned by read_dicomct_light.
    rtstruct : dict
        RTSTRUCT dictionary as returned by read_dicomrtstruct.
    struct_num : int
        Zero-based index into rtstruct['Struct'].

    Returns
    -------
    float
        Path length in mm.
    """
    from resample_contour_slices import resample_contour_slices
    struct = rtstruct['Struct'][struct_num]
    contour, _ = resample_contour_slices(struct['Slice'], ct, struct['Name'])
    return float(np.sum(contour == 1)) * (ct['PixelSpacingXi'] * 10.0)  # mm


def compute_and_save_manual_path_lengths(input_file: str, dicom_root: str, output_file: str,
                                         max_patients=None):
    """
    Compute ManualPathLength (mm) for every eligible row in the input dataset
    and save the augmented dataset to output_file.

    A row is eligible when ChainStatus=='Complete', VOIName is set,
    and Clinical_RTSTRUCT is set.

    Parameters
    ----------
    input_file : str
        Path to the input Excel file.
    dicom_root : str
        Root folder containing patient DICOM subdirectories.
    output_file : str
        Path for the output Excel file.
    max_patients : int, optional
        Stop after processing this many unique patients (for testing).
    """
    import os
    import pydicom
    from read_dicomct_light import read_dicomct_light
    from read_dicomrtstruct import read_dicomrtstruct

    def _find_file_in_folder(root_folder, filename):
        for dirpath, _, filenames in os.walk(root_folder):
            if filename in filenames:
                return os.path.join(dirpath, filename)
        return None

    def _find_ct_files_for_rtstruct(rtstruct_path, ct_folder):
        try:
            ds = pydicom.dcmread(rtstruct_path, stop_before_pixels=True)
        except Exception:
            return []
        ref_ct_uid = ''
        if (0x3006, 0x0010) in ds:
            for frame_ref in ds[0x3006, 0x0010]:
                if (0x3006, 0x0012) in frame_ref:
                    for study_ref in frame_ref[0x3006, 0x0012]:
                        if (0x3006, 0x0014) in study_ref:
                            for series_ref in study_ref[0x3006, 0x0014]:
                                uid = str(series_ref.get('SeriesInstanceUID', ''))
                                if uid:
                                    ref_ct_uid = uid
                                    break
        if not ref_ct_uid:
            return []
        ct_files = []
        for dirpath, _, filenames in os.walk(ct_folder):
            for fn in filenames:
                if not fn.lower().endswith('.dcm'):
                    continue
                fpath = os.path.join(dirpath, fn)
                try:
                    ct_ds = pydicom.dcmread(fpath, stop_before_pixels=True)
                    if (ct_ds.get('Modality', '') == 'CT' and
                            str(ct_ds.get('SeriesInstanceUID', '')) == ref_ct_uid):
                        ct_files.append(fpath)
                except Exception:
                    pass
        return ct_files

    def _find_struct_by_name(rtstruct, name):
        for idx, s in enumerate(rtstruct['Struct']):
            if s.get('Name', '').strip() == name:
                return idx
        return None

    print(f"Loading dataset from: {input_file}")
    df = pd.read_excel(input_file, engine='openpyxl')
    print(f"Loaded {len(df)} rows")

    if 'ManualPathLength' not in df.columns:
        df['ManualPathLength'] = None
    if 'ManualPathLengthStatus' not in df.columns:
        df['ManualPathLengthStatus'] = None

    eligible_mask = (
        (df.get('ChainStatus') == 'Complete')
        & df['VOIName'].notna()
        & (df['VOIName'] != 'N/A')
        & df['Clinical_RTSTRUCT'].notna()
        & (df['Clinical_RTSTRUCT'] != 'N/A')
    )
    eligible_df = df[eligible_mask]

    if max_patients is not None and max_patients > 0:
        first_n = eligible_df['pNumber'].unique()[:max_patients]
        eligible_df = eligible_df[eligible_df['pNumber'].isin(first_n)]
        print(f"Limited to first {max_patients} patients: {len(eligible_df)} rows")
    else:
        print(f"{len(eligible_df)} eligible rows to process")

    groups = eligible_df.groupby(['pNumber', 'Clinical_RTSTRUCT'], sort=False)
    n_groups = len(groups)
    group_num = 0
    processed = errors = 0

    for (patient_id, clinical_rtstruct_file), group in groups:
        group_num += 1
        group_indices = group.index.tolist()
        print(f"  Group {group_num}/{n_groups}: {patient_id} | {clinical_rtstruct_file} "
              f"({len(group_indices)} rows)")

        rtstruct = ct = None
        try:
            patient_folder = os.path.join(dicom_root, patient_id)
            if not os.path.isdir(patient_folder):
                for idx in group_indices:
                    df.at[idx, 'ManualPathLengthStatus'] = 'Error: Patient folder not found'
                errors += len(group_indices)
                continue

            rtstruct_folder = os.path.join(patient_folder, 'RTSTRUCT')
            rtstruct_path = _find_file_in_folder(rtstruct_folder, clinical_rtstruct_file)
            if not rtstruct_path:
                for idx in group_indices:
                    df.at[idx, 'ManualPathLengthStatus'] = 'Error: RTSTRUCT file not found'
                errors += len(group_indices)
                continue

            rtstruct = read_dicomrtstruct(rtstruct_path, verbose=False)

            ct_folder = os.path.join(patient_folder, 'CT')
            ct_files = _find_ct_files_for_rtstruct(rtstruct_path, ct_folder)
            if not ct_files:
                for idx in group_indices:
                    df.at[idx, 'ManualPathLengthStatus'] = 'Error: No CT files found'
                errors += len(group_indices)
                continue

            ct = read_dicomct_light(ct_files)

            for idx in group_indices:
                voi_name = df.at[idx, 'VOIName']
                processed += 1
                try:
                    struct_num = _find_struct_by_name(rtstruct, voi_name)
                    if struct_num is None:
                        df.at[idx, 'ManualPathLengthStatus'] = f'Error: VOI "{voi_name}" not found'
                        errors += 1
                        continue
                    pl = calculate_path_length_manual(ct, rtstruct, struct_num)
                    df.at[idx, 'ManualPathLength'] = round(pl, 2)
                    df.at[idx, 'ManualPathLengthStatus'] = 'OK'
                except Exception as e:
                    df.at[idx, 'ManualPathLengthStatus'] = f'Error: {e}'
                    errors += 1
        except Exception as e:
            print(f"  Error group ({patient_id}, {clinical_rtstruct_file}): {e}")
            for idx in group_indices:
                if pd.isna(df.at[idx, 'ManualPathLengthStatus']):
                    df.at[idx, 'ManualPathLengthStatus'] = f'Error: {e}'
            errors += len(group_indices)
        finally:
            del ct, rtstruct

    df.to_excel(output_file, index=False, engine='openpyxl')
    print(f"Processed {processed} rows, {errors} errors. Output: {output_file}")


# ============================================================================
# REGION-BASED BARPLOTS
# ============================================================================

# Define OAR categories by anatomical region
REGIONS = {
    'Head_Neck': [
        'OralCavity_Ext', 'PharynxConst', 'Larynx', 'Thyroid',
        'Mandible', 'SpinalCord', 'BrainStem', 'Parotid_L', 'Parotid_R',
        'Submandibular_L', 'Submandibular_R', 'BrachialPlex_L',
        'BrachialPlex_R'
    ],
    'Neuro_Cranial': [
        'Eye_L', 'Eye_R', 'Lens_L', 'Lens_R', 'Retina_L', 'Retina_R',
        'Cornea_L', 'Cornea_R', 'Cochlea_L', 'Cochlea_R',
        'LacrimalGland_L', 'LacrimalGland_R', 'Pituitary', 'Chiasm',
        'Hippocampus_L', 'Hippocampus_R'
    ],
    'Abdomen': [
        'Bowel', 'Bowel_Bag', 'Bowel_Bag_Full', 'Bowel_Full', 'CaudaEquina',
        'Duodenum', 'Kidney_L', 'Kidney_R', 'Liver', 'Pancreas', 'Spleen',
        'Stomach'
    ],
    'Pelvis': [
        'AnalCanal', 'Bladder', 'Bone_Pelvic', 'Bowel_Sigmoid', 'Femur_Head_L',
        'Femur_Head_R', 'Mesorectum', 'PenileBulb', 'Rectum',
        'SeminalVes', 'Uterus+Cervix', 'Vagina', 'Vasc_Pelvis',
        'VB_L4', 'VB_L5'
    ],
    'Thorax': [
        'A_Aorta', 'Breast_L', 'Breast_R', 'Bronchus_Prox', 'Carina',
        'GreatVes', 'Heart', 'Humerus_L', 'Humerus_R', 'Lung_L', 'Lung_R',
        'Sternum', 'ThoracicWall_L', 'ThoracicWall_R', 'Esophagus', 'SpinalCanal'
    ],
    'CNS': [
        'Brain', 'Cerebellum', 'OpticNerve_L', 'OpticNerve_R'
    ]
}


def create_region_barplots(results_file=None, base_output_dir='explore_results'):
    """
    Create boxplots summarizing APL, sDSC, vDSC, and dose deltas per OAR, grouped by anatomical region.
    
    All OARs in a region are shown in a single plot.
    
    Parameters
    ----------
    results_file : str, optional
        Path to the results Excel file. Defaults to contour_comparison_results_P0728_v7.xlsx.
    base_output_dir : str
        Base directory containing explore_results (default: 'explore_results')
    """
    import os
    from pathlib import Path
    
    # Default file path
    if results_file is None:
        script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
        results_file = str(script_dir.parent / 'contour_comparison_results_P0728_v7.xlsx')
    
    # Load data
    if not Path(results_file).exists():
        raise FileNotFoundError(f"Results file not found: {results_file}")
    
    df = pd.read_excel(results_file, engine='openpyxl')
    print(f"Loaded {len(df)} rows from {results_file}")
    
    # Create output directory - default to parent directory's explore_results
    script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    if base_output_dir == 'explore_results':
        output_dir = script_dir.parent / 'explore_results' / 'explore results per region'
    else:
        output_dir = Path(base_output_dir) / 'explore results per region'
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Saving plots to: {output_dir.absolute()}")
    
    # Check required columns
    required_cols = ['VOIName', 'APL', 'SDSC', 'Dice']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"Warning: Missing columns: {missing_cols}")
    
    # Process each region and metric type
    for region_name, oar_list in REGIONS.items():
        print(f"\nProcessing region: {region_name} ({len(oar_list)} OARs)")
        
        # Filter data for this region
        df_region = df[df['VOIName'].isin(oar_list)].copy()
        
        if len(df_region) == 0:
            print(f"  No data found for {region_name}")
            continue
        
        # Get OARs that actually have data
        oars_with_data = sorted(df_region['VOIName'].unique())
        print(f"  Found data for {len(oars_with_data)} OARs")
        
        # Filter OARs with count > 20
        oar_counts = df_region['VOIName'].value_counts()
        oars_with_data = sorted([oar for oar in oars_with_data if oar_counts[oar] > 20])
        print(f"  After filtering (N > 20): {len(oars_with_data)} OARs")
        
        if len(oars_with_data) == 0:
            print(f"  No OARs with N > 20 for {region_name}")
            continue
        
        # Filter dataframe to only include OARs with N > 20
        df_region = df_region[df_region['VOIName'].isin(oars_with_data)].copy()
        
        # Create APL boxplots
        _create_apl_region_boxplot(df_region, region_name, oars_with_data, output_dir)

        # Create vDSC boxplots
        _create_vdsc_region_boxplot(df_region, region_name, oars_with_data, output_dir)
        
        # Create sDSC boxplots
        _create_sdsc_region_boxplot(df_region, region_name, oars_with_data, output_dir)
        
        # Create dose delta boxplots (Delta_Dmax and Delta_Dmean)
        _create_dose_delta_region_boxplot(df_region, region_name, oars_with_data, output_dir)

        # Create zero-suppressed dose delta boxplots (only delta != 0)
        _create_dose_delta_nonzero_region_boxplot(df_region, region_name, oars_with_data, output_dir)
        
        # Same plots with whiskers ending at the 5th and 95th percentile (two-stage: dashed 1st-5th / 95th-99th, dots beyond 1st/99th)
        _create_dose_delta_region_boxplot(
            df_region, region_name, oars_with_data, output_dir,
            whis=(5, 95), showfliers=True, suffix='_p5_95', outer_whiskers=True
        )
        _create_dose_delta_nonzero_region_boxplot(
            df_region, region_name, oars_with_data, output_dir,
            whis=(5, 95), showfliers=True, suffix='_p5_95', outer_whiskers=True
        )

    print(f"\nAll region boxplots saved to: {output_dir.absolute()}")


def _create_apl_region_boxplot(df_region, region_name, oars_with_data, output_dir):
    """
    Create APL boxplot for a region showing all OARs with both tolerance values (0.5mm and 3mm) side-by-side.
    
    Parameters
    ----------
    df_region : pd.DataFrame
        Filtered dataframe for this region
    region_name : str
        Name of the anatomical region
    oars_with_data : list
        List of OARs with available data (already sorted)
    output_dir : Path
        Output directory
    """
    comparison_apl_col = 'APL_tol1' if region_name == 'Neuro_Cranial' else 'APL_tol3'
    comparison_apl_label = 'APL (tol=1mm)' if region_name == 'Neuro_Cranial' else 'APL (tol=3mm)'
    apl_boxplot_outlier_limit = 100000

    # Prepare data for both tolerances
    apl_tol05_data = []
    apl_tol3_data = []
    oar_labels = []
    sample_counts_05 = []
    sample_counts_3 = []
    
    for oar in oars_with_data:
        oar_df = df_region[df_region['VOIName'] == oar]
        apl_05_vals = oar_df['APL_tol05'].dropna().values
        apl_3_vals = oar_df[comparison_apl_col].dropna().values
        if region_name == 'Abdomen' and oar == 'Bowel_Bag':
            apl_05_vals = apl_05_vals[apl_05_vals <= apl_boxplot_outlier_limit]
            apl_3_vals = apl_3_vals[apl_3_vals <= apl_boxplot_outlier_limit]
        
        if len(apl_05_vals) > 0 or len(apl_3_vals) > 0:
            apl_tol05_data.append(apl_05_vals if len(apl_05_vals) > 0 else [0])
            apl_tol3_data.append(apl_3_vals if len(apl_3_vals) > 0 else [0])
            oar_labels.append(oar)
            sample_counts_05.append(len(apl_05_vals))
            sample_counts_3.append(len(apl_3_vals))
    
    if not apl_tol05_data and not apl_tol3_data:
        print(f"  No APL data for {region_name}")
        return
    
    # Create figure
    n_oars = len(oar_labels)
    fig_height = max(8, n_oars * 0.5)
    fig, ax = plt.subplots(figsize=(14, fig_height))
    
    # Create positions for side-by-side boxplots
    positions_05 = [i - 0.2 for i in range(1, n_oars + 1)]
    positions_3 = [i + 0.2 for i in range(1, n_oars + 1)]
    
    # Plot tolerance 0.5mm boxplots
    bp1 = ax.boxplot(apl_tol05_data, positions=positions_05, vert=False, patch_artist=True,
                     widths=0.35, showmeans=False,
                     boxprops=dict(facecolor='#3498db', alpha=0.7, edgecolor='#2874a6'),
                     medianprops=dict(color='#1a4d6d', linewidth=2),
                     whiskerprops=dict(color='#2874a6', linewidth=1.5),
                     capprops=dict(color='#2874a6', linewidth=1.5),
                     flierprops=dict(marker='o', markerfacecolor='#3498db', markersize=3, alpha=0.5))
    
    # Plot tolerance 3mm boxplots
    bp2 = ax.boxplot(apl_tol3_data, positions=positions_3, vert=False, patch_artist=True,
                     widths=0.35, showmeans=False,
                     boxprops=dict(facecolor='#9b59b6', alpha=0.7, edgecolor='#7d3c98'),
                     medianprops=dict(color='#512e5f', linewidth=2),
                     whiskerprops=dict(color='#7d3c98', linewidth=1.5),
                     capprops=dict(color='#7d3c98', linewidth=1.5),
                     flierprops=dict(marker='o', markerfacecolor='#9b59b6', markersize=3, alpha=0.5))
    
    # Set y-axis labels with sample counts (average of both tolerances)
    labels_with_n = [f'{oar} (n={max(n05, n3)})' for oar, n05, n3 in zip(oar_labels, sample_counts_05, sample_counts_3)]
    ax.set_yticks(range(1, n_oars + 1))
    ax.set_yticklabels(labels_with_n, fontsize=9)
    
    # Customize plot
    ax.set_xlabel('Added Path Length (APL) [mm]', fontsize=12, fontweight='bold')
    ax.set_ylabel('OAR', fontsize=12, fontweight='bold')
    ax.set_title(f'APL Distribution by OAR - {region_name.replace("_", " & ")}',
                 fontsize=14, fontweight='bold', pad=15)
    ax.grid(axis='x', alpha=0.3, linestyle='--')
    ax.set_xlim(left=0)
    
    # Add legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#3498db', alpha=0.7, edgecolor='#2874a6', label='APL (tol=0.5mm)'),
        Patch(facecolor='#9b59b6', alpha=0.7, edgecolor='#7d3c98', label=comparison_apl_label),
        plt.Line2D([0], [0], marker='D', color='w', markerfacecolor='red', markersize=5, label='Mean')
    ]
    ax.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(1.01, 1), fontsize=10)
    
    plt.tight_layout()
    
    # Save figure
    output_file = output_dir / f'APL_{region_name}.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {output_file.name}")


def _create_sdsc_region_boxplot(df_region, region_name, oars_with_data, output_dir):
    """
    Create sDSC + vDSC boxplot for a region showing all OARs with three metrics side-by-side:
    - SDSC (tol=0.5mm)
    - SDSC (tol=3mm)
    - VDSC (Dice)
    
    Parameters
    ----------
    df_region : pd.DataFrame
        Filtered dataframe for this region
    region_name : str
        Name of the anatomical region
    oars_with_data : list
        List of OARs with available data (already sorted)
    output_dir : Path
        Output directory
    """
    comparison_sdsc_col = 'SDSC_tol1' if region_name == 'Neuro_Cranial' else 'SDSC_tol3'
    comparison_sdsc_label = 'sDSC (tol=1mm)' if region_name == 'Neuro_Cranial' else 'sDSC (tol=3mm)'

    # Prepare data for all three metrics
    sdsc_tol05_data = []
    sdsc_tol3_data = []
    vdsc_data = []
    oar_labels = []
    sample_counts_05 = []
    sample_counts_3 = []
    sample_counts_vdsc = []
    
    for oar in oars_with_data:
        oar_df = df_region[df_region['VOIName'] == oar]
        sdsc_05_vals = oar_df['SDSC_tol05'].dropna().values
        sdsc_3_vals = oar_df[comparison_sdsc_col].dropna().values
        vdsc_vals = oar_df['Dice'].dropna().values
        
        if len(sdsc_05_vals) > 0 or len(sdsc_3_vals) > 0 or len(vdsc_vals) > 0:
            sdsc_tol05_data.append(sdsc_05_vals if len(sdsc_05_vals) > 0 else [0])
            sdsc_tol3_data.append(sdsc_3_vals if len(sdsc_3_vals) > 0 else [0])
            vdsc_data.append(vdsc_vals if len(vdsc_vals) > 0 else [0])
            oar_labels.append(oar)
            sample_counts_05.append(len(sdsc_05_vals))
            sample_counts_3.append(len(sdsc_3_vals))
            sample_counts_vdsc.append(len(vdsc_vals))
    
    if not sdsc_tol05_data and not sdsc_tol3_data and not vdsc_data:
        print(f"  No sDSC/vDSC data for {region_name}")
        return
    
    # Create figure
    n_oars = len(oar_labels)
    fig_height = max(8, n_oars * 0.5)
    fig, ax = plt.subplots(figsize=(14, fig_height))
    
    # Create positions for three side-by-side boxplots
    positions_05 = [i - 0.3 for i in range(1, n_oars + 1)]
    positions_3 = [i for i in range(1, n_oars + 1)]
    positions_vdsc = [i + 0.3 for i in range(1, n_oars + 1)]
    
    # Plot tolerance 0.5mm boxplots (SDSC)
    bp1 = ax.boxplot(sdsc_tol05_data, positions=positions_05, vert=False, patch_artist=True,
                     widths=0.25, showmeans=False,
                     boxprops=dict(facecolor='#e67e22', alpha=0.7, edgecolor='#ca6f1e'),
                     medianprops=dict(color='#935116', linewidth=2),
                     whiskerprops=dict(color='#ca6f1e', linewidth=1.5),
                     capprops=dict(color='#ca6f1e', linewidth=1.5),
                     flierprops=dict(marker='o', markerfacecolor='#e67e22', markersize=3, alpha=0.5))
    
    # Plot tolerance 3mm boxplots (SDSC)
    bp2 = ax.boxplot(sdsc_tol3_data, positions=positions_3, vert=False, patch_artist=True,
                     widths=0.25, showmeans=False,
                     boxprops=dict(facecolor='#16a085', alpha=0.7, edgecolor='#138d75'),
                     medianprops=dict(color='#0e6655', linewidth=2),
                     whiskerprops=dict(color='#138d75', linewidth=1.5),
                     capprops=dict(color='#138d75', linewidth=1.5),
                     flierprops=dict(marker='o', markerfacecolor='#16a085', markersize=3, alpha=0.5))
    
    # Plot VDSC (Dice) boxplots
    bp3 = ax.boxplot(vdsc_data, positions=positions_vdsc, vert=False, patch_artist=True,
                     widths=0.25, showmeans=False,
                     boxprops=dict(facecolor='#e74c3c', alpha=0.7, edgecolor='#c0392b'),
                     medianprops=dict(color='#922b21', linewidth=2),
                     whiskerprops=dict(color='#c0392b', linewidth=1.5),
                     capprops=dict(color='#c0392b', linewidth=1.5),
                     flierprops=dict(marker='o', markerfacecolor='#e74c3c', markersize=3, alpha=0.5))
    
    # Set y-axis labels with sample counts (max of all three metrics)
    labels_with_n = [f'{oar} (n={max(n05, n3, nvdsc)})' 
                     for oar, n05, n3, nvdsc in zip(oar_labels, sample_counts_05, sample_counts_3, sample_counts_vdsc)]
    ax.set_yticks(range(1, n_oars + 1))
    ax.set_yticklabels(labels_with_n, fontsize=9)
    
    # Customize plot
    ax.set_xlabel('Similarity Coefficient', fontsize=12, fontweight='bold')
    ax.set_ylabel('OAR', fontsize=12, fontweight='bold')
    ax.set_title(f'Geometric Similarity Distribution by OAR - {region_name.replace("_", " & ")}',
                 fontsize=14, fontweight='bold', pad=15)
    ax.grid(axis='x', alpha=0.3, linestyle='--')
    ax.set_xlim(0, 1.05)
    
    # Add legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#e67e22', alpha=0.7, edgecolor='#ca6f1e', label='sDSC (tol=0.5mm)'),
        Patch(facecolor='#16a085', alpha=0.7, edgecolor='#138d75', label=comparison_sdsc_label),
        Patch(facecolor='#e74c3c', alpha=0.7, edgecolor='#c0392b', label='vDSC (Dice)'),
        plt.Line2D([0], [0], marker='D', color='w', markerfacecolor='red', markersize=5, label='Mean')
    ]
    ax.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(1.01, 1), fontsize=10)
    
    plt.tight_layout()
    
    # Save figure
    output_file = output_dir / f'sDSC_{region_name}.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {output_file.name}")


def _create_vdsc_region_boxplot(df_region, region_name, oars_with_data, output_dir):
    """
    Create vDSC (Dice) boxplot for a region showing all OARs in one plot.
    
    Parameters
    ----------
    df_region : pd.DataFrame
        Filtered dataframe for this region
    region_name : str
        Name of the anatomical region
    oars_with_data : list
        List of OARs with available data (already sorted)
    output_dir : Path
        Output directory
    """
    # Prepare data for boxplot
    vdsc_data_by_oar = []
    oar_labels = []
    sample_counts = []
    
    for oar in oars_with_data:
        oar_df = df_region[df_region['VOIName'] == oar]
        vdsc_vals = oar_df['Dice'].dropna().values
        
        if len(vdsc_vals) > 0:
            vdsc_data_by_oar.append(vdsc_vals)
            oar_labels.append(oar)
            sample_counts.append(len(vdsc_vals))
    
    if not vdsc_data_by_oar:
        print(f"  No vDSC data for {region_name}")
        return
    
    # Create figure
    n_oars = len(oar_labels)
    fig_height = max(8, n_oars * 0.4)
    fig, ax = plt.subplots(figsize=(12, fig_height))
    
    # Create horizontal boxplot
    bp = ax.boxplot(vdsc_data_by_oar, vert=False, patch_artist=True,
                    widths=0.6, showmeans=False,
                    boxprops=dict(facecolor='#9b59b6', alpha=0.7),
                    medianprops=dict(color='purple', linewidth=2),
                    whiskerprops=dict(color='#9b59b6', linewidth=1.5),
                    capprops=dict(color='#9b59b6', linewidth=1.5),
                    flierprops=dict(marker='o', markerfacecolor='gray', markersize=4, alpha=0.5))
    
    # Set y-axis labels with sample counts
    labels_with_n = [f'{oar} (n={n})' for oar, n in zip(oar_labels, sample_counts)]
    ax.set_yticks(range(1, n_oars + 1))
    ax.set_yticklabels(labels_with_n, fontsize=9)
    
    # Customize plot
    ax.set_xlabel('Volumetric DICE Coefficient (vDSC)', fontsize=12, fontweight='bold')
    ax.set_ylabel('OAR', fontsize=12, fontweight='bold')
    ax.set_title(f'vDSC Distribution by OAR - {region_name.replace("_", " & ")}',
                 fontsize=14, fontweight='bold', pad=15)
    ax.grid(axis='x', alpha=0.3, linestyle='--')
    ax.set_xlim(0, 1.05)
    
    # Add legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#9b59b6', alpha=0.7, label='IQR (25th-75th percentile)'),
        plt.Line2D([0], [0], color='purple', linewidth=2, label='Median')
    ]
    ax.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(1.01, 1), fontsize=9)
    
    plt.tight_layout()
    
    # Save figure
    output_file = output_dir / f'vDSC_{region_name}.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {output_file.name}")


# Final results: only OARs with N > 49 are shown in the dose delta plots
DOSE_DELTA_MIN_N = 50
# Dose delta plots are clipped at +/- this value (Gy); whiskers beyond it get a label
DOSE_DELTA_XLIM = 5


def _annotate_clipped_whiskers(ax, data_list, positions, color, whis, outer_whiskers):
    """
    Label whisker ends that fall outside the clipped x-axis with their value in Gy.

    The outermost whisker end is used: 1st/99th percentile for two-stage whiskers,
    otherwise the end of the regular whisker (Tukey or percentile).
    """
    for values, pos in zip(data_list, positions):
        values = np.asarray(values, dtype=float)
        values = values[~np.isnan(values)]
        if len(values) == 0:
            continue

        if outer_whiskers:
            low, high = np.percentile(values, [1, 99])
        elif isinstance(whis, (tuple, list)):
            low, high = np.percentile(values, whis)
        else:
            q1, q3 = np.percentile(values, [25, 75])
            iqr = q3 - q1
            inside = values[(values >= q1 - whis * iqr) & (values <= q3 + whis * iqr)]
            low, high = inside.min(), inside.max()

        if high > DOSE_DELTA_XLIM:
            ax.text(DOSE_DELTA_XLIM - 0.05, pos + 0.03, f'{high:+.1f} Gy →',
                    ha='right', va='bottom', fontsize=7, fontweight='bold',
                    color=color, zorder=5)
        if low < -DOSE_DELTA_XLIM:
            ax.text(-DOSE_DELTA_XLIM + 0.05, pos + 0.03, f'← {low:+.1f} Gy',
                    ha='left', va='bottom', fontsize=7, fontweight='bold',
                    color=color, zorder=5)


def _draw_outer_whiskers(ax, data_list, positions, color, marker_color):
    """
    Second whisker stage for percentile boxplots (whiskers at 5th/95th percentile).

    Draws a thin dashed whisker with a cap from the 1st to the 5th percentile and from
    the 95th to the 99th percentile. Only the lowest/highest 1% are drawn as dots.
    """
    for values, pos in zip(data_list, positions):
        values = np.asarray(values, dtype=float)
        values = values[~np.isnan(values)]
        if len(values) == 0:
            continue
        p1, p5, p95, p99 = np.percentile(values, [1, 5, 95, 99])
        for start, end in ((p5, p1), (p95, p99)):
            ax.plot([start, end], [pos, pos], color=color, linewidth=1.2,
                    linestyle=(0, (4, 2)), alpha=0.9, zorder=2)
            ax.plot([end, end], [pos - 0.08, pos + 0.08], color=color, linewidth=1.5,
                    alpha=0.9, zorder=2)
        extremes = values[(values < p1) | (values > p99)]
        if len(extremes) > 0:
            ax.plot(extremes, np.full(len(extremes), pos), linestyle='none', marker='o',
                    markersize=3, markerfacecolor=marker_color, markeredgecolor='none',
                    alpha=0.5, zorder=2)


def _create_dose_delta_region_boxplot(df_region, region_name, oars_with_data, output_dir,
                                      whis=1.5, showfliers=True, suffix='', outer_whiskers=False):
    """
    Create dose delta boxplot for a region showing all OARs with Delta_Dmax and Delta_Dmean side-by-side.
    
    Parameters
    ----------
    df_region : pd.DataFrame
        Filtered dataframe for this region
    region_name : str
        Name of the anatomical region
    oars_with_data : list
        List of OARs with available data (already sorted)
    output_dir : Path
        Output directory
    """
    # Check if dose delta columns exist
    if 'Delta_Dmax' not in df_region.columns or 'Delta_Dmean' not in df_region.columns:
        print(f"  Skipping dose delta boxplot for {region_name} - columns not found")
        return
    
    # Prepare data for both metrics
    dmax_data = []
    dmean_data = []
    oar_labels = []
    sample_counts_dmax = []
    sample_counts_dmean = []
    
    for oar in oars_with_data:
        oar_df = df_region[df_region['VOIName'] == oar]
        dmax_vals = oar_df['Delta_Dmax'].dropna().values
        dmean_vals = oar_df['Delta_Dmean'].dropna().values

        if len(dmax_vals) < DOSE_DELTA_MIN_N or len(dmean_vals) < DOSE_DELTA_MIN_N:
            continue

        if len(dmax_vals) > 0 or len(dmean_vals) > 0:
            dmax_data.append(dmax_vals if len(dmax_vals) > 0 else [0])
            dmean_data.append(dmean_vals if len(dmean_vals) > 0 else [0])
            oar_labels.append(oar)
            sample_counts_dmax.append(len(dmax_vals))
            sample_counts_dmean.append(len(dmean_vals))
    
    if not dmax_data and not dmean_data:
        print(f"  No dose delta data for {region_name}")
        return
    
    # Create figure
    n_oars = len(oar_labels)
    fig_height = max(8, n_oars * 0.5)
    fig, ax = plt.subplots(figsize=(14, fig_height))
    
    # Create positions for side-by-side boxplots
    positions_dmax = [i - 0.2 for i in range(1, n_oars + 1)]
    positions_dmean = [i + 0.2 for i in range(1, n_oars + 1)]
    
    # Plot Delta_Dmax boxplots
    bp1 = ax.boxplot(dmax_data, positions=positions_dmax, vert=False, patch_artist=True,
                     widths=0.35, showmeans=False,
                     whis=whis, showfliers=showfliers and not outer_whiskers,
                     boxprops=dict(facecolor='#3498db', alpha=0.7, edgecolor='#2874a6'),
                     medianprops=dict(color='#1a4d6d', linewidth=2),
                     whiskerprops=dict(color='#2874a6', linewidth=1.5),
                     capprops=dict(color='#2874a6', linewidth=1.5),
                     flierprops=dict(marker='o', markerfacecolor='#3498db', markersize=3, alpha=0.5))
    
    # Plot Delta_Dmean boxplots
    bp2 = ax.boxplot(dmean_data, positions=positions_dmean, vert=False, patch_artist=True,
                     widths=0.35, showmeans=False,
                     whis=whis, showfliers=showfliers and not outer_whiskers,
                     boxprops=dict(facecolor='#e67e22', alpha=0.7, edgecolor='#ca6f1e'),
                     medianprops=dict(color='#935116', linewidth=2),
                     whiskerprops=dict(color='#ca6f1e', linewidth=1.5),
                     capprops=dict(color='#ca6f1e', linewidth=1.5),
                     flierprops=dict(marker='o', markerfacecolor='#e67e22', markersize=3, alpha=0.5))
    
    if outer_whiskers:
        _draw_outer_whiskers(ax, dmax_data, positions_dmax, '#2874a6', '#3498db')
        _draw_outer_whiskers(ax, dmean_data, positions_dmean, '#ca6f1e', '#e67e22')
    
    # Set y-axis labels with sample counts (max of both metrics)
    labels_with_n = [f'{oar} (n={max(n_dmax, n_dmean)})' for oar, n_dmax, n_dmean in zip(oar_labels, sample_counts_dmax, sample_counts_dmean)]
    ax.set_yticks(range(1, n_oars + 1))
    ax.set_yticklabels(labels_with_n, fontsize=9)
    
    # Add zero reference line
    ax.axvline(0, color='grey', linestyle='--', linewidth=1.5, alpha=0.7, zorder=1)
    
    # Customize plot
    ax.set_xlabel('Dose Difference (Gy)', fontsize=12, fontweight='bold')
    ax.set_ylabel('OAR', fontsize=12, fontweight='bold')
    whisker_note = '' if whis == 1.5 else f' (whiskers: {whis[0]}th-{whis[1]}th percentile)'
    if outer_whiskers:
        whisker_note += ', dashed: 1st-5th / 95th-99th'
    ax.set_title(f'Dose Delta Distribution by OAR - {region_name.replace("_", " & ")}{whisker_note}',
                 fontsize=14, fontweight='bold', pad=15)
    ax.grid(axis='x', alpha=0.3, linestyle='--')
    
    # Cap visualization at ±5 Gy (outliers beyond this range will not be shown)
    ax.set_xlim(-DOSE_DELTA_XLIM, DOSE_DELTA_XLIM)
    _annotate_clipped_whiskers(ax, dmax_data, positions_dmax, '#2874a6', whis, outer_whiskers)
    _annotate_clipped_whiskers(ax, dmean_data, positions_dmean, '#ca6f1e', whis, outer_whiskers)
    
    # Add legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#3498db', alpha=0.7, edgecolor='#2874a6', label='ΔDmax'),
        Patch(facecolor='#e67e22', alpha=0.7, edgecolor='#ca6f1e', label='ΔDmean')
    ]
    if outer_whiskers:
        legend_elements.append(plt.Line2D([0], [0], color='grey', linewidth=1.2, linestyle=(0, (4, 2)),
                                          label='1st-5th / 95th-99th percentile'))
    ax.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(1.01, 1), fontsize=10)
    
    plt.tight_layout()
    
    # Save figure
    output_file = output_dir / f'DoseDelta_{region_name}{suffix}.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {output_file.name}")


def _create_dose_delta_nonzero_region_boxplot(df_region, region_name, oars_with_data, output_dir,
                                              zero_tol=1e-6, whis=1.5, showfliers=True,
                                              suffix='', outer_whiskers=False):
    """
    Create a zero-suppressed dose delta boxplot for a region.

    Part 1: the percentage of patients with a delta of exactly 0 Gy (perfect agreement)
    is reported per OAR in the axis labels and in a CSV table.
    Part 2: the boxplot only contains patients with a delta != 0, so the box is not
    collapsed onto zero.

    Parameters
    ----------
    df_region : pd.DataFrame
        Filtered dataframe for this region
    region_name : str
        Name of the anatomical region
    oars_with_data : list
        List of OARs with available data (already sorted)
    output_dir : Path
        Output directory
    zero_tol : float
        Absolute tolerance (Gy) for treating a delta as exactly 0
    """
    if 'Delta_Dmax' not in df_region.columns or 'Delta_Dmean' not in df_region.columns:
        print(f"  Skipping non-zero dose delta boxplot for {region_name} - columns not found")
        return

    dmax_data = []
    dmean_data = []
    oar_labels = []
    table_rows = []

    for oar in oars_with_data:
        oar_df = df_region[df_region['VOIName'] == oar]
        row = {'OAR': oar}
        nonzero = {}
        for metric in ['Delta_Dmax', 'Delta_Dmean']:
            vals = oar_df[metric].dropna().values
            is_zero = np.isclose(vals, 0.0, atol=zero_tol)
            nonzero[metric] = vals[~is_zero]
            row[f'N_{metric}'] = len(vals)
            row[f'N_zero_{metric}'] = int(is_zero.sum())
            row[f'Pct_zero_{metric}'] = (
                100.0 * is_zero.sum() / len(vals) if len(vals) > 0 else np.nan
            )
            row[f'N_nonzero_{metric}'] = len(nonzero[metric])
            row[f'Median_nonzero_{metric}'] = (
                np.median(nonzero[metric]) if len(nonzero[metric]) > 0 else np.nan
            )
            row[f'Pct_positive_nonzero_{metric}'] = (
                100.0 * (nonzero[metric] > 0).mean() if len(nonzero[metric]) > 0 else np.nan
            )

        if row['N_Delta_Dmax'] < DOSE_DELTA_MIN_N or row['N_Delta_Dmean'] < DOSE_DELTA_MIN_N:
            continue

        dmax_data.append(nonzero['Delta_Dmax'])
        dmean_data.append(nonzero['Delta_Dmean'])
        oar_labels.append(oar)
        table_rows.append(row)

    if not oar_labels:
        print(f"  No dose delta data for {region_name}")
        return

    # Part 1: table with the percentage of exactly-zero deltas
    table_file = output_dir / f'DoseDelta_{region_name}_nonzero_summary.csv'
    pd.DataFrame(table_rows).round(2).to_csv(table_file, index=False)

    # Part 2: boxplot of non-zero deltas only
    n_oars = len(oar_labels)
    fig_height = max(8, n_oars * 0.6)
    fig, ax = plt.subplots(figsize=(14, fig_height))

    positions_dmax = [i - 0.2 for i in range(1, n_oars + 1)]
    positions_dmean = [i + 0.2 for i in range(1, n_oars + 1)]

    ax.boxplot(dmax_data, positions=positions_dmax, vert=False, patch_artist=True,
               widths=0.35, showmeans=False,
               whis=whis, showfliers=showfliers and not outer_whiskers,
               boxprops=dict(facecolor='#3498db', alpha=0.7, edgecolor='#2874a6'),
               medianprops=dict(color='#1a4d6d', linewidth=2),
               whiskerprops=dict(color='#2874a6', linewidth=1.5),
               capprops=dict(color='#2874a6', linewidth=1.5),
               flierprops=dict(marker='o', markerfacecolor='#3498db', markersize=3, alpha=0.5))

    ax.boxplot(dmean_data, positions=positions_dmean, vert=False, patch_artist=True,
               widths=0.35, showmeans=False,
               whis=whis, showfliers=showfliers and not outer_whiskers,
               boxprops=dict(facecolor='#e67e22', alpha=0.7, edgecolor='#ca6f1e'),
               medianprops=dict(color='#935116', linewidth=2),
               whiskerprops=dict(color='#ca6f1e', linewidth=1.5),
               capprops=dict(color='#ca6f1e', linewidth=1.5),
               flierprops=dict(marker='o', markerfacecolor='#e67e22', markersize=3, alpha=0.5))

    if outer_whiskers:
        _draw_outer_whiskers(ax, dmax_data, positions_dmax, '#2874a6', '#3498db')
        _draw_outer_whiskers(ax, dmean_data, positions_dmean, '#ca6f1e', '#e67e22')

    labels = [
        f"{row['OAR']} (n={max(row['N_Delta_Dmax'], row['N_Delta_Dmean'])})\n"
        f"Δ=0: Dmax {row['Pct_zero_Delta_Dmax']:.0f}% | Dmean {row['Pct_zero_Delta_Dmean']:.0f}%"
        for row in table_rows
    ]
    ax.set_yticks(range(1, n_oars + 1))
    ax.set_yticklabels(labels, fontsize=8)

    ax.axvline(0, color='grey', linestyle='--', linewidth=1.5, alpha=0.7, zorder=1)

    ax.set_xlabel('Dose Difference (Gy), patients with Δ ≠ 0 only', fontsize=12, fontweight='bold')
    ax.set_ylabel('OAR', fontsize=12, fontweight='bold')
    whisker_note = '' if whis == 1.5 else f' (whiskers: {whis[0]}th-{whis[1]}th percentile)'
    if outer_whiskers:
        whisker_note += ', dashed: 1st-5th / 95th-99th'
    ax.set_title(f'Dose Delta Distribution (zero-suppressed) by OAR - {region_name.replace("_", " & ")}{whisker_note}',
                 fontsize=14, fontweight='bold', pad=15)
    ax.grid(axis='x', alpha=0.3, linestyle='--')

    # Same ±5 Gy cap as the standard dose delta boxplot
    ax.set_xlim(-DOSE_DELTA_XLIM, DOSE_DELTA_XLIM)
    _annotate_clipped_whiskers(ax, dmax_data, positions_dmax, '#2874a6', whis, outer_whiskers)
    _annotate_clipped_whiskers(ax, dmean_data, positions_dmean, '#ca6f1e', whis, outer_whiskers)

    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#3498db', alpha=0.7, edgecolor='#2874a6', label='ΔDmax (Δ ≠ 0)'),
        Patch(facecolor='#e67e22', alpha=0.7, edgecolor='#ca6f1e', label='ΔDmean (Δ ≠ 0)')
    ]
    if outer_whiskers:
        legend_elements.append(plt.Line2D([0], [0], color='grey', linewidth=1.2, linestyle=(0, (4, 2)),
                                          label='1st-5th / 95th-99th percentile'))
    ax.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(1.01, 1), fontsize=10)

    plt.tight_layout()

    output_file = output_dir / f'DoseDelta_{region_name}_nonzero{suffix}.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {output_file.name}")


def _create_apl_region_barplot(df_region, region_name, oars_with_data, output_dir, max_oars_per_plot=10):
    """
    Create APL barplot for a region with both tolerances (0.1 and 0).
    
    Parameters
    ----------
    df_region : pd.DataFrame
        Filtered dataframe for this region
    region_name : str
        Name of the anatomical region
    oars_with_data : array
        List of OARs with available data
    output_dir : Path
        Output directory
    max_oars_per_plot : int
        Maximum OARs per plot (default: 10)
    """
    has_manual = 'ManualPathLength' in df_region.columns

    # Calculate averages per OAR
    apl_data = []
    for oar in sorted(oars_with_data):
        oar_df = df_region[df_region['VOIName'] == oar]

        apl_vals = oar_df['APL'].dropna()
        apl_mean = apl_vals.mean() if len(apl_vals) > 0 else np.nan

        if has_manual:
            mpl = oar_df['ManualPathLength'].dropna()
            mpl_mean = mpl.mean() if len(mpl) > 0 else np.nan
        else:
            mpl_mean = np.nan

        n_samples = len(apl_vals)

        if not np.isnan(apl_mean):
            apl_data.append({
                'OAR': oar,
                'APL_mean': apl_mean,
                'ManualPL_mean': mpl_mean,
                'N': n_samples
            })

    if not apl_data:
        return

    apl_df = pd.DataFrame(apl_data)

    # y-axis: highest mean value + 15% padding
    max_bar_height = apl_df['APL_mean'].max()
    if has_manual:
        mpl_max = apl_df['ManualPL_mean'].dropna().max()
        if not np.isnan(mpl_max):
            max_bar_height = max(max_bar_height, mpl_max)
    apl_ylim = max_bar_height * 1.15 if max_bar_height > 0 else 10

    # Determine how many bar groups per OAR
    show_manual = has_manual and not apl_df['ManualPL_mean'].isna().all()
    n_bars = 1 + int(show_manual)

    # Split into chunks of max_oars_per_plot
    n_oars = len(apl_df)
    n_chunks = int(np.ceil(n_oars / max_oars_per_plot))
    
    for chunk_idx in range(n_chunks):
        start_idx = chunk_idx * max_oars_per_plot
        end_idx = min((chunk_idx + 1) * max_oars_per_plot, n_oars)
        chunk_df = apl_df.iloc[start_idx:end_idx]
        
        oar_names = chunk_df['OAR'].values
        n_in_chunk = len(oar_names)
        
        # Create figure
        fig, ax = plt.subplots(figsize=(max(12, n_in_chunk * 1.2 * n_bars), 8))
        
        x = np.arange(n_in_chunk)
        width = 0.8 / n_bars  # divide available bar space evenly

        # Compute bar offsets centred at each x tick
        offsets = np.linspace(-(n_bars - 1) / 2 * width, (n_bars - 1) / 2 * width, n_bars)
        bar_idx = 0

        # Bar 1: APL (always present)
        bars1 = ax.bar(x + offsets[bar_idx], chunk_df['APL_mean'], width,
                       label='APL', color='#3498db', alpha=0.8)
        for bar in bars1:
            height = bar.get_height()
            if not np.isnan(height):
                ax.text(bar.get_x() + bar.get_width() / 2., height,
                        f'{height:.1f}', ha='center', va='bottom', fontsize=8)
        bar_idx += 1

        # Bar 2: Manual path length (optional)
        if show_manual:
            bars3 = ax.bar(x + offsets[bar_idx], chunk_df['ManualPL_mean'], width,
                           label='Manual PL (mm)', color='#27ae60', alpha=0.8)
            for bar in bars3:
                height = bar.get_height()
                if not np.isnan(height):
                    ax.text(bar.get_x() + bar.get_width() / 2., height,
                            f'{height:.1f}', ha='center', va='bottom', fontsize=8)

        # Customize plot
        ax.set_xlabel('OAR', fontsize=12, fontweight='bold')
        ax.set_ylabel('Average APL / Path Length (mm)', fontsize=12, fontweight='bold')
        
        part_label = f' (Part {chunk_idx + 1})' if n_chunks > 1 else ''
        ax.set_title(f'Average Added Path Length (APL) - {region_name.replace("_", " & ")}{part_label}',
                     fontsize=14, fontweight='bold', pad=15)
        
        # Create labels with sample counts
        labels = [f'{oar}\n(n={int(n)})' for oar, n in zip(chunk_df['OAR'], chunk_df['N'])]
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=9)
        
        ax.legend(loc='upper right', fontsize=10)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        
        ax.set_ylim(0, apl_ylim)
        
        plt.tight_layout()
        
        # Save figure
        suffix = f'_part{chunk_idx + 1}' if n_chunks > 1 else ''
        output_file = output_dir / f'APL_{region_name}{suffix}.png'
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"  Saved: {output_file.name}")


def _create_sdsc_region_barplot(df_region, region_name, oars_with_data, output_dir, max_oars_per_plot=10):
    """
    Create sDSC barplot for a region with both tolerances (0.1 and 0).
    
    Parameters
    ----------
    df_region : pd.DataFrame
        Filtered dataframe for this region
    region_name : str
        Name of the anatomical region
    oars_with_data : array
        List of OARs with available data
    output_dir : Path
        Output directory
    max_oars_per_plot : int
        Maximum OARs per plot (default: 10)
    """
    # Calculate averages per OAR
    sdsc_data = []
    for oar in sorted(oars_with_data):
        oar_df = df_region[df_region['VOIName'] == oar]
        
        # SDSC
        sdsc_vals = oar_df['SDSC'].dropna()
        sdsc_mean = sdsc_vals.mean() if len(sdsc_vals) > 0 else np.nan
        sdsc_std = sdsc_vals.std() if len(sdsc_vals) > 1 else 0
        
        n_samples = len(sdsc_vals)
        
        if not np.isnan(sdsc_mean):
            sdsc_data.append({
                'OAR': oar,
                'SDSC_mean': sdsc_mean,
                'SDSC_std': sdsc_std,
                'N': n_samples
            })
    
    if not sdsc_data:
        return
    
    sdsc_df = pd.DataFrame(sdsc_data)
    
    # Compute per-region y-axis limit from the highest mean+std in this region
    max_bar_height = 0
    for _, row in sdsc_df.iterrows():
        top = row['SDSC_mean'] + row['SDSC_std']
        if not np.isnan(top):
            max_bar_height = max(max_bar_height, top)
    sdsc_ylim = min(max_bar_height * 1.15, 1.05) if max_bar_height > 0 else 1.05
    
    # Split into chunks of max_oars_per_plot
    n_oars = len(sdsc_df)
    n_chunks = int(np.ceil(n_oars / max_oars_per_plot))
    
    for chunk_idx in range(n_chunks):
        start_idx = chunk_idx * max_oars_per_plot
        end_idx = min((chunk_idx + 1) * max_oars_per_plot, n_oars)
        chunk_df = sdsc_df.iloc[start_idx:end_idx]
        
        oar_names = chunk_df['OAR'].values
        n_in_chunk = len(oar_names)
        
        # Create figure
        fig, ax = plt.subplots(figsize=(max(12, n_in_chunk * 0.8), 8))
        
        x = np.arange(n_in_chunk)
        width = 0.6
        
        # Plot SDSC bars
        sdsc_yerr = np.array([np.minimum(chunk_df['SDSC_mean'].values, chunk_df['SDSC_std'].values),
                              chunk_df['SDSC_std'].values])
        bars = ax.bar(x, chunk_df['SDSC_mean'], width,
                      yerr=sdsc_yerr, capsize=3,
                      label='sDSC', color='#3498db', alpha=0.8)
        
        # Customize plot
        ax.set_xlabel('OAR', fontsize=12, fontweight='bold')
        ax.set_ylabel('Average sDSC (0-1)', fontsize=12, fontweight='bold')
        ax.set_ylim(0, sdsc_ylim)
        
        part_label = f' (Part {chunk_idx + 1})' if n_chunks > 1 else ''
        ax.set_title(f'Average Surface Dice Coefficient (sDSC) - {region_name.replace("_", " & ")}{part_label}',
                     fontsize=14, fontweight='bold', pad=15)
        
        # Create labels with sample counts
        labels = [f'{oar}\n(n={int(n)})' for oar, n in zip(chunk_df['OAR'], chunk_df['N'])]
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=9)
        
        ax.legend(loc='lower right', fontsize=10)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        
        # Add value labels on bars
        for bar in bars:
            height = bar.get_height()
            if not np.isnan(height):
                ax.text(bar.get_x() + bar.get_width()/2., height,
                        f'{height:.2f}', ha='center', va='bottom', fontsize=8)
        
        plt.tight_layout()
        
        # Save figure
        suffix = f'_part{chunk_idx + 1}' if n_chunks > 1 else ''
        output_file = output_dir / f'sDSC_{region_name}{suffix}.png'
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"  Saved: {output_file.name}")


def _create_vdsc_region_barplot(df_region, region_name, oars_with_data, output_dir, max_oars_per_plot=10):
    """
    Create vDSC (Dice) barplot for a region.
    
    Parameters
    ----------
    df_region : pd.DataFrame
        Filtered dataframe for this region
    region_name : str
        Name of the anatomical region
    oars_with_data : array
        List of OARs with available data
    output_dir : Path
        Output directory
    max_oars_per_plot : int
        Maximum OARs per plot (default: 10)
    """
    # Calculate averages per OAR
    vdsc_data = []
    for oar in sorted(oars_with_data):
        oar_df = df_region[df_region['VOIName'] == oar]
        
        # vDSC (Dice)
        vdsc = oar_df['Dice'].dropna()
        vdsc_mean = vdsc.mean() if len(vdsc) > 0 else np.nan
        vdsc_std = vdsc.std() if len(vdsc) > 1 else 0
        
        n_samples = len(vdsc)
        
        if not np.isnan(vdsc_mean):
            vdsc_data.append({
                'OAR': oar,
                'vDSC_mean': vdsc_mean,
                'vDSC_std': vdsc_std,
                'N': n_samples
            })
    
    if not vdsc_data:
        return
    
    vdsc_df = pd.DataFrame(vdsc_data)
    
    # Compute per-region y-axis limit from the highest mean+std in this region
    max_bar_height = 0
    for _, row in vdsc_df.iterrows():
        top = row['vDSC_mean'] + row['vDSC_std']
        if not np.isnan(top):
            max_bar_height = max(max_bar_height, top)
    vdsc_ylim = min(max_bar_height * 1.15, 1.05) if max_bar_height > 0 else 1.05
    
    # Split into chunks of max_oars_per_plot
    n_oars = len(vdsc_df)
    n_chunks = int(np.ceil(n_oars / max_oars_per_plot))
    
    for chunk_idx in range(n_chunks):
        start_idx = chunk_idx * max_oars_per_plot
        end_idx = min((chunk_idx + 1) * max_oars_per_plot, n_oars)
        chunk_df = vdsc_df.iloc[start_idx:end_idx]
        
        oar_names = chunk_df['OAR'].values
        n_in_chunk = len(oar_names)
        
        # Create figure
        fig, ax = plt.subplots(figsize=(max(12, n_in_chunk * 1.2), 8))
        
        x = np.arange(n_in_chunk)
        width = 0.6
        
        # Plot bars
        vdsc_yerr = np.array([np.minimum(chunk_df['vDSC_mean'].values, chunk_df['vDSC_std'].values),
                               chunk_df['vDSC_std'].values])
        bars = ax.bar(x, chunk_df['vDSC_mean'], width,
                      yerr=vdsc_yerr, capsize=3,
                      label='vDSC (Dice)', color='#9b59b6', alpha=0.8)
        
        # Customize plot
        ax.set_xlabel('OAR', fontsize=12, fontweight='bold')
        ax.set_ylabel('Average vDSC (0-1)', fontsize=12, fontweight='bold')
        ax.set_ylim(0, vdsc_ylim)
        
        part_label = f' (Part {chunk_idx + 1})' if n_chunks > 1 else ''
        ax.set_title(f'Average Volumetric Dice Coefficient (vDSC) - {region_name.replace("_", " & ")}{part_label}',
                     fontsize=14, fontweight='bold', pad=15)
        
        # Create labels with sample counts
        labels = [f'{oar}\n(n={int(n)})' for oar, n in zip(chunk_df['OAR'], chunk_df['N'])]
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=9)
        
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        
        # Add value labels on bars
        for bar in bars:
            height = bar.get_height()
            if not np.isnan(height):
                ax.text(bar.get_x() + bar.get_width()/2., height,
                        f'{height:.2f}', ha='center', va='bottom', fontsize=8)
        
        plt.tight_layout()
        
        # Save figure
        suffix = f'_part{chunk_idx + 1}' if n_chunks > 1 else ''
        output_file = output_dir / f'vDSC_{region_name}{suffix}.png'
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"  Saved: {output_file.name}")


def _create_sdsc_distribution_region_barplot(df_region, region_name, oars_with_data, output_dir, max_oars_per_plot=10):
    """
    Create stacked barplot showing sDSC score distribution per OAR for a region.

    Each bar represents one OAR and is divided into 5 sections (summing to 100%):
      - Perfect (=1.0)        dark green
      - Good (0.8–1.0)        light green
      - Fair (0.4–0.8)        orange
      - Poor (0.2–0.4)        light red
      - Very Poor (<0.2)      dark red

    Parameters
    ----------
    df_region : pd.DataFrame
        Filtered dataframe for this region
    region_name : str
        Name of the anatomical region
    oars_with_data : array
        List of OARs with available data
    output_dir : Path
        Output directory
    max_oars_per_plot : int
        Maximum OARs per plot (default: 10)
    """
    # Compute distribution per OAR
    dist_data = []
    for oar in sorted(oars_with_data):
        oar_df = df_region[df_region['VOIName'] == oar]
        valid = oar_df['SDSC'].dropna()
        total = len(valid)
        if total == 0:
            continue

        count_eq1 = int((valid == 1.0).sum())
        count_gt08 = int((valid > 0.8).sum())
        count_lt04 = int((valid < 0.4).sum())
        count_lt02 = int((valid < 0.2).sum())

        pct_perfect = 100.0 * count_eq1 / total
        pct_good = 100.0 * (count_gt08 - count_eq1) / total
        pct_fair = 100.0 * (total - count_gt08 - count_lt04) / total
        pct_poor = 100.0 * (count_lt04 - count_lt02) / total
        pct_very_poor = 100.0 * count_lt02 / total

        dist_data.append({
            'OAR': oar,
            'Perfect': pct_perfect,
            'Good': pct_good,
            'Fair': pct_fair,
            'Poor': pct_poor,
            'Very Poor': pct_very_poor,
            'N': total
        })

    if not dist_data:
        return

    dist_df = pd.DataFrame(dist_data)

    categories = ['Perfect', 'Good', 'Fair', 'Poor', 'Very Poor']
    colors = ['#27ae60', '#2ecc71', '#f39c12', '#e74c3c', '#c0392b']
    legend_labels = [
        'Perfect (=1.0)',
        'Good (0.8\u20131.0)',
        'Fair (0.4\u20130.8)',
        'Poor (0.2\u20130.4)',
        'Very Poor (<0.2)'
    ]

    # Split into chunks
    n_oars = len(dist_df)
    n_chunks = int(np.ceil(n_oars / max_oars_per_plot))

    for chunk_idx in range(n_chunks):
        start_idx = chunk_idx * max_oars_per_plot
        end_idx = min((chunk_idx + 1) * max_oars_per_plot, n_oars)
        chunk_df = dist_df.iloc[start_idx:end_idx]

        n_in_chunk = len(chunk_df)
        x = np.arange(n_in_chunk)
        width = 0.6

        fig, ax = plt.subplots(figsize=(max(12, n_in_chunk * 1.2), 8))

        bottom = np.zeros(n_in_chunk)
        bars_list = []
        for cat, color in zip(categories, colors):
            vals = chunk_df[cat].values
            b = ax.bar(x, vals, width, bottom=bottom, color=color, edgecolor='white', linewidth=0.5)
            bars_list.append(b)
            bottom += vals

        # Customize plot
        ax.set_xlabel('OAR', fontsize=12, fontweight='bold')
        ax.set_ylabel('Percentage (%)', fontsize=12, fontweight='bold')
        ax.set_ylim(0, 105)

        part_label = f' (Part {chunk_idx + 1})' if n_chunks > 1 else ''
        ax.set_title(
            f'sDSC Score Distribution (tol=0) \u2013 {region_name.replace("_", " & ")}{part_label}',
            fontsize=14, fontweight='bold', pad=15
        )

        labels = [f'{oar}\n(n={int(n)})' for oar, n in zip(chunk_df['OAR'], chunk_df['N'])]
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=9)

        ax.legend(bars_list, legend_labels, loc='upper right', fontsize=9,
                  title='sDSC Score Ranges', title_fontsize=10)
        ax.grid(axis='y', alpha=0.3, linestyle='--')

        # Add percentage labels inside bar sections that are large enough
        for cat_idx, cat in enumerate(categories):
            for bar_idx in range(n_in_chunk):
                val = chunk_df.iloc[bar_idx][cat]
                if val >= 5:  # Only label sections >= 5%
                    bar_bottom = sum(chunk_df.iloc[bar_idx][c] for c in categories[:cat_idx])
                    ax.text(x[bar_idx], bar_bottom + val / 2, f'{val:.0f}%',
                            ha='center', va='center', fontsize=8, fontweight='bold',
                            color='white' if cat_idx != 2 else 'black')

        plt.tight_layout()

        suffix = f'_part{chunk_idx + 1}' if n_chunks > 1 else ''
        output_file = output_dir / f'sDSC_distribution_{region_name}{suffix}.png'
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"  Saved: {output_file.name}")


def create_region_sdsc_distribution_barplots(results_file=None, base_output_dir='explore_results'):
    """
    Create stacked barplots showing sDSC score distribution per OAR, grouped by anatomical region.

    Each OAR gets one bar divided into 5 colour-coded sections (summing to 100%),
    matching the categories used in the per-VOI pie charts.

    Parameters
    ----------
    results_file : str, optional
        Path to the results Excel file. Defaults to contour_comparison_results_P0728_v6.xlsx.
    base_output_dir : str
        Base directory containing explore_results (default: 'explore_results')
    """
    import os
    from pathlib import Path

    if results_file is None:
        script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
        results_file = str(script_dir.parent / 'contour_comparison_results_P0728_v7.xlsx')

    if not Path(results_file).exists():
        raise FileNotFoundError(f"Results file not found: {results_file}")

    df = pd.read_excel(results_file, engine='openpyxl')
    print(f"Loaded {len(df)} rows from {results_file}")

    if 'VOIName' not in df.columns or 'SDSC_tol05' not in df.columns:
        raise ValueError("Results file must contain 'VOIName' and 'SDSC_tol05' columns")

    output_dir = Path(base_output_dir) / 'Explore results per region'
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Saving sDSC distribution plots to: {output_dir.absolute()}")

    for region_name, oar_list in REGIONS.items():
        print(f"\nProcessing region: {region_name} ({len(oar_list)} OARs)")

        df_region = df[df['VOIName'].isin(oar_list)].copy()
        if len(df_region) == 0:
            print(f"  No data found for {region_name}")
            continue

        oars_with_data = df_region['VOIName'].unique()
        print(f"  Found data for {len(oars_with_data)} OARs")

        _create_sdsc_distribution_region_barplot(df_region, region_name, oars_with_data, output_dir)

    print(f"\nAll sDSC distribution barplots saved to: {output_dir.absolute()}")


def create_hn_dose_delta_boxplots(results_file=None, base_output_dir='explore_results'):
    """
    Create boxplots of Delta_Dmax and Delta_Dmean for Head & Neck OARs.

    The H&N OAR list is split evenly across two figures per metric so that
    no single figure is overcrowded.

    Parameters
    ----------
    results_file : str, optional
        Path to the results Excel file. Must contain VOIName, Delta_Dmax and
        Delta_Dmean columns.  Defaults to the v7 results file.
    base_output_dir : str
        Base directory to save the plots.
    """
    import os
    from pathlib import Path

    if results_file is None:
        script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
        results_file = str(script_dir.parent / 'contour_comparison_results_P0728_v7.xlsx')

    if not Path(results_file).exists():
        raise FileNotFoundError(f"Results file not found: {results_file}")

    df = pd.read_excel(results_file, engine='openpyxl')
    print(f"Loaded {len(df)} rows from {results_file}")

    for col in ('VOIName', 'Delta_Dmax', 'Delta_Dmean'):
        if col not in df.columns:
            raise ValueError(f"Required column '{col}' not found in results file.")

    output_dir = Path(base_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Saving H&N dose delta boxplots to: {output_dir.absolute()}")

    hn_oars = REGIONS['Head_Neck']
    df_hn = df[df['VOIName'].isin(hn_oars)].copy()

    # Keep only OARs that have at least one non-NaN value in either metric
    oars_with_data = sorted(
        oar for oar in hn_oars
        if oar in df_hn['VOIName'].values and (
            df_hn.loc[df_hn['VOIName'] == oar, 'Delta_Dmax'].notna().any() or
            df_hn.loc[df_hn['VOIName'] == oar, 'Delta_Dmean'].notna().any()
        )
    )

    if not oars_with_data:
        print("  No H&N OARs with dose delta data found.")
        return

    n_oars = len(oars_with_data)
    # Split evenly into two halves
    half = int(np.ceil(n_oars / 2))
    chunks = [oars_with_data[:half], oars_with_data[half:]]
    chunks = [c for c in chunks if c]  # drop empty chunk if n_oars is odd

    def _draw_dose_delta_boxplots(oar_subset, metric_col, metric_label, part_idx, n_parts, output_dir):
        n_in_chunk = len(oar_subset)
        fig_width = max(14, n_in_chunk * 1.4)
        fig, ax = plt.subplots(figsize=(fig_width, 8))

        data_to_plot = []
        labels = []
        for oar in oar_subset:
            vals = df_hn.loc[df_hn['VOIName'] == oar, metric_col].dropna().values
            data_to_plot.append(vals)
            n = len(vals)
            labels.append(f'{oar}\n(n={n})')

        bp = ax.boxplot(
            data_to_plot,
            labels=labels,
            patch_artist=True,
            widths=0.6,
            showmeans=False,
            medianprops=dict(color='black', linewidth=2),
            flierprops=dict(marker='o', markersize=3, alpha=0.5),
        )

        color = '#3498db' if 'Dmax' in metric_col else '#e67e22'
        for patch in bp['boxes']:
            patch.set_facecolor(color)
            patch.set_alpha(0.75)

        ax.axhline(0, color='grey', linestyle='--', linewidth=1, alpha=0.6)
        ax.set_ylim(-10, 10)
        ax.set_xlabel('OAR', fontsize=12, fontweight='bold')
        ax.set_ylabel(f'{metric_label} (Gy)', fontsize=12, fontweight='bold')

        part_label = f' — Part {part_idx}' if n_parts > 1 else ''
        ax.set_title(
            f'Head & Neck — {metric_label} per OAR{part_label}',
            fontsize=14, fontweight='bold', pad=15
        )
        ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=9)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        plt.tight_layout()

        suffix = f'_part{part_idx}' if n_parts > 1 else ''
        fname = f'HN_{metric_col}{suffix}.png'
        plt.savefig(output_dir / fname, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"  Saved: {fname}")

    for metric_col, metric_label in [('Delta_Dmax', 'ΔDmax'), ('Delta_Dmean', 'ΔDmean')]:
        print(f"\n  Creating {metric_label} boxplots...")
        n_parts = len(chunks)
        for part_idx, oar_subset in enumerate(chunks, start=1):
            _draw_dose_delta_boxplots(oar_subset, metric_col, metric_label, part_idx, n_parts, output_dir)

    print(f"\nH&N dose delta boxplots saved to: {output_dir.absolute()}")


def create_oar_summary_table(results_file=None, dicom_root=r'Z:\ICoNEA\DICOM',
                             output_file=None):
    """
    Build a summary table with one row per OAR:

    Columns
    -------
    Region          : anatomical region (from REGIONS dict)
    OAR             : VOI name
    N               : number of Complete-chain rows for this OAR
    Slice_Thickness_mm : comma-separated sorted list of unique slice-thickness
                        values (mm) found in the CT DICOM headers of all
                        patients that have this OAR.  Falls back to 'N/A' when
                        DICOM root is unreachable.

    The table is saved as an Excel workbook at *output_file*.

    Parameters
    ----------
    results_file : str, optional
        Path to the v7 results Excel file.
    dicom_root : str
        Root folder that contains one subfolder per patient (pNumber),
        each containing a 'CT' subfolder.
    output_file : str, optional
        Destination xlsx path.  Defaults to oar_summary_table.xlsx next to
        the results file.
    """
    import os
    from pathlib import Path

    try:
        import pydicom
        _pydicom_ok = True
    except ImportError:
        _pydicom_ok = False
        print("  Warning: pydicom not installed — slice thickness will be 'N/A'.")

    if results_file is None:
        script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
        results_file = str(script_dir.parent / 'contour_comparison_results_P0728_v7.xlsx')

    if output_file is None:
        output_file = str(Path(results_file).parent / 'oar_summary_table.xlsx')

    if not Path(results_file).exists():
        raise FileNotFoundError(f"Results file not found: {results_file}")

    df = pd.read_excel(results_file, engine='openpyxl')
    print(f"  Loaded {len(df)} rows from {results_file}")

    # Work only on rows where the full processing chain completed
    df_ok = df[df['ChainStatus'] == 'Complete'].copy()
    print(f"  Using {len(df_ok)} Complete rows across {df_ok['pNumber'].nunique()} patients")

    # ------------------------------------------------------------------
    # Build region → OAR mapping (invert REGIONS dict)
    # ------------------------------------------------------------------
    oar_to_region = {}
    for region, oar_list in REGIONS.items():
        for oar in oar_list:
            oar_to_region[oar] = region.replace('_', ' & ')

    # All known OARs ordered region-first, then alphabetically within region
    all_oars_ordered = []
    for region in REGIONS:
        for oar in sorted(REGIONS[region]):
            all_oars_ordered.append(oar)

    # ------------------------------------------------------------------
    # Count N per OAR
    # ------------------------------------------------------------------
    n_per_oar = df_ok.groupby('VOIName')['pNumber'].count().to_dict()

    # ------------------------------------------------------------------
    # Read slice thickness from DICOM (cached by (pNumber, series_uid))
    # ------------------------------------------------------------------
    dicom_available = _pydicom_ok and os.path.isdir(dicom_root)

    if not dicom_available:
        reason = "pydicom not installed" if not _pydicom_ok else f"DICOM root not found: {dicom_root}"
        print(f"  Slice thickness lookup skipped ({reason})")

    # Cache: (pNumber, series_uid_str) -> slice_thickness_mm or None
    # Cache: (pNumber, series_uid_str) -> (slice_thickness_mm, pixel_spacing_mm) or (None, None)
    _ct_cache = {}

    def _get_ct_metadata(pnumber, series_uid_raw):
        """Return (slice_thickness_mm, pixel_spacing_mm) as floats, or (None, None)."""
        if not dicom_available:
            return None, None

        # CTSeriesUID stored as float in Excel → strip '.0'
        series_uid = str(series_uid_raw).rstrip('0').rstrip('.') if pd.notna(series_uid_raw) else None
        if not series_uid:
            return None, None

        key = (str(pnumber), series_uid)
        if key in _ct_cache:
            return _ct_cache[key]

        ct_folder = os.path.join(dicom_root, str(pnumber), 'CT')
        if not os.path.isdir(ct_folder):
            _ct_cache[key] = (None, None)
            return None, None

        # Walk CT folder, find any file belonging to this series
        for dirpath, _, filenames in os.walk(ct_folder):
            for fn in filenames:
                if not fn.lower().endswith('.dcm'):
                    continue
                fpath = os.path.join(dirpath, fn)
                try:
                    ds = pydicom.dcmread(fpath, stop_before_pixels=True)
                    file_series = str(ds.get('SeriesInstanceUID', '')).rstrip('0').rstrip('.')
                    if file_series == series_uid:
                        st_raw = ds.get('SliceThickness', None)
                        st = round(float(st_raw), 2) if st_raw else None

                        ps_raw = ds.get('PixelSpacing', None)
                        if ps_raw is not None and len(ps_raw) >= 1:
                            # PixelSpacing is [row_spacing, col_spacing]; report as
                            # "row x col" when they differ, else a single value
                            ps_row = round(float(ps_raw[0]), 4)
                            ps_col = round(float(ps_raw[1]), 4) if len(ps_raw) > 1 else ps_row
                            ps = f'{ps_row}x{ps_col}'
                        else:
                            ps = None

                        result = (st, ps)
                        _ct_cache[key] = result
                        return result
                except Exception:
                    continue

        _ct_cache[key] = (None, None)
        return None, None

    # ------------------------------------------------------------------
    # Gather unique slice thicknesses and pixel spacings per OAR
    # ------------------------------------------------------------------
    # For efficiency, iterate unique (pNumber, CTSeriesUID, VOIName) combos
    oar_slice_thicknesses = {oar: set() for oar in all_oars_ordered}
    oar_pixel_spacings = {oar: set() for oar in all_oars_ordered}

    if dicom_available:
        combos = (
            df_ok[['pNumber', 'CTSeriesUID', 'VOIName']]
            .dropna(subset=['CTSeriesUID', 'VOIName'])
            .drop_duplicates()
        )
        total = len(combos)
        print(f"  Reading CT metadata for {total} unique (patient, series, OAR) combinations...")

        for i, (_, row) in enumerate(combos.iterrows(), 1):
            if i % 500 == 0:
                print(f"    {i}/{total}...")
            oar = row['VOIName']
            if oar not in oar_slice_thicknesses:
                oar_slice_thicknesses[oar] = set()
            if oar not in oar_pixel_spacings:
                oar_pixel_spacings[oar] = set()
            st, ps = _get_ct_metadata(row['pNumber'], row['CTSeriesUID'])
            if st is not None:
                oar_slice_thicknesses[oar].add(st)
            if ps is not None:
                oar_pixel_spacings[oar].add(ps)

    # ------------------------------------------------------------------
    # Assemble table rows
    # ------------------------------------------------------------------
    rows = []
    for oar in all_oars_ordered:
        region = oar_to_region.get(oar, 'Unknown')
        n = n_per_oar.get(oar, 0)
        if n == 0:
            continue  # OAR not present in this dataset

        st_values = sorted(oar_slice_thicknesses.get(oar, set()))
        st_str = ', '.join(f'{v:.2f}' for v in st_values) if st_values else 'N/A'

        ps_values = sorted(oar_pixel_spacings.get(oar, set()))
        ps_str = ', '.join(ps_values) if ps_values else 'N/A'

        rows.append({
            'Region': region,
            'OAR': oar,
            'N': int(n),
            'Slice_Thickness_mm': st_str,
            'Pixel_Spacing_mm': ps_str,
        })

    if not rows:
        print("  No OARs with data found — table not written.")
        return

    summary_df = pd.DataFrame(rows, columns=['Region', 'OAR', 'N', 'Slice_Thickness_mm', 'Pixel_Spacing_mm'])

    # ------------------------------------------------------------------
    # Calculate overall averages for all OARs combined
    # ------------------------------------------------------------------
    required_metric_cols = ['SDSC_tol05', 'SDSC_tol3', 'APL_tol05', 'APL_tol3']
    missing_metric_cols = [col for col in required_metric_cols if col not in df_ok.columns]
    
    if missing_metric_cols:
        print(f"  Warning: Missing columns for overall averages: {missing_metric_cols}")
        overall_stats_df = None
    else:
        # Drop rows with missing metric values
        df_metrics = df_ok.dropna(subset=required_metric_cols)
        print(f"  Calculating overall averages from {len(df_metrics)} rows with complete metrics")
        
        overall_stats = {
            'Metric': ['sDSC (tol=0.5mm)', 'sDSC (tol=3mm)', 'APL (tol=0.5mm)', 'APL (tol=3mm)'],
            'Mean': [
                df_metrics['SDSC_tol05'].mean(),
                df_metrics['SDSC_tol3'].mean(),
                df_metrics['APL_tol05'].mean(),
                df_metrics['APL_tol3'].mean()
            ],
            'Std': [
                df_metrics['SDSC_tol05'].std(),
                df_metrics['SDSC_tol3'].std(),
                df_metrics['APL_tol05'].std(),
                df_metrics['APL_tol3'].std()
            ],
            'N': [
                df_metrics['SDSC_tol05'].count(),
                df_metrics['SDSC_tol3'].count(),
                df_metrics['APL_tol05'].count(),
                df_metrics['APL_tol3'].count()
            ]
        }
        overall_stats_df = pd.DataFrame(overall_stats)
        
        print(f"\n  Overall statistics across all OARs:")
        for idx, row in overall_stats_df.iterrows():
            print(f"    {row['Metric']:20s}: {row['Mean']:.3f} ± {row['Std']:.3f} (N={int(row['N'])})")

    # ------------------------------------------------------------------
    # Write to Excel with basic formatting
    # ------------------------------------------------------------------
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        summary_df.to_excel(writer, index=False, sheet_name='OAR Summary')

        ws = writer.sheets['OAR Summary']

        # Auto-width columns
        for col_cells in ws.iter_cols():
            max_len = max((len(str(cell.value)) if cell.value is not None else 0)
                          for cell in col_cells)
            ws.column_dimensions[col_cells[0].column_letter].width = min(max_len + 4, 60)

        # Colour header row
        from openpyxl.styles import PatternFill, Font
        header_fill = PatternFill(start_color='2C3E50', end_color='2C3E50', fill_type='solid')
        header_font = Font(color='FFFFFF', bold=True)
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font

        # Alternating row colours within each region group
        from openpyxl.styles import PatternFill as PF
        region_colors = {}
        palette = ['DCE8F5', 'FEF0D9', 'E8F5E9', 'F5E8F5', 'FFF9C4']
        for i, region in enumerate(sorted(set(r['Region'] for r in rows))):
            region_colors[region] = palette[i % len(palette)]

        for row_idx, row_obj in enumerate(ws.iter_rows(min_row=2), start=2):
            region_val = ws.cell(row=row_idx, column=1).value
            color = region_colors.get(region_val, 'FFFFFF')
            fill = PF(start_color=color, end_color=color, fill_type='solid')
            for cell in row_obj:
                cell.fill = fill

        # ------------------------------------------------------------------
        # Write overall statistics to second sheet
        # ------------------------------------------------------------------
        if overall_stats_df is not None:
            overall_stats_df.to_excel(writer, index=False, sheet_name='Overall Averages')
            
            ws_overall = writer.sheets['Overall Averages']
            
            # Auto-width columns
            for col_cells in ws_overall.iter_cols():
                max_len = max((len(str(cell.value)) if cell.value is not None else 0)
                              for cell in col_cells)
                ws_overall.column_dimensions[col_cells[0].column_letter].width = min(max_len + 4, 30)
            
            # Format header row
            header_fill = PatternFill(start_color='2C3E50', end_color='2C3E50', fill_type='solid')
            header_font = Font(color='FFFFFF', bold=True)
            for cell in ws_overall[1]:
                cell.fill = header_fill
                cell.font = header_font
            
            # Alternating row colors
            light_fill = PF(start_color='F0F0F0', end_color='F0F0F0', fill_type='solid')
            white_fill = PF(start_color='FFFFFF', end_color='FFFFFF', fill_type='solid')
            for row_idx in range(2, len(overall_stats_df) + 2):
                fill = light_fill if (row_idx % 2 == 0) else white_fill
                for cell in ws_overall[row_idx]:
                    cell.fill = fill

        # ------------------------------------------------------------------
        # Write OARs Considered sheet (all OARs from REGIONS)
        # ------------------------------------------------------------------
        oars_considered_rows = []
        total_oars = 0
        for region, oar_list in REGIONS.items():
            region_display = region.replace('_', ' & ')
            for oar in sorted(oar_list):
                n = n_per_oar.get(oar, 0)
                oars_considered_rows.append({
                    'Region': region_display,
                    'OAR': oar,
                    'N': int(n) if n > 0 else 0
                })
                total_oars += 1
        
        oars_considered_df = pd.DataFrame(oars_considered_rows, columns=['Region', 'OAR', 'N'])
        oars_considered_df.to_excel(writer, index=False, sheet_name='OARs Considered')
        
        ws_considered = writer.sheets['OARs Considered']
        
        # Auto-width columns
        for col_cells in ws_considered.iter_cols():
            max_len = max((len(str(cell.value)) if cell.value is not None else 0)
                          for cell in col_cells)
            ws_considered.column_dimensions[col_cells[0].column_letter].width = min(max_len + 4, 40)
        
        # Format header row
        for cell in ws_considered[1]:
            cell.fill = header_fill
            cell.font = header_font
        
        # Alternating row colors by region
        for row_idx, row_obj in enumerate(ws_considered.iter_rows(min_row=2), start=2):
            region_val = ws_considered.cell(row=row_idx, column=1).value
            color = region_colors.get(region_val, 'FFFFFF')
            fill = PF(start_color=color, end_color=color, fill_type='solid')
            for cell in row_obj:
                cell.fill = fill
        
        print(f"  Total OARs considered: {total_oars} across {len(REGIONS)} regions")

    print(f"  OAR summary table saved to: {output_file}")
    print(f"  Rows: {len(summary_df)} OARs across {summary_df['Region'].nunique()} regions")
    if overall_stats_df is not None:
        print(f"  Overall averages sheet included with {len(overall_stats_df)} metrics")


def create_apl_temporal_lineplot(results_file=None, output_file=None):
    """
    Create a line plot showing APL_tol05 and APL_tol3 average scores per month.
    
    Parameters
    ----------
    results_file : str, optional
        Path to the results Excel file. Defaults to contour_comparison_results_P0728_v7.xlsx
    output_file : str, optional
        Path for the output PNG file. Defaults to 'apl_temporal_lineplot.png' next to results file.
    
    Returns
    -------
    None
        Saves plot to disk
    """
    # --- Configure defaults ---
    if results_file is None:
        results_file = 'contour_comparison_results_P0728_v7.xlsx'
    if output_file is None:
        output_file = str(Path(results_file).parent / 'apl_temporal_lineplot.png')
    
    print(f"\nCreating temporal line plot for APL metrics...")
    print(f"  Input: {results_file}")
    print(f"  Output: {output_file}")
    
    # --- Load data ---
    if not Path(results_file).exists():
        raise FileNotFoundError(f"Results file not found: {results_file}")
    
    df = pd.read_excel(results_file, engine='openpyxl')
    print(f"  Loaded {len(df)} rows from {results_file}")
    
    # --- Check for required columns ---
    required_cols = ['Clinical_RTSTRUCT_Date', 'APL_tol05', 'APL_tol3']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"  ✗ Missing required columns: {missing_cols}")
        print(f"  Available columns: {list(df.columns)}")
        return
    
    # --- Work only on Complete rows ---
    if 'ChainStatus' in df.columns:
        df_ok = df[df['ChainStatus'] == 'Complete'].copy()
        print(f"  Using {len(df_ok)} Complete rows across {df_ok['pNumber'].nunique()} patients")
    else:
        df_ok = df.copy()
        print(f"  No ChainStatus column found, using all {len(df_ok)} rows")
    
    # --- Filter to only OARs in REGIONS dictionary ---
    all_oars = []
    for region, oar_list in REGIONS.items():
        all_oars.extend(oar_list)
    
    if 'VOIName' in df_ok.columns:
        before_count = len(df_ok)
        df_ok = df_ok[df_ok['VOIName'].isin(all_oars)].copy()
        print(f"  Filtered to {len(all_oars)} OARs from REGIONS dictionary: {len(df_ok)} rows (removed {before_count - len(df_ok)} rows)")
    else:
        print(f"  Warning: VOIName column not found, using all rows")
    
    # --- Convert date to datetime and create month bins ---
    # Dates are stored as floats in YYYYMMDD format (e.g., 20250130.0)
    # Convert to int first, then to string, then parse as datetime
    df_ok = df_ok.dropna(subset=['Clinical_RTSTRUCT_Date'])
    df_ok['Clinical_RTSTRUCT_Date'] = pd.to_datetime(
        df_ok['Clinical_RTSTRUCT_Date'].astype(int).astype(str), 
        format='%Y%m%d', 
        errors='coerce'
    )
    
    # Drop rows with invalid dates after parsing
    df_ok = df_ok.dropna(subset=['Clinical_RTSTRUCT_Date'])
    print(f"  {len(df_ok)} rows with valid dates")
    
    # Create year-month column for grouping
    df_ok['YearMonth'] = df_ok['Clinical_RTSTRUCT_Date'].dt.to_period('M')
    
    # Filter to December 2024 through June 2025
    df_ok = df_ok[(df_ok['YearMonth'] >= '2024-12') & (df_ok['YearMonth'] <= '2025-06')]
    print(f"  {len(df_ok)} rows in date range (Dec 2024 - Jun 2025)")
    
    # Drop rows with missing APL values
    df_ok = df_ok.dropna(subset=['APL_tol05', 'APL_tol3'])
    print(f"  {len(df_ok)} rows with valid APL values")
    
    if len(df_ok) == 0:
        print("  ✗ No valid data to plot")
        return
    
    # --- Calculate selected-period aggregate values for reference only ---
    overall_apl05_mean = df_ok['APL_tol05'].mean()
    overall_apl05_std = df_ok['APL_tol05'].std()
    overall_apl3_mean = df_ok['APL_tol3'].mean()
    overall_apl3_std = df_ok['APL_tol3'].std()
    
    print(f"\n  Selected-period aggregate statistics (not plotted as monthly values):")
    print(f"    APL (tol=0.5mm): {overall_apl05_mean:.3f} ± {overall_apl05_std:.3f}")
    print(f"    APL (tol=3mm):   {overall_apl3_mean:.3f} ± {overall_apl3_std:.3f}")
    
    # --- Calculate monthly averages ---
    monthly_stats = df_ok.groupby('YearMonth').agg({
        'APL_tol05': ['mean', 'std', 'count'],
        'APL_tol3': ['mean', 'std', 'count']
    }).reset_index()
    
    # Flatten column names
    monthly_stats.columns = ['YearMonth', 'APL05_mean', 'APL05_std', 'APL05_count', 
                              'APL3_mean', 'APL3_std', 'APL3_count']
    
    # Convert YearMonth back to timestamp for plotting
    monthly_stats['Date'] = monthly_stats['YearMonth'].dt.to_timestamp()
    
    print(f"\n  Monthly bins: {len(monthly_stats)} months from {monthly_stats['Date'].min()} to {monthly_stats['Date'].max()}")
    print(f"  Samples per month: {monthly_stats['APL05_count'].min()}-{monthly_stats['APL05_count'].max()}")
    print("\n  Monthly-bin averages used in the plot:")
    print(
        monthly_stats[
            ['YearMonth', 'APL05_mean', 'APL05_count', 'APL3_mean', 'APL3_count']
        ].to_string(index=False)
    )
    
    # --- Create line plot ---
    fig, ax = plt.subplots(figsize=(14, 6))
    
    # Plot APL_tol05 (0.5mm)
    ax.plot(monthly_stats['Date'], monthly_stats['APL05_mean'], 
            marker='o', linewidth=2, markersize=6, 
            label='APL (tol=0.5mm)', color='#2E86AB', alpha=0.8)
    
    # Plot APL_tol3 (3mm)
    ax.plot(monthly_stats['Date'], monthly_stats['APL3_mean'], 
            marker='s', linewidth=2, markersize=6,
            label='APL (tol=3mm)', color='#A23B72', alpha=0.8)
    
    # Styling
    ax.set_xlabel('Month', fontsize=12, fontweight='bold')
    ax.set_ylabel('Average Added Path Length (mm)', fontsize=12, fontweight='bold')
    ax.set_title(
        'APL Temporal Trends: Monthly Averages (2024-12 to 2025-06)',
        fontsize=14,
        fontweight='bold',
        pad=20
    )
    ax.legend(fontsize=11, frameon=True, fancybox=True, shadow=True)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.set_ylim(bottom=0)
    
    # Format x-axis as month plus sample count per monthly bin.
    ax.set_xticks(monthly_stats['Date'])
    ax.set_xticklabels(
        [
            f"{row['YearMonth']}\n(N={int(row['APL05_count'])})"
            for _, row in monthly_stats.iterrows()
        ],
        rotation=45,
        ha='right'
    )
    
    plt.tight_layout()
    
    # Save figure
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"\n  ✓ Temporal line plot saved to: {output_file}")
    plt.close()


def create_sdsc_temporal_lineplot(results_file=None, output_file=None):
    """
    Create a line plot showing SDSC_tol05 and SDSC_tol3 average scores per month.
    
    Parameters
    ----------
    results_file : str, optional
        Path to the results Excel file. Defaults to contour_comparison_results_P0728_v7.xlsx
    output_file : str, optional
        Path for the output PNG file. Defaults to 'sdsc_temporal_lineplot.png' next to results file.
    
    Returns
    -------
    None
        Saves plot to disk
    """
    # --- Configure defaults ---
    if results_file is None:
        results_file = 'contour_comparison_results_P0728_v7.xlsx'
    if output_file is None:
        output_file = str(Path(results_file).parent / 'sdsc_temporal_lineplot.png')
    
    print(f"\nCreating temporal line plot for SDSC metrics...")
    print(f"  Input: {results_file}")
    print(f"  Output: {output_file}")
    
    # --- Load data ---
    if not Path(results_file).exists():
        raise FileNotFoundError(f"Results file not found: {results_file}")
    
    df = pd.read_excel(results_file, engine='openpyxl')
    print(f"  Loaded {len(df)} rows from {results_file}")
    
    # --- Check for required columns ---
    required_cols = ['Clinical_RTSTRUCT_Date', 'SDSC_tol05', 'SDSC_tol3']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"  ✗ Missing required columns: {missing_cols}")
        print(f"  Available columns: {list(df.columns)}")
        return
    
    # --- Work only on Complete rows ---
    if 'ChainStatus' in df.columns:
        df_ok = df[df['ChainStatus'] == 'Complete'].copy()
        print(f"  Using {len(df_ok)} Complete rows across {df_ok['pNumber'].nunique()} patients")
    else:
        df_ok = df.copy()
        print(f"  No ChainStatus column found, using all {len(df_ok)} rows")
    
    # --- Filter to only OARs in REGIONS dictionary ---
    all_oars = []
    for region, oar_list in REGIONS.items():
        all_oars.extend(oar_list)
    
    if 'VOIName' in df_ok.columns:
        before_count = len(df_ok)
        df_ok = df_ok[df_ok['VOIName'].isin(all_oars)].copy()
        print(f"  Filtered to {len(all_oars)} OARs from REGIONS dictionary: {len(df_ok)} rows (removed {before_count - len(df_ok)} rows)")
    else:
        print(f"  Warning: VOIName column not found, using all rows")
    
    # --- Convert date to datetime and create month bins ---
    # Dates are stored as integers in YYYYMMDD format (e.g., 20250130)
    # Convert to int first, then to string, then parse as datetime
    df_ok = df_ok.dropna(subset=['Clinical_RTSTRUCT_Date'])
    df_ok['Clinical_RTSTRUCT_Date'] = pd.to_datetime(
        df_ok['Clinical_RTSTRUCT_Date'].astype(int).astype(str), 
        format='%Y%m%d', 
        errors='coerce'
    )
    
    # Drop rows with invalid dates after parsing
    df_ok = df_ok.dropna(subset=['Clinical_RTSTRUCT_Date'])
    print(f"  {len(df_ok)} rows with valid dates")
    
    # Create year-month column for grouping
    df_ok['YearMonth'] = df_ok['Clinical_RTSTRUCT_Date'].dt.to_period('M')
    
    # Filter to December 2024 through June 2025
    df_ok = df_ok[(df_ok['YearMonth'] >= '2024-12') & (df_ok['YearMonth'] <= '2025-06')]
    print(f"  {len(df_ok)} rows in date range (Dec 2024 - Jun 2025)")
    
    # Drop rows with missing SDSC values
    df_ok = df_ok.dropna(subset=['SDSC_tol05', 'SDSC_tol3'])
    print(f"  {len(df_ok)} rows with valid SDSC values")
    
    if len(df_ok) == 0:
        print("  ✗ No valid data to plot")
        return
    
    # --- Calculate selected-period aggregate values for reference only ---
    overall_sdsc05_mean = df_ok['SDSC_tol05'].mean()
    overall_sdsc05_std = df_ok['SDSC_tol05'].std()
    overall_sdsc3_mean = df_ok['SDSC_tol3'].mean()
    overall_sdsc3_std = df_ok['SDSC_tol3'].std()
    
    print(f"\n  Selected-period aggregate statistics (not plotted as monthly values):")
    print(f"    sDSC (tol=0.5mm): {overall_sdsc05_mean:.3f} ± {overall_sdsc05_std:.3f}")
    print(f"    sDSC (tol=3mm):   {overall_sdsc3_mean:.3f} ± {overall_sdsc3_std:.3f}")
    
    # --- Calculate monthly averages ---
    monthly_stats = df_ok.groupby('YearMonth').agg({
        'SDSC_tol05': ['mean', 'std', 'count'],
        'SDSC_tol3': ['mean', 'std', 'count']
    }).reset_index()
    
    # Flatten column names
    monthly_stats.columns = ['YearMonth', 'SDSC05_mean', 'SDSC05_std', 'SDSC05_count', 
                              'SDSC3_mean', 'SDSC3_std', 'SDSC3_count']
    
    # Convert YearMonth back to timestamp for plotting
    monthly_stats['Date'] = monthly_stats['YearMonth'].dt.to_timestamp()
    
    # --- Calculate percentage of perfect scores (sDSC = 1.0) per month ---
    def calc_perfect_pct(group):
        perfect_count = (group['SDSC_tol3'] == 1.0).sum()
        total_count = len(group)
        return (perfect_count / total_count * 100) if total_count > 0 else 0
    
    perfect_pct_per_month = df_ok.groupby('YearMonth').apply(calc_perfect_pct).reset_index()
    perfect_pct_per_month.columns = ['YearMonth', 'Perfect_Pct']
    perfect_pct_per_month['Date'] = perfect_pct_per_month['YearMonth'].dt.to_timestamp()
    
    # Merge with monthly_stats
    monthly_stats = monthly_stats.merge(perfect_pct_per_month[['Date', 'Perfect_Pct']], on='Date')
    
    print(f"\n  Monthly bins: {len(monthly_stats)} months from {monthly_stats['Date'].min()} to {monthly_stats['Date'].max()}")
    print(f"  Samples per month: {monthly_stats['SDSC05_count'].min()}-{monthly_stats['SDSC05_count'].max()}")
    print(f"  Perfect scores (sDSC=1.0) per month: {monthly_stats['Perfect_Pct'].min():.1f}%-{monthly_stats['Perfect_Pct'].max():.1f}%")
    print("\n  Monthly-bin averages used in the plot:")
    print(
        monthly_stats[
            [
                'YearMonth',
                'SDSC05_mean',
                'SDSC05_count',
                'SDSC3_mean',
                'SDSC3_count',
                'Perfect_Pct'
            ]
        ].to_string(index=False)
    )
    
    # --- Create line plot with dual Y-axes ---
    fig, ax1 = plt.subplots(figsize=(14, 6))
    
    # Primary Y-axis: sDSC values
    ax1.plot(monthly_stats['Date'], monthly_stats['SDSC05_mean'], 
            marker='o', linewidth=2, markersize=6, 
            label='sDSC (tol=0.5mm)', color='#F18F01', alpha=0.8)
    
    ax1.plot(monthly_stats['Date'], monthly_stats['SDSC3_mean'], 
            marker='s', linewidth=2, markersize=6,
            label='sDSC (tol=3mm)', color='#06A77D', alpha=0.8)
    
    ax1.set_xlabel('Month', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Average Surface DICE Score', fontsize=12, fontweight='bold')
    ax1.set_ylim(bottom=0, top=1.0)
    ax1.grid(True, alpha=0.3, linestyle='--')
    ax1.tick_params(axis='y')
    
    # Secondary Y-axis: Perfect score percentage
    ax2 = ax1.twinx()
    ax2.plot(monthly_stats['Date'], monthly_stats['Perfect_Pct'], 
            marker='D', linewidth=2, markersize=6, linestyle='--',
            label='% Perfect Scores (sDSC=1.0)', color='#E63946', alpha=0.8)
    
    ax2.set_ylabel('% Perfect Scores (sDSC=1.0)', fontsize=12, fontweight='bold', color='#E63946')
    ax2.set_ylim(bottom=0, top=100)
    ax2.tick_params(axis='y', labelcolor='#E63946')
    
    # Combine legends from both axes
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=11, frameon=True, fancybox=True, shadow=True, loc='best')
    
    ax1.set_title(
        'sDSC Temporal Trends: Monthly Averages (2024-12 to 2025-06)',
        fontsize=14,
        fontweight='bold',
        pad=20
    )
    
    # Format x-axis as month plus sample count per monthly bin.
    ax1.set_xticks(monthly_stats['Date'])
    ax1.set_xticklabels(
        [
            f"{row['YearMonth']}\n(N={int(row['SDSC05_count'])})"
            for _, row in monthly_stats.iterrows()
        ],
        rotation=45,
        ha='right'
    )
    
    plt.tight_layout()
    
    # Save figure
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"\n  ✓ Temporal line plot saved to: {output_file}")
    plt.close()


def main():
    """Main execution function."""
    print("="*80)
    print("Contour Comparison Results Explorer")
    print("="*80)

    import os
    script_dir = Path(os.path.dirname(os.path.abspath(__file__)))

    # -----------------------------------------------------------------------
    # Configuration
    # -----------------------------------------------------------------------
    BASE_RESULTS_FILE = str(script_dir.parent / 'contour_comparison_results_P0728_v7.xlsx')
    results_to_plot = BASE_RESULTS_FILE
    
    # Create output folder structure
    BASE_OUTPUT_DIR = script_dir.parent / 'explore_results'
    OVERALL_OUTPUT_DIR = BASE_OUTPUT_DIR / 'Overall'
    
    # Ensure directories exist
    BASE_OUTPUT_DIR.mkdir(exist_ok=True)
    OVERALL_OUTPUT_DIR.mkdir(exist_ok=True)
    
    print(f"\nOutput directories:")
    print(f"  Base: {BASE_OUTPUT_DIR}")
    print(f"  Overall: {OVERALL_OUTPUT_DIR}")

    # -----------------------------------------------------------------------
    # Step 1: create APL barplots
    # -----------------------------------------------------------------------
    print("\n" + "="*80)
    print("Creating region APL barplots...")
    print("="*80)
    try:
        create_region_barplots(results_to_plot, str(BASE_OUTPUT_DIR))
    except Exception as e:
        print(f"Error occurred: {e}")
        import traceback
        traceback.print_exc()

    # -----------------------------------------------------------------------
    # Step 2: create H&N Dmax / Dmean delta boxplots
    # -----------------------------------------------------------------------
    print("\n" + "="*80)
    print("Creating H&N dose delta boxplots...")
    print("="*80)
    try:
        create_hn_dose_delta_boxplots(results_to_plot, str(OVERALL_OUTPUT_DIR))
    except Exception as e:
        print(f"Error occurred: {e}")
        import traceback
        traceback.print_exc()

    # -----------------------------------------------------------------------
    # Step 3: create per-VOI plots (histograms + dose-distance + sdsc05 correlations)
    # -----------------------------------------------------------------------
    print("\n" + "="*80)
    print("Creating per-VOI visualisations (histograms, correlation plots)...")
    print("="*80)
    try:
        create_voi_scatterplots(results_to_plot, str(BASE_OUTPUT_DIR))
    except Exception as e:
        print(f"Error occurred: {e}")
        import traceback
        traceback.print_exc()

    # -----------------------------------------------------------------------
    # Step 4: OAR summary table (region / OAR / N / slice thickness)
    # -----------------------------------------------------------------------
    print("\n" + "="*80)
    print("Creating OAR summary table...")
    print("="*80)
    try:
        create_oar_summary_table(
            results_file=results_to_plot,
            dicom_root=r'Z:\ICoNEA\DICOM',
            output_file=str(OVERALL_OUTPUT_DIR / 'oar_summary_table.xlsx'),
        )
    except Exception as e:
        print(f"Error occurred: {e}")
        import traceback
        traceback.print_exc()

    # -----------------------------------------------------------------------
    # Step 5: APL temporal line plot (monthly averages of APL_tol05 and APL_tol3)
    # -----------------------------------------------------------------------
    print("\n" + "="*80)
    print("Creating APL temporal line plot...")
    print("="*80)
    try:
        create_apl_temporal_lineplot(
            results_file=results_to_plot,
            output_file=str(OVERALL_OUTPUT_DIR / 'apl_temporal_lineplot.png'),
        )
    except Exception as e:
        print(f"Error occurred: {e}")
        import traceback
        traceback.print_exc()

    # -----------------------------------------------------------------------
    # Step 6: SDSC temporal line plot (monthly averages of SDSC_tol05 and SDSC_tol3)
    # -----------------------------------------------------------------------
    print("\n" + "="*80)
    print("Creating SDSC temporal line plot...")
    print("="*80)
    try:
        create_sdsc_temporal_lineplot(
            results_file=results_to_plot,
            output_file=str(OVERALL_OUTPUT_DIR / 'sdsc_temporal_lineplot.png'),
        )
    except Exception as e:
        print(f"Error occurred: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*80)
    print("Analysis complete!")
    print(f"All results saved to: {BASE_OUTPUT_DIR}")
    print(f"  - Per-VOI plots: {BASE_OUTPUT_DIR / '{VOI_Name}/'}")
    print(f"  - Per-region plots: {BASE_OUTPUT_DIR / 'Explore results per region/'}")
    print(f"  - Overall/general plots: {OVERALL_OUTPUT_DIR}")
    print("="*80)


if __name__ == '__main__':
    main()
