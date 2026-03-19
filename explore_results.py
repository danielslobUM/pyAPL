"""
Explore and visualize contour comparison results

This script loads the results CSV from quantifycontourdifferences_P0728.py
and creates visualizations showing average metrics (APL, DICE, SDSC) for each VOI.
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path


def load_results(results_file='contour_comparison_results_P0728_v5.xlsx'):
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
        bars2 = ax1.bar(x + width/2, sdsc_values, width, label='SDSC', color='#3498db', alpha=0.8)
        
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
        results_file = str(script_dir.parent / 'contour_comparison_results_P0728_v6.xlsx')
    
    # Load raw results
    if not Path(results_file).exists():
        raise FileNotFoundError(f"Results file not found: {results_file}")
    
    df = pd.read_excel(results_file, engine='openpyxl')
    print(f"Loaded {len(df)} rows from {results_file}")
    
    # Check required columns
    if 'VOIName' not in df.columns or 'SDSC_tol0' not in df.columns:
        raise ValueError("Results file must contain 'VOIName' and 'SDSC_tol0' columns")
    
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
        valid = voi_df['SDSC_tol0'].dropna()
        total_count = len(valid)
        
        # Skip if no data
        if total_count == 0:
            continue
        
        # Compute counts from raw SDSC_tol0 values
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


def create_voi_scatterplots(results_file='contour_comparison_results_P0728_v5.xlsx', base_output_dir='explore_results'):
    """
    Create visualizations for each VOI showing metric distributions and clustering.
    
    For each VOI, creates:
    - histograms.png: 2x2 grid with histogram + KDE for SDSC_tol0, SDSC_tol0.1, VDSC (Dice), APL
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
    
    # Load results
    if not Path(results_file).exists():
        print(f"Error: File not found: {results_file}")
        return
    
    df = pd.read_excel(results_file)
    print(f"Loaded {len(df)} rows from {results_file}")
    
    # Check required columns
    required_cols = ['VOIName', 'SDSC_tol0', 'SDSC', 'Dice', 'APL']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"Error: Missing columns: {missing_cols}")
        return
    
    # Create base output directory
    base_path = Path(base_output_dir)
    base_path.mkdir(exist_ok=True)
    print(f"Saving charts to: {base_path.absolute()}")
    
    # Get unique VOIs
    unique_vois = df['VOIName'].unique()
    print(f"Found {len(unique_vois)} unique VOIs")
    
    # New column: SDSC_tol0 GMM cluster label, e.g. 'Heart_1', 'Heart_2'
    df['SDSC_tol0_GMM_cluster'] = ''
    
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
        
        # ========== Assign SDSC_tol0 GMM cluster labels back to main DataFrame ==========
        valid_sdsc = voi_df.dropna(subset=['SDSC_tol0'])
        if len(valid_sdsc) > 0:
            labels, centroid_dict, _ = gmm_clustering(valid_sdsc['SDSC_tol0'])
            # rank 1 = lowest centroid, rank 2 = next, etc.
            rank_map = {
                cid: rank + 1
                for rank, (cid, _) in enumerate(
                    sorted(centroid_dict.items(), key=lambda x: x[1])
                )
            }
            cluster_values = [f"{voi_name}_{rank_map[lbl]}" for lbl in labels]
            df.loc[valid_sdsc.index, 'SDSC_tol0_GMM_cluster'] = cluster_values
        
        # ========== Histograms with KDE (2x2 grid) ==========
        create_histograms_plot(voi_df, voi_name, voi_output_path, n_samples)
        
        # ========== GMM + 1D K-means comparison plot ==========
        create_gmm_kmeans_plot(voi_df, voi_name, voi_output_path, n_samples)
    
    # Save updated DataFrame with SDSC_tol0 GMM cluster assignments as v6
    output_excel = str(Path(results_file).parent / 'quantifycontourdifferences_P0728_v6.xlsx')
    df.to_excel(output_excel, index=False)
    print(f"Cluster assignments saved to '{output_excel}'")
    
    print(f"\nVOI visualizations saved successfully to '{base_path}' folder.")


def create_histograms_plot(voi_df, voi_name, output_path, n_samples):
    """
    Create a 2x2 grid of histograms with KDE for all metrics.
    
    Layout:
    - Top-left: SDSC (tol=0.0) and SDSC (tol=0.1) overlaid
    - Top-right: VDSC (Dice)
    - Bottom-left: APL
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
    
    # Plot 1: SDSC_tol0 and SDSC (tol 0.1) overlaid (top-left)
    ax = axes[0, 0]
    valid_tol0 = voi_df.dropna(subset=['SDSC_tol0'])
    valid_tol1 = voi_df.dropna(subset=['SDSC'])
    if len(valid_tol0) > 0:
        ax.hist(valid_tol0['SDSC_tol0'], bins=20, alpha=0.5, color='#27ae60', label='SDSC (tol=0.0)', density=True)
        if len(valid_tol0) > 1:
            try:
                kde = gaussian_kde(valid_tol0['SDSC_tol0'])
                x_range = np.linspace(0, 1, 200)
                ax.plot(x_range, kde(x_range), color='#27ae60', linewidth=2)
            except np.linalg.LinAlgError:
                pass
    if len(valid_tol1) > 0:
        ax.hist(valid_tol1['SDSC'], bins=20, alpha=0.5, color='#3498db', label='SDSC (tol=0.1)', density=True)
        if len(valid_tol1) > 1:
            try:
                kde = gaussian_kde(valid_tol1['SDSC'])
                x_range = np.linspace(0, 1, 200)
                ax.plot(x_range, kde(x_range), color='#3498db', linewidth=2)
            except np.linalg.LinAlgError:
                pass
    ax.set_xlabel('SDSC Value', fontsize=11)
    ax.set_ylabel('Density', fontsize=11)
    ax.set_title('Distribution: SDSC Metrics', fontsize=12, weight='bold')
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
    
    # Plot 3: APL histogram + KDE (bottom-left)
    ax = axes[1, 0]
    valid_apl = voi_df.dropna(subset=['APL'])
    if len(valid_apl) > 0:
        ax.hist(valid_apl['APL'], bins=25, alpha=0.6, color='#9b59b6', label='APL', density=True, edgecolor='black')
        if len(valid_apl) > 1:
            try:
                kde = gaussian_kde(valid_apl['APL'])
                apl_min, apl_max = valid_apl['APL'].min(), valid_apl['APL'].max()
                x_range = np.linspace(max(0, apl_min - (apl_max - apl_min) * 0.1), 
                                     apl_max + (apl_max - apl_min) * 0.1, 300)
                ax.plot(x_range, kde(x_range), color='#8e44ad', linewidth=3, label='KDE', alpha=0.8)
            except np.linalg.LinAlgError:
                pass
    ax.set_xlabel('APL (mm)', fontsize=11)
    ax.set_ylabel('Density', fontsize=11)
    ax.set_title('Distribution: APL (Added Path Length)', fontsize=12, weight='bold')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    
    # Plot 4: Summary statistics table (bottom-right)
    ax = axes[1, 1]
    ax.axis('off')
    
    # Build statistics table
    stats_data = []
    for col, label, fmt in [('SDSC_tol0', 'SDSC (tol=0.0)', '.3f'), 
                              ('SDSC', 'SDSC (tol=0.1)', '.3f'),
                              ('Dice', 'VDSC (Dice)', '.3f'), 
                              ('APL', 'APL (mm)', '.2f')]:
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
        table.set_fontsize(10)
        table.scale(1.2, 1.8)
        
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


def create_gmm_kmeans_plot(voi_df, voi_name, output_path, n_samples):
    """
    Create a comparison plot of GMM and 1D K-means (Ckmeans-style) clustering
    for all metrics: SDSC_tol0, SDSC (tol 0.1), VDSC (Dice), and APL.
    
    Layout: 2x4 grid
    - Row 1: GMM clustering for each metric
    - Row 2: 1D K-means clustering for each metric
    
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
    from sklearn.mixture import GaussianMixture
    from sklearn.cluster import KMeans
    import numpy as np
    import matplotlib.pyplot as plt
    
    metrics = [
        ('SDSC_tol0', 'SDSC (tol=0.0)', (0, 1)),
        ('SDSC', 'SDSC (tol=0.1)', (0, 1)),
        ('Dice', 'VDSC (Dice)', (0, 1)),
        ('APL', 'APL (mm)', None),  # No fixed range for APL
    ]
    
    def kmeans_1d_clustering(data):
        """Apply 1D K-means with optimal k selection via silhouette score."""
        from sklearn.metrics import silhouette_score
        
        if len(data) < 3:
            return np.zeros(len(data), dtype=int), {0: data.mean()}, 1
        
        # Check if all values are identical
        if data.std() < 1e-10:
            return np.zeros(len(data), dtype=int), {0: data.mean()}, 1
        
        data_reshaped = data.values.reshape(-1, 1)
        
        # Try 2 to max_k clusters, select best by silhouette score
        max_k = min(6, len(data) // 2)
        max_k = max(2, max_k)
        
        best_score = -1
        best_labels = None
        best_centroids = None
        best_n = 1
        
        for k in range(2, max_k + 1):
            try:
                kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
                labels = kmeans.fit_predict(data_reshaped)
                # Check we actually got k clusters (can happen with few unique values)
                if len(np.unique(labels)) < 2:
                    continue
                score = silhouette_score(data_reshaped, labels)
                if score > best_score:
                    best_score = score
                    best_labels = labels
                    best_centroids = kmeans.cluster_centers_.flatten()
                    best_n = k
            except Exception:
                continue
        
        # If no multi-cluster solution found, or silhouette is very low, use 1 cluster
        if best_labels is None or best_score < 0.3:
            return np.zeros(len(data), dtype=int), {0: data.mean()}, 1
        
        centroid_dict = {}
        for cid in np.unique(best_labels):
            centroid_dict[cid] = data[best_labels == cid].mean()
        
        return best_labels, centroid_dict, best_n
    
    # Create 2x4 grid
    fig, axes = plt.subplots(2, 4, figsize=(24, 10))
    fig.suptitle(f'{voi_name} - GMM vs 1D K-means Cluster Comparison (N={n_samples})', 
                 fontsize=16, weight='bold', y=0.995)
    
    method_names = ['Gaussian Mixture Model (GMM)', '1D K-means (Silhouette)']
    clustering_funcs = [gmm_clustering, kmeans_1d_clustering]
    
    for row, (method_name, cluster_func) in enumerate(zip(method_names, clustering_funcs)):
        for col, (metric_col, metric_label, ylim) in enumerate(metrics):
            ax = axes[row, col]
            
            if metric_col not in voi_df.columns:
                ax.text(0.5, 0.5, f'{metric_col}\nnot available', transform=ax.transAxes,
                       ha='center', va='center', fontsize=12)
                ax.set_title(f'{method_name}\n{metric_label}', fontsize=10, weight='bold')
                continue
            
            valid_data = voi_df.dropna(subset=[metric_col])
            if len(valid_data) == 0:
                ax.text(0.5, 0.5, 'No data', transform=ax.transAxes,
                       ha='center', va='center', fontsize=12)
                ax.set_title(f'{method_name}\n{metric_label}', fontsize=10, weight='bold')
                continue
            
            # Apply clustering
            labels, centroid_dict, n_clusters = cluster_func(valid_data[metric_col])
            
            # Create color mapping
            unique_labels = np.unique(labels)
            n_unique = len(unique_labels)
            cmap = plt.cm.Set1 if row == 0 else plt.cm.Set2
            label_colors = {lid: cmap(i/max(1, n_unique-1)) for i, lid in enumerate(unique_labels)}
            point_colors = [label_colors[lid] for lid in labels]
            
            # Scatter plot
            ax.scatter(valid_data['index'], valid_data[metric_col],
                      c=point_colors, alpha=0.6, s=40, edgecolors='black', linewidth=0.3)
            
            # Plot centroids with matching colors
            for i, (cluster_id, centroid) in enumerate(sorted(centroid_dict.items(), key=lambda x: x[1])):
                ax.axhline(centroid, color=label_colors[cluster_id],
                          linestyle='--', linewidth=2, alpha=0.8,
                          label=f'C{i+1}: μ={centroid:.3f}')
            
            # Set axis limits
            if ylim:
                ax.set_ylim(-0.05, 1.05)
            
            # Invert y-axis for APL so 0 is at top and values increase downward
            if metric_col == 'APL':
                ax.invert_yaxis()
            
            # Labels and formatting
            ax.set_xlabel('Sample Index', fontsize=9)
            ax.set_ylabel(metric_label, fontsize=9)
            ax.set_title(f'{method_name}\n{metric_label} ({n_clusters} clusters)',
                        fontsize=10, weight='bold')
            ax.grid(True, alpha=0.3)
            if len(centroid_dict) > 0:
                ax.legend(fontsize=7, loc='best')
    
    plt.tight_layout()
    plt.savefig(output_path / 'gmm_kmeans_clustering.png', dpi=150, bbox_inches='tight')
    plt.close()


def main():
    """Main execution function."""
    print("="*80)
    print("Contour Comparison Results Explorer")
    print("="*80)
    
    # Load results
    # results_file = 'contour_comparison_results_P0728_v3.xlsx'
    # df = load_results(results_file)
    
    # Show VOI prevalence
    # show_voi_prevalence(df)
    
    # Plot status distribution
    # plot_status_distribution(df)
    
    # Calculate VOI averages
    # voi_averages = calculate_voi_averages(df)
    
    # Print summary statistics
    # print_summary_statistics(df, voi_averages)
    
    # Create bar plot visualizations
    # print("\n" + "="*80)
    # print("Creating bar plot visualizations...")
    # print("="*80)
    # plot_voi_metrics(voi_averages)
    
    # Create boxplot visualizations
    # print("\n" + "="*80)
    # print("Creating boxplot visualizations...")
    # print("="*80)
    # plot_voi_boxplots(df)
    
    # Create VOI pie charts from investigate_output.xlsx
    # print("\n" + "="*80)
    # print("Creating VOI pie charts...")
    # print("="*80)
    # create_voi_pie_charts('investigate_output.xlsx', 'explore_results')
    
    # Create VOI scatterplots from v5 results
    print("\n" + "="*80)
    print("Creating VOI scatterplots...")
    print("="*80)
    try:
        create_voi_scatterplots('contour_comparison_results_P0728_v5.xlsx', 'explore_results')
    except Exception as e:
        print(f"Error occurred: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*80)
    print("Analysis complete!")
    print("="*80)


if __name__ == '__main__':
    main()
