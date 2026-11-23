"""
Stratify the v7 results on tumour location (RTPLAN_DoseReferenceDescription).

The description starts with a plan/beam reference (e.g. "P1B1", "p2b1", "P1b1_")
that is not related to the tumour location; this prefix is stripped. The
remaining text is the tumour location, which is matched against a keyword
(default: 'mam', catching 'mamma', 'Mamma', 'MamLi', 'mamila', 'rug/mam pal').

Output: an Excel file listing every matching location variation with its row
count, overall and per OAR (VOIName).
"""

import re
from pathlib import Path

import pandas as pd

from explore_results import _create_dose_delta_region_boxplot

DESCRIPTION_COL = 'RTPLAN_DoseReferenceDescription'

# Leading plan/beam reference: p<digits>b<digits>, any case, optional separators
PLAN_BEAM_PREFIX = re.compile(r'^\s*p\d*\s*b\d*[\s_\-]*', flags=re.IGNORECASE)


def extract_tumour_location(description):
    """Return the description without its leading p*b* reference."""
    if pd.isna(description):
        return None
    location = PLAN_BEAM_PREFIX.sub('', str(description)).strip()
    return location or None


def select_location(df, keyword='mam'):
    """Return the rows whose tumour location contains `keyword` (case-insensitive)."""
    df = df.copy()
    df['TumourLocation'] = df[DESCRIPTION_COL].map(extract_tumour_location)
    mask = df['TumourLocation'].str.contains(keyword, case=False, na=False)
    return df[mask]


def summarize_location_variations(df_loc):
    """Count rows (and dose-delta rows) per location variation, overall and per OAR."""
    # Skipped patients appear as a single row without VOIName; nothing to count per OAR
    df_loc = df_loc[df_loc['VOIName'].notna()]
    has_dose = df_loc['Delta_Dmean'].notna() | df_loc['Delta_Dmax'].notna()
    df_loc = df_loc.assign(HasDoseDelta=has_dose)

    variations = (
        df_loc.groupby('TumourLocation')
        .agg(N_rows=('VOIName', 'size'),
             N_rows_with_dose_delta=('HasDoseDelta', 'sum'),
             N_patients=('pNumber', 'nunique'),
             N_OARs=('VOIName', 'nunique'))
        .sort_values('N_rows', ascending=False)
        .reset_index()
    )

    per_oar = (
        df_loc.groupby(['VOIName', 'TumourLocation'])
        .agg(N_rows=('VOIName', 'size'),
             N_rows_with_dose_delta=('HasDoseDelta', 'sum'))
        .reset_index()
        .sort_values(['VOIName', 'N_rows'], ascending=[True, False])
    )

    oar_totals = (
        df_loc.groupby('VOIName')
        .agg(N_rows=('VOIName', 'size'),
             N_rows_with_dose_delta=('HasDoseDelta', 'sum'),
             N_patients=('pNumber', 'nunique'),
             N_variations=('TumourLocation', 'nunique'))
        .sort_values('N_rows', ascending=False)
        .reset_index()
    )

    pivot = pd.crosstab(df_loc['VOIName'], df_loc['TumourLocation'])
    pivot = pivot.loc[oar_totals['VOIName'], variations['TumourLocation']]
    pivot.insert(0, 'Total', pivot.sum(axis=1))

    return variations, per_oar, oar_totals, pivot


def plot_location_dose_delta(df_loc, location_name, output_dir, min_rows=20):
    """
    Dose delta boxplot (5th-95th whiskers) for one tumour location, styled like
    DoseDelta_<Region>_p5_95. Same OAR filters as the region plots: N > min_rows
    rows, then DOSE_DELTA_MIN_N valid deltas (applied inside the plot function).
    """
    oar_counts = df_loc['VOIName'].value_counts()
    oars_with_data = sorted(oar_counts[oar_counts > min_rows].index)
    df_plot = df_loc[df_loc['VOIName'].isin(oars_with_data)]
    _create_dose_delta_region_boxplot(
        df_plot, location_name, oars_with_data, output_dir,
        whis=(5, 95), showfliers=True, suffix='_p5_95', outer_whiskers=True
    )


def main(keyword='mam', location_name='Mamma'):
    script_dir = Path(__file__).parent
    results_file = script_dir.parent / 'contour_comparison_results_P0728_v7.xlsx'
    output_dir = script_dir.parent / 'explore_results' / 'Tumour_location' / keyword
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_excel(results_file)
    df_loc = select_location(df, keyword)
    variations, per_oar, oar_totals, pivot = summarize_location_variations(df_loc)

    output_file = output_dir / f'{keyword}_location_variations.xlsx'
    with pd.ExcelWriter(output_file) as writer:
        variations.to_excel(writer, sheet_name='Variations', index=False)
        oar_totals.to_excel(writer, sheet_name='OAR_totals', index=False)
        per_oar.to_excel(writer, sheet_name='Per_OAR', index=False)
        pivot.to_excel(writer, sheet_name='OAR_x_Variation')

    print(f"Rows matching '{keyword}': {len(df_loc)} of {len(df)} "
          f"({df_loc['pNumber'].nunique()} patients, {len(variations)} variations, "
          f"{len(oar_totals)} OARs)")
    print(f"Saved: {output_file}")

    # Also save next to the region plots (e.g. DoseDelta_Thorax_p5_95.png)
    region_output_dir = script_dir.parent / 'explore_results' / 'explore results per region'
    region_output_dir.mkdir(parents=True, exist_ok=True)
    for plot_dir in (output_dir, region_output_dir):
        plot_location_dose_delta(df_loc, location_name, plot_dir)
    return df_loc


def export_location_subset(sites=None):
    """
    Save all v7 rows/columns for the given tumour sites in one file, with a
    'TumourSite' column (site label) inserted right after pNumber.

    sites : dict mapping site label -> location keyword
    """
    if sites is None:
        sites = {'lung': 'long', 'mam': 'mam'}
    project_dir = Path(__file__).parent.parent
    results_file = project_dir / 'contour_comparison_results_P0728_v7.xlsx'
    df = pd.read_excel(results_file)

    location = df[DESCRIPTION_COL].map(extract_tumour_location)
    site = pd.Series(pd.NA, index=df.index, dtype='object')
    for label, keyword in sites.items():
        mask = location.str.contains(keyword, case=False, na=False)
        overlap = mask & site.notna()
        if overlap.any():
            raise ValueError(f"{overlap.sum()} rows match more than one site: "
                             f"{sorted(location[overlap].unique())}")
        site[mask] = label

    df_sites = df[site.notna()].copy()
    df_sites.insert(df_sites.columns.get_loc('pNumber') + 1, 'TumourSite', site[site.notna()])

    output_file = project_dir / f"contour_comparison_results_P0728_v7_{'_'.join(sites)}.xlsx"
    df_sites.to_excel(output_file, index=False)
    print(f"Saved {len(df_sites)} rows: {df_sites['TumourSite'].value_counts().to_dict()} -> {output_file}")


def plot_lung_fractionation_scatterplots(schemes=(20, 30), metric='Delta_Dmax', oars=None):
    """
    Plain distance-vs-|dose delta| scatterplots (as Delta_Dmax_distance_scatterplot_plain)
    for non-SBRT lung patients, one plot per OAR and fraction scheme.
    Defaults to the OARs of the non-SBRT lung constraint table.
    """
    from distance_dose_threshold_analysis import create_plain_scatterplot, prepare_metric_data

    if oars is None:
        oars = ['BrachialPlex_L', 'BrachialPlex_R', 'Esophagus', 'Heart',
                'Lung_L', 'Lung_R', 'SpinalCanal']
    project_dir = Path(__file__).parent.parent
    df = pd.read_excel(project_dir / 'contour_comparison_results_P0728_v7.xlsx')
    df_lung = select_location(df, 'long')
    df_lung = df_lung[~df_lung['TumourLocation'].str.contains('sbrt', case=False)]

    output_root = project_dir / 'explore_results' / 'Tumour_location' / 'long' / 'non_SBRT'
    counts = []
    for n_fractions in schemes:
        df_scheme = df_lung[df_lung['RTPLAN_NumberOfFractions'] == n_fractions]
        output_dir = output_root / f'{n_fractions}fx'
        output_dir.mkdir(parents=True, exist_ok=True)
        for oar in oars:
            metric_df = prepare_metric_data(df_scheme[df_scheme['VOIName'] == oar], metric)
            counts.append({'Fractions': n_fractions, 'VOIName': oar, 'N_plotted': len(metric_df),
                           'N_patients': df_scheme.loc[df_scheme['VOIName'] == oar, 'pNumber'].nunique()})
            if metric_df.empty:
                continue
            create_plain_scatterplot(
                metric_df, metric,
                output_dir / f'{oar}_{metric}_distance_scatterplot_plain.png',
                f'{oar} (lung non-SBRT, {n_fractions}#)',
                scatter_kwargs=dict(s=45, color='#d62728', alpha=0.85,
                                    edgecolors='black', linewidths=0.6),
            )

    counts_df = pd.DataFrame(counts)
    counts_df.to_excel(output_root / f'{metric}_scatterplot_counts.xlsx', index=False)
    print(counts_df.pivot(index='VOIName', columns='Fractions', values='N_plotted').to_string())
    print(f"Saved to: {output_root}")


# Non-SBRT lung constraint table (physical dose, Gy), per number of fractions.
# Dmax is used as proxy for D0.03cc. The table refers to expanded structures
# (BrachialPlex_5, Esophagus_5, SpinalCanal_3); v7 only has the unexpanded ones.
# Dmean limits (MHD < 10 Gy, MLD < 20 Gy) are applied per structure as written.
# None = no numeric constraint (ALARA): every point counts as met.
LUNG_CONSTRAINTS_GY = {
    'Delta_Dmax': {
        'BrachialPlex_L': {20: 60.5, 30: 70.1},
        'BrachialPlex_R': {20: 60.5, 30: 70.1},
        'Esophagus': {20: 62.2, 30: 70.9},
        'Heart': {20: 62.2, 30: 70.9},
        'SpinalCanal': {20: 48.7, 30: 54.0},
    },
    'Delta_Dmean': {
        'Esophagus': {20: None, 30: None},
        'Heart': {20: 10.0, 30: 10.0},
        'Lung_L': {20: 20.0, 30: 20.0},
        'Lung_R': {20: 20.0, 30: 20.0},
    },
}


def plot_lung_constraint_scatterplots(schemes=(20, 30)):
    """
    Distance-vs-|dose delta| scatterplots for non-SBRT lung patients, coloured by
    whether the AI-contour DVH parameter violates the constraint (red) or not (green).
    """
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from distance_dose_threshold_analysis import DISTANCE_COLUMN, prepare_metric_data

    project_dir = Path(__file__).parent.parent
    df = pd.read_excel(project_dir / 'contour_comparison_results_P0728_v7.xlsx')
    df_lung = select_location(df, 'long')
    df_lung = df_lung[~df_lung['TumourLocation'].str.contains('sbrt', case=False)]
    output_root = project_dir / 'explore_results' / 'Tumour_location' / 'long' / 'non_SBRT'

    summary = []
    for metric, oar_limits in LUNG_CONSTRAINTS_GY.items():
        parameter = metric.replace('Delta_', '')
        for oar, limits in oar_limits.items():
            for n_fractions in schemes:
                limit = limits[n_fractions]
                df_oar = df_lung[(df_lung['RTPLAN_NumberOfFractions'] == n_fractions)
                                 & (df_lung['VOIName'] == oar)]
                metric_df = prepare_metric_data(df_oar, metric)
                if metric_df.empty:
                    continue
                ai_values = df_oar.loc[metric_df.index, f'AI_{parameter}']
                clin_values = df_oar.loc[metric_df.index, f'Clin_{parameter}']
                check_limit = float('inf') if limit is None else limit
                ai_violates = ai_values >= check_limit
                n_ai, n_clin = int(ai_violates.sum()), int((clin_values >= check_limit).sum())
                n_total = len(metric_df)
                summary.append({
                    'Fractions': n_fractions, 'VOIName': oar, 'Parameter': parameter,
                    'Constraint_Gy': limit, 'N': n_total,
                    'N_AI_violations': n_ai, 'N_Clin_violations': n_clin,
                    'N_AI_only_violations': int((ai_violates & (clin_values < check_limit)).sum()),
                    'AI_max_Gy': ai_values.max(),
                })

                fig, ax = plt.subplots(figsize=(12, 9))
                for violates, color in ((False, '#2ca02c'), (True, '#d62728')):
                    points = metric_df[ai_violates == violates]
                    ax.scatter(points[DISTANCE_COLUMN], points[f'Absolute_{metric}'],
                               s=45, color=color, alpha=0.85, edgecolors='black', linewidths=0.6)
                y_max = metric_df[f'Absolute_{metric}'].max()
                ax.set_ylim(bottom=-max(y_max * 0.03, 0.1))
                constraint_text = (
                    f'Constraint {parameter}: ALARA (no threshold)' if limit is None else
                    f'Constraint AI {parameter} < {limit:g} Gy: '
                    f'AI violations {n_ai}/{n_total} (clinical: {n_clin}/{n_total})'
                )
                ax.set_title(
                    f'{oar} (lung non-SBRT, {n_fractions}#): OAR-to-PTV Distance vs Absolute {metric} '
                    f'(N={n_total})\n{constraint_text}'
                )
                ax.set_xlabel('Distance from OAR to PTV (cm)')
                ax.set_ylabel(f'Absolute {metric}')
                ax.grid(alpha=0.2)
                legend_items = (
                    (('#2ca02c', 'No constraint (ALARA)'),) if limit is None else
                    (('#d62728', f'AI {parameter} ≥ {limit:g} Gy (violated)'),
                     ('#2ca02c', f'AI {parameter} < {limit:g} Gy (met)'))
                )
                ax.legend(handles=[
                    Line2D([0], [0], marker='o', linestyle='', markersize=8, markerfacecolor=color,
                           markeredgecolor='black', label=label)
                    for color, label in legend_items
                ], loc='upper right')
                fig.tight_layout()
                fig.savefig(output_root / f'{n_fractions}fx'
                            / f'{oar}_{metric}_distance_scatterplot_constraint.png', dpi=300)
                plt.close(fig)

    summary_df = pd.DataFrame(summary)
    summary_df.to_excel(output_root / 'AI_constraint_violations.xlsx', index=False)
    print(summary_df.to_string(index=False))
    print(f"Saved to: {output_root}")


SPINAL_MARKERS = {'SpinalCanal': 'o', 'SpinalCord': '^'}
SPINAL_COLORS = {'SpinalCanal': '#1f77b4', 'SpinalCord': '#ff7f0e'}


def plot_lung_spinal_combined_scatterplots(schemes=(20, 30)):
    """
    SpinalCord and SpinalCanal together in one distance-vs-|dose delta| scatterplot
    per fraction scheme (non-SBRT lung), marker shape = structure.
    Delta_Dmax: coloured by the SpinalCanal constraint (applied to both structures).
    Delta_Dmean: no constraint, coloured by structure.
    """
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from distance_dose_threshold_analysis import DISTANCE_COLUMN, prepare_metric_data

    project_dir = Path(__file__).parent.parent
    df = pd.read_excel(project_dir / 'contour_comparison_results_P0728_v7.xlsx')
    df_lung = select_location(df, 'long')
    df_lung = df_lung[~df_lung['TumourLocation'].str.contains('sbrt', case=False)]
    output_root = project_dir / 'explore_results' / 'Tumour_location' / 'long' / 'non_SBRT'

    counts = []
    for metric in ('Delta_Dmax', 'Delta_Dmean'):
        parameter = metric.replace('Delta_', '')
        for n_fractions in schemes:
            limit = LUNG_CONSTRAINTS_GY[metric].get('SpinalCanal', {}).get(n_fractions)
            df_scheme = df_lung[df_lung['RTPLAN_NumberOfFractions'] == n_fractions]

            fig, ax = plt.subplots(figsize=(12, 9))
            n_per_oar, y_max = {}, 0.0
            n_ai = n_total = 0
            for oar, marker in SPINAL_MARKERS.items():
                df_oar = df_scheme[df_scheme['VOIName'] == oar]
                metric_df = prepare_metric_data(df_oar, metric)
                n_per_oar[oar] = len(metric_df)
                counts.append({'Metric': metric, 'Fractions': n_fractions, 'VOIName': oar,
                               'N_plotted': len(metric_df), 'N_patients': df_oar['pNumber'].nunique()})
                if metric_df.empty:
                    continue
                y_max = max(y_max, metric_df[f'Absolute_{metric}'].max())
                if limit is None:
                    colors = SPINAL_COLORS[oar]
                else:
                    ai_violates = df_oar.loc[metric_df.index, f'AI_{parameter}'] >= limit
                    colors = ai_violates.map({True: '#d62728', False: '#2ca02c'})
                    n_ai += int(ai_violates.sum())
                n_total += len(metric_df)
                ax.scatter(metric_df[DISTANCE_COLUMN], metric_df[f'Absolute_{metric}'], marker=marker,
                           s=55, c=colors, alpha=0.85, edgecolors='black', linewidths=0.6)
            if n_total == 0:
                plt.close(fig)
                continue

            ax.set_ylim(bottom=-max(y_max * 0.03, 0.1))
            n_text = ', '.join(f'{oar} N={n}' for oar, n in n_per_oar.items())
            constraint_text = (
                f'Constraint {parameter}: none' if limit is None else
                f'Constraint AI {parameter} < {limit:g} Gy (SpinalCanal limit, applied to both): '
                f'AI violations {n_ai}/{n_total}'
            )
            ax.set_title(f'SpinalCord + SpinalCanal (lung non-SBRT, {n_fractions}#): '
                         f'OAR-to-PTV Distance vs Absolute {metric}\n{n_text}\n{constraint_text}')
            ax.set_xlabel('Distance from OAR to PTV (cm)')
            ax.set_ylabel(f'Absolute {metric}')
            ax.grid(alpha=0.2)
            legend_items = [
                Line2D([0], [0], marker=marker, linestyle='', markersize=8,
                       markerfacecolor=SPINAL_COLORS[oar] if limit is None else 'white',
                       markeredgecolor='black', label=oar)
                for oar, marker in SPINAL_MARKERS.items()
            ]
            if limit is not None:
                legend_items += [
                    Line2D([0], [0], marker='s', linestyle='', markersize=8, markerfacecolor=color,
                           markeredgecolor='black', label=label)
                    for color, label in (('#d62728', f'AI {parameter} ≥ {limit:g} Gy (violated)'),
                                         ('#2ca02c', f'AI {parameter} < {limit:g} Gy (met)'))
                ]
            ax.legend(handles=legend_items, loc='upper right')
            fig.tight_layout()
            fig.savefig(output_root / f'{n_fractions}fx'
                        / f'SpinalCord_SpinalCanal_{metric}_distance_scatterplot_combined.png', dpi=300)
            plt.close(fig)

    counts_df = pd.DataFrame(counts)
    print(counts_df.to_string(index=False))
    print(f"Saved to: {output_root}")


if __name__ == '__main__':
    main(keyword='mam', location_name='Mamma')
    main(keyword='long', location_name='Long')
    export_location_subset()
    plot_lung_fractionation_scatterplots(metric='Delta_Dmax')
    plot_lung_fractionation_scatterplots(metric='Delta_Dmean')
    plot_lung_spinal_combined_scatterplots()
    main(keyword='mam', location_name='Mamma')
    main(keyword='long', location_name='Long')
