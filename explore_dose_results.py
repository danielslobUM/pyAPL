"""
explore_dose_results.py — Summarise and visualise dose statistics from the
Dose_Per_Contour tab of the v3 dataset.

For each OAR (VOIName) this script produces:
  - A summary table of average AI_Dmean, Clin_Dmean, AI_Dmax, Clin_Dmax and n
  - Boxplots of Delta_Dmean (AI − Clinical mean dose) per OAR
  - Boxplots of Delta_Dmax  (AI − Clinical near-max dose) per OAR

Usage
-----
    python explore_dose_results.py
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path


# ============================================================================
# CONFIGURATION
# ============================================================================

SCRIPT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
INPUT_FILE = str(
    SCRIPT_DIR.parent
    / 'contour_comparison_results_P0728_v6_with_dist_dose_zorglijn_v3.xlsx'
)
SHEET_NAME = 'Dose_Per_Contour'
MIN_N = 2                   # Minimum samples to include an OAR in boxplots

# Anatomical region groupings — mirrored from explore_results.py
REGIONS = {
    'Head_Neck': [
        'BrachialPlex_L', 'BrachialPlex_R', 'BrainStem', 'Cerebellum',
        'Chiasm', 'Cochlea_L', 'Cochlea_R', 'Cornea_L', 'Cornea_R', 'Eye_L', 'Eye_R',
        'Hippocampus_L', 'Hippocampus_R', 'LacrimalGland_L', 'LacrimalGland_R',
        'Larynx', 'Lens_L', 'Lens_R', 'Mandible', 'OpticNerve_L', 'OpticNerve_R',
        'OralCavity_Ext', 'Parotid_L', 'Parotid_R', 'PharynxConst', 'Pituitary',
        'Retina_L', 'Retina_R', 'Submandibular_L', 'Submandibular_R', 'Thyroid',
    ],
    'Abdomen': [
        'Bowel', 'Bowel_Bag', 'Bowel_Bag_Full', 'Bowel_Full', 'CaudaEquina',
        'Duodenum', 'Kidney_L', 'Kidney_R', 'Liver', 'Pancreas', 'Spleen',
        'Stomach',
    ],
    'Pelvis': [
        'AnalCanal', 'Bladder', 'Bone_Pelvic', 'Bowel_Sigmoid', 'Femur_Head_L',
        'Femur_Head_R', 'Mesorectum', 'PenileBulb', 'Rectum', 'SeminalVes',
        'Uterus+Cervix', 'Vagina', 'Vasc_Pelvis',
    ],
    'Thorax': [
        'A_Aorta', 'Breast_L', 'Breast_R', 'Bronchus_Prox', 'Carina', 'Esophagus',
        'GreatVes', 'Heart', 'Humerus_L', 'Humerus_R', 'Lung_L', 'Lung_R',
        'Sternum', 'ThoracicWall_L', 'ThoracicWall_R', 'Trachea',
    ],
    'CNS': [
        'SpinalCanal', 'SpinalCord',
    ],
}


# ============================================================================
# DATA LOADING
# ============================================================================

def load_dose_data(input_file: str, sheet_name: str) -> pd.DataFrame:
    """Load and validate the Dose_Per_Contour sheet."""
    path = Path(input_file)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    df = pd.read_excel(input_file, sheet_name=sheet_name, engine='openpyxl')
    print(f"Loaded {len(df)} rows from '{sheet_name}' in {path.name}")

    # Keep only successfully processed rows
    df = df[df['DoseStatus'] == 'OK'].copy()
    print(f"{len(df)} rows with DoseStatus == 'OK' retained")

    # Ensure numeric types
    for col in ['AI_Dmean', 'AI_Dmax', 'Clin_Dmean', 'Clin_Dmax',
                'Delta_Dmean', 'Delta_Dmax']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    return df


# ============================================================================
# SUMMARY TABLE
# ============================================================================

def calculate_oar_averages(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute per-OAR mean ± std for dose columns and sample count.

    Returns a DataFrame sorted alphabetically by VOIName.
    """
    agg = df.groupby('VOIName').agg(
        N=('AI_Dmean', 'count'),
        AI_Dmean_mean=('AI_Dmean', 'mean'),
        AI_Dmean_std=('AI_Dmean', 'std'),
        Clin_Dmean_mean=('Clin_Dmean', 'mean'),
        Clin_Dmean_std=('Clin_Dmean', 'std'),
        AI_Dmax_mean=('AI_Dmax', 'mean'),
        AI_Dmax_std=('AI_Dmax', 'std'),
        Clin_Dmax_mean=('Clin_Dmax', 'mean'),
        Clin_Dmax_std=('Clin_Dmax', 'std'),
        Delta_Dmean_mean=('Delta_Dmean', 'mean'),
        Delta_Dmax_mean=('Delta_Dmax', 'mean'),
    ).reset_index().sort_values('VOIName')

    return agg


def print_summary_table(agg: pd.DataFrame) -> None:
    """Print the per-OAR averages to the console."""
    print(f"\n{'='*100}")
    print("DOSE SUMMARY PER OAR  (mean ± std, Gy)")
    print(f"{'='*100}")
    header = (
        f"{'VOIName':<30} {'N':>4}  "
        f"{'AI_Dmean':>10}  {'Clin_Dmean':>10}  "
        f"{'AI_Dmax':>10}  {'Clin_Dmax':>10}  "
        f"{'Δ Dmean':>9}  {'Δ Dmax':>9}"
    )
    print(header)
    print('-' * 100)
    for _, row in agg.iterrows():
        std_dm_ai   = f"±{row['AI_Dmean_std']:.2f}"   if not np.isnan(row['AI_Dmean_std'])   else ''
        std_dm_clin = f"±{row['Clin_Dmean_std']:.2f}" if not np.isnan(row['Clin_Dmean_std']) else ''
        std_dx_ai   = f"±{row['AI_Dmax_std']:.2f}"    if not np.isnan(row['AI_Dmax_std'])    else ''
        std_dx_clin = f"±{row['Clin_Dmax_std']:.2f}"  if not np.isnan(row['Clin_Dmax_std'])  else ''
        print(
            f"{row['VOIName']:<30} {int(row['N']):>4}  "
            f"{row['AI_Dmean_mean']:>6.2f}{std_dm_ai:<6}  "
            f"{row['Clin_Dmean_mean']:>6.2f}{std_dm_clin:<6}  "
            f"{row['AI_Dmax_mean']:>6.2f}{std_dx_ai:<6}  "
            f"{row['Clin_Dmax_mean']:>6.2f}{std_dx_clin:<6}  "
            f"{row['Delta_Dmean_mean']:>+9.3f}  "
            f"{row['Delta_Dmax_mean']:>+9.3f}"
        )
    print(f"{'='*100}\n")


# ============================================================================
# BOXPLOTS
# ============================================================================

def _assign_region(oar_name: str) -> str:
    """Return the anatomical region for an OAR, or 'Other' if not listed."""
    for region, oars in REGIONS.items():
        if oar_name in oars:
            return region
    return 'Other'


def _make_boxplots(df: pd.DataFrame, delta_col: str, ylabel: str,
                   title_prefix: str, output_prefix: str,
                   min_n: int) -> None:
    """
    Produce one boxplot figure per anatomical region for delta_col.
    OARs not listed in REGIONS are collected into an 'Other' figure.
    """
    counts = df.groupby('VOIName')[delta_col].count()
    valid_oars = counts[counts >= min_n].index.tolist()

    if not valid_oars:
        print(f"No OARs with ≥{min_n} samples for {delta_col} — skipping.")
        return

    # Group OARs by region, preserving REGIONS order then Other
    region_oars: dict = {r: [] for r in list(REGIONS.keys()) + ['Other']}
    for oar in valid_oars:
        region_oars[_assign_region(oar)].append(oar)

    for region_name, oar_list in region_oars.items():
        if not oar_list:
            continue
        oar_list = sorted(oar_list)
        print(f"  {region_name}: {len(oar_list)} OARs")

        data = [df.loc[df['VOIName'] == oar, delta_col].dropna().values
                for oar in oar_list]
        labels = [f"{oar}\n(n={len(d)})" for oar, d in zip(oar_list, data)]

        fig, ax = plt.subplots(figsize=(max(12, len(oar_list) * 0.9), 7))

        bp = ax.boxplot(
            data,
            patch_artist=True,
            medianprops=dict(color='black', linewidth=2),
            flierprops=dict(marker='o', markersize=4, alpha=0.5),
            widths=0.6,
        )

        # Colour boxes: blue if median ≥ 0, red if < 0
        for patch, d in zip(bp['boxes'], data):
            median = np.median(d) if len(d) > 0 else 0
            patch.set_facecolor('#3498db' if median >= 0 else '#e74c3c')
            patch.set_alpha(0.7)

        ax.axhline(0, color='black', linestyle='--', linewidth=1, alpha=0.6)
        ax.set_xticks(range(1, len(oar_list) + 1))
        ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=9)
        ax.set_ylabel(ylabel, fontsize=12, fontweight='bold')
        ax.set_xlabel('OAR', fontsize=12, fontweight='bold')
        ax.set_title(
            f'{title_prefix} — {region_name}\n'
            f'(AI − Clinical, Gy; blue = AI higher, red = AI lower)',
            fontsize=13, fontweight='bold', pad=14
        )
        ax.grid(axis='y', alpha=0.3, linestyle='--')

        plt.tight_layout()
        out_path = str(SCRIPT_DIR / f"{output_prefix}_{region_name}.png")
        plt.savefig(out_path, dpi=150, bbox_inches='tight')
        print(f"    Saved: {out_path}")
        plt.show()


def plot_delta_boxplots(df: pd.DataFrame, min_n: int = MIN_N) -> None:
    """Create Delta_Dmean and Delta_Dmax boxplots per anatomical region."""
    print("\nGenerating Delta_Dmean boxplots …")
    _make_boxplots(
        df,
        delta_col='Delta_Dmean',
        ylabel='ΔDmean  (Gy)',
        title_prefix='Delta Mean Dose per OAR  (AI − Clinical)',
        output_prefix='dose_delta_dmean_boxplots',
        min_n=min_n,
    )

    print("Generating Delta_Dmax boxplots …")
    _make_boxplots(
        df,
        delta_col='Delta_Dmax',
        ylabel='ΔDmax / D0.03cc  (Gy)',
        title_prefix='Delta Near-Max Dose (D0.03cc) per OAR  (AI − Clinical)',
        output_prefix='dose_delta_dmax_boxplots',
        min_n=min_n,
    )


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    print('=' * 70)
    print('Dose Results Explorer')
    print('=' * 70)
    print(f'Input file : {INPUT_FILE}')
    print(f'Sheet      : {SHEET_NAME}')
    print('=' * 70)

    df = load_dose_data(INPUT_FILE, SHEET_NAME)
    agg = calculate_oar_averages(df)
    print_summary_table(agg)
    plot_delta_boxplots(df)
