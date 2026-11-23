"""
Categorize OAR risk levels in statistical_analysis_results.xlsx.

The script reads the "Acceptable" sheet and appends/replaces a worksheet named
"risk categorization" in the same workbook.
"""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_WORKBOOK = "statistical_analysis_results.xlsx"
DEFAULT_RESULTS = "contour_comparison_results_P0728_v7.xlsx"
SOURCE_SHEET = "Acceptable"
OUTPUT_SHEET = "risk categorization"
PERCENTILE_OUTPUT_SHEET = "risk categorization P5-P95"
PERCENTILE_NONZERO_OUTPUT_SHEET = "risk cat P5-P95 nonzero"  # Excel max 31 chars
# Worst absolute 5th/95th percentile delta (Gy) per risk class, lowest class first.
# Anything above the last limit also falls in the last (highest) class.
PERCENTILE_RISK_LIMITS_GY = (
    (1.0, "Low risk"),
    (3.0, "Medium risk"),
    (5.0, "High risk"),
)
MIN_OAR_OBSERVATIONS = 20
FINAL_MIN_OAR_OBSERVATIONS = 50  # final results section: N > 49
REQUIRED_COLUMNS = [
    "OAR",
    "sDSC_tol0_5_Mean",
    "Boxplot_Min_Max_Range_Dmean",
    "Boxplot_Min_Max_Range_Dmax",
]


def resolve_workbook_path(workbook: str) -> Path:
    """Resolve a workbook path from common project locations."""
    path = Path(workbook)
    script_dir = Path(__file__).resolve().parent
    candidates = [
        path,
        Path.cwd() / path,
        script_dir / path,
        script_dir.parent / path,
    ]

    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()

    raise FileNotFoundError(f"Workbook not found: {workbook}")


def workbook_has_required_columns(workbook_path: Path) -> bool:
    """Check whether the source sheet contains the columns needed now."""
    try:
        source_columns = pd.read_excel(
            workbook_path,
            sheet_name=SOURCE_SHEET,
            nrows=0,
        ).columns
    except Exception:
        return False
    return all(column in source_columns for column in REQUIRED_COLUMNS)


def resolve_current_workbook_path(workbook: str) -> Path:
    """Prefer the requested workbook, unless its source sheet is stale."""
    workbook_path = resolve_workbook_path(workbook)
    if workbook_has_required_columns(workbook_path):
        return workbook_path

    updated_path = workbook_path.with_name(
        f"{workbook_path.stem}_updated{workbook_path.suffix}"
    )
    if updated_path.is_file() and workbook_has_required_columns(updated_path):
        print(
            f"{workbook_path.name} does not contain the current boxplot range "
            f"columns; using {updated_path.name} instead."
        )
        return updated_path

    return workbook_path


def parse_boxplot_range_span(value: object) -> float:
    """Parse "min to max" and return the boxplot whisker span in Gy."""
    if pd.isna(value):
        return np.nan
    if isinstance(value, (int, float, np.number)):
        return abs(float(value))

    numbers = re.findall(r"[-+]?\d*\.?\d+", str(value))
    if len(numbers) < 2:
        return np.nan
    range_min, range_max = float(numbers[0]), float(numbers[1])
    return abs(range_max - range_min)


def categorize_dose_risk(dmean_span: float, dmax_span: float) -> int:
    """Assign dose risk from the worst Dmean/Dmax boxplot min-max span."""
    if any(pd.isna(value) for value in (dmean_span, dmax_span)):
        return 0

    max_span = max(dmean_span, dmax_span)
    if 0 <= max_span <= 0.5:
        return 1
    if max_span <= 1:
        return 2
    return 3


def categorize_risk(
    sdsc_tol05: float,
    dmean_span: float,
    dmax_span: float,
) -> str:
    """Assign final risk category from dose span first, then sDSC."""
    if any(pd.isna(value) for value in (sdsc_tol05, dmean_span, dmax_span)):
        return "Uncategorized"

    dose_risk = categorize_dose_risk(dmean_span, dmax_span)
    if dose_risk == 1:
        return "Risk class 1"
    if dose_risk == 2:
        return "Risk class 3" if sdsc_tol05 < 0.8 else "Risk class 2"
    if dose_risk == 3:
        return "Risk class 3"
    return "Uncategorized"


def categorize_reason(
    sdsc_tol05: float,
    dmean_span: float,
    dmax_span: float,
) -> str:
    """Return a compact explanation for the assigned category."""
    if any(pd.isna(value) for value in (sdsc_tol05, dmean_span, dmax_span)):
        return "Missing sDSC or boxplot range value"

    dose_risk = categorize_dose_risk(dmean_span, dmax_span)
    max_span = max(dmean_span, dmax_span)
    if dose_risk == 1:
        return f"Dose span {max_span:.3f} Gy is 0-0.5 Gy; sDSC does not alter class 1"
    if dose_risk == 2 and sdsc_tol05 < 0.8:
        return f"Dose span {max_span:.3f} Gy is 0.5-1 Gy and sDSC < 0.8; upgraded to class 3"
    if dose_risk == 2:
        return f"Dose span {max_span:.3f} Gy is 0.5-1 Gy and sDSC >= 0.8; remains class 2"
    if dose_risk == 3:
        return f"Dose span {max_span:.3f} Gy is >1 Gy; sDSC does not alter class 3"
    return "Dose span could not be categorized"


def parse_median_percentile_range(value: object) -> tuple[float, float, float]:
    """Parse "median (p5 to p95)" and return (median, p5, p95)."""
    if pd.isna(value):
        return (np.nan, np.nan, np.nan)

    numbers = re.findall(r"[-+]?\d*\.?\d+", str(value))
    if len(numbers) < 3:
        return (np.nan, np.nan, np.nan)
    return (float(numbers[0]), float(numbers[1]), float(numbers[2]))


def categorize_percentile_risk(max_abs_percentile: float) -> str:
    """Assign risk from the worst absolute 5th/95th percentile delta in Gy."""
    if pd.isna(max_abs_percentile):
        return "Uncategorized"
    for limit, category in PERCENTILE_RISK_LIMITS_GY:
        if max_abs_percentile <= limit:
            return category
    # Anything wider than the last limit is merged into the highest risk class
    return PERCENTILE_RISK_LIMITS_GY[-1][1]


def build_percentile_risk_categorization(
    dmean_df: pd.DataFrame,
    dmax_df: pd.DataFrame,
    nonzero: bool = False,
) -> pd.DataFrame:
    """
    Categorize OARs on the 5th-95th percentile range of Delta Dmean and Delta Dmax.

    Low risk: both ranges within -1 to 1 Gy. Medium risk: within -3 to 3 Gy.
    High risk: everything wider (the -5 to 5 Gy class and beyond).

    With nonzero=True the percentiles are taken over patients with a delta != 0 only.
    An OAR whose deltas are all exactly 0 has no spread and is Low risk.
    """
    median_columns = {
        "Dmean": "Median_P5_P95_NonZero_Dmean" if nonzero else "Median_Delta_Dmean",
        "Dmax": "Median_P5_P95_NonZero_Dmax" if nonzero else "Median_Delta_Dmax",
    }
    sheets = {"Dmean": ("Per_OAR_Dmean", dmean_df), "Dmax": ("Per_OAR_Dmax", dmax_df)}
    extra_columns = ["Pct_Zero", "N_NonZero"] if nonzero else []

    merged = None
    for label, (sheet_name, sheet_df) in sheets.items():
        median_column = median_columns[label]
        required = ["OAR", "N", median_column] + [
            f"{column}_{label}" for column in extra_columns
        ]
        missing = [column for column in required if column not in sheet_df.columns]
        if missing:
            raise ValueError(
                f"Missing required columns in {sheet_name}: {', '.join(missing)}. "
                "Re-run statistical_analysis.py to regenerate the workbook."
            )

        parsed = sheet_df[median_column].apply(parse_median_percentile_range)
        part = pd.DataFrame({
            "OAR": sheet_df["OAR"],
            f"N_{label}": pd.to_numeric(sheet_df["N"], errors="coerce"),
            f"Median_P5_P95_{label}": sheet_df[median_column],
            f"P5_{label}": parsed.str[1],
            f"P95_{label}": parsed.str[2],
        })
        for column in extra_columns:
            part[f"{column}_{label}"] = pd.to_numeric(
                sheet_df[f"{column}_{label}"], errors="coerce"
            )
        merged = part if merged is None else merged.merge(part, on="OAR", how="outer")

    if nonzero:
        # No non-zero deltas means perfect agreement: no spread to categorize
        for label in ("Dmean", "Dmax"):
            all_zero = merged[f"N_NonZero_{label}"] == 0
            merged.loc[all_zero, [f"P5_{label}", f"P95_{label}"]] = 0.0
    elif merged[["P5_Dmean", "P95_Dmean", "P5_Dmax", "P95_Dmax"]].isna().all().all():
        raise ValueError(
            "No 'median (p5 to p95)' values found in Median_Delta_Dmean/Dmax. "
            "Re-run statistical_analysis.py to regenerate the workbook."
        )

    merged = merged[
        (merged["N_Dmean"] >= MIN_OAR_OBSERVATIONS)
        & (merged["N_Dmax"] >= MIN_OAR_OBSERVATIONS)
    ].copy()
    merged["Final_Results_N_gt_49"] = (
        (merged["N_Dmean"] >= FINAL_MIN_OAR_OBSERVATIONS)
        & (merged["N_Dmax"] >= FINAL_MIN_OAR_OBSERVATIONS)
    )

    dmean_worst = merged[["P5_Dmean", "P95_Dmean"]].abs().max(axis=1, skipna=False)
    dmax_worst = merged[["P5_Dmax", "P95_Dmax"]].abs().max(axis=1, skipna=False)
    merged["Risk_Dmean"] = dmean_worst.apply(categorize_percentile_risk)
    merged["Risk_Dmax"] = dmax_worst.apply(categorize_percentile_risk)

    order = {
        category: rank
        for rank, category in enumerate(
            [name for _, name in PERCENTILE_RISK_LIMITS_GY] + ["Uncategorized"]
        )
    }
    inverse_order = {rank: category for category, rank in order.items()}

    # The OAR gets the higher risk class of Dmean and Dmax
    category_column = (
        "Risk_Category_P5_P95_NonZero" if nonzero else "Risk_Category_P5_P95"
    )
    merged["_rank"] = np.maximum(
        merged["Risk_Dmean"].map(order), merged["Risk_Dmax"].map(order)
    )
    merged[category_column] = merged["_rank"].map(inverse_order)
    merged = merged.sort_values(["_rank", "OAR"]).drop(columns="_rank")

    output_columns = [
        "OAR",
        category_column,
        "Median_P5_P95_Dmean",
        "Risk_Dmean",
        "Median_P5_P95_Dmax",
        "Risk_Dmax",
        "N_Dmean",
        "N_Dmax",
        "Final_Results_N_gt_49",
    ]
    if nonzero:
        output_columns += [
            "Pct_Zero_Dmean",
            "Pct_Zero_Dmax",
            "N_NonZero_Dmean",
            "N_NonZero_Dmax",
        ]
    output_columns += [
        "P5_Dmean",
        "P95_Dmean",
        "P5_Dmax",
        "P95_Dmax",
    ]
    return merged[output_columns]


def build_risk_categorization(
    source_df: pd.DataFrame,
    dmean_df: pd.DataFrame,
    dmax_df: pd.DataFrame,
) -> pd.DataFrame:
    """Build the risk categorization table from the Acceptable sheet."""
    missing_columns = [
        column for column in REQUIRED_COLUMNS if column not in source_df.columns
    ]
    if missing_columns:
        raise ValueError(
            "Missing required columns in "
            f"{SOURCE_SHEET}: {', '.join(missing_columns)}"
        )

    for sheet_name, sheet_df in (
        ("Per_OAR_Dmean", dmean_df),
        ("Per_OAR_Dmax", dmax_df),
    ):
        missing_n_columns = [
            column for column in ("OAR", "N") if column not in sheet_df.columns
        ]
        if missing_n_columns:
            raise ValueError(
                f"Missing required columns in {sheet_name}: "
                f"{', '.join(missing_n_columns)}"
            )

    risk_df = source_df[REQUIRED_COLUMNS].copy()
    dmean_n = dmean_df[["OAR", "N"]].rename(columns={"N": "N_Dmean"})
    dmax_n = dmax_df[["OAR", "N"]].rename(columns={"N": "N_Dmax"})
    risk_df = risk_df.merge(dmean_n, on="OAR", how="left")
    risk_df = risk_df.merge(dmax_n, on="OAR", how="left")
    risk_df["N_Dmean"] = pd.to_numeric(risk_df["N_Dmean"], errors="coerce")
    risk_df["N_Dmax"] = pd.to_numeric(risk_df["N_Dmax"], errors="coerce")
    risk_df = risk_df[
        (risk_df["N_Dmean"] >= MIN_OAR_OBSERVATIONS)
        & (risk_df["N_Dmax"] >= MIN_OAR_OBSERVATIONS)
    ].copy()
    risk_df["Final_Results_N_gt_49"] = (
        (risk_df["N_Dmean"] >= FINAL_MIN_OAR_OBSERVATIONS)
        & (risk_df["N_Dmax"] >= FINAL_MIN_OAR_OBSERVATIONS)
    )
    risk_df["sDSC_tol0_5_Mean"] = pd.to_numeric(
        risk_df["sDSC_tol0_5_Mean"],
        errors="coerce",
    )
    risk_df["Boxplot_Dmean_Span_Gy"] = risk_df[
        "Boxplot_Min_Max_Range_Dmean"
    ].apply(parse_boxplot_range_span)
    risk_df["Boxplot_Dmax_Span_Gy"] = risk_df[
        "Boxplot_Min_Max_Range_Dmax"
    ].apply(parse_boxplot_range_span)
    risk_df["Dose_Risk_Class"] = risk_df.apply(
        lambda row: categorize_dose_risk(
            row["Boxplot_Dmean_Span_Gy"],
            row["Boxplot_Dmax_Span_Gy"],
        ),
        axis=1,
    )
    risk_df["Risk_Category"] = risk_df.apply(
        lambda row: categorize_risk(
            row["sDSC_tol0_5_Mean"],
            row["Boxplot_Dmean_Span_Gy"],
            row["Boxplot_Dmax_Span_Gy"],
        ),
        axis=1,
    )
    risk_df["Risk_Rule"] = risk_df.apply(
        lambda row: categorize_reason(
            row["sDSC_tol0_5_Mean"],
            row["Boxplot_Dmean_Span_Gy"],
            row["Boxplot_Dmax_Span_Gy"],
        ),
        axis=1,
    )

    return risk_df[
        [
            "OAR",
            "Risk_Category",
            "Risk_Rule",
            "N_Dmean",
            "N_Dmax",
            "Final_Results_N_gt_49",
            "sDSC_tol0_5_Mean",
            "Dose_Risk_Class",
            "Boxplot_Min_Max_Range_Dmean",
            "Boxplot_Dmean_Span_Gy",
            "Boxplot_Min_Max_Range_Dmax",
            "Boxplot_Dmax_Span_Gy",
        ]
    ].sort_values(["Risk_Category", "OAR"])


def save_risk_sheets(
    workbook_path: Path,
    sheets: dict[str, pd.DataFrame],
) -> Path:
    """Append or replace the risk categorization sheets in the workbook."""
    def write_sheet(path: Path) -> None:
        with pd.ExcelWriter(
            path,
            engine="openpyxl",
            mode="a",
            if_sheet_exists="replace",
        ) as writer:
            for sheet_name, sheet_df in sheets.items():
                sheet_df.to_excel(writer, sheet_name=sheet_name, index=False)

    try:
        write_sheet(workbook_path)
        return workbook_path
    except PermissionError:
        fallback_path = workbook_path.with_name(
            f"{workbook_path.stem}_updated{workbook_path.suffix}"
        )
        shutil.copy2(workbook_path, fallback_path)
        write_sheet(fallback_path)
        print(
            f"Could not overwrite open workbook {workbook_path.name}; "
            f"saved as {fallback_path.name}"
        )
        return fallback_path


def add_region_column(
    table: pd.DataFrame,
    dmean_df: pd.DataFrame,
    dmax_df: pd.DataFrame,
) -> pd.DataFrame:
    """Insert the anatomical Region (from the per-OAR sheets) after the OAR column."""
    regions = pd.concat(
        [frame[["OAR", "Region"]] for frame in (dmean_df, dmax_df)
         if "Region" in frame.columns]
    ).drop_duplicates("OAR").set_index("OAR")["Region"]
    table = table.copy()
    table.insert(1, "Region", table["OAR"].map(regions))
    return table


def add_wilcoxon_columns(
    table: pd.DataFrame,
    dmean_df: pd.DataFrame,
    dmax_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Add the Wilcoxon signed-rank results from the per-OAR sheets.

    Wilcoxon_Significant is "Yes" when ΔDmean and/or ΔDmax differs significantly
    from 0 (p < 0.05, test from statistical_analysis.py). Columns are inserted after
    Risk_Dmax when present, otherwise appended.
    """
    wilcoxon_columns = {
        "Dmean": (dmean_df, ["P_value_Dmean", "Significant_Dmean"]),
        "Dmax": (dmax_df, ["P_value_Dmax", "Significant_Dmax"]),
    }
    table = table.copy()
    new_columns = {}
    for label, (frame, columns) in wilcoxon_columns.items():
        missing = [column for column in columns if column not in frame.columns]
        if missing:
            raise ValueError(
                f"Missing Wilcoxon columns in Per_OAR_{label}: {', '.join(missing)}"
            )
        lookup = frame.drop_duplicates("OAR").set_index("OAR")
        for column in columns:
            new_columns[column] = table["OAR"].map(lookup[column])

    significant = (
        new_columns["Significant_Dmean"].fillna(False).astype(bool)
        | new_columns["Significant_Dmax"].fillna(False).astype(bool)
    )
    ordered = {
        "Wilcoxon_Significant": significant.map({True: "Yes", False: "No"}),
        "P_value_Dmean": new_columns["P_value_Dmean"],
        "Significant_Dmean": new_columns["Significant_Dmean"],
        "P_value_Dmax": new_columns["P_value_Dmax"],
        "Significant_Dmax": new_columns["Significant_Dmax"],
    }
    position = (
        table.columns.get_loc("Risk_Dmax") + 1
        if "Risk_Dmax" in table.columns
        else len(table.columns)
    )
    for offset, (name, values) in enumerate(ordered.items()):
        table.insert(position + offset, name, values)
    return table


def add_threshold_exceedance_columns(
    table: pd.DataFrame,
    results_df: pd.DataFrame,
    category_column: str,
) -> pd.DataFrame:
    """
    Report the % of cases whose delta falls outside the range of the OAR's risk class.

    The range is -1 to 1 Gy for Low, -3 to 3 Gy for Medium and -5 to 5 Gy for High
    risk. A row is counted when its ΔDmean or ΔDmax is below the lower or above the
    upper bound (i.e. |delta| > limit), so both directions are included.
    Columns are inserted after Significant_Dmax when present, otherwise appended.
    """
    limits = {name: limit for limit, name in PERCENTILE_RISK_LIMITS_GY}
    thresholds = table[category_column].map(limits)

    new_columns = {
        "Risk_Range_Gy": thresholds.apply(
            lambda limit: f"-{limit:g} to {limit:g}" if pd.notna(limit) else ""
        )
    }
    for label in ("Dmean", "Dmax"):
        values = results_df[["VOIName", f"Delta_{label}"]].dropna()
        values[f"Delta_{label}"] = pd.to_numeric(
            values[f"Delta_{label}"], errors="coerce"
        ).abs()
        grouped = values.groupby("VOIName")[f"Delta_{label}"]
        n_valid = table["OAR"].map(grouped.size())
        n_exceed = pd.Series(
            [
                int((grouped.get_group(oar) > limit).sum())
                if pd.notna(limit) and oar in grouped.groups
                else np.nan
                for oar, limit in zip(table["OAR"], thresholds)
            ],
            index=table.index,
        )
        new_columns[f"Pct_Outside_Range_{label}"] = (
            100.0 * n_exceed / n_valid
        ).round(1)

    table = table.copy()
    position = (
        table.columns.get_loc("Significant_Dmax") + 1
        if "Significant_Dmax" in table.columns
        else len(table.columns)
    )
    for offset, (name, column) in enumerate(new_columns.items()):
        table.insert(position + offset, name, column)
    return table


def run(
    workbook: str = DEFAULT_WORKBOOK,
    results: str = DEFAULT_RESULTS,
) -> pd.DataFrame:
    """Create the risk categorization sheet and return the result table."""
    workbook_path = resolve_current_workbook_path(workbook)
    source_df = pd.read_excel(workbook_path, sheet_name=SOURCE_SHEET)
    dmean_df = pd.read_excel(workbook_path, sheet_name="Per_OAR_Dmean")
    dmax_df = pd.read_excel(workbook_path, sheet_name="Per_OAR_Dmax")
    risk_df = add_wilcoxon_columns(
        add_region_column(
            build_risk_categorization(source_df, dmean_df, dmax_df),
            dmean_df,
            dmax_df,
        ),
        dmean_df,
        dmax_df,
    )
    sheets = {OUTPUT_SHEET: risk_df}
    try:
        results_df = pd.read_excel(
            resolve_workbook_path(results),
            usecols=["VOIName", "Delta_Dmean", "Delta_Dmax"],
        )
    except (FileNotFoundError, ValueError) as error:
        results_df = None
        print(f"Skipping threshold exceedance columns: {error}")
    percentile_tables = {}
    for sheet_name, nonzero, category_column in (
        (PERCENTILE_OUTPUT_SHEET, False, "Risk_Category_P5_P95"),
        (PERCENTILE_NONZERO_OUTPUT_SHEET, True, "Risk_Category_P5_P95_NonZero"),
    ):
        try:
            table = build_percentile_risk_categorization(
                dmean_df, dmax_df, nonzero=nonzero
            )
        except ValueError as error:
            print(f"Skipping '{sheet_name}': {error}")
            continue
        table = add_wilcoxon_columns(
            add_region_column(table, dmean_df, dmax_df), dmean_df, dmax_df
        )
        if results_df is not None:
            table = add_threshold_exceedance_columns(table, results_df, category_column)
        sheets[sheet_name] = table
        percentile_tables[sheet_name] = (table, category_column)
    output_path = save_risk_sheets(workbook_path, sheets)

    print(
        f"Saved {len(risk_df)} rows to '{OUTPUT_SHEET}' "
        f"in {output_path}"
    )
    for sheet_name, (table, category_column) in percentile_tables.items():
        print(f"Saved {len(table)} rows to '{sheet_name}' in {output_path}")
        print(f"\n{sheet_name}, all OARs with N >= {MIN_OAR_OBSERVATIONS}:")
        print(table[category_column].value_counts().to_string())
        final_table = table[table["Final_Results_N_gt_49"]]
        print(
            f"\n{sheet_name}, final results N > 49 "
            f"({len(final_table)} of {len(table)} OARs):"
        )
        print(final_table[category_column].value_counts().to_string())
    print(f"\nAll OARs with N >= {MIN_OAR_OBSERVATIONS}:")
    print(risk_df["Risk_Category"].value_counts().to_string())
    final_df = risk_df[risk_df["Final_Results_N_gt_49"]]
    print(
        f"\nFinal results, OARs with N > 49 "
        f"({len(final_df)} of {len(risk_df)} OARs):"
    )
    print(final_df["Risk_Category"].value_counts().to_string())
    return risk_df


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Add a risk categorization sheet to statistical analysis results."
        )
    )
    parser.add_argument("--workbook", default=DEFAULT_WORKBOOK)
    parser.add_argument("--results", default=DEFAULT_RESULTS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run(args.workbook, args.results)


if __name__ == "__main__":
    main()
