"""
Compare the previous and current APL temporal lineplot calculations.

Previous implementation:
- Complete rows only
- OARs listed in explore_results.REGIONS only
- Valid Clinical_RTSTRUCT_Date
- Valid APL_tol05 and APL_tol3
- Monthly bins using YearMonth
- Date range 2024-12 through 2025-06

Current implementation:
- Same filters and monthly-bin averaging
- Date range 2024-12 through 2025-05

Outputs are written to explore_results/Overall.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "pyAPL"))

from explore_results import REGIONS  # noqa: E402


RESULTS_FILE = PROJECT_ROOT / "contour_comparison_results_P0728_v7.xlsx"
OUTPUT_DIR = PROJECT_ROOT / "explore_results" / "Overall"


def _prepare_apl_data(results_file: Path = RESULTS_FILE) -> pd.DataFrame:
    """Apply the shared filters used by the APL temporal lineplot."""
    df = pd.read_excel(results_file, engine="openpyxl")

    if "ChainStatus" in df.columns:
        df = df[df["ChainStatus"] == "Complete"].copy()
    else:
        df = df.copy()

    all_oars = [oar for oars in REGIONS.values() for oar in oars]
    if "VOIName" in df.columns:
        df = df[df["VOIName"].isin(all_oars)].copy()

    df = df.dropna(subset=["Clinical_RTSTRUCT_Date"])
    df["Clinical_RTSTRUCT_Date"] = pd.to_datetime(
        df["Clinical_RTSTRUCT_Date"].astype(int).astype(str),
        format="%Y%m%d",
        errors="coerce",
    )
    df = df.dropna(subset=["Clinical_RTSTRUCT_Date"])
    df = df.dropna(subset=["APL_tol05", "APL_tol3"])
    df["YearMonth"] = df["Clinical_RTSTRUCT_Date"].dt.to_period("M")
    return df


def calculate_monthly_apl(
    df: pd.DataFrame,
    start_month: str,
    end_month: str,
) -> pd.DataFrame:
    """Calculate the monthly-bin APL means for a specific date window."""
    window_df = df[
        (df["YearMonth"] >= start_month)
        & (df["YearMonth"] <= end_month)
    ].copy()

    monthly_stats = window_df.groupby("YearMonth").agg({
        "APL_tol05": ["mean", "std", "count"],
        "APL_tol3": ["mean", "std", "count"],
    }).reset_index()

    monthly_stats.columns = [
        "YearMonth",
        "APL05_mean",
        "APL05_std",
        "APL05_count",
        "APL3_mean",
        "APL3_std",
        "APL3_count",
    ]
    monthly_stats["Date"] = monthly_stats["YearMonth"].dt.to_timestamp()
    return monthly_stats


def save_apl_plot(monthly_stats: pd.DataFrame, output_file: Path, title: str) -> None:
    """Save an APL temporal plot from monthly-bin statistics."""
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(
        monthly_stats["Date"],
        monthly_stats["APL05_mean"],
        marker="o",
        linewidth=2,
        markersize=6,
        label="APL (tol=0.5mm)",
        color="#2E86AB",
        alpha=0.8,
    )
    ax.plot(
        monthly_stats["Date"],
        monthly_stats["APL3_mean"],
        marker="s",
        linewidth=2,
        markersize=6,
        label="APL (tol=3mm)",
        color="#A23B72",
        alpha=0.8,
    )

    ax.set_xlabel("Month", fontsize=12, fontweight="bold")
    ax.set_ylabel("Average Added Path Length (mm)", fontsize=12, fontweight="bold")
    ax.set_title(title, fontsize=14, fontweight="bold", pad=20)
    ax.legend(fontsize=11, frameon=True, fancybox=True, shadow=True)
    ax.grid(True, alpha=0.3, linestyle="--")
    ax.set_ylim(bottom=0)

    import matplotlib.dates as mdates

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.xaxis.set_major_locator(
        mdates.MonthLocator(interval=max(1, len(monthly_stats) // 12))
    )
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches="tight")
    plt.close()


def build_comparison() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return old monthly stats, current monthly stats, and their comparison."""
    df = _prepare_apl_data()
    old_stats = calculate_monthly_apl(df, "2024-12", "2025-06")
    current_stats = calculate_monthly_apl(df, "2024-12", "2025-05")

    comparison = old_stats.merge(
        current_stats,
        on="YearMonth",
        how="outer",
        suffixes=("_old", "_current"),
    ).sort_values("YearMonth")

    for metric in ("APL05", "APL3"):
        comparison[f"{metric}_mean_difference_current_minus_old"] = (
            comparison[f"{metric}_mean_current"]
            - comparison[f"{metric}_mean_old"]
        )

    return old_stats, current_stats, comparison


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    old_stats, current_stats, comparison = build_comparison()

    old_plot = OUTPUT_DIR / "apl_temporal_lineplot_old_2024-12_to_2025-06.png"
    current_plot = OUTPUT_DIR / "apl_temporal_lineplot_current_2024-12_to_2025-05.png"
    comparison_xlsx = OUTPUT_DIR / "apl_temporal_old_vs_current_comparison.xlsx"

    save_apl_plot(
        old_stats,
        old_plot,
        "APL Temporal Trends: Monthly Averages",
    )
    save_apl_plot(
        current_stats,
        current_plot,
        "APL Temporal Trends: Monthly Averages (2024-12 to 2025-05)",
    )

    with pd.ExcelWriter(comparison_xlsx, engine="openpyxl") as writer:
        old_stats.to_excel(writer, sheet_name="old_2024-12_to_2025-06", index=False)
        current_stats.to_excel(
            writer,
            sheet_name="current_2024-12_to_2025-05",
            index=False,
        )
        comparison.to_excel(writer, sheet_name="comparison", index=False)

    print("Old monthly-bin averages:")
    print(old_stats[["YearMonth", "APL05_mean", "APL05_count", "APL3_mean", "APL3_count"]].to_string(index=False))
    print("\nCurrent monthly-bin averages:")
    print(current_stats[["YearMonth", "APL05_mean", "APL05_count", "APL3_mean", "APL3_count"]].to_string(index=False))
    print("\nOutputs:")
    print(f"  {old_plot}")
    print(f"  {current_plot}")
    print(f"  {comparison_xlsx}")


if __name__ == "__main__":
    main()
