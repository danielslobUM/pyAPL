"""
calculate_dvh_parameters - Calculate DVH parameters for paired RTSTRUCT structures.

Translated from fCalcDVHfromDCM_FV.m
Frank Dankers @ MAASTRO

Computes per structure (automatic / Limbus AI vs. clinically adjusted):
- Dmean, Dmax, Dmin, Dstd, D0.03cc, Volume (cm³), Outside (%)
- Delta metrics: AdjustedDmean - AutomaticDmean, AdjustedD0.03cc - AutomaticD0.03cc
"""

import os
import sys
import time
import numpy as np
import pydicom
import pandas as pd
from pathlib import Path
from skimage.draw import polygon as sk_polygon
from scipy.interpolate import RegularGridInterpolator

from read_dicomrtstruct import read_dicomrtstruct
from read_dicomct_light import read_dicomct_light


# ============================================================================
# CONFIGURATION
# ============================================================================

DICOM_ROOT_FOLDER = r"\\smb.isilon01.ad.maastro.nl\Research\Projects\phys\p0728-automation\ICoNEA\DICOM"
SCRIPT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_FILE = str(SCRIPT_DIR.parent / 'dvh_parameters_results.xlsx')


def calculate_dvh_parameters(dose_int, struct_num_1, struct_num_2, struct_auto, struct_adj,
                             ct_grid=None):
    """
    Calculate DVH parameters and dose gradient at the adjusted contour surface.

    Methodology matches fCalcDVHfromDCM_FV:
      1. Structures are rasterised onto the CT grid (fine grid). If ct_grid is
         not supplied the dose grid is used as fallback.
      2. Edge voxels contribute half volume weight (0.5), interior voxels full (1.0).
      3. Dose at each voxel centre is obtained by trilinear interpolation inside
         the 3-D dose matrix (scipy RegularGridInterpolator, method='linear').
      4. Dmean is volume-weighted; Dmax is the unweighted maximum.
      5. Voxels outside the dose grid return NaN and are excluded from statistics;
         the outside percentage is printed as a warning.

    Parameters
    ----------
    dose_int : dict
        Dose cube dict from read_rtdose, with keys 'cube', 'resolution', 'ct'.
    struct_num_1 : int
        0-based index of the automatic structure in struct_auto.
    struct_num_2 : int
        0-based index of the adjusted structure in struct_adj.
    struct_auto : dict
        RTSTRUCT dict from read_dicomrtstruct for the automatic contours.
    struct_adj : dict
        RTSTRUCT dict from read_dicomrtstruct for the adjusted contours.
    ct_grid : dict, optional
        CT grid descriptor from read_dicomct_light. When supplied the structure
        is rasterised at CT resolution and dose is trilinearly interpolated.
        When None the dose grid itself is used (degraded accuracy, no blending).

    Returns
    -------
    dvh_parm : dict
    gradient_calc : dict
    dVdose2 : ndarray
        Dose values (Gy) per adjusted-structure voxel (NaN = outside dose grid).
    w2 : ndarray
        Volume weights per adjusted-structure voxel (0.5 edge, 1.0 interior).
    """
    dose_cube = dose_int['cube']
    dose_ct   = dose_int['ct']

    # Grid to rasterise on: CT (fine) if available, else dose grid
    grid = ct_grid if ct_grid is not None else dose_ct

    # -------------------------------------------------------------------------
    # Large ROI span check — matches fCalcDVHfromDCM_FV ctspacing_scalinglargeroi
    # Span = LR_range × AP_range in cm².  Threshold 1500 cm² (≡ MATLAB's value
    # after dividing mm² by 100).  Scale factor 2 doubles the rasterisation step,
    # halving the number of voxels along each in-plane axis (4× speed-up).
    # -------------------------------------------------------------------------
    _SPAN_THRESHOLD_CM2 = 1500.0
    _SCALE_FACTOR       = 2.0

    def _span_cm2(slices):
        xs = [v for sl in slices if sl['X'] is not None for v in sl['X'].tolist()]
        zs = [v for sl in slices if sl['Z'] is not None for v in sl['Z'].tolist()]
        if not xs or not zs:
            return 0.0
        return (max(xs) - min(xs)) * (max(zs) - min(zs))

    slices1 = struct_auto['Struct'][struct_num_1]['Slice']
    slices2 = struct_adj['Struct'][struct_num_2]['Slice']
    scale1  = _SCALE_FACTOR if _span_cm2(slices1) > _SPAN_THRESHOLD_CM2 else 1.0
    scale2  = _SCALE_FACTOR if _span_cm2(slices2) > _SPAN_THRESHOLD_CM2 else 1.0
    if scale1 > 1.0:
        print(f"    Warning: automatic structure span {_span_cm2(slices1):.1f} cm² "
              f"> {_SPAN_THRESHOLD_CM2} cm², scaling CT spacing ×{scale1:.0f}")
    if scale2 > 1.0:
        print(f"    Warning: adjusted structure span {_span_cm2(slices2):.1f} cm² "
              f"> {_SPAN_THRESHOLD_CM2} cm², scaling CT spacing ×{scale2:.0f}")

    # -------------------------------------------------------------------------
    # Rasterise both structures onto the chosen grid with edge/interior weights
    # -------------------------------------------------------------------------
    ix1, iy1, iz1, w1 = resample_contour_with_weights(slices1, grid, inplane_scale=scale1)
    ix2, iy2, iz2, w2 = resample_contour_with_weights(slices2, grid, inplane_scale=scale2)

    # -------------------------------------------------------------------------
    # Build trilinear interpolator over the dose grid
    # Coordinate axes must match the array axes of dose_cube (Xi, Yi, Zi)
    # -------------------------------------------------------------------------
    x_dose = (dose_ct['PixelFirstXi']
               + np.arange(dose_ct['PixelNumXi']) * dose_ct['PixelSpacingXi'])
    y_dose = (dose_ct['PixelFirstYi']
               + np.arange(dose_ct['PixelNumYi']) * dose_ct['PixelSpacingYi'])
    z_dose = (dose_ct['PixelFirstZi']
               + np.arange(dose_ct['PixelNumZi']) * dose_ct['PixelSpacingZi'])

    interp = RegularGridInterpolator(
        (x_dose, y_dose, z_dose),
        dose_cube,
        method='linear',
        bounds_error=False,
        fill_value=np.nan,   # NaN for voxels outside the dose grid
    )

    # -------------------------------------------------------------------------
    # Convert voxel indices → world coordinates (cm) and query interpolator
    # -------------------------------------------------------------------------
    def _sample_dose(ix, iy, iz):
        if ix.size == 0:
            return np.array([], dtype=float)
        qx = grid['PixelFirstXi'] + ix * grid['PixelSpacingXi']
        qy = grid['PixelFirstYi'] + iy * grid['PixelSpacingYi']
        qz = grid['PixelFirstZi'] + iz * grid['PixelSpacingZi']
        return interp(np.column_stack([qx, qy, qz]))

    dVdose1 = _sample_dose(ix1, iy1, iz1)
    dVdose2 = _sample_dose(ix2, iy2, iz2)

    # -------------------------------------------------------------------------
    # Volume-weighted dose statistics (NaN = outside dose grid, excluded)
    # -------------------------------------------------------------------------
    def _dmean(dVdose, w):
        if dVdose.size == 0:
            return float('nan')
        valid = ~np.isnan(dVdose)
        if not valid.any():
            return float('nan')
        return float(np.average(dVdose[valid], weights=w[valid]))

    def _dmax(dVdose):
        if dVdose.size == 0:
            return float('nan')
        valid = ~np.isnan(dVdose)
        return float(np.max(dVdose[valid])) if valid.any() else float('nan')

    def _dmin(dVdose):
        if dVdose.size == 0:
            return float('nan')
        valid = ~np.isnan(dVdose)
        return float(np.min(dVdose[valid])) if valid.any() else float('nan')

    def _dosestd(dVdose, w, dmean):
        if dVdose.size == 0:
            return float('nan')
        valid = ~np.isnan(dVdose)
        if not valid.any():
            return float('nan')
        d, ww = dVdose[valid], w[valid]
        return float(np.sqrt(np.sum((d - dmean) ** 2 * ww) / np.sum(ww)))

    def _outside_pct(dVdose, w):
        if dVdose.size == 0:
            return 100.0
        return float(100.0 * np.sum(w[np.isnan(dVdose)]) / np.sum(w))

    # voxel volume in cm³ (spacings are already in cm from read_dicomct_light)
    voxel_vol_cm3 = float(
        grid['PixelSpacingXi'] * grid['PixelSpacingYi'] * grid['PixelSpacingZi']
    )

    def _volume_cm3(w, dVdose):
        valid = ~np.isnan(dVdose)
        return float(np.sum(w[valid])) * voxel_vol_cm3

    def _d_at_volume_cm3(dVdose, w, vol_threshold_cm3):
        """
        D(x cc): dose received by the hottest x cm³ of the structure.
        Equivalent to reading the DVH at cumulative volume = x cm³.
        Sort voxels by dose descending, accumulate weighted volume until the
        threshold is reached, then interpolate linearly between the two
        surrounding voxels.
        """
        valid = ~np.isnan(dVdose)
        if not valid.any():
            return float('nan')
        d = dVdose[valid]
        v = w[valid] * voxel_vol_cm3  # per-voxel volume in cm³
        total = float(np.sum(v))
        if vol_threshold_cm3 > total:
            return float('nan')  # structure smaller than threshold
        # sort descending by dose (hottest first)
        idx = np.argsort(d)[::-1]
        d_s = d[idx]
        v_s = v[idx]
        cum_v = np.cumsum(v_s)
        # first index where cumulative volume >= threshold
        over = np.searchsorted(cum_v, vol_threshold_cm3)
        if over == 0:
            return float(d_s[0])
        # linear interpolation between voxels over-1 and over
        v_lo = cum_v[over - 1]
        v_hi = cum_v[over] if over < len(cum_v) else cum_v[-1]
        d_lo = float(d_s[over - 1])
        d_hi = float(d_s[over]) if over < len(d_s) else float(d_s[-1])
        if v_hi == v_lo:
            return d_lo
        frac = (vol_threshold_cm3 - v_lo) / (v_hi - v_lo)
        return d_lo + frac * (d_hi - d_lo)

    for tag, dv, w in [('automatic', dVdose1, w1), ('adjusted', dVdose2, w2)]:
        pct = _outside_pct(dv, w)
        if pct > 0:
            print(f"    Warning: {tag} structure {pct:.1f}% outside dose grid")

    auto_dmean    = _dmean(dVdose1, w1)
    adj_dmean     = _dmean(dVdose2, w2)
    auto_d003cc   = _d_at_volume_cm3(dVdose1, w1, 0.03)
    adj_d003cc    = _d_at_volume_cm3(dVdose2, w2, 0.03)

    dvh_parm = {
        'AutomaticDmean':       auto_dmean,
        'AutomaticDmax':        _dmax(dVdose1),
        'AutomaticDmin':        _dmin(dVdose1),
        'AutomaticDstd':        _dosestd(dVdose1, w1, auto_dmean),
        'AutomaticD0.03cc':     auto_d003cc,
        'AutomaticVolume_cm3':  _volume_cm3(w1, dVdose1),
        'AutomaticOutside_pct': _outside_pct(dVdose1, w1),
        'AdjustedDmean':        adj_dmean,
        'AdjustedDmax':         _dmax(dVdose2),
        'AdjustedDmin':         _dmin(dVdose2),
        'AdjustedDstd':         _dosestd(dVdose2, w2, adj_dmean),
        'AdjustedD0.03cc':      adj_d003cc,
        'AdjustedVolume_cm3':   _volume_cm3(w2, dVdose2),
        'AdjustedOutside_pct':  _outside_pct(dVdose2, w2),
        # Differences: Adjusted minus Automatic (positive = Adjusted receives more dose)
        'DeltaDmean':           adj_dmean - auto_dmean
                                    if not (np.isnan(adj_dmean) or np.isnan(auto_dmean))
                                    else float('nan'),
        'DeltaD0.03cc':         adj_d003cc - auto_d003cc
                                    if not (np.isnan(adj_d003cc) or np.isnan(auto_d003cc))
                                    else float('nan'),
}

    return dvh_parm, dVdose2, w2, voxel_vol_cm3


# ============================================================================
# DVH CURVE
# ============================================================================

def _fill_edge_gaps(rows, cols, vary):
    """
    Insert intermediate pixels wherever consecutive edge pixels are >1 apart
    along the specified axis ('row' or 'col').
    Matches fCalcDVHfromDCM_FV missing-edge-voxel interpolation using interp1.
    """
    if vary == 'col':
        delta = np.abs(np.diff(cols))
    else:
        delta = np.abs(np.diff(rows))

    missing = np.where(delta > 1)[0]
    if len(missing) == 0:
        return rows, cols

    seg_rows, seg_cols = [], []
    prev = 0
    for idx in missing:
        seg_rows.append(rows[prev:idx + 1])
        seg_cols.append(cols[prev:idx + 1])

        r0, r1 = int(rows[idx]), int(rows[idx + 1])
        c0, c1 = int(cols[idx]), int(cols[idx + 1])

        if vary == 'col':
            sign = int(np.sign(c1 - c0)) or 1
            ins_c = np.arange(c0 + sign, c1, sign, dtype=int)
            if len(ins_c):
                ins_r = np.round(np.interp(ins_c, [c0, c1], [r0, r1])).astype(int)
                seg_rows.append(ins_r)
                seg_cols.append(ins_c)
        else:
            sign = int(np.sign(r1 - r0)) or 1
            ins_r = np.arange(r0 + sign, r1, sign, dtype=int)
            if len(ins_r):
                ins_c = np.round(np.interp(ins_r, [r0, r1], [c0, c1])).astype(int)
                seg_rows.append(ins_r)
                seg_cols.append(ins_c)

        prev = idx + 1

    seg_rows.append(rows[prev:])
    seg_cols.append(cols[prev:])

    return np.concatenate(seg_rows), np.concatenate(seg_cols)


def _fill_contour_edge_voxels(rows, cols, mask_h, mask_w):
    """
    Fill missing horizontal then vertical edge voxels for a single contour.
    Matches fCalcDVHfromDCM_FV: first fill |dcol|>1, then fill |drow|>1.
    Returns clipped integer arrays within (mask_h, mask_w).
    """
    rows = rows.astype(int)
    cols = cols.astype(int)
    rows, cols = _fill_edge_gaps(rows, cols, vary='col')
    rows, cols = _fill_edge_gaps(rows, cols, vary='row')
    valid = (rows >= 0) & (rows < mask_h) & (cols >= 0) & (cols < mask_w)
    return rows[valid], cols[valid]


def resample_contour_with_weights(struct_slices: list, grid: dict,
                                  inplane_scale: float = 1.0):
    """
    Rasterise a structure onto *grid* and return per-voxel indices and volume
    weights, matching the fCalcDVHfromDCM_FV methodology:
      - edge voxels (polygon boundary)  → weight 0.5
      - interior voxels                 → weight 1.0

    Parameters
    ----------
    struct_slices : list of dict
        ContourSequence slice list with 'X', 'Y', 'Z' keys (cm).
    grid : dict
        Grid descriptor dict (PixelFirstXi/Yi/Zi, PixelSpacingXi/Yi/Zi,
        PixelNumXi/Yi/Zi) — may be the CT grid or the dose grid.
    inplane_scale : float
        Factor by which to coarsen the in-plane rasterisation spacing.
        1.0 = full CT resolution.  2.0 = half resolution (MATLAB large-ROI
        scaling: ctspacing_scalinglargeroi_scalefactor).

    Returns
    -------
    ix, iy, iz : ndarray of int
        Voxel indices along axes 0, 1, 2 of the grid volume.
    weights : ndarray of float
        0.5 for edge voxels, 1.0 for interior voxels.

    Rows/cols convention (matching fCalcDVHfromDCM_FV):
        MATLAB  rows = AP (DICOM Y), cols = LR (DICOM X)
        Python  rows (ix / loc_rows) = Xi = LR (DICOM X)
                cols (iz / loc_cols) = Zi = reversed-AP direction
        The labels differ but the set of physical voxels selected is equivalent.
    """
    from collections import defaultdict

    nxi = grid['PixelNumXi']
    nyi = grid['PixelNumYi']
    nzi = grid['PixelNumZi']
    # Apply inplane_scale to coarsen rasterisation (large-ROI optimisation)
    sx  = grid['PixelSpacingXi'] * inplane_scale
    sz  = grid['PixelSpacingZi'] * inplane_scale

    # --- group contours by Y (slice) index; multiple contours per slice possible ---
    slices_by_yi = defaultdict(list)
    for sl in struct_slices:
        if sl['X'] is None or len(sl['X']) == 0:
            continue
        yi = int(np.round((sl['Y'][0] - grid['PixelFirstYi']) / grid['PixelSpacingYi']))
        if 0 <= yi < nyi:
            slices_by_yi[yi].append(sl)

    ix_list, iy_list, iz_list, w_list = [], [], [], []

    for yi, contours in slices_by_yi.items():

        # gather all contour points on this slice as global grid indices
        all_xi, all_zi = [], []
        contour_grids = []

        for sl in contours:
            xi = np.round((sl['X'] - grid['PixelFirstXi']) / sx).astype(int)
            zi = np.round((sl['Z'] - grid['PixelFirstZi']) / sz).astype(int)

            # close contour if endpoints do not coincide (poly/pencil drawn)
            # matches MATLAB: if endpoint != startpoint by ~1 ct_spacing, append start
            if xi[0] != xi[-1] or zi[0] != zi[-1]:
                xi = np.append(xi, xi[0])
                zi = np.append(zi, zi[0])

            all_xi.extend(xi.tolist())
            all_zi.extend(zi.tolist())
            contour_grids.append((xi, zi))

        if not all_xi:
            continue

        all_xi_arr = np.array(all_xi)
        all_zi_arr = np.array(all_zi)

        # local grid: compact bounding box of all contour points on this slice
        # (matches MATLAB's minallcontourpointsonslice local coordinate system)
        min_xi_loc = int(np.min(all_xi_arr))
        min_zi_loc = int(np.min(all_zi_arr))
        max_xi_loc = int(np.max(all_xi_arr))
        max_zi_loc = int(np.max(all_zi_arr))

        h = max_xi_loc - min_xi_loc + 1   # rows = Xi axis
        w = max_zi_loc - min_zi_loc + 1   # cols = Zi axis
        cummask = np.zeros((h, w), dtype=float)

        for xi_cont, zi_cont in contour_grids:
            # convert to local coordinates (0-based, relative to bounding box)
            loc_rows = xi_cont - min_xi_loc
            loc_cols = zi_cont - min_zi_loc

            # poly2mask: fill polygon interior (skimage polygon matches MATLAB poly2mask)
            rr, cc = sk_polygon(loc_rows, loc_cols, shape=(h, w))
            mask_inside = np.zeros((h, w), dtype=bool)
            v = (rr >= 0) & (rr < h) & (cc >= 0) & (cc < w)
            mask_inside[rr[v], cc[v]] = True

            # fill in missing horizontal/vertical edge voxels
            # (needed for poly/pencil contours with gaps between consecutive points)
            edge_r, edge_c = _fill_contour_edge_voxels(loc_rows, loc_cols, h, w)

            # exclude explicit edge pixels from poly2mask interior
            # (poly2mask has right-edge artefacts; edge pixels are not "inside")
            mask_inside[edge_r, edge_c] = False

            # update cumulative mask: +0.5 for edge, +1 for interior
            # even/odd XOR logic correctly handles holes (donut structures)
            np.add.at(cummask, (edge_r, edge_c), 0.5)
            cummask[mask_inside] += 1.0

        # process cummask → 0 (outside) / 0.5 (edge) / 1.0 (inside)
        # even  mod value → outside (includes holes)
        # odd   mod value → inside
        # other mod value → edge (boundary voxels, contribute 0.5 volume)
        mod = cummask % 2
        final_mask = np.full((h, w), 0.5)
        final_mask[np.isclose(mod, 0.0)] = 0.0
        final_mask[np.isclose(mod, 1.0)] = 1.0

        # edge voxels → weight 0.5
        e_r, e_c = np.where(np.isclose(final_mask, 0.5))
        if e_r.size > 0:
            gxi = e_r + min_xi_loc
            gzi = e_c + min_zi_loc
            valid = (gxi >= 0) & (gxi < nxi) & (gzi >= 0) & (gzi < nzi)
            if valid.any():
                ix_list.append(gxi[valid])
                iy_list.append(np.full(int(valid.sum()), yi, dtype=int))
                iz_list.append(gzi[valid])
                w_list.append(np.full(int(valid.sum()), 0.5))

        # interior voxels → weight 1.0
        i_r, i_c = np.where(np.isclose(final_mask, 1.0))
        if i_r.size > 0:
            gxi = i_r + min_xi_loc
            gzi = i_c + min_zi_loc
            valid = (gxi >= 0) & (gxi < nxi) & (gzi >= 0) & (gzi < nzi)
            if valid.any():
                ix_list.append(gxi[valid])
                iy_list.append(np.full(int(valid.sum()), yi, dtype=int))
                iz_list.append(gzi[valid])
                w_list.append(np.ones(int(valid.sum())))

    if not ix_list:
        empty = np.array([], dtype=int)
        return empty, empty, empty, np.array([], dtype=float)

    return (
        np.concatenate(ix_list),
        np.concatenate(iy_list),
        np.concatenate(iz_list),
        np.concatenate(w_list),
    )


def calculate_dvh_curve(dVdose: np.ndarray, weights: np.ndarray,
                        voxel_vol_cm3: float = None,
                        dosebins_desired: np.ndarray = None) -> tuple:
    """
    Compute a cumulative DVH matching fCalcDVHfromDCM_FV methodology:
      - sort dose values ascending
      - cumulative sum of volumes (descending = volume receiving >= each dose)
      - anchor at 0 Gy → 100 % volume
      - reduce duplicate-dose vertical lines
      - optionally interpolate to desired dose bins

    Parameters
    ----------
    dVdose : ndarray
        Per-voxel dose values in Gy (NaN = outside dose grid, excluded).
    weights : ndarray
        Per-voxel volume weights (0.5 edge, 1.0 interior).
    voxel_vol_cm3 : float, optional
        Physical voxel volume in cm³. When given, output volume axis is in cm³;
        otherwise weights are used directly (relative units).
    dosebins_desired : ndarray, optional
        Monotonically increasing dose values (Gy) to interpolate the DVH onto.
        When None, all unique sorted dose values are returned.

    Returns
    -------
    dose_out : ndarray — dose values (Gy)
    volume_pct : ndarray — cumulative volume (% of total volume inside dose grid)
    """
    valid = ~np.isnan(dVdose)
    dose_vals = dVdose[valid]
    w_vals    = weights[valid]

    if dose_vals.size == 0:
        return np.array([0.0, 0.0]), np.array([0.0, 0.0])

    v_vals = w_vals * voxel_vol_cm3 if voxel_vol_cm3 is not None else w_vals

    # sort dV and dVdose (matches MATLAB: [dVdoseSort, idx] = sort(dVdose))
    sort_idx    = np.argsort(dose_vals)
    dose_sorted = dose_vals[sort_idx]
    v_sorted    = v_vals[sort_idx]

    total_vol = float(np.sum(v_sorted))

    # cumulative volume descending: volume receiving >= each dose value
    cum_v    = np.cumsum(v_sorted)
    cum_desc = total_vol - cum_v

    dvh = np.column_stack([dose_sorted, cum_desc])

    # add anchor rows: 0 Gy → 100 % and first dose value → 100 %
    dvh = np.vstack([
        [0.0,            total_vol],
        [dose_sorted[0], total_vol],
        dvh,
    ])

    # remove duplicate doses (reduce vertical lines in DVH, matches MATLAB todelete)
    dupl = np.concatenate([[False], np.diff(dvh[:, 0]) == 0])
    # keep the first of each run of duplicates (start of the vertical segment)
    dupl[np.where(np.diff(dupl.astype(int)) == 1)[0] + 1] = False
    dvh = dvh[~dupl]

    # interpolate to desired dose bins
    if dosebins_desired is not None:
        vol_out = np.interp(dosebins_desired, dvh[:, 0], dvh[:, 1], right=0.0)
        dose_out = dosebins_desired
    else:
        dose_out = dvh[:, 0]
        vol_out  = dvh[:, 1]

    return dose_out, vol_out / total_vol * 100.0


def save_results_to_xlsx(dvh_parm: dict, output_file: str,
                         struct_name_1: str = 'Automatic', struct_name_2: str = 'Adjusted') -> None:
    """
    Save DVH parameters to an Excel file.

    Parameters
    ----------
    dvh_parm : dict
        Output of calculate_dvh_parameters (scalar metrics).
    output_file : str
        Path to the output .xlsx file.
    struct_name_1 : str
        Label for the automatic structure (default 'Automatic').
    struct_name_2 : str
        Label for the adjusted structure (default 'Adjusted').
    """
    import pandas as pd

    # --- DVH parameters sheet ---
    dvh_df = pd.DataFrame([{
        f'{struct_name_1}_Dmean':       dvh_parm.get('AutomaticDmean'),
        f'{struct_name_1}_Dmax':        dvh_parm.get('AutomaticDmax'),
        f'{struct_name_1}_Dmin':        dvh_parm.get('AutomaticDmin'),
        f'{struct_name_1}_Dstd':        dvh_parm.get('AutomaticDstd'),
        f'{struct_name_1}_D0.03cc':     dvh_parm.get('AutomaticD0.03cc'),
        f'{struct_name_1}_Volume_cm3':  dvh_parm.get('AutomaticVolume_cm3'),
        f'{struct_name_1}_Outside_pct': dvh_parm.get('AutomaticOutside_pct'),
        f'{struct_name_2}_Dmean':       dvh_parm.get('AdjustedDmean'),
        f'{struct_name_2}_Dmax':        dvh_parm.get('AdjustedDmax'),
        f'{struct_name_2}_Dmin':        dvh_parm.get('AdjustedDmin'),
        f'{struct_name_2}_Dstd':        dvh_parm.get('AdjustedDstd'),
        f'{struct_name_2}_D0.03cc':     dvh_parm.get('AdjustedD0.03cc'),
        f'{struct_name_2}_Volume_cm3':  dvh_parm.get('AdjustedVolume_cm3'),
        f'{struct_name_2}_Outside_pct': dvh_parm.get('AdjustedOutside_pct'),
        'DeltaDmean':                   dvh_parm.get('DeltaDmean'),
        'DeltaD0.03cc':                 dvh_parm.get('DeltaD0.03cc'),
    }])

    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        dvh_df.to_excel(writer, sheet_name='DVH_Parameters', index=False)

    print(f"Results saved to: {output_file}")


# ============================================================================
# RTDOSE READER
# ============================================================================

def read_rtdose(rtdose_path: str) -> dict:
    """
    Read an RTDOSE DICOM file and return a dose_int dict matching the
    format expected by calculate_dvh_parameters.

    The dose_ct grid dict is built using the exact same axis conventions as
    read_dicomct_light so that resample_contour_slices maps RTSTRUCT world
    coordinates onto the dose array correctly:

        PixelSpacingXi = PixelSpacing[0] / 10  (Xi axis, matches CT)
        PixelSpacingZi = PixelSpacing[1] / 10  (Zi axis, matches CT)
        PixelFirstXi   = ImagePositionPatient[0] / 10
        PixelFirstYi   = (ImagePositionPatient[2] + GridFrameOffsetVector[0]) / 10
        PixelFirstZi   = (-ImagePositionPatient[1] / 10) - PixelSpacingZi * (Rows - 1)

    The dose cube is transposed from (frames, rows, cols) to (cols, frames, rows)
    and the rows axis is flipped so that axis-2 index 0 = most posterior voxel,
    matching the CT image convention used by resample_contour_slices.

    Returns
    -------
    dict with keys:
        'cube'       : 3D ndarray of dose values (Gy), shape (Columns, Frames, Rows)
        'resolution' : dict with 'x', 'y', 'z' voxel spacing in cm
        'ct'         : CT-compatible grid dict for resample_contour_slices
    """
    ds = pydicom.dcmread(rtdose_path)
    scaling = float(ds.DoseGridScaling)
    pixel_array = ds.pixel_array.astype(np.float64) * scaling  # (frames, rows, cols)

    pixel_spacing  = ds.PixelSpacing           # [row_spacing, col_spacing] in mm
    image_position = [float(v) for v in ds.ImagePositionPatient]  # [X, Y, Z] mm LPS
    grid_offsets   = np.array(ds.GridFrameOffsetVector, dtype=float)  # mm along slice axis

    n_cols   = int(ds.Columns)        # Xi dimension (LR = column direction)
    n_rows   = int(ds.Rows)           # Zi dimension (AP = row direction)
    n_frames = len(grid_offsets)      # Yi dimension (SI = frame direction)

    # -------------------------------------------------------------------------
    # Patient orientation (HFS / HFP / FFS / FFP)
    # Matches fCalcDVHfromDCM_FV: detect from ImageOrientationPatient and
    # GridFrameOffsetVector sign, then flip pixel_array so that after transpose:
    #   col axis (axis 2 of raw array) increases in +LR (DICOM X)
    #   row axis (axis 1 of raw array) increases in +AP (DICOM Y)
    #   frame axis (axis 0) increases in +SI (DICOM Z)
    # For HFS all three flips are +1 and nothing is changed.
    # -------------------------------------------------------------------------
    orientation  = [float(v) for v in ds.ImageOrientationPatient]
    flip_lr = int(np.sign(orientation[0]))   # +1 HFS/FFP; -1 HFP/FFS
    flip_ap = int(np.sign(orientation[4]))   # +1 HFS/FFS; -1 HFP/FFP
    flip_si = int(np.sign(grid_offsets[-1] - grid_offsets[0])) if len(grid_offsets) > 1 else 1

    if flip_lr < 0:
        pixel_array = np.flip(pixel_array, axis=2)   # flip LR (cols)
    if flip_ap < 0:
        pixel_array = np.flip(pixel_array, axis=1)   # flip AP (rows)
    if flip_si < 0:
        pixel_array = np.flip(pixel_array, axis=0)   # flip SI (frames)
        grid_offsets = grid_offsets[::-1].copy()

    # Spacings in cm (keep PixelSpacing[0]/[1] assignment matching read_dicomct_light)
    px_x = float(pixel_spacing[0]) / 10.0   # cm, Xi (LR) axis spacing
    px_z = float(pixel_spacing[1]) / 10.0   # cm, Zi (AP) axis spacing
    px_y = float(abs(grid_offsets[1] - grid_offsets[0])) / 10.0 if len(grid_offsets) > 1 else 1.0

    # Transpose to (cols, frames, rows) = (Xi=LR, Yi=SI, Zi_raw=AP) then flip
    # the rows axis so Zi[0] = most-posterior voxel (highest AP value),
    # i.e. Zi increases in the −AP direction (matching read_dicomct_light convention).
    cube_transposed = np.transpose(pixel_array, (2, 0, 1))
    cube = np.ascontiguousarray(np.flip(cube_transposed, axis=2))

    # Origins — account for patient orientation.
    # After orientation flips, col 0 = minimum LR, row 0 = minimum AP.
    lr_first_mm  = image_position[0] + min(0.0, flip_lr * (n_cols - 1) * float(pixel_spacing[0]))
    ap_first_mm  = image_position[1] + min(0.0, flip_ap * (n_rows - 1) * float(pixel_spacing[1]))
    ap_max_mm    = ap_first_mm + (n_rows - 1) * float(pixel_spacing[1])

    px_first_x = lr_first_mm / 10.0
    px_first_y = (image_position[2] + float(grid_offsets[0])) / 10.0
    px_first_z = -ap_max_mm / 10.0

    dose_ct = {
        'PixelFirstXi':   px_first_x,
        'PixelFirstYi':   px_first_y,
        'PixelFirstZi':   px_first_z,
        'PixelSpacingXi': px_x,
        'PixelSpacingYi': px_y,
        'PixelSpacingZi': px_z,
        'PixelNumXi':     n_cols,
        'PixelNumYi':     n_frames,
        'PixelNumZi':     n_rows,
    }

    resolution = {
        'x': px_x,
        'y': px_y,
        'z': px_z,
    }

    return {'cube': cube, 'resolution': resolution, 'ct': dose_ct}


def scan_rtdose_files(patient_folder: str) -> list:
    """Walk patient_folder/RTDOSE/ and return paths to all RTDOSE .dcm files."""
    rtdose_folder = os.path.join(patient_folder, 'RTDOSE')
    if not os.path.isdir(rtdose_folder):
        rtdose_folder = patient_folder

    paths = []
    for dirpath, _, filenames in os.walk(rtdose_folder):
        for fn in filenames:
            if fn.lower().endswith('.dcm'):
                fpath = os.path.join(dirpath, fn)
                try:
                    ds = pydicom.dcmread(fpath, stop_before_pixels=True)
                    if ds.get('Modality', '') == 'RTDOSE':
                        paths.append(fpath)
                except Exception:
                    pass
    return paths


def find_matching_rtdose(patient_folder: str, rtplan_sop_uid: str,
                         ct_for_uid: str) -> str | None:
    """
    Select the correct RTDOSE file for a given DICOM chain.

    Matching priority (from inspect_rtdose_chain logic):
      Within each tier, candidates with DoseSummationType == 'PLAN' are
      preferred over those without.

      1. FoR match + RTPLAN UID match + DoseSummationType == 'PLAN'  (best)
      1b. FoR match + RTPLAN UID match (any DoseSummationType)
      2. RTPLAN UID match only, FoR mismatch                         (warn)
      3. FoR match only, no RTPLAN reference                         (warn)
      4. First RTDOSE found anywhere                                  (warn)

    Parameters
    ----------
    patient_folder : str
        Root folder for the patient.
    rtplan_sop_uid : str
        SOPInstanceUID of the approved RTPLAN in the chain.
    ct_for_uid : str
        FrameOfReferenceUID of the CT series in the chain.

    Returns
    -------
    tuple (str or None, str)
        (absolute path to the selected RTDOSE file or None, status string)
    """
    rtdose_folder = os.path.join(patient_folder, 'RTDOSE')
    if not os.path.isdir(rtdose_folder):
        rtdose_folder = patient_folder

    candidates = []   # list of (path, for_uid, ref_plan_uid, dose_sum_type)
    for dirpath, _, filenames in os.walk(rtdose_folder):
        for fn in sorted(filenames):
            if not fn.lower().endswith('.dcm'):
                continue
            fpath = os.path.join(dirpath, fn)
            try:
                ds = pydicom.dcmread(fpath, stop_before_pixels=True)
                if ds.get('Modality', '') != 'RTDOSE':
                    continue
                rd_for = str(ds.get('FrameOfReferenceUID', '')).strip()
                dose_sum_type = str(ds.get('DoseSummationType', '')).strip()
                # ReferencedRTPlanSequence (300C,0002)
                ref_plan = ''
                try:
                    seq = ds[0x300C, 0x0002].value
                    if seq:
                        ref_plan = str(seq[0].ReferencedSOPInstanceUID).strip()
                except (KeyError, AttributeError, IndexError):
                    pass
                candidates.append((fpath, rd_for, ref_plan, dose_sum_type))
            except Exception:
                pass

    if not candidates:
        return None, 'NO RTDOSE'

    # Log all candidates considered
    print(f"  [INFO] RTDOSE candidates evaluated ({len(candidates)}):")
    for path, rd_for, ref_plan, dst in candidates:
        for_ok   = '✓' if rd_for   == ct_for_uid     else '✗'
        plan_ok  = '✓' if ref_plan == rtplan_sop_uid else '✗'
        print(f"    {os.path.basename(path):40s}  "
              f"FoR={for_ok}  RTPLAN={plan_ok}  DoseSummationType={dst!r}")

    # Priority 1: FoR match + RTPLAN UID match — prefer DoseSummationType == 'PLAN'
    for path, rd_for, ref_plan, dst in candidates:
        if rd_for == ct_for_uid and ref_plan == rtplan_sop_uid and dst == 'PLAN':
            return path, 'FoR+RTPLAN+PLAN'
    for path, rd_for, ref_plan, dst in candidates:
        if rd_for == ct_for_uid and ref_plan == rtplan_sop_uid:
            print(f"  [WARN] RTDOSE matched but DoseSummationType={dst!r} "
                  f"(expected 'PLAN'): {os.path.basename(path)}")
            return path, f'FoR+RTPLAN (DoseSummationType={dst})'

    # Priority 2: RTPLAN UID match only (FoR mismatch — unusual but usable)
    for path, rd_for, ref_plan, dst in candidates:
        if ref_plan == rtplan_sop_uid:
            print(f"  [WARN] RTDOSE matched by RTPLAN UID but FoR mismatch "
                  f"(DoseSummationType={dst!r}): {os.path.basename(path)}")
            return path, f'RTPLAN only, FoR mismatch (DoseSummationType={dst})'

    # Priority 3: FoR match only (no RTPLAN reference in RTDOSE)
    for path, rd_for, ref_plan, dst in candidates:
        if rd_for == ct_for_uid:
            print(f"  [WARN] RTDOSE matched by FoR UID only, no RTPLAN ref "
                  f"(DoseSummationType={dst!r}): {os.path.basename(path)}")
            return path, f'FoR only, no RTPLAN ref (DoseSummationType={dst})'

    # Priority 4: first available (last resort)
    print(f"  [WARN] No UID-matched RTDOSE found, using first available: "
          f"{os.path.basename(candidates[0][0])}")
    return candidates[0][0], 'No UID match, first available'


# ============================================================================
# CT SPACING DERIVATION FROM RTSTRUCT
# ============================================================================

def _derive_ct_spacing_from_rtstruct(struct_slices: list) -> list:
    """
    Estimate CT grid spacing from RTSTRUCT contour coordinates when no CT
    DICOM series is available.

    Matches fCalcDVHfromDCM_FV 'derivefromrtstruct' mode:
      - In-plane spacing: most frequent non-zero step in contour X/Z point diffs
        (wand-tool contours align exactly to CT voxel centres).
      - Slice spacing: median of unique Y (SI) value differences.

    Parameters
    ----------
    struct_slices : list of dict
        ContourSequence slice list with 'X', 'Y', 'Z' keys (cm).

    Returns
    -------
    list [sx_cm, sy_cm, sz_cm] or None if derivation fails.
    """
    # --- Slice (SI) spacing from unique Y values ---
    y_vals = [sl['Y'][0] for sl in struct_slices
              if sl['Y'] is not None and len(sl['Y']) > 0]
    if len(y_vals) < 2:
        return None
    unique_y = np.unique(y_vals)
    y_diffs  = np.diff(np.sort(unique_y))
    y_diffs  = y_diffs[y_diffs > 1e-4]
    if len(y_diffs) == 0:
        return None
    sy = float(np.median(y_diffs))

    # --- In-plane spacing: mode of per-step absolute diffs within contours ---
    all_dx, all_dz = [], []
    for sl in struct_slices:
        if sl['X'] is None or len(sl['X']) < 2:
            continue
        dx = np.abs(np.diff(sl['X']))
        dz = np.abs(np.diff(sl['Z']))
        all_dx.extend(dx[dx > 1e-4].tolist())
        all_dz.extend(dz[dz > 1e-4].tolist())

    if not all_dx or not all_dz:
        return None

    def _mode(diffs):
        rounded = np.round(np.array(diffs), 4)
        vals, counts = np.unique(rounded, return_counts=True)
        return float(vals[np.argmax(counts)])

    sx = _mode(all_dx)
    sz = _mode(all_dz)

    # Sanity bounds: 0.1 mm – 10 mm in cm
    if not (0.01 <= sx <= 1.0 and 0.01 <= sz <= 1.0 and 0.05 <= sy <= 2.0):
        return None

    return [sx, sy, sz]


# ============================================================================
# MAIN: ITERATE OVER ALL PATIENTS
# ============================================================================

def process_all_patients(dicom_root: str, output_file: str,
                         max_patients: int = None) -> None:
    """
    Iterate over patient folders in dicom_root, compute DVH parameters
    for each complete DICOM chain, and save aggregated results to output_file.

    Parameters
    ----------
    dicom_root : str
        Root ICoNEA DICOM directory.
    output_file : str
        Path for the output Excel file.
    max_patients : int, optional
        Maximum number of patients to process. If None, all patients are processed.
    """
    from quantifycontourdifferences_P0728_v5 import discover_patient_folders, identify_dicom_chain
    patients = discover_patient_folders(dicom_root)
    print(f"Found {len(patients)} patient folders.")

    if max_patients is not None:
        patients = patients[:max_patients]
        print(f"Limited to first {max_patients} patient(s).")

    all_dvh_rows = []      # scalar metrics, one row per chain/structure pair

    for patient in patients:
        patient_id = patient['patient_id']
        patient_folder = patient['patient_folder']
        print(f"\n{'='*60}")
        print(f"Patient: {patient_id}")

        try:
            chains = identify_dicom_chain(patient_folder, verbose=False)
        except Exception as e:
            print(f"  [ERROR] Chain identification failed: {e}")
            continue

        for chain in chains:
            if chain.get('chain_status') != 'Complete':
                continue
            if not chain.get('clinical_rtstruct') or not chain.get('limbus_ai_rtstruct'):
                continue
            if not chain.get('ct_series'):
                continue

            print(f"  Chain: {chain['clinical_rtstruct']['filename']}")

            try:
                # --- Load both RTSTRUCTs first (needed for CT-spacing fallback) ---
                rtstruct_auto = read_dicomrtstruct(
                    chain['limbus_ai_rtstruct']['path'], verbose=False)
                rtstruct_adj = read_dicomrtstruct(
                    chain['clinical_rtstruct']['path'], verbose=False)

                # --- Find RTDOSE (UID-linked to the approved RTPLAN in the chain) ---
                rtplan_sop_uid = chain['rtplan']['sop_instance_uid']
                ct_for_uid     = chain['ct_series']['frame_ref_uid']
                rtplan_file    = chain['rtplan'].get('filename', '')
                rtplan_label   = chain['rtplan'].get('plan_label', '') or chain['rtplan'].get('plan_name', '')
                print(f"  [INFO] RTPLAN considered: {rtplan_file} (label={rtplan_label!r})")
                rtdose_path, rtdose_id_status = find_matching_rtdose(
                    patient_folder, rtplan_sop_uid, ct_for_uid)
                if not rtdose_path:
                    print(f"  [SKIP] No RTDOSE file found for {patient_id}")
                    continue
                print(f"  [INFO] RTDOSE selected: {os.path.basename(rtdose_path)} "
                      f"[{rtdose_id_status}]")
                dose_int = read_rtdose(rtdose_path)

                # --- Load CT grid (fine rasterisation grid for DVH) ---
                # Priority:
                #   1. CT DICOM series via read_dicomct_light   (best accuracy)
                #   2. CT spacing derived from RTSTRUCT coordinates (no CT files)
                #      → builds a synthetic grid over the dose grid extent
                #   3. Dose grid itself                          (coarsest fallback)
                ct_files = chain['ct_series']['files']
                ct_grid  = None
                try:
                    ct_grid = read_dicomct_light(ct_files, read_image_data=False)
                    print(f"  [INFO] CT grid loaded from DICOM CT series")
                except Exception as e:
                    print(f"  [WARN] CT grid load failed: {e}")
                    # --- Fallback: derive CT spacing from RTSTRUCT ---
                    # Use the first structure with enough points
                    derived = None
                    for s in rtstruct_auto['Struct']:
                        derived = _derive_ct_spacing_from_rtstruct(s['Slice'])
                        if derived:
                            break
                    if derived:
                        # Build synthetic CT grid covering the dose grid extent
                        # at the derived in-plane spacing
                        dc = dose_int['ct']
                        sx_ct, sy_ct, sz_ct = derived
                        ct_grid = {
                            'PixelFirstXi':   dc['PixelFirstXi'],
                            'PixelFirstYi':   dc['PixelFirstYi'],
                            'PixelFirstZi':   dc['PixelFirstZi'],
                            'PixelSpacingXi': sx_ct,
                            'PixelSpacingYi': dc['PixelSpacingYi'],
                            'PixelSpacingZi': sz_ct,
                            'PixelNumXi': max(1, int(np.ceil(
                                dc['PixelSpacingXi'] * dc['PixelNumXi'] / sx_ct))),
                            'PixelNumYi': dc['PixelNumYi'],
                            'PixelNumZi': max(1, int(np.ceil(
                                dc['PixelSpacingZi'] * dc['PixelNumZi'] / sz_ct))),
                        }
                        print(f"  [INFO] CT spacing derived from RTSTRUCT: "
                              f"Xi={sx_ct:.4f} cm, Zi={sz_ct:.4f} cm, "
                              f"Yi={sy_ct:.4f} cm")
                    else:
                        print(f"  [WARN] CT spacing derivation failed, using dose grid")
                        ct_grid = None

                # --- Process each common structure ---
                auto_names = [s['Name'] for s in rtstruct_auto['Struct']]
                adj_names  = [s['Name'] for s in rtstruct_adj['Struct']]
                common = [(i, adj_names.index(n), n)
                          for i, n in enumerate(auto_names)
                          if n in adj_names]

                n_common    = len(common)
                n_patients  = len(patients)
                patient_idx = patients.index(patient)

                for oar_idx, (struct_num_1, struct_num_2, voi_name) in enumerate(common):
                    # --- Progress meter ---
                    overall = f"[Patient {patient_idx+1}/{n_patients}]"
                    oar_prog = f"[OAR {oar_idx+1}/{n_common}]"
                    print(f"  {overall} {oar_prog} Processing: {voi_name} ...",
                          end='', flush=True)

                    t_start = time.time()
                    try:
                        dvh_parm, dVdose2, w2, voxel_vol_cm3 = (
                            calculate_dvh_parameters(
                                dose_int, struct_num_1, struct_num_2,
                                rtstruct_auto, rtstruct_adj,
                                ct_grid=ct_grid,
                            )
                        )
                        elapsed = time.time() - t_start

                        all_dvh_rows.append({
                            'PatientID':              patient_id,
                            'VOIName':                voi_name,
                            'Clinical_RTSTRUCT':      chain['clinical_rtstruct']['filename'],
                            'RTPLAN_file':            rtplan_file,
                            'RTPLAN_label':           rtplan_label,
                            'RTDOSE_file':            os.path.basename(rtdose_path),
                            'RTDOSE_id_status':       rtdose_id_status,
                            'Processing_time_s':      round(elapsed, 2),
                            'AutomaticDmean':         dvh_parm['AutomaticDmean'],
                            'AutomaticDmax':          dvh_parm['AutomaticDmax'],
                            'AutomaticDmin':          dvh_parm['AutomaticDmin'],
                            'AutomaticDstd':          dvh_parm['AutomaticDstd'],
                            'AutomaticD0.03cc':       dvh_parm['AutomaticD0.03cc'],
                            'AutomaticVolume_cm3':    dvh_parm['AutomaticVolume_cm3'],
                            'AutomaticOutside_pct':   dvh_parm['AutomaticOutside_pct'],
                            'AdjustedDmean':          dvh_parm['AdjustedDmean'],
                            'AdjustedDmax':           dvh_parm['AdjustedDmax'],
                            'AdjustedDmin':           dvh_parm['AdjustedDmin'],
                            'AdjustedDstd':           dvh_parm['AdjustedDstd'],
                            'AdjustedD0.03cc':        dvh_parm['AdjustedD0.03cc'],
                            'AdjustedVolume_cm3':     dvh_parm['AdjustedVolume_cm3'],
                            'AdjustedOutside_pct':    dvh_parm['AdjustedOutside_pct'],
                            'DeltaDmean':             dvh_parm['DeltaDmean'],
                            'DeltaD0.03cc':           dvh_parm['DeltaD0.03cc'],
                        })

                        print(f" done ({elapsed:.1f}s) — "
                              f"Dmean={dvh_parm['AdjustedDmean']:.3f}, "
                              f"Dmax={dvh_parm['AdjustedDmax']:.3f}, "
                              f"Vol={dvh_parm['AdjustedVolume_cm3']:.2f}cm³, "
                              f"Outside={dvh_parm['AdjustedOutside_pct']:.1f}%")

                    except Exception as e:
                        elapsed = time.time() - t_start
                        print(f" ERROR ({elapsed:.1f}s): {e}")
                        continue

            except Exception as e:
                print(f"  [ERROR] Processing chain: {e}")
                continue

    # --- Save aggregated results ---
    if not all_dvh_rows:
        print("\nNo results to save.")
        return

    dvh_df = pd.DataFrame(all_dvh_rows)

    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        dvh_df.to_excel(writer, sheet_name='DVH_Parameters', index=False)

    print(f"\nResults saved to: {output_file}")
    print(f"  DVH parameter rows: {len(dvh_df)}")


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    dicom_root = DICOM_ROOT_FOLDER
    max_patients = None

    if len(sys.argv) > 1:
        dicom_root = sys.argv[1]
    if len(sys.argv) > 2:
        max_patients = int(sys.argv[2]) if sys.argv[2].lower() != 'none' else None

    print("=" * 60)
    print("Calculate DVH Parameters - All Patients")
    print("=" * 60)
    print(f"DICOM root:   {dicom_root}")
    print(f"Output file:  {OUTPUT_FILE}")
    print(f"Max patients: {max_patients if max_patients is not None else 'All'}")
    print("=" * 60)

    process_all_patients(dicom_root, OUTPUT_FILE, max_patients)

