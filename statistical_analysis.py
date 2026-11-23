"""
Statistical Analysis for AI vs Clinical Contour Comparison

This script performs statistical analyses for the research paper comparing
AI-generated and clinical contours. All analyses use the v7 Excel file
as the primary data source.

Main analyses:
0. Overall Dataset Summary:
   - Patient count, total rows, unique OARs
   - OAR-specific counts (filtered for N > 19) with regional classification
   - Mean ± SD for all geometric metrics (SDSC, APL, Dice at multiple tolerances)
   - Mean ± SD for all dosimetric metrics (AI/Clinical Dmean, Dmax, deltas)

1. Overall Wilcoxon signed-rank tests comparing paired doses:
   - AI_Dmean vs Clinical_Dmean
   - AI_Dmax vs Clinical_Dmax

2. Per-OAR Wilcoxon signed-rank tests:
   - Separate analysis for each organ at risk (OAR)
   - Minimum sample size: n ≥ 20 per OAR
   - Tests: AI_Dmean vs Clin_Dmean AND AI_Dmax vs Clin_Dmax per OAR
   - Identifies which structures show systematic differences
   - Results include anatomical region classification (Head_Neck, Neuro_Cranial, Thorax, Abdomen, Pelvis, CNS)

3. Per-OAR Correlation Analysis:
   - Calculates Pearson and Spearman correlations between distance to PTV and:
     * SDSC_tol05, SDSC_tol3 (Surface Distance Standard Coefficient)
     * APL_tol05, APL_tol3 (Average Path Length)
     * Dice (Volume Dice Similarity Coefficient)
     * Delta_Dmean, Delta_Dmax (dose differences)
   - Reports correlation coefficients, p-values, and significance indicators

4. Excel output with multiple sheets:
   - Dataset summary (patient count, rows, OAR counts N>19, mean geometric & dosimetric metrics)
   - Overall Wilcoxon tests (overall test results + regional summary statistics)
   - Per-OAR results for Dmean (AI vs Clinical) with Region column
   - Per-OAR results for Dmax (AI vs Clinical) with Region column
   - Distance correlations (distance to PTV vs geometric/dose metrics)

Regional summary shows:
   - Number of OARs analyzed per region
   - Number and percentage of significant OARs per region
   - Separate statistics for Dmean and Dmax

Statistical test explanation:
- Wilcoxon signed-rank test: non-parametric paired test
- Tests if AI doses differ significantly from Clinical doses
- W statistic: sum of positive ranks (scipy convention)
- Effect size (r): standardized measure of effect magnitude
- Pearson correlation: measures linear relationship
- Spearman correlation: measures monotonic relationship (non-parametric)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats
from scipy.stats import wilcoxon
from typing import Tuple, Dict, Optional
import warnings
from datetime import datetime


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


def get_oar_region(oar_name: str) -> str:
    """
    Map an OAR name to its anatomical region.
    
    Parameters
    ----------
    oar_name : str
        Name of the organ at risk
        
    Returns
    -------
    str
        Region name ('Head_Neck', 'Neuro_Cranial', 'Abdomen', 'Pelvis', 'Thorax', 'CNS', or 'Other')
    """
    for region, oars in REGIONS.items():
        if oar_name in oars:
            return region
    return 'Other'


def load_data(results_file: str = 'contour_comparison_results_P0728_v7.xlsx') -> pd.DataFrame:
    """
    Load the primary results file for statistical analysis.
    
    Parameters
    ----------
    results_file : str
        Path to the v7 Excel file containing all analysis results
        
    Returns
    -------
    pd.DataFrame
        Loaded data with all columns
        
    Raises
    ------
    FileNotFoundError
        If the results file does not exist
    """
    file_path = Path(results_file)
    
    if not file_path.exists():
        raise FileNotFoundError(
            f"Results file not found: {results_file}\n"
            f"Please ensure the v7 Excel file is in the current directory."
        )
    
    df = pd.read_excel(file_path)
    print(f"Loaded {len(df)} rows from {results_file}")
    print(f"Columns available: {len(df.columns)}")
    print(f"Column names: {', '.join(df.columns)}\n")
    
    return df


def _legacy_wilcoxon_signed_rank_test(
    data1: np.ndarray,
    data2: np.ndarray,
    alternative: str = 'two-sided',
    name1: str = 'Group 1',
    name2: str = 'Group 2'
) -> Dict:
    """
    Perform Wilcoxon signed-rank test for paired samples.
    
    The Wilcoxon signed-rank test is a non-parametric test that evaluates
    whether the median difference between paired observations is significantly
    different from zero. It is appropriate when:
    - Data are paired (e.g., same structure from same patient)
    - Distribution may not be normal
    - Testing for systematic differences
    
    Test procedure:
    1. Calculate differences: d = data1 - data2
    2. Remove zero differences
    3. Rank absolute differences (smallest |d| = rank 1)
    4. Apply original signs to ranks (positive or negative)
    5. Calculate W+ (sum of positive ranks) and W- (sum of negative ranks)
    6. Test statistic W is typically the smaller of W+ and W- (scipy reports W+)
    7. Compare to null distribution to get p-value
    
    The W statistic:
    - W represents the sum of ranks for one direction of differences
    - Under null hypothesis (no difference), W+ ≈ W-
    - Larger deviations from expected value indicate stronger evidence
    - With scipy: larger W+ = more positive differences dominate
    
    Parameters
    ----------
    data1 : np.ndarray
        First set of paired observations (e.g., AI values)
    data2 : np.ndarray
        Second set of paired observations (e.g., Clinical values)
    alternative : str, optional
        Alternative hypothesis: 'two-sided', 'less', or 'greater'
        Default is 'two-sided'
    name1 : str, optional
        Name for first group (for reporting)
    name2 : str, optional
        Name for second group (for reporting)
        
    Returns
    -------
    dict
        Dictionary containing:
        - statistic: Wilcoxon test statistic
        - p_value: p-value for the test
        - n_pairs: number of valid pairs
        - median_diff: median of differences
        - mean_diff: mean of differences
        - std_diff: standard deviation of differences
        - effect_size: effect size (r = Z / sqrt(N))
        - differences: array of differences
    """
    # Ensure arrays
    data1 = np.asarray(data1)
    data2 = np.asarray(data2)
    
    # Check for equal length
    if len(data1) != len(data2):
        raise ValueError(
            f"Arrays must have same length. Got {len(data1)} and {len(data2)}"
        )
    
    # Remove pairs where either value is NaN
    mask = ~(np.isnan(data1) | np.isnan(data2))
    data1_clean = data1[mask]
    data2_clean = data2[mask]
    
    # Calculate differences
    differences = data1_clean - data2_clean
    
    # Remove zero differences for the test
    n_pairs = len(differences)
    n_zeros = np.sum(differences == 0)
    
    if n_pairs < 10:
        warnings.warn(
            f"Small sample size (n={n_pairs}). Results may not be reliable."
        )
    
    # Perform Wilcoxon signed-rank test
    try:
        statistic, p_value = stats.wilcoxon(
            data1_clean, 
            data2_clean,
            alternative=alternative,
            zero_method='wilcox'  # Discard zero differences (Wilcoxon's original method)
        )
    except ValueError as e:
        print(f"Error in Wilcoxon test: {e}")
        return {
            'statistic': np.nan,
            'p_value': np.nan,
            'n_pairs': n_pairs,
            'n_zeros': n_zeros,
            'error': str(e)
        }
    
    # Calculate descriptive statistics
    median_diff = np.median(differences)
    mean_diff = np.mean(differences)
    std_diff = np.std(differences, ddof=1)
    
    # Calculate effect size (r = Z / sqrt(N))
    # Approximate Z from p-value for two-sided test
    if alternative == 'two-sided':
        z_score = stats.norm.ppf(1 - p_value / 2)
    else:
        z_score = stats.norm.ppf(1 - p_value)
    effect_size = abs(z_score) / np.sqrt(n_pairs)
    
    # Calculate 95% confidence interval for median difference (using bootstrap)
    ci_lower, ci_upper = _bootstrap_ci_median(differences)
    
    return {
        'statistic': statistic,
        'p_value': p_value,
        'n_pairs': n_pairs,
        'n_zeros': n_zeros,
        'median_diff': median_diff,
        'mean_diff': mean_diff,
        'std_diff': std_diff,
        'effect_size': effect_size,
        'ci_lower': ci_lower,
        'ci_upper': ci_upper,
        'differences': differences,
        'name1': name1,
        'name2': name2,
        'alternative': alternative
    }


def wilcoxon_signed_rank_test(
    data1: np.ndarray,
    data2: np.ndarray,
    alternative: str = 'two-sided',
    name1: str = 'Group 1',
    name2: str = 'Group 2',
    zero_method: str = 'wilcox',
    correction: bool = False,
    method: str = 'auto'
) -> Dict:
    """
    Perform a Wilcoxon signed-rank test for paired samples using SciPy.

    Following the scipy.stats.wilcoxon documentation, paired differences are
    calculated first and passed to wilcoxon as x with y=None. This avoids tiny
    floating point subtraction artifacts changing ranks for tied differences.
    """
    data1 = np.asarray(data1, dtype=float)
    data2 = np.asarray(data2, dtype=float)

    if len(data1) != len(data2):
        raise ValueError(
            f"Arrays must have same length. Got {len(data1)} and {len(data2)}"
        )

    valid_mask = ~(np.isnan(data1) | np.isnan(data2))
    data1_clean = data1[valid_mask]
    data2_clean = data2[valid_mask]
    differences = np.around(data1_clean - data2_clean, decimals=12)

    n_pairs = len(differences)
    n_zeros = int(np.sum(differences == 0))

    if n_pairs < 10:
        warnings.warn(
            f"Small sample size (n={n_pairs}). Results may not be reliable."
        )

    if n_pairs == 0:
        return {
            'statistic': np.nan,
            'p_value': np.nan,
            'n_pairs': n_pairs,
            'n_zeros': n_zeros,
            'error': 'No valid paired observations after dropping NaNs'
        }

    median_diff = np.median(differences)
    mean_diff = np.mean(differences)
    std_diff = np.std(differences, ddof=1) if n_pairs > 1 else 0.0

    if np.all(differences == 0):
        return {
            'statistic': 0.0,
            'p_value': 1.0,
            'n_pairs': n_pairs,
            'n_zeros': n_zeros,
            'median_diff': median_diff,
            'mean_diff': mean_diff,
            'std_diff': std_diff,
            'effect_size': 0.0,
            'ci_lower': 0.0,
            'ci_upper': 0.0,
            'differences': differences,
            'name1': name1,
            'name2': name2,
            'alternative': alternative,
            'zero_method': zero_method,
            'method': method
        }

    try:
        test_result = wilcoxon(
            differences,
            y=None,
            zero_method=zero_method,
            correction=correction,
            alternative=alternative,
            method=method
        )
        statistic = float(test_result.statistic)
        p_value = float(test_result.pvalue)
    except ValueError as e:
        print(f"Error in Wilcoxon test: {e}")
        return {
            'statistic': np.nan,
            'p_value': np.nan,
            'n_pairs': n_pairs,
            'n_zeros': n_zeros,
            'error': str(e)
        }

    if p_value <= 0:
        effect_size = np.inf
    elif p_value >= 1:
        effect_size = 0.0
    elif alternative == 'two-sided':
        z_score = stats.norm.ppf(1 - p_value / 2)
        effect_size = abs(z_score) / np.sqrt(n_pairs)
    else:
        z_score = stats.norm.ppf(1 - p_value)
        effect_size = abs(z_score) / np.sqrt(n_pairs)

    ci_lower, ci_upper = _bootstrap_ci_median(differences)

    return {
        'statistic': statistic,
        'p_value': p_value,
        'n_pairs': n_pairs,
        'n_zeros': n_zeros,
        'median_diff': median_diff,
        'mean_diff': mean_diff,
        'std_diff': std_diff,
        'effect_size': effect_size,
        'ci_lower': ci_lower,
        'ci_upper': ci_upper,
        'differences': differences,
        'name1': name1,
        'name2': name2,
        'alternative': alternative,
        'zero_method': zero_method,
        'method': method
    }


def _bootstrap_ci_median(data: np.ndarray, n_bootstrap: int = 10000, alpha: float = 0.05) -> Tuple[float, float]:
    """
    Calculate bootstrap confidence interval for the median.
    
    Parameters
    ----------
    data : np.ndarray
        Data array
    n_bootstrap : int
        Number of bootstrap samples
    alpha : float
        Significance level (default 0.05 for 95% CI)
        
    Returns
    -------
    tuple
        (lower_bound, upper_bound) of confidence interval
    """
    n = len(data)
    bootstrap_medians = np.zeros(n_bootstrap)
    
    rng = np.random.default_rng(42)  # Fixed seed for reproducibility
    
    for i in range(n_bootstrap):
        sample = rng.choice(data, size=n, replace=True)
        bootstrap_medians[i] = np.median(sample)
    
    ci_lower = np.percentile(bootstrap_medians, alpha / 2 * 100)
    ci_upper = np.percentile(bootstrap_medians, (1 - alpha / 2) * 100)
    
    return ci_lower, ci_upper


def calculate_correlation(
    data1: np.ndarray,
    data2: np.ndarray,
    name1: str,
    name2: str
) -> Dict:
    """
    Calculate Pearson and Spearman correlation coefficients between two variables.
    
    Pearson correlation:
    - Measures linear relationship
    - Assumes normal distribution
    - Range: -1 (perfect negative) to +1 (perfect positive)
    
    Spearman correlation:
    - Measures monotonic relationship (not necessarily linear)
    - Non-parametric (no distribution assumption)
    - More robust to outliers
    - Range: -1 (perfect negative monotonic) to +1 (perfect positive monotonic)
    
    Parameters
    ----------
    data1 : np.ndarray
        First variable (e.g., distance to PTV)
    data2 : np.ndarray
        Second variable (e.g., SDSC, APL, dose delta)
    name1 : str
        Name of first variable
    name2 : str
        Name of second variable
        
    Returns
    -------
    dict
        Dictionary containing:
        - pearson_r: Pearson correlation coefficient
        - pearson_p: p-value for Pearson test
        - spearman_r: Spearman correlation coefficient
        - spearman_p: p-value for Spearman test
        - n_pairs: number of valid pairs
        - name1, name2: variable names
    """
    from scipy.stats import pearsonr, spearmanr
    
    # Ensure arrays
    data1 = np.asarray(data1)
    data2 = np.asarray(data2)
    
    # Check for equal length
    if len(data1) != len(data2):
        raise ValueError(
            f"Arrays must have same length. Got {len(data1)} and {len(data2)}"
        )
    
    # Remove pairs where either value is NaN
    mask = ~(np.isnan(data1) | np.isnan(data2))
    data1_clean = data1[mask]
    data2_clean = data2[mask]
    
    n_pairs = len(data1_clean)
    
    if n_pairs < 3:
        return {
            'pearson_r': np.nan,
            'pearson_p': np.nan,
            'spearman_r': np.nan,
            'spearman_p': np.nan,
            'n_pairs': n_pairs,
            'name1': name1,
            'name2': name2,
            'error': 'Insufficient data (n < 3)'
        }
    
    try:
        # Calculate Pearson correlation
        pearson_r, pearson_p = pearsonr(data1_clean, data2_clean)
        
        # Calculate Spearman correlation
        spearman_r, spearman_p = spearmanr(data1_clean, data2_clean)
        
        return {
            'pearson_r': pearson_r,
            'pearson_p': pearson_p,
            'spearman_r': spearman_r,
            'spearman_p': spearman_p,
            'n_pairs': n_pairs,
            'name1': name1,
            'name2': name2
        }
        
    except Exception as e:
        return {
            'pearson_r': np.nan,
            'pearson_p': np.nan,
            'spearman_r': np.nan,
            'spearman_p': np.nan,
            'n_pairs': n_pairs,
            'name1': name1,
            'name2': name2,
            'error': str(e)
        }


def _collect_metric_values(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    """
    Collect non-null values from a set of columns into a single series.
    """
    values = []
    for col in columns:
        if col in df.columns:
            values.extend(df[col].dropna().tolist())
    return pd.Series(values, dtype='float64')


def _format_mode_values(values: pd.Series, decimals: int) -> str:
    """
    Format the mode for a numeric series using rounded values.

    Returns a comma-separated string if multiple modes are present.
    """
    if values.empty:
        return ''

    mode_values = values.round(decimals).mode()
    if mode_values.empty:
        return ''

    return ', '.join(f"{mode_value:.{decimals}f}" for mode_value in mode_values.tolist())


def _summarize_numeric_values(values: pd.Series, decimals: int) -> Dict[str, str]:
    """
    Return formatted mean, median (Q1 - Q3), and mode strings for a numeric series.
    """
    clean_values = pd.to_numeric(values, errors='coerce').dropna()
    if clean_values.empty:
        return {'mean': '', 'median': '', 'mode': ''}

    q1, q3 = np.percentile(clean_values, [25, 75])

    return {
        'mean': f"{clean_values.mean():.{decimals}f}",
        'median': (
            f"{clean_values.median():.{decimals}f} "
            f"({q1:.{decimals}f} - {q3:.{decimals}f})"
        ),
        'mode': _format_mode_values(clean_values, decimals),
    }


# Absolute tolerance (Gy) for treating a dose delta as exactly 0
ZERO_DELTA_TOLERANCE_GY = 1e-6


def _format_boxplot_min_max_range(values: pd.Series, decimals: int = 3) -> str:
    """
    Return the min-max range inside the 1.5*IQR boxplot whisker fences.
    """
    clean_values = pd.to_numeric(values, errors='coerce').dropna()
    if clean_values.empty:
        return ''

    q1, q3 = np.percentile(clean_values, [25, 75])
    iqr = q3 - q1
    lower_fence = q1 - 1.5 * iqr
    upper_fence = q3 + 1.5 * iqr
    non_outlier_values = clean_values[
        (clean_values >= lower_fence)
        & (clean_values <= upper_fence)
    ]
    if non_outlier_values.empty:
        return ''

    return (
        f"{non_outlier_values.min():.{decimals}f} "
        f"to {non_outlier_values.max():.{decimals}f}"
    )


def _format_median_percentile_range(values: pd.Series, decimals: int = 3) -> str:
    """
    Return "median (p5 to p95)" using the 5th and 95th percentile.
    """
    clean_values = pd.to_numeric(values, errors='coerce').dropna()
    if clean_values.empty:
        return ''

    p5, p95 = np.percentile(clean_values, [5, 95])
    return (
        f"{clean_values.median():.{decimals}f} "
        f"({p5:.{decimals}f} to {p95:.{decimals}f})"
    )


def _count_boxplot_outliers(values: pd.Series) -> int:
    """
    Count values outside the 1.5*IQR boxplot whisker fences.
    """
    clean_values = pd.to_numeric(values, errors='coerce').dropna()
    if clean_values.empty:
        return 0

    q1, q3 = np.percentile(clean_values, [25, 75])
    iqr = q3 - q1
    lower_fence = q1 - 1.5 * iqr
    upper_fence = q3 + 1.5 * iqr
    return int(((clean_values < lower_fence) | (clean_values > upper_fence)).sum())


OAR_SUMMARY_METRICS = [
    ('vDSC', ['Dice'], 4),
    ('sDSC_tol0_5', ['SDSC_tol05'], 4),
    ('sDSC_tol3', ['SDSC_tol3'], 4),
    ('APL_tol0_5', ['APL_tol05'], 4),
    ('APL_tol3', ['APL_tol3'], 4),
    ('Delta_Dmax_0_03cc', ['Delta_Dmax'], 3),
    ('Delta_Dmean', ['Delta_Dmean'], 3),
]


def _summarize_oar_metric(oar_df: pd.DataFrame, candidate_columns: list[str], decimals: int) -> Dict[str, str]:
    """
    Summarize a per-OAR metric using the first available column from a list.
    """
    for column in candidate_columns:
        if column in oar_df.columns:
            values = oar_df[column].dropna()
            if not values.empty:
                return _summarize_numeric_values(values, decimals)
    return {'mean': '', 'median': '', 'mode': ''}


def analyze_correlations_per_oar(
    df: pd.DataFrame,
    min_sample_size: int = 20
) -> pd.DataFrame:
    """
    Analyze correlations between distance to PTV and geometric/dose metrics per OAR.
    
    For each OAR, calculates both Pearson and Spearman correlations between
    dist_to_ptv and the following metrics:
    1. SDSC_tol05 (Surface Distance Standard Coefficient, tolerance 0.5mm)
    2. SDSC_tol3 (Surface Distance Standard Coefficient, tolerance 3mm)
    3. APL_tol05 (Average Path Length, tolerance 0.5mm)
    4. APL_tol3 (Average Path Length, tolerance 3mm)
    5. Dice (Volume Dice Similarity Coefficient - VDSC)
    6. Delta_Dmean (AI_Dmean - Clin_Dmean)
    7. Delta_Dmax (AI_Dmax - Clin_Dmax)
    
    Parameters
    ----------
    df : pd.DataFrame
        Data containing VOIName, dist_to_ptv, and metric columns
    min_sample_size : int
        Minimum number of observations required per OAR
        
    Returns
    -------
    pd.DataFrame
        Summary table with correlation results for each OAR and metric pair
    """
    if 'VOIName' not in df.columns:
        raise ValueError("DataFrame must contain 'VOIName' column")
    
    if 'dist_to_ptv' not in df.columns:
        raise ValueError("DataFrame must contain 'dist_to_ptv' column for correlation analysis")
    
    # Calculate delta columns as AI - Clinical (always recalculate to ensure consistency)
    if 'AI_Dmean' in df.columns and 'Clin_Dmean' in df.columns:
        df['Delta_Dmean'] = df['AI_Dmean'] - df['Clin_Dmean']
        print("  Recalculated Delta_Dmean = AI_Dmean - Clin_Dmean")
    
    if 'AI_Dmax' in df.columns and 'Clin_Dmax' in df.columns:
        df['Delta_Dmax'] = df['AI_Dmax'] - df['Clin_Dmax']
        print("  Recalculated Delta_Dmax = AI_Dmax - Clin_Dmax")
    
    # Define metrics to correlate with distance
    metrics = [
        ('SDSC_tol05', 'SDSC (tol=0.5mm)'),
        ('SDSC_tol3', 'SDSC (tol=3mm)'),
        ('APL_tol05', 'APL (tol=0.5mm)'),
        ('APL_tol3', 'APL (tol=3mm)'),
        ('Dice', 'VDSC (Dice)'),
        ('Delta_Dmean', '|ΔDmean|'),
        ('Delta_Dmax', '|ΔDmax|')
    ]
    
    # Delta metrics for which absolute values should be used
    abs_metrics = {'Delta_Dmean', 'Delta_Dmax'}
    
    print(f"\n{'=' * 80}")
    print(f"CORRELATION ANALYSIS: Distance to PTV vs Geometric/Dose Metrics")
    print(f"{'=' * 80}\n")
    print(f"Minimum sample size: n ≥ {min_sample_size}")
    print(f"Analyzing correlations per OAR for {len(metrics)} metrics\n")
    
    # Check which metrics are available
    available_metrics = []
    for col, display_name in metrics:
        if col in df.columns:
            available_metrics.append((col, display_name))
        else:
            print(f"⚠️  Column '{col}' not found in data, skipping")
    
    if not available_metrics:
        print("❌ No correlation metrics available in dataset")
        return pd.DataFrame()
    
    print(f"✓ Found {len(available_metrics)} metrics for correlation analysis\n")
    
    # Group by VOIName
    grouped = df.groupby('VOIName')
    
    results_list = []
    oars_analyzed = 0
    oars_skipped = 0
    
    for voi_name, voi_df in grouped:
        # Get valid distance data
        valid_dist = voi_df['dist_to_ptv'].dropna()
        
        if len(valid_dist) < min_sample_size:
            oars_skipped += 1
            continue
        
        oars_analyzed += 1
        
        # Calculate correlations for each metric
        for metric_col, metric_name in available_metrics:
            # Get data for this metric
            # Use absolute values for dose deltas: correlation with distance
            # should reflect magnitude of difference, not direction
            if metric_col in abs_metrics:
                metric_data = voi_df[metric_col].abs()
            else:
                metric_data = voi_df[metric_col]
            dist_data = voi_df['dist_to_ptv']
            
            # Calculate correlation
            corr_results = calculate_correlation(
                dist_data.values,
                metric_data.values,
                'Distance to PTV',
                metric_name
            )
            
            if 'error' not in corr_results:
                results_list.append({
                    'OAR': voi_name,
                    'Region': get_oar_region(voi_name),
                    'Metric': metric_name,
                    'N': corr_results['n_pairs'],
                    'Pearson_r': corr_results['pearson_r'],
                    'Pearson_p': corr_results['pearson_p'],
                    'Pearson_Sig': corr_results['pearson_p'] < 0.05 if not np.isnan(corr_results['pearson_p']) else False,
                    'Spearman_r': corr_results['spearman_r'],
                    'Spearman_p': corr_results['spearman_p'],
                    'Spearman_Sig': corr_results['spearman_p'] < 0.05 if not np.isnan(corr_results['spearman_p']) else False
                })
    
    print(f"\n✓ Analyzed {oars_analyzed} OARs with n ≥ {min_sample_size}")
    print(f"  Skipped {oars_skipped} OARs with n < {min_sample_size}\n")
    
    # Create summary DataFrame
    if results_list:
        results_df = pd.DataFrame(results_list)
        # Sort by OAR name, then by metric
        results_df = results_df.sort_values(['OAR', 'Metric'])
        return results_df
    else:
        print("⚠️  No OARs met the minimum sample size requirement")
        return pd.DataFrame()


def calculate_overall_summary(df: pd.DataFrame) -> Dict:
    """
    Calculate overall summary statistics for the entire dataset.
    
    Computes:
    1. Dataset size: number of patients and total rows
    2. OAR counts: number of observations per OAR (filtered for N>19)
    3. Geometric metrics: mean ± SD for SDSC, APL, Dice at various tolerances
    4. Dosimetric metrics: mean ± SD for AI/Clinical doses and deltas
    5. Per-OAR metric summaries: mean, median, and mode for geometric and dosimetric scores
    
    Parameters
    ----------
    df : pd.DataFrame
        Full dataset with all columns
        
    Returns
    -------
    dict
        Dictionary containing summary statistics
    """
    summary = {}
    
    # ========== Dataset Size ==========
    summary['n_rows'] = len(df)
    
    if 'pNumber' in df.columns:
        summary['n_patients'] = df['pNumber'].nunique()
    else:
        summary['n_patients'] = None
    
    if 'VOIName' in df.columns:
        summary['n_oars'] = df['VOIName'].nunique()
    else:
        summary['n_oars'] = None
    
    # ========== OAR Counts (N > 19) ==========
    if 'VOIName' in df.columns:
        oar_counts = df.groupby('VOIName').size().reset_index(name='Count')
        oar_counts = oar_counts[oar_counts['Count'] > 19].sort_values('Count', ascending=False)
        
        # Add region information
        oar_counts['Region'] = oar_counts['VOIName'].apply(get_oar_region)
        
        summary['oar_counts'] = oar_counts
        print(f"  DEBUG: Found {len(oar_counts)} OARs with N > 19")
    else:
        summary['oar_counts'] = pd.DataFrame()
        print(f"  DEBUG: No VOIName column found, oar_counts set to empty DataFrame")
    
    # ========== Geometric Metrics ==========
    geometric_metrics = [
        ('SDSC_tol05', 'SDSC (tol=0.5mm)'),
        ('SDSC_tol1', 'SDSC (tol=1mm)'),
        ('SDSC_tol3', 'SDSC (tol=3mm)'),
        ('APL_tol05', 'APL (tol=0.5mm)'),
        ('APL_tol1', 'APL (tol=1mm)'),
        ('APL_tol3', 'APL (tol=3mm)'),
        ('Dice', 'VDSC (Dice)'),
        ('SDSC', 'SDSC (raw)'),
        ('APL', 'APL (raw)')
    ]
    
    summary['geometric'] = {}
    for col, display_name in geometric_metrics:
        if col in df.columns:
            data = df[col].dropna()
            if len(data) > 0:
                summary['geometric'][display_name] = {
                    'mean': data.mean(),
                    'std': data.std(ddof=1),
                    'median': data.median(),
                    'q1': np.percentile(data, 25),
                    'q3': np.percentile(data, 75),
                    'min': data.min(),
                    'max': data.max(),
                    'n': len(data)
                }
    
    # ========== Dosimetric Metrics ==========
    # Calculate deltas as AI - Clinical (always recalculate to ensure consistency)
    if 'AI_Dmean' in df.columns and 'Clin_Dmean' in df.columns:
        df['Delta_Dmean'] = df['AI_Dmean'] - df['Clin_Dmean']
    
    if 'AI_Dmax' in df.columns and 'Clin_Dmax' in df.columns:
        df['Delta_Dmax'] = df['AI_Dmax'] - df['Clin_Dmax']
    
    dosimetric_metrics = [
        ('AI_Dmean', 'AI Mean Dose'),
        ('Clin_Dmean', 'Clinical Mean Dose'),
        ('Delta_Dmean', 'ΔDmean (AI - Clinical)'),
        ('AI_Dmax', 'AI Max Dose'),
        ('Clin_Dmax', 'Clinical Max Dose'),
        ('Delta_Dmax', 'ΔDmax (AI - Clinical)')
    ]
    
    summary['dosimetric'] = {}
    for col, display_name in dosimetric_metrics:
        if col in df.columns:
            data = df[col].dropna()
            if len(data) > 0:
                summary['dosimetric'][display_name] = {
                    'mean': data.mean(),
                    'std': data.std(ddof=1),
                    'median': data.median(),
                    'q1': np.percentile(data, 25),
                    'q3': np.percentile(data, 75),
                    'min': data.min(),
                    'max': data.max(),
                    'n': len(data)
                }

    # ========== Per-OAR Metric Summaries ========== 
    oar_metric_summary_rows = []
    if 'VOIName' in df.columns and not summary['oar_counts'].empty:
        for _, oar_row in summary['oar_counts'].iterrows():
            oar_name = oar_row['VOIName']
            oar_df = df[df['VOIName'] == oar_name]

            oar_stats = {'VOIName': oar_name}
            for metric_label, candidate_columns, decimals in OAR_SUMMARY_METRICS:
                metric_stats = _summarize_oar_metric(oar_df, candidate_columns, decimals)
                oar_stats[f'{metric_label}_Mean'] = metric_stats['mean']
                oar_stats[f'{metric_label}_Median'] = metric_stats['median']
                oar_stats[f'{metric_label}_Mode'] = metric_stats['mode']

            if 'Delta_Dmean' in oar_df.columns:
                oar_stats['Boxplot_Min_Max_Range_Dmean'] = (
                    _format_boxplot_min_max_range(oar_df['Delta_Dmean'])
                )
                oar_stats['N_Outliers_Dmean'] = (
                    _count_boxplot_outliers(oar_df['Delta_Dmean'])
                )
                oar_stats['Delta_Dmean_Median'] = (
                    _format_median_percentile_range(oar_df['Delta_Dmean'])
                )
            if 'Delta_Dmax' in oar_df.columns:
                oar_stats['Boxplot_Min_Max_Range_Dmax'] = (
                    _format_boxplot_min_max_range(oar_df['Delta_Dmax'])
                )
                oar_stats['N_Outliers_Dmax'] = (
                    _count_boxplot_outliers(oar_df['Delta_Dmax'])
                )
                oar_stats['Delta_Dmax_0_03cc_Median'] = (
                    _format_median_percentile_range(oar_df['Delta_Dmax'])
                )

            oar_metric_summary_rows.append(oar_stats)

    summary['oar_metric_summary'] = pd.DataFrame(oar_metric_summary_rows)
    
    return summary


def print_overall_summary(summary: Dict) -> None:
    """
    Print formatted overall dataset summary.
    
    Parameters
    ----------
    summary : dict
        Summary statistics from calculate_overall_summary()
    """
    print("=" * 80)
    print("OVERALL DATASET SUMMARY")
    print("=" * 80)
    
    # Dataset size
    print("\nDataset Size:")
    print(f"  Total rows: {summary['n_rows']:,}")
    if summary['n_patients'] is not None:
        print(f"  Unique patients: {summary['n_patients']:,}")
    if summary['n_oars'] is not None:
        print(f"  Unique OARs: {summary['n_oars']:,}")
    
    # OAR counts (N > 19)
    if 'oar_counts' in summary and isinstance(summary['oar_counts'], pd.DataFrame) and not summary['oar_counts'].empty:
        print(f"\nOAR Counts (N > 19): {len(summary['oar_counts'])} OARs")
        print("-" * 80)
        print(f"{'OAR':<30} {'Region':<15} {'Count':>10}")
        print("-" * 80)
        
        # Show top 20 OARs by count
        display_limit = min(20, len(summary['oar_counts']))
        for idx, row in summary['oar_counts'].head(display_limit).iterrows():
            print(f"{row['VOIName']:<30} {row['Region']:<15} {row['Count']:>10,}")
        
        if len(summary['oar_counts']) > display_limit:
            remaining = len(summary['oar_counts']) - display_limit
            print(f"\n  ... and {remaining} more OARs (see Dataset_Summary sheet in Excel)")
    
    # Geometric metrics
    if summary['geometric']:
        print("\nGeometric Accuracy Metrics:")
        print("-" * 80)
        print(f"{'Metric':<25} {'Mean ± SD':<20} {'Median':<12} {'Range':<20} {'N':<10}")
        print("-" * 80)
        
        for metric_name, stats in summary['geometric'].items():
            mean_str = f"{stats['mean']:.4f} ± {stats['std']:.4f}"
            median_str = f"{stats['median']:.4f}"
            range_str = f"[{stats['min']:.4f}, {stats['max']:.4f}]"
            n_str = f"{stats['n']:,}"
            print(f"{metric_name:<25} {mean_str:<20} {median_str:<12} {range_str:<20} {n_str:<10}")
    
    # Dosimetric metrics
    if summary['dosimetric']:
        print("\nDosimetric Metrics (Gy):")
        print("-" * 80)
        print(f"{'Metric':<30} {'Mean ± SD':<20} {'Median':<12} {'Range':<20} {'N':<10}")
        print("-" * 80)
        
        for metric_name, stats in summary['dosimetric'].items():
            mean_str = f"{stats['mean']:.3f} ± {stats['std']:.3f}"
            median_str = f"{stats['median']:.3f}"
            range_str = f"[{stats['min']:.3f}, {stats['max']:.3f}]"
            n_str = f"{stats['n']:,}"
            print(f"{metric_name:<30} {mean_str:<20} {median_str:<12} {range_str:<20} {n_str:<10}")
    
    print("=" * 80)
    print()


def print_wilcoxon_results(results: Dict, verbose: bool = True) -> None:
    """
    Print formatted results from Wilcoxon signed-rank test.
    
    Parameters
    ----------
    results : dict
        Results dictionary from wilcoxon_signed_rank_test()
    verbose : bool
        If True, print detailed statistics
    """
    if 'error' in results:
        print(f"❌ Test failed: {results['error']}")
        return
    
    print("=" * 80)
    print(f"WILCOXON SIGNED-RANK TEST: {results['name1']} vs {results['name2']}")
    print("=" * 80)
    
    print(f"\nSample Information:")
    print(f"  Number of valid pairs: {results['n_pairs']}")
    print(f"  Zero differences: {results['n_zeros']}")
    
    print(f"\nDescriptive Statistics (Differences = {results['name1']} - {results['name2']}):")
    print(f"  Mean difference: {results['mean_diff']:.4f} ± {results['std_diff']:.4f} (SD)")
    print(f"  Median difference: {results['median_diff']:.4f}")
    print(f"  95% CI for median: [{results['ci_lower']:.4f}, {results['ci_upper']:.4f}]")
    
    print(f"\nTest Results:")
    print(f"  Test statistic (W): {results['statistic']:.2f}")
    print(f"    → W = sum of ranks for positive differences (scipy convention)")
    print(f"    → Larger W with small p-value = systematic difference exists")
    print(f"  P-value ({results['alternative']}): {results['p_value']:.6f}")
    print(f"  Effect size (r): {results['effect_size']:.3f}")
    
    # Interpret significance
    alpha = 0.05
    if results['p_value'] < alpha:
        print(f"  ✓ Result: SIGNIFICANT (p < {alpha})")
    else:
        print(f"  ✗ Result: NOT SIGNIFICANT (p >= {alpha})")
    
    # Interpret effect size (Cohen's guidelines for r)
    r = results['effect_size']
    if r < 0.1:
        effect_interpretation = "negligible"
    elif r < 0.3:
        effect_interpretation = "small"
    elif r < 0.5:
        effect_interpretation = "medium"
    else:
        effect_interpretation = "large"
    print(f"  Effect size interpretation: {effect_interpretation}")
    
    if verbose:
        print(f"\nDifference Distribution:")
        print(f"  Min: {np.min(results['differences']):.4f}")
        print(f"  25th percentile: {np.percentile(results['differences'], 25):.4f}")
        print(f"  50th percentile (median): {results['median_diff']:.4f}")
        print(f"  75th percentile: {np.percentile(results['differences'], 75):.4f}")
        print(f"  Max: {np.max(results['differences']):.4f}")
    
    print("=" * 80)
    print()


def compare_dose_metrics(
    df: pd.DataFrame,
    ai_col: str,
    clin_col: str,
    metric_name: str,
    alternative: str = 'two-sided',
    verbose: bool = True
) -> Dict:
    """
    Compare AI and Clinical dose metrics using Wilcoxon signed-rank test.
    
    Parameters
    ----------
    df : pd.DataFrame
        Data containing paired observations
    ai_col : str
        Column name for AI values
    clin_col : str
        Column name for Clinical values
    metric_name : str
        Name of the metric being compared (e.g., 'Dmean', 'Dmax')
    alternative : str, optional
        Alternative hypothesis for the test
    verbose : bool, optional
        Whether to print detailed results
        
    Returns
    -------
    dict
        Test results from wilcoxon_signed_rank_test()
    """
    # Check if columns exist
    if ai_col not in df.columns:
        raise ValueError(f"Column '{ai_col}' not found in dataframe")
    if clin_col not in df.columns:
        raise ValueError(f"Column '{clin_col}' not found in dataframe")
    
    # Extract data
    ai_data = df[ai_col].values
    clin_data = df[clin_col].values
    
    # Perform test
    results = wilcoxon_signed_rank_test(
        ai_data,
        clin_data,
        alternative=alternative,
        name1=f'AI {metric_name}',
        name2=f'Clinical {metric_name}'
    )
    
    # Print results
    if verbose:
        print_wilcoxon_results(results, verbose=True)
    
    return results


def analyze_per_oar(
    df: pd.DataFrame,
    ai_col: str,
    clin_col: str,
    metric_name: str,
    min_sample_size: int = 20,
    alternative: str = 'two-sided'
) -> pd.DataFrame:
    """
    Perform Wilcoxon signed-rank test for each OAR separately, comparing AI vs Clinical doses.
    
    Parameters
    ----------
    df : pd.DataFrame
        Data containing VOIName and dose columns
    ai_col : str
        Column name for AI dose values
    clin_col : str
        Column name for Clinical dose values
    metric_name : str
        Display name for the metric (e.g., 'Dmean', 'Dmax')
    min_sample_size : int
        Minimum number of observations required per OAR
    alternative : str
        Alternative hypothesis for the test
        
    Returns
    -------
    pd.DataFrame
        Summary table with test results for each OAR, including:
        - OAR: Structure name
        - Region: Anatomical region (Head_Neck, Neuro_Cranial, Thorax, Abdomen, Pelvis, CNS, or Other)
        - N: Sample size
        - Mean_Delta, Median_Delta (median (5th to 95th percentile)), IQR, Min_Max_Range, N_Outliers:
          Descriptive statistics for the paired dose differences
        - SD: Standard deviation of the paired dose differences
        - W_statistic: Wilcoxon test statistic
        - P_value: Statistical significance
        - Significant: Boolean indicator
        - Effect_Size: Standardized effect size (r)
        - CI_lower, CI_upper: 95% confidence interval
        Sorted by Region, then by P_value within each region
    """
    if 'VOIName' not in df.columns:
        raise ValueError("DataFrame must contain 'VOIName' column for per-OAR analysis")
    
    if ai_col not in df.columns:
        raise ValueError(f"Column '{ai_col}' not found in dataframe")
    
    if clin_col not in df.columns:
        raise ValueError(f"Column '{clin_col}' not found in dataframe")
    
    print(f"\n{'=' * 80}")
    print(f"PER-OAR ANALYSIS: {metric_name} (AI vs Clinical)")
    print(f"{'=' * 80}\n")
    print(f"Minimum sample size: n ≥ {min_sample_size}")
    print(f"Testing if AI {metric_name} differs significantly from Clinical {metric_name} per OAR\n")
    
    # Group by VOIName
    grouped = df.groupby('VOIName')
    
    results_list = []
    oars_analyzed = 0
    oars_skipped = 0
    metric_suffix = metric_name
    
    for voi_name, voi_df in grouped:
        # Get valid paired data for this OAR
        valid_mask = ~(voi_df[ai_col].isna() | voi_df[clin_col].isna())
        ai_data = voi_df.loc[valid_mask, ai_col]
        clin_data = voi_df.loc[valid_mask, clin_col]
        n = len(ai_data)
        
        # Skip if sample size too small
        if n < min_sample_size:
            oars_skipped += 1
            continue
        
        # Perform Wilcoxon test comparing AI vs Clinical
        try:
            results = wilcoxon_signed_rank_test(
                ai_data.values,
                clin_data.values,
                alternative=alternative,
                name1=f'AI {metric_name}',
                name2=f'Clinical {metric_name}'
            )
            
            if 'error' not in results:
                differences = results['differences']
                q1, q3 = np.percentile(differences, [25, 75])
                p5, p95 = np.percentile(differences, [5, 95])
                nonzero_differences = differences[
                    ~np.isclose(differences, 0.0, atol=ZERO_DELTA_TOLERANCE_GY)
                ]
                if len(nonzero_differences) > 0:
                    nz_p5, nz_p95 = np.percentile(nonzero_differences, [5, 95])
                    nonzero_median_range = (
                        f"{np.median(nonzero_differences):.3f} "
                        f"({nz_p5:.3f} to {nz_p95:.3f})"
                    )
                else:
                    nonzero_median_range = ''
                iqr = q3 - q1
                lower_fence = q1 - 1.5 * iqr
                upper_fence = q3 + 1.5 * iqr
                n_outliers = np.sum(
                    (differences < lower_fence) | (differences > upper_fence)
                )
                non_outlier_differences = differences[
                    (differences >= lower_fence)
                    & (differences <= upper_fence)
                ]
                if len(non_outlier_differences) > 0:
                    boxplot_min = non_outlier_differences.min()
                    boxplot_max = non_outlier_differences.max()
                else:
                    boxplot_min = np.nan
                    boxplot_max = np.nan

                results_list.append({
                    'OAR': voi_name,
                    'Region': get_oar_region(voi_name),
                    'N': results['n_pairs'],
                    f'Mean_Delta_{metric_suffix}': results['mean_diff'],
                    f'Median_Delta_{metric_suffix}': (
                        f"{results['median_diff']:.3f} ({p5:.3f} to {p95:.3f})"
                    ),
                    f'Pct_Zero_{metric_suffix}': (
                        100.0 * (len(differences) - len(nonzero_differences))
                        / len(differences)
                    ),
                    f'N_NonZero_{metric_suffix}': int(len(nonzero_differences)),
                    f'Median_P5_P95_NonZero_{metric_suffix}': nonzero_median_range,
                    f'IQR_{metric_suffix}': (
                        f"{iqr:.3f} ({q3:.3f} - {q1:.3f})"
                    ),
                    f'Boxplot_Min_Max_Range_{metric_suffix}': (
                        f"{boxplot_min:.3f} to {boxplot_max:.3f}"
                    ),
                    f'N_Outliers_{metric_suffix}': int(n_outliers),
                    f'Min_Max_Range_{metric_suffix}': (
                        f"{differences.min():.3f} to {differences.max():.3f}"
                    ),
                    'SD': results['std_diff'],
                    'W_statistic': results['statistic'],
                    f'P_value_{metric_suffix}': results['p_value'],
                    f'Significant_{metric_suffix}': results['p_value'] < 0.05,
                    'Effect_Size': results['effect_size'],
                    'CI_lower': results['ci_lower'],
                    'CI_upper': results['ci_upper']
                })
                oars_analyzed += 1
        except Exception as e:
            print(f"  ⚠️  Error analyzing {voi_name}: {e}")
            continue
    
    print(f"\n✓ Analyzed {oars_analyzed} OARs with n ≥ {min_sample_size}")
    print(f"  Skipped {oars_skipped} OARs with n < {min_sample_size}\n")
    
    # Create summary DataFrame
    if results_list:
        results_df = pd.DataFrame(results_list)
        # Sort by region first, then by p-value within each region
        results_df = results_df.sort_values(
            ['Region', f'P_value_{metric_suffix}']
        )
        return results_df
    else:
        print("⚠️  No OARs met the minimum sample size requirement")
        return pd.DataFrame()


def _format_p_value(value: object) -> str:
    """Format p-values compactly for Excel summary tables."""
    if value == '' or pd.isna(value):
        return ''
    value = float(value)
    if value < 0.001:
        return '<0.001'
    return f"{value:.3f}"


def _format_significant(value: object) -> str:
    """Format boolean significance flags for Excel summary tables."""
    if value == '' or pd.isna(value):
        return ''
    return 'Yes' if bool(value) else 'No'


def _format_summary_number(value: object, decimals: int = 3) -> str:
    """Format numeric values for the Dataset_Summary sheet."""
    if value == '' or pd.isna(value):
        return ''
    return f"{float(value):.{decimals}f}"


def _create_overall_summary_df(
    summary: Dict,
    per_oar_dmean: pd.DataFrame | None = None,
    per_oar_dmax: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Convert overall summary statistics to a DataFrame for Excel export.
    
    Parameters
    ----------
    summary : dict
        Summary statistics from calculate_overall_summary()
        
    Returns
    -------
    pd.DataFrame
        Formatted summary table
    """
    rows = []
    
    # Dataset size section
    rows.append({'Category': 'Dataset Size', 'OAR': 'Total Rows', 'Count': f"{summary['n_rows']:,}", 'Details': ''})
    if summary['n_patients'] is not None:
        rows.append({'Category': 'Dataset Size', 'OAR': 'Unique Patients', 'Count': f"{summary['n_patients']:,}", 'Details': ''})
    if summary['n_oars'] is not None:
        rows.append({'Category': 'Dataset Size', 'OAR': 'Unique OARs', 'Count': f"{summary['n_oars']:,}", 'Details': ''})
    
    # Empty row separator
    rows.append({'Category': '', 'OAR': '', 'Count': '', 'Details': ''})
    
    # OAR counts section (N > 19)
    if 'oar_counts' in summary and isinstance(summary['oar_counts'], pd.DataFrame) and not summary['oar_counts'].empty:
        metric_summary = summary.get('oar_metric_summary', pd.DataFrame())
        metric_summary_lookup = {}
        if isinstance(metric_summary, pd.DataFrame) and not metric_summary.empty and 'VOIName' in metric_summary.columns:
            metric_summary_lookup = metric_summary.set_index('VOIName').to_dict(orient='index')

        dmean_wilcoxon_lookup = {}
        if per_oar_dmean is not None and not per_oar_dmean.empty and 'OAR' in per_oar_dmean.columns:
            dmean_wilcoxon_lookup = per_oar_dmean.set_index('OAR').to_dict(orient='index')

        dmax_wilcoxon_lookup = {}
        if per_oar_dmax is not None and not per_oar_dmax.empty and 'OAR' in per_oar_dmax.columns:
            dmax_wilcoxon_lookup = per_oar_dmax.set_index('OAR').to_dict(orient='index')

        rows.append({'Category': 'OAR Counts (N > 19)', 'OAR': 'Total OARs with N > 19',
                    'Count': f"{len(summary['oar_counts']):,}", 'Details': ''})
        rows.append({'Category': '', 'OAR': '', 'Count': '', 'Details': ''})
        
        for idx, oar_row in summary['oar_counts'].iterrows():
            oar_stats = metric_summary_lookup.get(oar_row['VOIName'], {})
            dmean_wilcoxon = dmean_wilcoxon_lookup.get(oar_row['VOIName'], {})
            dmax_wilcoxon = dmax_wilcoxon_lookup.get(oar_row['VOIName'], {})
            rows.append({
                'Category': 'OAR Counts (N > 19)',
                'OAR': oar_row['VOIName'],
                'Count': f"{oar_row['Count']:,}",
                'Details': f"Region: {oar_row['Region']}",
                'vDSC_Mean': oar_stats.get('vDSC_Mean', ''),
                'vDSC_Median': oar_stats.get('vDSC_Median', ''),
                'vDSC_Mode': oar_stats.get('vDSC_Mode', ''),
                'sDSC_tol0_5_Mean': oar_stats.get('sDSC_tol0_5_Mean', ''),
                'sDSC_tol0_5_Median': oar_stats.get('sDSC_tol0_5_Median', ''),
                'sDSC_tol0_5_Mode': oar_stats.get('sDSC_tol0_5_Mode', ''),
                'sDSC_tol3_Mean': oar_stats.get('sDSC_tol3_Mean', ''),
                'sDSC_tol3_Median': oar_stats.get('sDSC_tol3_Median', ''),
                'sDSC_tol3_Mode': oar_stats.get('sDSC_tol3_Mode', ''),
                'APL_tol0_5_Mean': oar_stats.get('APL_tol0_5_Mean', ''),
                'APL_tol0_5_Median': oar_stats.get('APL_tol0_5_Median', ''),
                'APL_tol0_5_Mode': oar_stats.get('APL_tol0_5_Mode', ''),
                'APL_tol3_Mean': oar_stats.get('APL_tol3_Mean', ''),
                'APL_tol3_Median': oar_stats.get('APL_tol3_Median', ''),
                'APL_tol3_Mode': oar_stats.get('APL_tol3_Mode', ''),
                'Delta_Dmax_0_03cc_Mean': oar_stats.get('Delta_Dmax_0_03cc_Mean', ''),
                'Delta_Dmax_0_03cc_Median': oar_stats.get('Delta_Dmax_0_03cc_Median', ''),
                'Delta_Dmax_0_03cc_Mode': oar_stats.get('Delta_Dmax_0_03cc_Mode', ''),
                'Boxplot_Min_Max_Range_Dmax': oar_stats.get('Boxplot_Min_Max_Range_Dmax', ''),
                'N_Outliers_Dmax': oar_stats.get('N_Outliers_Dmax', ''),
                'Delta_Dmean_Mean': oar_stats.get('Delta_Dmean_Mean', ''),
                'Delta_Dmean_Median': oar_stats.get('Delta_Dmean_Median', ''),
                'Delta_Dmean_Mode': oar_stats.get('Delta_Dmean_Mode', ''),
                'Boxplot_Min_Max_Range_Dmean': oar_stats.get('Boxplot_Min_Max_Range_Dmean', ''),
                'N_Outliers_Dmean': oar_stats.get('N_Outliers_Dmean', ''),
                'Wilcoxon_W_Dmean': _format_summary_number(dmean_wilcoxon.get('W_statistic', '')),
                'Wilcoxon_P_Dmean': _format_p_value(dmean_wilcoxon.get('P_value_Dmean', np.nan)),
                'Wilcoxon_Significant_Dmean': _format_significant(dmean_wilcoxon.get('Significant_Dmean', np.nan)),
                'Wilcoxon_Effect_Size_Dmean': _format_summary_number(dmean_wilcoxon.get('Effect_Size', '')),
                'Wilcoxon_W_Dmax': _format_summary_number(dmax_wilcoxon.get('W_statistic', '')),
                'Wilcoxon_P_Dmax': _format_p_value(dmax_wilcoxon.get('P_value_Dmax', np.nan)),
                'Wilcoxon_Significant_Dmax': _format_significant(dmax_wilcoxon.get('Significant_Dmax', np.nan)),
                'Wilcoxon_Effect_Size_Dmax': _format_summary_number(dmax_wilcoxon.get('Effect_Size', ''))
            })
        
        # Empty row separator
        rows.append({'Category': '', 'OAR': '', 'Count': '', 'Details': ''})
    
    # Geometric metrics section
    if summary['geometric']:
        for metric_name, stats in summary['geometric'].items():
            rows.append({
                'Category': 'Geometric Metrics',
                'OAR': metric_name,
                'Count': f"{stats['mean']:.4f} ± {stats['std']:.4f}",
                'Details': f"Median (Q1 - Q3): {stats['median']:.4f} ({stats['q1']:.4f} - {stats['q3']:.4f}), Range: [{stats['min']:.4f}, {stats['max']:.4f}], N: {stats['n']:,}"
            })
    
    # Empty row separator
    rows.append({'Category': '', 'OAR': '', 'Count': '', 'Details': ''})
    
    # Dosimetric metrics section
    if summary['dosimetric']:
        for metric_name, stats in summary['dosimetric'].items():
            rows.append({
                'Category': 'Dosimetric Metrics (Gy)',
                'OAR': metric_name,
                'Count': f"{stats['mean']:.3f} ± {stats['std']:.3f}",
                'Details': f"Median (Q1 - Q3): {stats['median']:.3f} ({stats['q1']:.3f} - {stats['q3']:.3f}), Range: [{stats['min']:.3f}, {stats['max']:.3f}], N: {stats['n']:,}"
            })
    
    summary_df = pd.DataFrame(rows)
    column_order = [
        'Category', 'OAR', 'Count', 'Details',
        'vDSC_Mean', 'vDSC_Median', 'vDSC_Mode',
        'sDSC_tol0_5_Mean', 'sDSC_tol0_5_Median', 'sDSC_tol0_5_Mode',
        'sDSC_tol3_Mean', 'sDSC_tol3_Median', 'sDSC_tol3_Mode',
        'APL_tol0_5_Mean', 'APL_tol0_5_Median', 'APL_tol0_5_Mode',
        'APL_tol3_Mean', 'APL_tol3_Median', 'APL_tol3_Mode',
        'Delta_Dmax_0_03cc_Mean', 'Delta_Dmax_0_03cc_Median', 'Delta_Dmax_0_03cc_Mode',
        'Boxplot_Min_Max_Range_Dmax', 'N_Outliers_Dmax',
        'Delta_Dmean_Mean', 'Delta_Dmean_Median', 'Delta_Dmean_Mode',
        'Boxplot_Min_Max_Range_Dmean', 'N_Outliers_Dmean',
        'Wilcoxon_W_Dmean', 'Wilcoxon_P_Dmean',
        'Wilcoxon_Significant_Dmean', 'Wilcoxon_Effect_Size_Dmean',
        'Wilcoxon_W_Dmax', 'Wilcoxon_P_Dmax',
        'Wilcoxon_Significant_Dmax', 'Wilcoxon_Effect_Size_Dmax'
    ]
    return summary_df.reindex(columns=column_order)


def _create_regional_summary(per_oar_dmean: pd.DataFrame, per_oar_dmax: pd.DataFrame) -> pd.DataFrame:
    """
    Create regional summary statistics from per-OAR results.
    
    Parameters
    ----------
    per_oar_dmean : pd.DataFrame
        Per-OAR results for Dmean
    per_oar_dmax : pd.DataFrame
        Per-OAR results for Dmax
        
    Returns
    -------
    pd.DataFrame
        Regional summary with columns:
        - Region: Anatomical region
        - Dmean_N_OARs: Number of OARs analyzed for Dmean
        - Dmean_Significant: Number of significant OARs for Dmean
        - Dmean_Pct_Significant: Percentage significant for Dmean
        - Dmax_N_OARs: Number of OARs analyzed for Dmax
        - Dmax_Significant: Number of significant OARs for Dmax
        - Dmax_Pct_Significant: Percentage significant for Dmax
    """
    regional_data = []
    
    # Define region order
    regions = [
        'Head_Neck', 'Neuro_Cranial', 'Thorax', 'Abdomen', 'Pelvis', 'CNS',
        'Other'
    ]
    
    for region in regions:
        # Dmean statistics
        if not per_oar_dmean.empty:
            dmean_region = per_oar_dmean[per_oar_dmean['Region'] == region]
            dmean_n = len(dmean_region)
            dmean_sig = (dmean_region['P_value_Dmean'] < 0.05).sum() if dmean_n > 0 else 0
            dmean_pct = (dmean_sig / dmean_n * 100) if dmean_n > 0 else 0
        else:
            dmean_n = 0
            dmean_sig = 0
            dmean_pct = 0
        
        # Dmax statistics
        if not per_oar_dmax.empty:
            dmax_region = per_oar_dmax[per_oar_dmax['Region'] == region]
            dmax_n = len(dmax_region)
            dmax_sig = (dmax_region['P_value_Dmax'] < 0.05).sum() if dmax_n > 0 else 0
            dmax_pct = (dmax_sig / dmax_n * 100) if dmax_n > 0 else 0
        else:
            dmax_n = 0
            dmax_sig = 0
            dmax_pct = 0
        
        # Only add row if at least one metric has data for this region
        if dmean_n > 0 or dmax_n > 0:
            regional_data.append({
                'Region': region,
                'Dmean_N_OARs': dmean_n,
                'Dmean_Significant': dmean_sig,
                'Dmean_Pct_Significant': f"{dmean_pct:.1f}%",
                'Dmax_N_OARs': dmax_n,
                'Dmax_Significant': dmax_sig,
                'Dmax_Pct_Significant': f"{dmax_pct:.1f}%"
            })
    
    if regional_data:
        return pd.DataFrame(regional_data)
    else:
        return pd.DataFrame()


def _create_acceptable_df(
    overall_summary: Dict,
    per_oar_dmean: pd.DataFrame,
    per_oar_dmax: pd.DataFrame
) -> pd.DataFrame:
    """Create the overarching per-OAR table for the Acceptable sheet."""
    columns = [
        'OAR',
        'sDSC_tol0_5_Mean',
        'vDSC_Mean',
        'Median_Delta_Dmean',
        'IQR_Dmean',
        'Boxplot_Min_Max_Range_Dmean',
        'N_Outliers_Dmean',
        'Min_Max_Range_Dmean',
        'P_value_Dmean',
        'Significant_Dmean',
        'Median_Delta_Dmax',
        'IQR_Dmax',
        'Boxplot_Min_Max_Range_Dmax',
        'N_Outliers_Dmax',
        'Min_Max_Range_Dmax',
        'P_value_Dmax',
        'Significant_Dmax',
    ]

    oar_counts = overall_summary.get('oar_counts', pd.DataFrame())
    if oar_counts.empty:
        return pd.DataFrame(columns=columns)

    acceptable_df = (
        oar_counts[['VOIName']]
        .rename(columns={'VOIName': 'OAR'})
        .reset_index(drop=True)
    )

    metric_summary = overall_summary.get('oar_metric_summary', pd.DataFrame())
    if not metric_summary.empty:
        metric_columns = [
            column for column in
            ['VOIName', 'sDSC_tol0_5_Mean', 'vDSC_Mean']
            if column in metric_summary.columns
        ]
        acceptable_df = acceptable_df.merge(
            metric_summary[metric_columns].rename(columns={'VOIName': 'OAR'}),
            on='OAR',
            how='left'
        )

    if not per_oar_dmean.empty:
        dmean_columns = [
            column for column in columns
            if column == 'OAR' or column.endswith('_Dmean')
        ]
        acceptable_df = acceptable_df.merge(
            per_oar_dmean[dmean_columns],
            on='OAR',
            how='left'
        )

    if not per_oar_dmax.empty:
        dmax_columns = [
            column for column in columns
            if column == 'OAR' or column.endswith('_Dmax')
        ]
        acceptable_df = acceptable_df.merge(
            per_oar_dmax[dmax_columns],
            on='OAR',
            how='left'
        )

    return acceptable_df.reindex(columns=columns)


def save_results_to_excel(
    overall_summary: Dict,
    overall_results: Dict,
    per_oar_dmean: pd.DataFrame,
    per_oar_dmax: pd.DataFrame,
    correlations: pd.DataFrame,
    output_file: str = 'statistical_analysis_results.xlsx'
) -> None:
    """
    Save all statistical results to an Excel file with multiple sheets.
    
    Parameters
    ----------
    overall_summary : dict
        Overall dataset summary statistics from calculate_overall_summary()
    overall_results : dict
        Dictionary with overall Wilcoxon test results
    per_oar_dmean : pd.DataFrame
        Per-OAR results for Dmean (AI vs Clinical)
    per_oar_dmax : pd.DataFrame
        Per-OAR results for Dmax (AI vs Clinical)
    correlations : pd.DataFrame
        Per-OAR correlation results between distance and metrics
    output_file : str
        Output Excel file name
        
    Notes
    -----
    Creates an Excel file with five sheets:
    0. Dataset_Summary: Overall dataset statistics (patients, rows, OAR counts N>19, mean metrics)
    1. Overall_Wilcoxon: Overall test results + Regional summary statistics
    2. Per_OAR_Dmean: Detailed per-OAR results for Dmean
    3. Per_OAR_Dmax: Detailed per-OAR results for Dmax
    4. Distance_Correlations: Per-OAR correlations between distance and geometric/dose metrics
    
    The Overall_Wilcoxon sheet includes:
    - Top section: Overall Wilcoxon test results for Dmean and Dmax
    - Bottom section: Regional summary showing number and percentage of 
      significant OARs per anatomical region for both metrics
    """
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        # Sheet 0: Overall dataset summary
        if overall_summary:
            summary_df = _create_overall_summary_df(
                overall_summary,
                per_oar_dmean,
                per_oar_dmax
            )
            summary_df.to_excel(writer, sheet_name='Dataset_Summary', index=False)
            print(f"  - Dataset_Summary sheet: {len(summary_df)} rows")
            
            # Debug: Check if OAR counts are included
            if 'oar_counts' in overall_summary and not overall_summary['oar_counts'].empty:
                print(f"    * Includes {len(overall_summary['oar_counts'])} OARs with N > 19")
        
        # Sheet 1: Overall Wilcoxon tests with regional statistics
        if overall_results:
            overall_data = []
            for metric, results in overall_results.items():
                if 'error' not in results:
                    overall_data.append({
                        'Metric': metric,
                        'N': results['n_pairs'],
                        'Mean_Delta': results['mean_diff'],
                        'Median_Delta': results['median_diff'],
                        'SD': results['std_diff'],
                        'CI_Lower': results['ci_lower'],
                        'CI_Upper': results['ci_upper'],
                        'W_Statistic': results['statistic'],
                        'P_value': results['p_value'],
                        'Significant': results['p_value'] < 0.05,
                        'Effect_Size': results['effect_size']
                    })
            
            if overall_data:
                overall_df = pd.DataFrame(overall_data)
                
                # Create regional summary statistics
                regional_summary = _create_regional_summary(per_oar_dmean, per_oar_dmax)
                
                # Write overall results starting at row 0
                overall_df.to_excel(writer, sheet_name='Overall_Wilcoxon', index=False, startrow=0)
                
                # Write regional summary below overall results (with 2 empty rows gap)
                if not regional_summary.empty:
                    regional_summary.to_excel(
                        writer, 
                        sheet_name='Overall_Wilcoxon', 
                        index=False, 
                        startrow=len(overall_df) + 3
                    )
        
        # Sheet 2: Per-OAR Dmean (AI vs Clinical)
        if not per_oar_dmean.empty:
            per_oar_dmean.to_excel(writer, sheet_name='Per_OAR_Dmean', index=False)
        
        # Sheet 3: Per-OAR Dmax (AI vs Clinical)
        if not per_oar_dmax.empty:
            per_oar_dmax.to_excel(writer, sheet_name='Per_OAR_Dmax', index=False)
        
        # Sheet 4: Distance correlations
        if not correlations.empty:
            correlations.to_excel(writer, sheet_name='Distance_Correlations', index=False)

        acceptable_df = _create_acceptable_df(
            overall_summary,
            per_oar_dmean,
            per_oar_dmax
        )
        acceptable_df.to_excel(writer, sheet_name='Acceptable', index=False)
    
    print(f"✓ Results saved to: {output_file}")
    print(f"  Sheet 1: Dataset_Summary (overall dataset statistics)")
    print(f"  Sheet 2: Overall_Wilcoxon (includes regional summary statistics)")
    print(f"  Sheet 3: Per_OAR_Dmean (n={len(per_oar_dmean) if not per_oar_dmean.empty else 0} OARs)")
    print(f"  Sheet 4: Per_OAR_Dmax (n={len(per_oar_dmax) if not per_oar_dmax.empty else 0} OARs)")
    print(f"  Sheet 5: Distance_Correlations (n={len(correlations) if not correlations.empty else 0} rows)")
    print(f"  Sheet 6: Acceptable (overarching per-OAR summary)")
    print()


def _resolve_writable_excel_path(output_file: str) -> str:
    """Return a fallback output path if the requested workbook is open/locked."""
    output_path = Path(output_file)
    fallback_path = output_path.with_name(
        f"{output_path.stem}_updated{output_path.suffix}"
    )
    timestamped_path = output_path.with_name(
        f"{output_path.stem}_{datetime.now():%Y%m%d_%H%M%S}{output_path.suffix}"
    )

    for candidate in (output_path, fallback_path, timestamped_path):
        if not candidate.exists():
            if candidate != output_path:
                print(
                    f"  - {output_path} appears to be open or locked; "
                    f"saving to {candidate} instead."
                )
            return str(candidate)

        try:
            with candidate.open('r+b'):
                pass
            if candidate != output_path:
                print(
                    f"  - {output_path} appears to be open or locked; "
                    f"saving to {candidate} instead."
                )
            return str(candidate)
        except PermissionError:
            continue

    print(
        f"  - {output_path} and fallback files appear locked; "
        f"saving to {timestamped_path} instead."
    )
    return str(timestamped_path)


def main():
    """
    Main analysis pipeline for statistical comparisons.
    Performs both overall and per-OAR analyses.
    """
    print("\n" + "=" * 80)
    print("STATISTICAL ANALYSIS: AI vs CLINICAL CONTOURS")
    print("=" * 80 + "\n")
    
    # Load data
    print("Step 1: Loading data...")
    df = load_data('contour_comparison_results_P0728_v7.xlsx')
    
    # ============================================================================
    # OVERALL DATASET SUMMARY
    # ============================================================================
    
    print("\n" + "=" * 80)
    print("Step 2: Computing Overall Dataset Summary")
    print("=" * 80 + "\n")
    
    overall_summary = calculate_overall_summary(df)
    print_overall_summary(overall_summary)
    
    # ============================================================================
    # VALIDATE DOSE COLUMNS
    # ============================================================================
    
    print("\n" + "=" * 80)
    print("Step 3: Validating Dose Columns")
    print("=" * 80 + "\n")
    
    # Define exact column names
    required_cols = ['AI_Dmean', 'AI_Dmax', 'Clin_Dmean', 'Clin_Dmax']
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    if missing_cols:
        print(f"❌ Missing required columns: {', '.join(missing_cols)}")
        print(f"\nAvailable columns: {', '.join(df.columns)}")
        print("\nPlease ensure the v7 file contains: AI_Dmean, AI_Dmax, Clin_Dmean, Clin_Dmax")
        return
    
    print(f"✓ Found AI_Dmean column")
    print(f"✓ Found AI_Dmax column")
    print(f"✓ Found Clin_Dmean column")
    print(f"✓ Found Clin_Dmax column")
    
    # Store column names for later use
    dose_columns = {
        'ai_dmean': 'AI_Dmean',
        'clin_dmean': 'Clin_Dmean',
        'ai_dmax': 'AI_Dmax',
        'clin_dmax': 'Clin_Dmax'
    }
    
    # Perform Wilcoxon signed-rank tests comparing AI vs Clinical doses
    print("\n" + "=" * 80)
    print("Step 4: Performing Wilcoxon Signed-Rank Tests (OVERALL)")
    print("=" * 80 + "\n")
    print("Testing whether AI doses differ significantly from Clinical doses.")
    print("Null hypothesis: No difference between AI and Clinical doses\n")
    
    # Store results for summary
    all_results = {}
    
    # Test 1: AI_Dmean vs Clinical_Dmean
    print("\n### TEST 1: MEAN DOSE (AI vs Clinical) ###\n")
    try:
        results_dmean = compare_dose_metrics(
            df,
            ai_col=dose_columns['ai_dmean'],
            clin_col=dose_columns['clin_dmean'],
            metric_name='Dmean',
            alternative='two-sided',
            verbose=True
        )
        all_results['Dmean'] = results_dmean
        
    except Exception as e:
        print(f"❌ Error in Dmean comparison: {e}")
    
    # Test 2: AI_Dmax vs Clinical_Dmax
    print("\n### TEST 2: MAX DOSE (AI vs Clinical) ###\n")
    try:
        results_dmax = compare_dose_metrics(
            df,
            ai_col=dose_columns['ai_dmax'],
            clin_col=dose_columns['clin_dmax'],
            metric_name='Dmax',
            alternative='two-sided',
            verbose=True
        )
        all_results['Dmax'] = results_dmax
        
    except Exception as e:
        print(f"❌ Error in Dmax comparison: {e}")
    
    # Summary of overall results
    if all_results:
        print("\n" + "=" * 80)
        print("OVERALL SUMMARY")
        print("=" * 80 + "\n")
        
        summary_data = []
        for metric, results in all_results.items():
            if 'error' not in results:
                summary_data.append({
                    'Metric': metric,
                    'N': results['n_pairs'],
                    'Mean Diff': f"{results['mean_diff']:.4f}",
                    'Median Diff': f"{results['median_diff']:.4f}",
                    'P-value': f"{results['p_value']:.6f}",
                    'Significant': '✓' if results['p_value'] < 0.05 else '✗',
                    'Effect Size': f"{results['effect_size']:.3f}"
                })
        
        if summary_data:
            summary_df = pd.DataFrame(summary_data)
            print(summary_df.to_string(index=False))
            print()
    
    # ============================================================================
    # STEP 5: PER-OAR ANALYSIS
    # ============================================================================
    
    print("\n" + "=" * 80)
    print("Step 5: Per-OAR Analysis")
    print("=" * 80 + "\n")
    
    min_sample_size = 20
    
    # Per-OAR analysis for Dmean (AI vs Clinical)
    per_oar_dmean = analyze_per_oar(
        df,
        ai_col=dose_columns['ai_dmean'],
        clin_col=dose_columns['clin_dmean'],
        metric_name='Dmean',
        min_sample_size=min_sample_size,
        alternative='two-sided'
    )
    
    if not per_oar_dmean.empty:
        print("PER-OAR RESULTS: Dmean (AI vs Clinical)")
        print("-" * 80)
        
        # Format for display
        display_df = per_oar_dmean.copy()
        display_df['Mean_Delta_Dmean'] = display_df['Mean_Delta_Dmean'].apply(lambda x: f"{x:.4f}")
        display_df['SD'] = display_df['SD'].apply(lambda x: f"{x:.4f}")
        display_df['P_value_Dmean'] = display_df['P_value_Dmean'].apply(lambda x: f"{x:.6f}")
        display_df['Effect_Size'] = display_df['Effect_Size'].apply(lambda x: f"{x:.3f}")
        display_df['Significant_Dmean'] = display_df['Significant_Dmean'].apply(lambda x: '✓' if x else '✗')
        
        # Show top results
        print("\nTop 10 most significant OARs:")
        print(display_df.head(10).to_string(index=False))
        
        # Count significant results
        n_significant = (per_oar_dmean['P_value_Dmean'] < 0.05).sum()
        print(f"\n✓ Significant OARs (p < 0.05): {n_significant} / {len(per_oar_dmean)}")
        
        # Summary by region
        print("\nSummary by anatomical region:")
        for region in [
            'Head_Neck', 'Neuro_Cranial', 'Thorax', 'Abdomen', 'Pelvis',
            'CNS', 'Other'
        ]:
            region_df = per_oar_dmean[per_oar_dmean['Region'] == region]
            if len(region_df) > 0:
                n_sig = (region_df['P_value_Dmean'] < 0.05).sum()
                print(f"  {region:12s}: {n_sig}/{len(region_df)} significant")
        print()
    
    # Per-OAR analysis for Dmax (AI vs Clinical)
    per_oar_dmax = analyze_per_oar(
        df,
        ai_col=dose_columns['ai_dmax'],
        clin_col=dose_columns['clin_dmax'],
        metric_name='Dmax',
        min_sample_size=min_sample_size,
        alternative='two-sided'
    )
    
    if not per_oar_dmax.empty:
        print("PER-OAR RESULTS: Dmax (AI vs Clinical)")
        print("-" * 80)
        
        # Format for display
        display_df = per_oar_dmax.copy()
        display_df['Mean_Delta_Dmax'] = display_df['Mean_Delta_Dmax'].apply(lambda x: f"{x:.4f}")
        display_df['SD'] = display_df['SD'].apply(lambda x: f"{x:.4f}")
        display_df['P_value_Dmax'] = display_df['P_value_Dmax'].apply(lambda x: f"{x:.6f}")
        display_df['Effect_Size'] = display_df['Effect_Size'].apply(lambda x: f"{x:.3f}")
        display_df['Significant_Dmax'] = display_df['Significant_Dmax'].apply(lambda x: '✓' if x else '✗')
        
        # Show top results
        print("\nTop 10 most significant OARs:")
        print(display_df.head(10).to_string(index=False))
        
        # Count significant results
        n_significant = (per_oar_dmax['P_value_Dmax'] < 0.05).sum()
        print(f"\n✓ Significant OARs (p < 0.05): {n_significant} / {len(per_oar_dmax)}")
        
        # Summary by region
        print("\nSummary by anatomical region:")
        for region in [
            'Head_Neck', 'Neuro_Cranial', 'Thorax', 'Abdomen', 'Pelvis',
            'CNS', 'Other'
        ]:
            region_df = per_oar_dmax[per_oar_dmax['Region'] == region]
            if len(region_df) > 0:
                n_sig = (region_df['P_value_Dmax'] < 0.05).sum()
                print(f"  {region:12s}: {n_sig}/{len(region_df)} significant")
        print()
    
    # ============================================================================
    # STEP 6: CORRELATION ANALYSIS
    # ============================================================================
    
    print("\n" + "=" * 80)
    print("Step 6: Correlation Analysis")
    print("=" * 80 + "\n")
    
    # Analyze correlations between distance to PTV and geometric/dose metrics
    correlations = pd.DataFrame()  # Initialize empty DataFrame
    
    try:
        correlations = analyze_correlations_per_oar(
            df,
            min_sample_size=min_sample_size
        )
        
        if not correlations.empty:
            print("CORRELATION RESULTS SUMMARY")
            print("-" * 80)
            
            # Show some example results
            print("\nExample correlations (first 15 rows):")
            display_df = correlations.copy()
            display_df['Pearson_r'] = display_df['Pearson_r'].apply(lambda x: f"{x:.3f}" if not np.isnan(x) else "NaN")
            display_df['Pearson_p'] = display_df['Pearson_p'].apply(lambda x: f"{x:.4f}" if not np.isnan(x) else "NaN")
            display_df['Spearman_r'] = display_df['Spearman_r'].apply(lambda x: f"{x:.3f}" if not np.isnan(x) else "NaN")
            display_df['Spearman_p'] = display_df['Spearman_p'].apply(lambda x: f"{x:.4f}" if not np.isnan(x) else "NaN")
            display_df['Pearson_Sig'] = display_df['Pearson_Sig'].apply(lambda x: '✓' if x else '✗')
            display_df['Spearman_Sig'] = display_df['Spearman_Sig'].apply(lambda x: '✓' if x else '✗')
            
            print(display_df.head(15).to_string(index=False))
            
            # Summary statistics
            n_pearson_sig = (correlations['Pearson_Sig']).sum()
            n_spearman_sig = (correlations['Spearman_Sig']).sum()
            total_tests = len(correlations)
            
            print(f"\n✓ Pearson significant: {n_pearson_sig} / {total_tests} ({n_pearson_sig/total_tests*100:.1f}%)")
            print(f"✓ Spearman significant: {n_spearman_sig} / {total_tests} ({n_spearman_sig/total_tests*100:.1f}%)")
            
            # Summary by metric
            print("\nSignificant correlations by metric:")
            for metric in correlations['Metric'].unique():
                metric_df = correlations[correlations['Metric'] == metric]
                n_p = (metric_df['Pearson_Sig']).sum()
                n_s = (metric_df['Spearman_Sig']).sum()
                print(f"  {metric:20s}: Pearson {n_p}/{len(metric_df)}, Spearman {n_s}/{len(metric_df)}")
            print()
        else:
            print("⚠️  No correlation results (possibly dist_to_ptv column not available)")
    
    except Exception as e:
        print(f"⚠️  Error in correlation analysis: {e}")
        print("    Continuing with other analyses...")
    
    # ============================================================================
    # STEP 7: SAVE RESULTS TO EXCEL
    # ============================================================================
    
    print("\n" + "=" * 80)
    print("Step 7: Saving Results")
    print("=" * 80 + "\n")
    
    try:
        output_file = _resolve_writable_excel_path(
            'statistical_analysis_results.xlsx'
        )
        save_results_to_excel(
            overall_summary=overall_summary,
            overall_results=all_results,
            per_oar_dmean=per_oar_dmean,
            per_oar_dmax=per_oar_dmax,
            correlations=correlations,
            output_file=output_file
        )
    except Exception as e:
        print(f"⚠️  Could not save Excel file: {e}")
    
    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
