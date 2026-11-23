"""
Per-structure summary heatmap (Figure 1) built from statistical_analysis_results.xlsx.

Recreates the mock-up layout: one row per structure (grouped by body region, with a
rotated region label and tinted row background) and four colour-coded columns:
    APL median | sDSC median [P5,P95] | dDmean median [P5,P95] | dD0.03cc median [P5,P95]

Data come from the 'Dataset_Summary' sheet, whose cells are strings like
"0.8689 (0.6421 - 0.9435)" or "-0.002 (-0.543 to 0.220)".

Usage:
    python plot_structure_heatmap.py [--input FILE] [--output FILE] [--tol {0_5,3}]
                                     [--apl-scale 1.0] [--apl-unit mm] [--min-n 51]
"""
import argparse
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import Normalize, to_rgba
from matplotlib.patches import Rectangle

# Region display order / label / row tint (matches the mock-up palette)
REGIONS = [
    ("Thorax", "Thorax", "#f6e5e5"),
    ("Abdomen", "Abdomen", "#e6f0e6"),
    ("Pelvis", "Pelvis", "#e5ecf6"),
    ("Head_Neck", "Head & Neck", "#f2e8f6"),
    ("Neuro_Cranial", "Neuro-cranial", "#f6f0e3"),
    ("CNS", "CNS", "#e8eef0"),
]
HEADER_BG = "#d9e2ef"
NUM = r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?"


def parse_med_range(s):
    """'m (lo - hi)' / 'm (lo to hi)' -> (m, lo, hi); plain number -> (m, nan, nan)."""
    if pd.isna(s):
        return np.nan, np.nan, np.nan
    if isinstance(s, (int, float)):
        return float(s), np.nan, np.nan
    nums = re.findall(NUM, str(s).replace(" - ", " to "))
    # 'lo - hi' with negative hi would be ambiguous; the file uses ' to ' for negatives
    # but ' - ' for the positive-only metrics, which is handled by the replace above.
    vals = [float(n) for n in nums]
    if len(vals) >= 3:
        return vals[0], vals[1], vals[2]
    if len(vals) == 1:
        return vals[0], np.nan, np.nan
    return np.nan, np.nan, np.nan


def load_table(path, tol, apl_scale, min_n, exclude=()):
    ds = pd.read_excel(path, sheet_name="Dataset_Summary")
    ds = ds[ds["Details"].astype(str).str.startswith("Region:")].copy()
    ds["Region"] = ds["Details"].str.replace("Region:", "", regex=False).str.strip()
    ds["N"] = pd.to_numeric(ds["Count"].astype(str).str.replace(",", ""), errors="coerce")
    ds = ds[ds["N"] >= min_n]
    ds = ds[~ds["OAR"].isin(exclude)]

    out = pd.DataFrame({"OAR": ds["OAR"], "Region": ds["Region"], "N": ds["N"].astype(int)})
    out["apl"] = [parse_med_range(v)[0] * apl_scale for v in ds[f"APL_tol{tol}_Median"]]
    for key, col in [
        ("sdsc", f"sDSC_tol{tol}_Median"),
        ("dmean", "Delta_Dmean_Median"),
        ("dmax", "Delta_Dmax_0_03cc_Median"),
    ]:
        parsed = [parse_med_range(v) for v in ds[col]]
        out[key], out[key + "_lo"], out[key + "_hi"] = zip(*parsed)
    return out.reset_index(drop=True)


def robust_norm(values, lo_pct=5, hi_pct=95):
    v = np.asarray(values, float)
    v = v[np.isfinite(v)]
    lo, hi = np.percentile(v, [lo_pct, hi_pct])
    if hi == lo:
        hi = lo + 1e-9
    return Normalize(lo, hi, clip=True)


# Colour ramps (low -> high value) sampled from the v1 screenshot, one per column.
# dDmean and dD0.03cc share the same ramp.
COLUMN_COLOURS = [
    ["#e6eff8", "#c4d9ee", "#a4cae2", "#75aed8"],  # APL: pale blue -> medium blue
    # sDSC: pale green (good, high sDSC) -> medium green (poor, low sDSC), same lightness range
    # as the blue APL ramp; the score is inverted below so that in every column pale = good
    # agreement, saturated = worse.
    ["#e8f5e3", "#c7e6bf", "#9fd495", "#6dba70"],
    ["#fde587", "#f9cb60", "#f7a93e", "#f4742b", "#e6321a"],  # delta: yellow -> orange -> red
]


def _shade_cmap(stops):
    """Return f(t in 0..1) -> RGBA interpolating the given colour stops."""
    from matplotlib.colors import LinearSegmentedColormap

    cm = LinearSegmentedColormap.from_list("shade", stops)
    return lambda t: cm(float(t))


def make_figure(df, output, tol, apl_unit, title, footnote):
    tol_txt = {"0_5": "0.5", "3": "3"}[tol]

    # Order rows: region order, then N descending within region
    order = {r[0]: i for i, r in enumerate(REGIONS)}
    df = df.assign(_o=df["Region"].map(order).fillna(len(order))).sort_values(
        ["_o", "N"], ascending=[True, False]
    )

    # (header, value col, lo col, hi col, normalised score 0=bad..1=good, fmt)
    apl_norm = robust_norm(df["apl"])
    sdsc_norm = robust_norm(df["sdsc"])
    df = df.assign(
        dmean_ext=df[["dmean_lo", "dmean_hi"]].abs().max(axis=1),
        dmax_ext=df[["dmax_lo", "dmax_hi"]].abs().max(axis=1),
    )
    # Colour deltas by the worst-case extent (max |P5|,|P95|): the median is ~0 for most OARs.
    # Both delta columns share ONE normalisation so their shades are comparable.
    d_norm = robust_norm(pd.concat([df["dmean_ext"], df["dmax_ext"]]))
    # One hue per column; darker shade = larger value shown. dDmean and dD0.03cc share a hue.
    cm_apl, cm_sdsc, cm_delta = (_shade_cmap(c) for c in COLUMN_COLOURS)
    # (header, value col, lo col, hi col, intensity 0..1 (darker = larger), colormap)
    cols = [
        (f"APL\n({apl_unit})", "apl", None, None,
         lambda r: apl_norm(r["apl"]), cm_apl),
        (f"sDSC\n({tol_txt} mm)", "sdsc", "sdsc_lo", "sdsc_hi",
         lambda r: 1 - sdsc_norm(r["sdsc"]), cm_sdsc),
        ("ΔDmean\n(Gy)", "dmean", "dmean_lo", "dmean_hi",
         lambda r: d_norm(r["dmean_ext"]), cm_delta),
        ("ΔD0.03cc\n(Gy)", "dmax", "dmax_lo", "dmax_hi",
         lambda r: d_norm(r["dmax_ext"]), cm_delta),
    ]
    # Layout modelled on the v1 screenshot: no title/borders/header fill, right-aligned names,
    # rotated region labels, inset (gapped) colour cells and heavy separators between regions.
    widths = [2.5, 1.1, 2.1, 2.3, 2.3]
    xs = np.concatenate([[0], np.cumsum(widths)])
    total_w = xs[-1]
    x_left = -0.55  # room for the rotated region labels

    n = len(df)
    gap = 0.9  # extra white space (in rows) between regions
    n_gaps = max(df["Region"].nunique() - 1, 0)
    total_rows = n + gap * n_gaps
    row_h, head_h = 0.235, 0.62
    fig_h = head_h + total_rows * row_h + 1.35
    fig = plt.figure(figsize=(8.9, fig_h), facecolor="white")
    ax = fig.add_axes([0.02, 0.85 / fig_h, 0.96, (head_h + total_rows * row_h) / fig_h])
    ax.set_xlim(x_left, total_w)
    ax.set_ylim(total_rows + head_h / row_h, 0)  # header on top; y grows downward
    ax.axis("off")
    hh = head_h / row_h  # header height in row units
    renderer = fig.canvas.get_renderer()
    units_per_px = (total_w - x_left) / ax.get_window_extent(renderer).width

    # Header: bold, centred over each colour column, no background
    for j, (hdr, *_rest) in enumerate(cols, start=1):
        ax.text(xs[j] + widths[j] / 2, hh - 0.25, hdr, ha="center", va="bottom",
                fontsize=9, fontweight="bold", linespacing=1.15)

    def fmt_val(v, signed, dec):
        return f"{v:{'+' if signed else ''}.{dec}f}"

    def draw_cell_text(xc, yc, r, vcol, lo, hi, signed, dec, fs):
        """Bold median + highlighted [P5, P95] chip, centred as a pair in the cell."""
        m = r[vcol]
        if not np.isfinite(m):
            ax.text(xc, yc, "n/a", ha="center", va="center", fontsize=fs)
            return
        med = fmt_val(m, signed, dec)
        if lo is None or not (np.isfinite(r[lo]) and np.isfinite(r[hi])):
            ax.text(xc, yc, med, ha="center", va="center", fontsize=fs, fontweight="bold")
            return
        rng = f"[{fmt_val(r[lo], signed, dec)}, {fmt_val(r[hi], signed, dec)}]"
        t_m = ax.text(0, yc, med, ha="left", va="center", fontsize=fs, fontweight="bold")
        t_r = ax.text(0, yc, rng, ha="left", va="center", fontsize=fs - 0.4,
                      bbox=dict(boxstyle="round,pad=0.18", fc="white", ec="none", alpha=0.6))
        w_m = t_m.get_window_extent(renderer).width * units_per_px
        w_r = t_r.get_window_extent(renderer).width * units_per_px
        sp = 0.09
        x0 = xc - (w_m + sp + w_r) / 2
        t_m.set_x(x0)
        t_r.set_x(x0 + w_m + sp)

    label = {r[0]: r[1] for r in REGIONS}
    gx, gy = 0.05, 0.07  # cell inset -> white gaps between cells
    y = hh
    group_start = y
    prev_region = None
    for _, r in df.iterrows():
        if prev_region is not None and r["Region"] != prev_region:
            _region_label(ax, label.get(prev_region, prev_region), group_start, y, x_left)
            ax.plot([x_left, total_w], [y + gap / 2, y + gap / 2], color=SEP_COLOUR, lw=1.5,
                    solid_capstyle="butt")
            y += gap
            group_start = y
        prev_region = r["Region"]
        ax.text(widths[0] - 0.1, y + 0.5, f"{r['OAR']} (N={r['N']})", ha="right", va="center",
                fontsize=7.5)
        for j, (_h, vcol, lo, hi, score, cmap) in enumerate(cols, start=1):
            sc = score(r)
            fc = cmap(sc) if np.isfinite(sc) else "#dddddd"
            ax.add_patch(Rectangle((xs[j] + gx, y + gy), widths[j] - 2 * gx, 1 - 2 * gy,
                                   fc=fc, ec="none"))
            xc, yc = xs[j] + widths[j] / 2, y + 0.5
            if vcol == "apl":
                draw_cell_text(xc, yc, r, vcol, None, None, False, 0, 7.2)
            elif vcol == "sdsc":
                draw_cell_text(xc, yc, r, vcol, lo, hi, False, 2, 6.6)
            else:
                draw_cell_text(xc, yc, r, vcol, lo, hi, True, 2, 6.6)
        y += 1
    _region_label(ax, label.get(prev_region, prev_region), group_start, y, x_left)

    if title:
        fig.suptitle(title, fontsize=11, fontweight="bold", y=1 - 0.15 / fig_h)
    fig.text(0.03, 0.4 / fig_h, footnote, fontsize=6.8, ha="left", va="center")
    fig.savefig(output, dpi=250, facecolor="white")
    plt.close(fig)
    print(f"Saved {output} ({n} structures)")


SEP_COLOUR = "#4d5963"
LABEL_COLOUR = "#2f5d8c"


def _region_label(ax, text, y0, y1, x):
    ax.text(x + 0.2, (y0 + y1) / 2, text.upper(), rotation=90, ha="center", va="center",
            fontsize=7.5, fontweight="bold", color=LABEL_COLOUR, clip_on=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="statistical_analysis_results.xlsx")
    ap.add_argument("--output", default="figure1_structure_heatmap.png")
    ap.add_argument("--tol", choices=["0_5", "3"], default="0_5",
                    help="surface tolerance (mm) used for sDSC and APL")
    ap.add_argument("--apl-scale", type=float, default=1.0,
                    help="multiply APL values (e.g. 0.001 or voxel->mm conversion)")
    ap.add_argument("--apl-unit", default="mm")
    ap.add_argument("--min-n", type=int, default=51,
                    help="keep structures with at least this many pairs (51 = more than 50)")
    ap.add_argument("--exclude", nargs="*", default=["Carina"],
                    help="structures to leave out (default: Carina)")
    ap.add_argument("--title", default="", help="optional figure title (none by default)")
    a = ap.parse_args()

    df = load_table(a.input, a.tol, a.apl_scale, a.min_n, a.exclude)
    make_figure(
        df, a.output, a.tol, a.apl_unit, a.title,
        "Cells show the median (bold) and the highlighted [P5, P95] range (5th–95th percentile).\n"
        "Shading: pale = good agreement, saturated = worse. Blue = APL (darker = larger),\n"
        "green = sDSC (darker = lower), yellow-red = Δ (redder = larger max(|P5|,|P95|); shared scale).\n"
        "Colour scales span the 5th–95th percentile of each column.",
    )


if __name__ == "__main__":
    main()
