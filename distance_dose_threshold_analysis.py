"""
Analyze absolute dose differences as a function of OAR-to-PTV distance.

For each OAR and for Delta_Dmean and Delta_Dmax, this script:
1. Converts signed dose differences to absolute values.
2. Finds the smallest distance containing at least 90% of the total
   absolute dose-difference magnitude.
3. Creates a scatterplot with the distance thresholds marked.
4. Exports a data-driven distance-bucket summary.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr


DEFAULT_INPUT = "contour_comparison_results_P0728_v7.xlsx"
DEFAULT_OUTPUT_DIR = "explore_results"
OAR_COLUMN = "VOIName"
DISTANCE_COLUMN = "dist_to_ptv"
SDSC_COLUMN = "SDSC_tol05"
DOSE_METRICS = ("Delta_Dmean", "Delta_Dmax")
FIXED_THRESHOLD_CM = 1.0
ACCEPTABLE_DOSE_DIFF_GY = {
    "Delta_Dmean": 1.0,
    "Delta_Dmax": 2.0,
}


def resolve_input_path(input_file: str) -> Path:
    """Resolve an input path from common project locations."""
    path = Path(input_file)
    script_dir = Path(__file__).resolve().parent
    candidates = [
        path,
        Path.cwd() / path,
        Path.cwd().parent / path,
        script_dir / path,
        script_dir.parent / path,
    ]

    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()

    raise FileNotFoundError(f"Input file not found: {input_file}")


def prepare_metric_data(df: pd.DataFrame, metric: str) -> pd.DataFrame:
    """Return valid distance and absolute dose-difference observations."""
    metric_df = df[[DISTANCE_COLUMN, metric, SDSC_COLUMN]].copy()
    metric_df[DISTANCE_COLUMN] = pd.to_numeric(
        metric_df[DISTANCE_COLUMN], errors="coerce"
    )
    metric_df[metric] = pd.to_numeric(metric_df[metric], errors="coerce")
    metric_df[SDSC_COLUMN] = pd.to_numeric(
        metric_df[SDSC_COLUMN], errors="coerce"
    )
    metric_df = metric_df.dropna(subset=[DISTANCE_COLUMN, metric])
    metric_df = metric_df[metric_df[DISTANCE_COLUMN] >= 0]
    metric_df[f"Absolute_{metric}"] = metric_df[metric].abs()
    metric_df["SDSC_tol05_equals_1"] = metric_df[SDSC_COLUMN] == 1.0
    metric_df["exceeds_acceptable_dose_diff_above_1cm"] = (
        (metric_df[DISTANCE_COLUMN] > FIXED_THRESHOLD_CM)
        & (metric_df[f"Absolute_{metric}"] > ACCEPTABLE_DOSE_DIFF_GY[metric])
    )
    return metric_df


def resolve_output_path(output_dir: str) -> Path:
    """Resolve relative output paths from the project root."""
    path = Path(output_dir)
    if path.is_absolute():
        return path
    return Path(__file__).resolve().parent.parent / path


def save_summary_excel(
    summary_df: pd.DataFrame,
    output_file: Path,
    extra_sheets: dict[str, pd.DataFrame] | None = None,
) -> Path:
    """Save Excel summaries, using an updated filename if the file is locked."""
    def write_workbook(path: Path) -> None:
        if extra_sheets:
            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                summary_df.to_excel(
                    writer,
                    sheet_name="All_Results",
                    index=False,
                )
                for sheet_name, sheet_df in extra_sheets.items():
                    sheet_df.to_excel(
                        writer,
                        sheet_name=sheet_name,
                        index=False,
                    )
        else:
            summary_df.to_excel(path, index=False)

    try:
        write_workbook(output_file)
        return output_file
    except PermissionError:
        fallback_file = output_file.with_name(
            f"{output_file.stem}_updated{output_file.suffix}"
        )
        write_workbook(fallback_file)
        print(
            f"Could not overwrite open workbook {output_file.name}; "
            f"saved as {fallback_file.name}"
        )
        return fallback_file


def find_capture_threshold(
    metric_df: pd.DataFrame,
    metric: str,
    target_capture: float,
) -> dict:
    """
    Find the smallest distance capturing the target absolute-delta magnitude.

    Observations are grouped by distance and accumulated from nearest to
    farthest. Thus, a threshold of x cm includes all observations whose
    OAR-to-PTV distance is less than or equal to x.
    """
    absolute_column = f"Absolute_{metric}"
    by_distance = (
        metric_df.groupby(DISTANCE_COLUMN, as_index=False)
        .agg(
            absolute_delta_sum=(absolute_column, "sum"),
            observation_count=(absolute_column, "size"),
        )
        .sort_values(DISTANCE_COLUMN)
    )

    total_absolute_delta = by_distance["absolute_delta_sum"].sum()
    if total_absolute_delta <= 0:
        raise ValueError(f"{metric} contains no non-zero absolute differences")

    by_distance["cumulative_absolute_delta"] = (
        by_distance["absolute_delta_sum"].cumsum()
    )
    by_distance["cumulative_capture"] = (
        by_distance["cumulative_absolute_delta"] / total_absolute_delta
    )
    by_distance["cumulative_observations"] = (
        by_distance["observation_count"].cumsum()
    )

    threshold_row = by_distance.loc[
        by_distance["cumulative_capture"] >= target_capture
    ].iloc[0]

    return {
        "metric": metric,
        "threshold_key": f"{target_capture * 100:.0f}",
        "threshold_label": f"{target_capture * 100:.0f}% capture",
        "threshold_cm": float(threshold_row[DISTANCE_COLUMN]),
        "target_capture_percent": target_capture * 100,
        "actual_capture_percent": float(
            threshold_row["cumulative_capture"] * 100
        ),
        "observations_within_threshold": int(
            threshold_row["cumulative_observations"]
        ),
        "total_observations": len(metric_df),
        "observation_percent": float(
            threshold_row["cumulative_observations"] / len(metric_df) * 100
        ),
        "total_absolute_delta": float(total_absolute_delta),
    }


def find_fixed_distance_threshold(
    metric_df: pd.DataFrame,
    metric: str,
    threshold_cm: float = FIXED_THRESHOLD_CM,
) -> dict:
    """Summarize capture statistics at a fixed distance threshold."""
    absolute_column = f"Absolute_{metric}"
    total_absolute_delta = metric_df[absolute_column].sum()
    if total_absolute_delta <= 0:
        raise ValueError(f"{metric} contains no non-zero absolute differences")

    within_threshold = metric_df[metric_df[DISTANCE_COLUMN] <= threshold_cm]
    captured_absolute_delta = within_threshold[absolute_column].sum()

    return {
        "metric": metric,
        "threshold_key": f"{threshold_cm:g}cm",
        "threshold_label": f"fixed {threshold_cm:g} cm",
        "threshold_cm": threshold_cm,
        "target_capture_percent": np.nan,
        "actual_capture_percent": captured_absolute_delta / total_absolute_delta * 100,
        "observations_within_threshold": len(within_threshold),
        "total_observations": len(metric_df),
        "observation_percent": len(within_threshold) / len(metric_df) * 100,
        "total_absolute_delta": float(total_absolute_delta),
    }


def freedman_diaconis_bin_count(values: pd.Series) -> int:
    """Calculate a data-driven number of histogram-style distance buckets."""
    values = values.dropna().to_numpy()
    if len(values) < 2 or np.ptp(values) == 0:
        return 1

    q1, q3 = np.percentile(values, [25, 75])
    bin_width = 2 * (q3 - q1) / np.cbrt(len(values))
    if bin_width <= 0:
        return max(1, int(np.ceil(np.sqrt(len(values)))))

    return max(1, int(np.ceil(np.ptp(values) / bin_width)))


def create_bucket_summary(
    metric_df: pd.DataFrame,
    metric: str,
) -> tuple[pd.DataFrame, int]:
    """Summarize absolute dose differences in data-driven distance buckets."""
    absolute_column = f"Absolute_{metric}"
    dose_threshold_label = f"{ACCEPTABLE_DOSE_DIFF_GY[metric]:g}gy"
    dose_exceedance_count_column = (
        f"dose_diff_gt_{dose_threshold_label}_above_1cm_count"
    )
    dose_exceedance_percent_column = (
        f"dose_diff_gt_{dose_threshold_label}_above_1cm_percent"
    )
    bucket_count = freedman_diaconis_bin_count(metric_df[DISTANCE_COLUMN])

    if bucket_count == 1:
        bucket_ids = pd.Series(0, index=metric_df.index)
    else:
        bucket_ids = pd.cut(
            metric_df[DISTANCE_COLUMN],
            bins=bucket_count,
            labels=False,
            include_lowest=True,
        )

    bucket_df = metric_df.assign(bucket_id=bucket_ids)
    summary = (
        bucket_df.groupby("bucket_id", observed=True)
        .agg(
            distance_min_cm=(DISTANCE_COLUMN, "min"),
            distance_max_cm=(DISTANCE_COLUMN, "max"),
            observation_count=(absolute_column, "size"),
            sdsc_tol05_eq_1_count=("SDSC_tol05_equals_1", "sum"),
            mean_absolute_delta=(absolute_column, "mean"),
            median_absolute_delta=(absolute_column, "median"),
            absolute_delta_sum=(absolute_column, "sum"),
            **{
                dose_exceedance_count_column: (
                    "exceeds_acceptable_dose_diff_above_1cm",
                    "sum",
                )
            },
        )
        .reset_index(drop=True)
    )
    summary["sdsc_tol05_eq_1_percent"] = (
        summary["sdsc_tol05_eq_1_count"] / summary["observation_count"] * 100
    )
    summary[dose_exceedance_percent_column] = (
        summary[dose_exceedance_count_column]
        / summary["observation_count"]
        * 100
    )
    total_absolute_delta = summary["absolute_delta_sum"].sum()
    summary["bucket_capture_percent"] = (
        summary["absolute_delta_sum"] / total_absolute_delta * 100
    )
    summary["cumulative_capture_percent"] = (
        summary["absolute_delta_sum"].cumsum() / total_absolute_delta * 100
    )
    return summary, bucket_count


def calculate_correlation_for_subset(
    subset_df: pd.DataFrame,
    metric: str,
) -> dict:
    """Calculate Pearson and Spearman correlations for one subset."""
    absolute_column = f"Absolute_{metric}"
    x = subset_df[DISTANCE_COLUMN]
    y = subset_df[absolute_column]
    pearson = np.nan
    spearman = np.nan

    if len(subset_df) >= 2 and x.nunique() > 1 and y.nunique() > 1:
        pearson = float(pearsonr(x, y).statistic)
        spearman = float(spearmanr(x, y).statistic)

    return {
        "pearson": pearson,
        "spearman": spearman,
        "n": len(subset_df),
    }


def calculate_bin_correlations(
    metric_df: pd.DataFrame,
    metric: str,
    threshold_90_cm: float,
) -> dict[str, dict]:
    """Calculate correlations inside the three visual distance bins."""
    green_bucket_start = max(FIXED_THRESHOLD_CM, threshold_90_cm)
    bins = {
        "before_1cm": metric_df[
            metric_df[DISTANCE_COLUMN] <= FIXED_THRESHOLD_CM
        ],
        "between_1cm_and_90": metric_df[
            (metric_df[DISTANCE_COLUMN] > FIXED_THRESHOLD_CM)
            & (metric_df[DISTANCE_COLUMN] <= threshold_90_cm)
        ],
        "above_90": metric_df[
            metric_df[DISTANCE_COLUMN] > green_bucket_start
        ],
    }

    return {
        bin_name: calculate_correlation_for_subset(subset_df, metric)
        for bin_name, subset_df in bins.items()
    }


def format_correlation_pair(correlation: dict) -> str:
    """Format Pearson and Spearman coefficients for one summary cell."""
    pearson = correlation["pearson"]
    spearman = correlation["spearman"]
    if np.isnan(pearson) or np.isnan(spearman):
        return "Pearson=NA; Spearman=NA"
    return f"Pearson={pearson:.3f}; Spearman={spearman:.3f}"


def format_count_percent(count: int, total: int) -> str:
    """Format a count and percentage using the subset size as denominator."""
    if total <= 0:
        return "0 (0.0%)"
    return f"{count} ({count / total * 100:.1f}%)"


def count_sdsc_one_by_threshold(
    metric_df: pd.DataFrame,
    threshold_cm: float,
) -> dict[str, str]:
    """Count exact SDSC_tol05 == 1.0 rows up to and above a threshold."""
    subsets = {
        "up_to": metric_df[metric_df[DISTANCE_COLUMN] <= threshold_cm],
        "above": metric_df[metric_df[DISTANCE_COLUMN] > threshold_cm],
    }
    counts = {}

    for subset_name, subset_df in subsets.items():
        count = int(subset_df["SDSC_tol05_equals_1"].sum())
        counts[subset_name] = format_count_percent(count, len(subset_df))

    return counts


def count_dose_diff_exceedance_above_fixed_threshold(
    metric_df: pd.DataFrame,
) -> str:
    """Count points above the fixed distance and acceptable dose thresholds."""
    above_fixed = metric_df[metric_df[DISTANCE_COLUMN] > FIXED_THRESHOLD_CM]
    count = int(above_fixed["exceeds_acceptable_dose_diff_above_1cm"].sum())
    return format_count_percent(count, len(above_fixed))


def create_top_spearman_table(results_df: pd.DataFrame) -> pd.DataFrame:
    """Return the ten OARs with strongest mean absolute full-data Spearman."""
    analyzed = results_df[results_df["status"] == "analyzed"].copy()
    if analyzed.empty or "spearman_all_values" not in analyzed.columns:
        return pd.DataFrame()

    spearman_table = analyzed.pivot(
        index="OAR",
        columns="metric",
        values="spearman_all_values",
    ).rename(
        columns={
            "Delta_Dmean": "Spearman_Dmean",
            "Delta_Dmax": "Spearman_Dmax",
        }
    )
    required_columns = ["Spearman_Dmean", "Spearman_Dmax"]
    spearman_table = spearman_table.reindex(columns=required_columns).dropna()
    spearman_table["Mean_Absolute_Spearman"] = (
        spearman_table[required_columns].abs().mean(axis=1)
    )
    return (
        spearman_table.sort_values(
            "Mean_Absolute_Spearman",
            ascending=False,
        )
        .head(10)
        .reset_index()
    )


def parse_spearman_from_summary(value: object) -> float:
    """Extract a Spearman coefficient from a formatted correlation cell."""
    if not isinstance(value, str):
        return np.nan

    match = re.search(r"Spearman=([-+]?\d*\.?\d+)", value)
    if not match:
        return np.nan
    return float(match.group(1))


def create_top_bin_correlation_table(results_df: pd.DataFrame) -> pd.DataFrame:
    """Return the OARs with strongest accumulated bin-wise correlations."""
    analyzed = results_df[results_df["status"] == "analyzed"].copy()
    if analyzed.empty:
        return pd.DataFrame()

    correlation_columns = [
        "correlation_before_1cm_bin",
        "correlation_between_1cm_and_90_bin",
        "correlation_above_90_bin",
    ]
    available_columns = [
        column for column in correlation_columns if column in analyzed.columns
    ]
    if not available_columns:
        return pd.DataFrame()

    rows = []
    for oar_name, oar_df in analyzed.groupby("OAR", sort=True):
        row = {"OAR": oar_name}
        all_abs_spearman = []

        for metric, suffix in (
            ("Delta_Dmean", "Dmean"),
            ("Delta_Dmax", "Dmax"),
        ):
            metric_df = oar_df[oar_df["metric"] == metric]
            metric_abs_spearman = []
            if not metric_df.empty:
                metric_row = metric_df.iloc[0]
                for column in available_columns:
                    spearman = parse_spearman_from_summary(
                        metric_row[column]
                    )
                    if not np.isnan(spearman):
                        abs_spearman = abs(spearman)
                        metric_abs_spearman.append(abs_spearman)
                        all_abs_spearman.append(abs_spearman)

            row[f"{suffix}_mean_abs_bin_spearman"] = (
                float(np.mean(metric_abs_spearman))
                if metric_abs_spearman
                else np.nan
            )
            row[f"{suffix}_valid_bin_correlations"] = len(
                metric_abs_spearman
            )

        row["Accumulated_mean_abs_bin_spearman"] = (
            float(np.mean(all_abs_spearman))
            if all_abs_spearman
            else np.nan
        )
        row["Valid_bin_correlations_total"] = len(all_abs_spearman)
        rows.append(row)

    return (
        pd.DataFrame(rows)
        .dropna(subset=["Accumulated_mean_abs_bin_spearman"])
        .sort_values("Accumulated_mean_abs_bin_spearman", ascending=False)
        .head(20)
        .reset_index(drop=True)
    )


def create_scatterplot(
    metric_df: pd.DataFrame,
    metric: str,
    thresholds: list[dict],
    bin_correlations: dict[str, dict],
    output_file: Path,
    oar_name: str,
) -> None:
    """Create an absolute dose-difference scatterplot."""
    absolute_column = f"Absolute_{metric}"
    dose_threshold = ACCEPTABLE_DOSE_DIFF_GY[metric]
    fixed_threshold = FIXED_THRESHOLD_CM
    x_max = metric_df[DISTANCE_COLUMN].max()
    y_max = metric_df[absolute_column].max()
    capture_90_threshold = next(
        (
            threshold["threshold_cm"]
            for threshold in thresholds
            if threshold["threshold_key"] == "90"
        ),
        np.nan,
    )
    green_bucket_start = (
        max(fixed_threshold, capture_90_threshold)
        if not np.isnan(capture_90_threshold)
        else np.nan
    )

    fig, ax = plt.subplots(figsize=(12, 9))
    red_end = min(fixed_threshold, x_max)
    red_count = int((metric_df[DISTANCE_COLUMN] <= fixed_threshold).sum())
    if red_end > 0 and y_max > 0:
        ax.fill_between(
            [0, red_end],
            [0, 0],
            [y_max, y_max],
            color="red",
            alpha=0.20,
            label=f"distance <= {fixed_threshold:g} cm (N={red_count})",
            zorder=0,
        )
    if x_max > fixed_threshold and not np.isnan(capture_90_threshold):
        orange_start = fixed_threshold
        orange_end = min(capture_90_threshold, x_max)
        if orange_end > orange_start:
            orange_count = int(
                (
                    (metric_df[DISTANCE_COLUMN] > orange_start)
                    & (metric_df[DISTANCE_COLUMN] <= orange_end)
                    & (metric_df[absolute_column] <= dose_threshold)
                ).sum()
            )
            ax.fill_between(
                [orange_start, orange_end],
                [0, 0],
                [dose_threshold, dose_threshold],
                color="orange",
                alpha=0.20,
                label=(
                    f"{fixed_threshold:g} cm to 90% threshold "
                    f"and <= {dose_threshold:.0f} Gy (N={orange_count})"
                ),
                zorder=0,
            )

        if x_max > green_bucket_start:
            green_count = int(
                (
                    (metric_df[DISTANCE_COLUMN] > green_bucket_start)
                    & (metric_df[absolute_column] <= dose_threshold)
                ).sum()
            )
            ax.fill_between(
                [green_bucket_start, x_max],
                [0, 0],
                [dose_threshold, dose_threshold],
                color="green",
                alpha=0.20,
                label=(
                    f">90% threshold and <= {dose_threshold:.0f} Gy "
                    f"(N={green_count})"
                ),
                zorder=0,
            )

    ax.scatter(
        metric_df[DISTANCE_COLUMN],
        metric_df[absolute_column],
        s=12,
        alpha=0.25,
        edgecolors="none",
    )
    sdsc_one_df = metric_df[metric_df["SDSC_tol05_equals_1"]]
    if not sdsc_one_df.empty:
        ax.scatter(
            sdsc_one_df[DISTANCE_COLUMN],
            sdsc_one_df[absolute_column],
            marker="*",
            s=70,
            color="yellow",
            edgecolors="black",
            linewidths=0.5,
            alpha=0.95,
            label=f"{SDSC_COLUMN} = 1.0 (N={len(sdsc_one_df)})",
            zorder=5,
        )
    dose_exceedance_df = metric_df[
        metric_df["exceeds_acceptable_dose_diff_above_1cm"]
    ]
    if not dose_exceedance_df.empty and not np.isnan(green_bucket_start):
        green_triangle_df = dose_exceedance_df[
            dose_exceedance_df[DISTANCE_COLUMN] > green_bucket_start
        ]
        orange_triangle_df = dose_exceedance_df[
            dose_exceedance_df[DISTANCE_COLUMN] <= green_bucket_start
        ]
    else:
        green_triangle_df = dose_exceedance_df.iloc[0:0]
        orange_triangle_df = dose_exceedance_df

    if not orange_triangle_df.empty:
        ax.scatter(
            orange_triangle_df[DISTANCE_COLUMN],
            orange_triangle_df[absolute_column],
            marker="^",
            s=65,
            color="darkorange",
            edgecolors="black",
            linewidths=0.5,
            alpha=0.95,
            label=(
                f">{ACCEPTABLE_DOSE_DIFF_GY[metric]:.0f} Gy "
                f"and distance > {FIXED_THRESHOLD_CM:g} cm "
                f"before above-90% bucket "
                f"(N={len(orange_triangle_df)})"
            ),
            zorder=6,
        )
    if not green_triangle_df.empty:
        ax.scatter(
            green_triangle_df[DISTANCE_COLUMN],
            green_triangle_df[absolute_column],
            marker="^",
            s=65,
            color="green",
            edgecolors="black",
            linewidths=0.5,
            alpha=0.95,
            label=(
                f">{ACCEPTABLE_DOSE_DIFF_GY[metric]:.0f} Gy "
                f"in above-90% bucket "
                f"(N={len(green_triangle_df)})"
            ),
            zorder=6,
        )

    threshold_styles = {
        "90": ("green", "--"),
        f"{FIXED_THRESHOLD_CM:g}cm": ("red", "--"),
    }
    for threshold in thresholds:
        color, linestyle = threshold_styles.get(
            threshold["threshold_key"],
            ("purple", "-."),
        )
        threshold_cm = threshold["threshold_cm"]
        ax.axvline(
            threshold_cm,
            color=color,
            linestyle=linestyle,
            linewidth=2,
            label=(
                f"{threshold['threshold_label']} threshold: "
                f"{threshold_cm:.2f} cm"
            ),
        )

    if x_max > FIXED_THRESHOLD_CM:
        ax.hlines(
            dose_threshold,
            xmin=FIXED_THRESHOLD_CM,
            xmax=x_max,
            colors="darkorange",
            linestyles="-.",
            linewidth=2,
            label=(
                f"acceptable dose threshold: "
                f"{dose_threshold:.0f} Gy for distance > "
                f"{FIXED_THRESHOLD_CM:g} cm"
            ),
        )

    y_padding = max(y_max * 0.03, 0.1)
    ax.set_ylim(bottom=-y_padding)

    ax.set_title(
        f"{oar_name}: OAR-to-PTV Distance vs Absolute {metric} "
        f"(N={len(metric_df)})"
    )
    ax.set_xlabel("Distance from OAR to PTV (cm)")
    ax.set_ylabel(f"Absolute {metric}")
    ax.grid(alpha=0.2)

    correlation_lines = []
    for bin_name, bin_label in (
        ("before_1cm", f"<= {FIXED_THRESHOLD_CM:g} cm"),
        (
            "between_1cm_and_90",
            f"> {FIXED_THRESHOLD_CM:g} cm to 90%",
        ),
        ("above_90", "> 90%"),
    ):
        correlation = bin_correlations[bin_name]
        if (
            np.isnan(correlation["pearson"])
            or np.isnan(correlation["spearman"])
        ):
            coefficient_text = "Pearson=NA, Spearman=NA"
        else:
            coefficient_text = (
                f"Pearson={correlation['pearson']:.3f}, "
                f"Spearman={correlation['spearman']:.3f}"
            )

        correlation_lines.append(
            f"{bin_label} bin (n={correlation['n']}): {coefficient_text}"
        )

    handles, labels = ax.get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="upper left",
        bbox_to_anchor=(0.01, 0.89),
        ncol=2,
        fontsize=7,
        frameon=True,
    )
    fig.text(
        0.99,
        0.89,
        "\n".join(correlation_lines),
        ha="right",
        va="top",
        fontsize=8,
        bbox={
            "boxstyle": "round",
            "facecolor": "white",
            "alpha": 0.85,
            "edgecolor": "gray",
        },
    )
    fig.tight_layout(rect=(0, 0, 1, 0.82))
    fig.savefig(output_file, dpi=300)
    plt.close(fig)


def create_plain_scatterplot(
    metric_df: pd.DataFrame,
    metric: str,
    output_file: Path,
    oar_name: str,
    scatter_kwargs: dict | None = None,
) -> None:
    """Create an absolute dose-difference scatterplot without risk zones."""
    absolute_column = f"Absolute_{metric}"
    y_max = metric_df[absolute_column].max()

    fig, ax = plt.subplots(figsize=(12, 9))
    ax.scatter(
        metric_df[DISTANCE_COLUMN],
        metric_df[absolute_column],
        **(scatter_kwargs or dict(
            s=14, color="#08306b", alpha=0.6, edgecolors="none"
        )),
    )

    y_padding = max(y_max * 0.03, 0.1)
    ax.set_ylim(bottom=-y_padding)
    ax.set_title(
        f"{oar_name}: OAR-to-PTV Distance vs Absolute {metric} "
        f"(N={len(metric_df)})"
    )
    ax.set_xlabel("Distance from OAR to PTV (cm)")
    ax.set_ylabel(f"Absolute {metric}")
    ax.grid(alpha=0.2)

    fig.tight_layout()
    fig.savefig(output_file, dpi=300)
    plt.close(fig)


def run_analysis(
    input_file: str,
    output_dir: str,
    target_capture: float = 0.90,
    min_observations: int = 20,
) -> pd.DataFrame:
    """Run the threshold analysis separately for every OAR and dose metric."""
    input_path = resolve_input_path(input_file)
    output_path = resolve_output_path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    required_columns = [OAR_COLUMN, DISTANCE_COLUMN, SDSC_COLUMN, *DOSE_METRICS]
    df = pd.read_excel(input_path, usecols=required_columns)
    df = df.dropna(subset=[OAR_COLUMN])

    results = []
    for oar_name, oar_df in df.groupby(OAR_COLUMN, sort=True):
        oar_name = str(oar_name)
        oar_output_path = output_path / oar_name
        oar_output_path.mkdir(parents=True, exist_ok=True)
        oar_results = []

        for metric in DOSE_METRICS:
            metric_df = prepare_metric_data(oar_df, metric)
            if len(metric_df) < min_observations:
                skipped_result = {
                    "OAR": oar_name,
                    "metric": metric,
                    "status": "insufficient_observations",
                    "total_observations": len(metric_df),
                    "minimum_observations": min_observations,
                }
                results.append(skipped_result)
                oar_results.append(skipped_result)
                print(
                    f"Skipping {oar_name} {metric}: only "
                    f"{len(metric_df)} valid observations"
                )
                continue

            try:
                thresholds = [
                    find_capture_threshold(metric_df, metric, target_capture)
                ]
                thresholds.append(
                    find_fixed_distance_threshold(
                        metric_df,
                        metric,
                        FIXED_THRESHOLD_CM,
                    )
                )
            except ValueError as error:
                skipped_result = {
                    "OAR": oar_name,
                    "metric": metric,
                    "status": "no_nonzero_dose_differences",
                    "total_observations": len(metric_df),
                    "minimum_observations": min_observations,
                }
                results.append(skipped_result)
                oar_results.append(skipped_result)
                print(f"Skipping {oar_name} {metric}: {error}")
                continue

            bucket_summary, bucket_count = create_bucket_summary(
                metric_df,
                metric,
            )
            threshold_summary = {
                "OAR": oar_name,
                "metric": metric,
                "status": "analyzed",
                "minimum_observations": min_observations,
                "total_observations": len(metric_df),
                "total_absolute_delta": thresholds[0]["total_absolute_delta"],
                "distance_bucket_count": bucket_count,
            }
            all_values_correlation = calculate_correlation_for_subset(
                metric_df,
                metric,
            )
            threshold_90_cm = next(
                threshold["threshold_cm"]
                for threshold in thresholds
                if threshold["threshold_key"] == "90"
            )
            bin_correlations = calculate_bin_correlations(
                metric_df,
                metric,
                threshold_90_cm,
            )
            threshold_summary.update({
                "pearson_all_values": all_values_correlation["pearson"],
                "spearman_all_values": all_values_correlation["spearman"],
                "correlation_before_1cm_bin": (
                    format_correlation_pair(bin_correlations["before_1cm"])
                ),
                "correlation_between_1cm_and_90_bin": (
                    format_correlation_pair(
                        bin_correlations["between_1cm_and_90"]
                    )
                ),
                "correlation_above_90_bin": (
                    format_correlation_pair(bin_correlations["above_90"])
                ),
                (
                    "dose_diff_gt_"
                    f"{ACCEPTABLE_DOSE_DIFF_GY[metric]:g}gy_above_1cm"
                ): (
                    count_dose_diff_exceedance_above_fixed_threshold(
                        metric_df
                    )
                ),
            })
            for threshold in thresholds:
                threshold_key = threshold["threshold_key"]
                sdsc_counts = count_sdsc_one_by_threshold(
                    metric_df,
                    threshold["threshold_cm"],
                )
                threshold_summary.update({
                    f"threshold_{threshold_key}_cm": (
                        threshold["threshold_cm"]
                    ),
                    f"actual_capture_{threshold_key}_percent": (
                        threshold["actual_capture_percent"]
                    ),
                    f"observations_within_{threshold_key}_threshold": (
                        threshold["observations_within_threshold"]
                    ),
                    f"observation_{threshold_key}_percent": (
                        threshold["observation_percent"]
                    ),
                    f"sdsc_tol05_eq_1_up_to_{threshold_key}_threshold": (
                        sdsc_counts["up_to"]
                    ),
                    f"sdsc_tol05_eq_1_above_{threshold_key}_threshold": (
                        sdsc_counts["above"]
                    ),
                })

            results.append(threshold_summary)
            oar_results.append(threshold_summary)

            bucket_summary.to_csv(
                oar_output_path / f"{metric}_distance_buckets.csv",
                index=False,
            )
            create_scatterplot(
                metric_df,
                metric,
                thresholds,
                bin_correlations,
                oar_output_path / f"{metric}_distance_scatterplot.png",
                oar_name,
            )
            create_plain_scatterplot(
                metric_df,
                metric,
                oar_output_path / f"{metric}_distance_scatterplot_plain.png",
                oar_name,
            )

            for threshold in thresholds:
                target_text = (
                    f"{threshold['target_capture_percent']:.2f}%"
                    if not np.isnan(threshold["target_capture_percent"])
                    else threshold["threshold_label"]
                )
                print(
                    f"{oar_name} {metric}: "
                    f"{threshold['actual_capture_percent']:.2f}% of total "
                    f"absolute dose difference is within "
                    f"{threshold['threshold_cm']:.2f} cm ({target_text})"
                )

        if oar_results:
            save_summary_excel(
                pd.DataFrame(oar_results),
                oar_output_path / "distance_threshold_summary.xlsx",
            )

    results_df = pd.DataFrame(results)
    if not results_df.empty:
        column_order = [
            "OAR",
            *[column for column in results_df.columns if column != "OAR"],
        ]
        results_df = results_df.reindex(columns=column_order)
    top_spearman_df = create_top_spearman_table(results_df)
    top_bin_correlation_df = create_top_bin_correlation_table(results_df)
    save_summary_excel(
        results_df,
        output_path / "distance_threshold_summary_per_oar.xlsx",
        extra_sheets={
            "Top_10_Spearman": top_spearman_df,
            "Top_20_Bin_Correlations": top_bin_correlation_df,
        },
    )
    if not top_spearman_df.empty:
        print("\nTop 10 OARs by mean absolute Spearman correlation:")
        print(top_spearman_df.to_string(index=False))
    if not top_bin_correlation_df.empty:
        print("\nTop 20 OARs by accumulated bin-wise Spearman correlation:")
        print(top_bin_correlation_df.to_string(index=False))
    return results_df


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Plot absolute dose differences against OAR-to-PTV distance and "
            "find the minimum distance capturing a target percentage."
        )
    )
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
    )
    parser.add_argument(
        "--capture",
        type=float,
        default=0.90,
        help="Primary capture fraction between 0 and 1 (default: 0.90)",
    )
    parser.add_argument(
        "--min-observations",
        type=int,
        default=20,
        help="Minimum valid observations required per OAR and metric (default: 20)",
    )
    args = parser.parse_args()
    if not 0 < args.capture <= 1:
        parser.error("--capture must be greater than 0 and at most 1")
    if args.min_observations < 1:
        parser.error("--min-observations must be at least 1")
    return args


def main() -> None:
    args = parse_args()
    run_analysis(
        args.input,
        args.output_dir,
        args.capture,
        args.min_observations,
    )


if __name__ == "__main__":
    main()
