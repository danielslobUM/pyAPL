"""
Forest plot of dose differences per structure (same data/filters as plot_structure_heatmap.py).

Panel A: dDmean, panel B: dD0.03cc. Each row is one structure: dot = median, whisker = [P5, P95].
The shaded band marks the +/- BAND Gy acceptable range. The x axis is limited to +/- XLIM Gy;
whiskers that extend beyond it are clipped with an arrowhead and the true P5/P95 value is
written at the side of the bar.

Usage:
    python plot_structure_forest.py [--input FILE] [--output FILE] [--xlim 6] [--band 1]
                                    [--min-n 51] [--exclude Carina ...]
"""
import argparse

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D

from plot_structure_heatmap import REGIONS, load_table

INK = "#2f5d8c"  # dots, whiskers, separators
BAND = "#d6eae5"  # acceptable-range band
OUT_COLOUR = "#b03a2e"  # labels for values beyond the axis limit


def draw_panel(ax, df, prefix, title, xlim, band, show_labels, y, first_rows=()):
    med, lo, hi = df[prefix].to_numpy(), df[prefix + "_lo"].to_numpy(), df[prefix + "_hi"].to_numpy()

    ax.axvspan(-band, band, color=BAND, zorder=0, lw=0)
    ax.axvline(0, color="#1d3b57", lw=0.9, zorder=1)
    for idx, (yi, m, l, h) in enumerate(zip(y, med, lo, hi)):
        below = idx in first_rows  # first row of a region: label goes under the bar, away from the separator
        if not np.isfinite(m):
            continue
        lc = float(np.clip(l, -xlim, xlim)) if np.isfinite(l) else m
        hc = float(np.clip(h, -xlim, xlim)) if np.isfinite(h) else m
        ax.plot([lc, hc], [yi, yi], color=INK, lw=1.1, zorder=2, solid_capstyle="butt")
        # caps only on ends that are inside the axis; arrowheads + value text on clipped ends
        for end, val, side in ((lc, l, -1), (hc, h, 1)):
            if not np.isfinite(val):
                continue
            if abs(val) <= xlim:
                ax.plot([end, end], [yi - 0.22, yi + 0.22], color=INK, lw=1.0, zorder=2)
            else:
                ax.plot([side * xlim], [yi], marker="<" if side < 0 else ">", ms=3.2,
                        color=OUT_COLOUR, zorder=4, clip_on=False)
                # value sits just inside the axis edge, above the arrowhead (outside would
                # collide with the structure names on the left)
                ax.text(side * (xlim - 0.12), yi + (0.2 if below else -0.2), f"{val:+.1f}",
                        ha="left" if side < 0 else "right", va="top" if below else "bottom", fontsize=5.8,
                        color=OUT_COLOUR, fontweight="bold", clip_on=False)
        ax.plot([float(np.clip(m, -xlim, xlim))], [yi], "o", ms=3.4, color=INK, zorder=3)

    ax.set_xlim(-xlim, xlim)
    ax.set_xticks(np.arange(-xlim, xlim + 1e-9, xlim / 2))
    ax.set_xticklabels([f"{t:g}" for t in np.arange(-xlim, xlim + 1e-9, xlim / 2)], fontsize=7)
    ax.grid(axis="x", color="#e6e6e6", lw=0.6, zorder=0)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#444444")
    ax.tick_params(axis="y", length=0)
    ax.set_title(title, fontsize=9, fontweight="bold", pad=8)
    ax.set_yticks(y)
    if show_labels:
        ax.set_yticklabels(df["label"], fontsize=6.6)
    else:
        ax.tick_params(axis="y", labelleft=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="statistical_analysis_results.xlsx")
    ap.add_argument("--output", default="figure2_structure_forest.png")
    ap.add_argument("--xlim", type=float, default=6.0, help="x-axis limit (Gy); values beyond are annotated")
    ap.add_argument("--band", type=float, default=1.0, help="half-width of the shaded band (Gy)")
    ap.add_argument("--min-n", type=int, default=51)
    ap.add_argument("--exclude", nargs="*", default=["Carina"])
    ap.add_argument("--tol", choices=["0_5", "3"], default="0_5")
    a = ap.parse_args()

    df = load_table(a.input, a.tol, 1.0, a.min_n, a.exclude)
    order = {r[0]: i for i, r in enumerate(REGIONS)}
    df = df.assign(_o=df["Region"].map(order).fillna(len(order))).sort_values(
        ["_o", "N"], ascending=[True, False]
    ).reset_index(drop=True)
    df["label"] = [f"{o} (N={n})" for o, n in zip(df["OAR"], df["N"])]

    n = len(df)
    gap = 1.2  # extra white space (in rows) between regions
    regions = df["Region"].tolist()
    y = np.zeros(n)
    for i in range(1, n):
        y[i] = y[i - 1] + 1 + (gap if regions[i] != regions[i - 1] else 0)
    first = set()  # the gap keeps labels clear of the separators, so no special placement
    total = y[-1] + 1
    fig, axes = plt.subplots(1, 2, figsize=(8.9, 0.17 * total + 1.5), sharey=True,
                             gridspec_kw={"wspace": 0.28}, facecolor="white")
    draw_panel(axes[0], df, "dmean", "A   ΔDmean (Gy)", a.xlim, a.band, True, y, first)
    draw_panel(axes[1], df, "dmax", "B   ΔD0.03cc (Gy)", a.xlim, a.band, False, y, first)
    axes[0].set_ylim(y[-1] + 0.5, -0.5)

    # region separators (in the middle of each gap) and rotated region labels on the left
    label = {r[0]: r[1] for r in REGIONS}
    seps = []
    label_txts = []
    starts = [0] + [i for i in range(1, n) if regions[i] != regions[i - 1]]
    ends = [s - 1 for s in starts[1:]] + [n - 1]
    for s, e in zip(starts, ends):
        if s > 0:
            seps.append((y[s - 1] + y[s]) / 2)
        label_txts.append(axes[0].text(-0.56, (y[s] + y[e]) / 2, label.get(regions[s], regions[s]).upper(),
                     transform=axes[0].get_yaxis_transform(), rotation=90, ha="center",
                     va="center", fontsize=7.5, fontweight="bold", color=INK, clip_on=False))

    fig.text(0.02, 0.01,
             f"Dot = median, whisker = [P5, P95]; shaded band = ±{a.band:g} Gy. "
             f"Whiskers beyond ±{a.xlim:g} Gy are clipped (◀ ▶) and the true value is printed at the end of the bar.",
             fontsize=6.5, ha="left", va="bottom", wrap=True)
    fig.subplots_adjust(left=0.29, right=0.95, top=1 - 0.5 / fig.get_figheight(),
                        bottom=0.6 / fig.get_figheight())
    # one continuous separator per region boundary, from the region labels to the right edge,
    # running across both panels and the gap between them
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    # start the lines at the left edge of the region names
    x0 = min(fig.transFigure.inverted().transform((t.get_window_extent(r).x0, 0))[0]
             for t in label_txts)
    x1 = axes[1].get_position().x1
    for yv in seps:
        yf = fig.transFigure.inverted().transform(axes[0].transData.transform((0, yv)))[1]
        fig.add_artist(Line2D([x0, x1], [yf, yf], transform=fig.transFigure, color=INK, lw=1.0,
                              solid_capstyle="butt", zorder=1))
    fig.savefig(a.output, dpi=250, facecolor="white")
    print(f"Saved {a.output} ({n} structures)")


if __name__ == "__main__":
    main()
