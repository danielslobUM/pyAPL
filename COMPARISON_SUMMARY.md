# Before/After Comparison: resample_contour_slices.py

## Summary

This document provides a side-by-side comparison of the key sections that were changed to make the Python implementation match the MATLAB code more closely.

---

## 1. Interpolation Sampling

### Before (Original Python)
```python
current_sampling = np.arange(len(rts_cs[i]['X']))
new_sampling = np.arange(0, len(rts_cs[i]['X']), 0.1)

# Interpolate X, Y, Z coordinates
f_x = interp1d(current_sampling, rts_cs[i]['X'], kind='linear')
f_y = interp1d(current_sampling, rts_cs[i]['Y'], kind='linear')
f_z = interp1d(current_sampling, rts_cs[i]['Z'], kind='linear')

rts_cs_upsamp_x = f_x(new_sampling)
rts_cs_upsamp_y = f_y(new_sampling)
rts_cs_upsamp_z = f_z(new_sampling)
```

### After (Corrected Python)
```python
current_sampling = np.arange(1, len(rts_cs[i]['X']) + 1)
new_sampling = np.arange(1, len(rts_cs[i]['X']) + 1, 0.1)

# Interpolate X, Y, Z coordinates
rts_cs_upsamp_x = np.interp(new_sampling, current_sampling, rts_cs[i]['X'])
rts_cs_upsamp_y = np.interp(new_sampling, current_sampling, rts_cs[i]['Y'])
rts_cs_upsamp_z = np.interp(new_sampling, current_sampling, rts_cs[i]['Z'])
```

### MATLAB Reference
```matlab
current_sampling = 1:length(RTS_cs(i).X); 
new_sampling = 1:0.1:length(RTS_cs(i).X);
RTS_cs_upsamp_X = interp1(current_sampling,RTS_cs(i).X,new_sampling);
```

**Change**: Match MATLAB's 1-based sampling range and use simpler `np.interp` instead of `scipy.interpolate.interp1d`

---

## 2. Coordinate to Grid Conversion

### Before (Original Python)
```python
rts_cs_grid[:, 0] = np.round((rts_cs_aux[:, 0] - ct['PixelFirstXi']) / ct['PixelSpacingXi']).astype(int)
rts_cs_grid[:, 1] = np.round((rts_cs_aux[:, 1] - ct['PixelFirstYi']) / ct['PixelSpacingYi']).astype(int)
rts_cs_grid[:, 2] = np.round((rts_cs_aux[:, 2] - ct['PixelFirstZi']) / ct['PixelSpacingZi']).astype(int)
```

### After (Corrected Python)
```python
rts_cs_grid[:, 0] = np.round((rts_cs_aux[:, 0] - ct['PixelFirstXi']) / ct['PixelSpacingXi']).astype(int) + 1
rts_cs_grid[:, 1] = np.round((rts_cs_aux[:, 1] - ct['PixelFirstYi']) / ct['PixelSpacingYi']).astype(int) + 1
rts_cs_grid[:, 2] = np.round((rts_cs_aux[:, 2] - ct['PixelFirstZi']) / ct['PixelSpacingZi']).astype(int) + 1
```

### MATLAB Reference
```matlab
RTS_cs_grid(:,1) = round((RTS_cs_aux(:,1)-CT.PixelFirstXi)./CT.PixelSpacingXi)+1;
RTS_cs_grid(:,2) = round((RTS_cs_aux(:,2)-CT.PixelFirstYi)./CT.PixelSpacingYi)+1;
RTS_cs_grid(:,3) = round((RTS_cs_aux(:,3)-CT.PixelFirstZi)./CT.PixelSpacingZi)+1;
```

**Change**: Added `+1` to maintain MATLAB's 1-based indexing convention

---

## 3. Outside Grid Validation

### Before (Original Python)
```python
# MISSING - No outside grid limit check!
```

### After (Corrected Python)
```python
# It may occur that RTSTRUCTs are far off the GRID. This is probably due to
# an error, then pixels are considered invalid
outside_grid_limit = 5  # in pixels

non_valid = ((rts_cs_grid[:, 0] < -outside_grid_limit) | 
             (rts_cs_grid[:, 1] < -outside_grid_limit) | 
             (rts_cs_grid[:, 2] < -outside_grid_limit) |
             (rts_cs_grid[:, 0] > ct['PixelNumXi'] + outside_grid_limit) |
             (rts_cs_grid[:, 1] > ct['PixelNumYi'] + outside_grid_limit) |
             (rts_cs_grid[:, 2] > ct['PixelNumZi'] + outside_grid_limit))

rts_cs_grid = rts_cs_grid[~non_valid, :]

# Check if we have any valid points left
if len(rts_cs_grid) == 0:
    # Return empty volume
    ...
```

### MATLAB Reference
```matlab
outside_grid_limit = 5; % in pixels

non_valid = (RTS_cs_grid(:,1)<-outside_grid_limit) | (RTS_cs_grid(:,2)<-outside_grid_limit) | ...
    (RTS_cs_grid(:,3)<-outside_grid_limit) | ...
    (RTS_cs_grid(:,1) > CT.PixelNumXi+outside_grid_limit) | ...
    (RTS_cs_grid(:,2) > CT.PixelNumYi+outside_grid_limit) | ...
    (RTS_cs_grid(:,3) > CT.PixelNumZi+outside_grid_limit); 

RTS_cs_grid = RTS_cs_grid(~non_valid,:);
```

**Change**: Added the completely missing outside grid limit validation

---

## 4. Boundary Clamping

### Before (Original Python)
```python
if (np.any(rts_cs_grid < 0) or 
    np.any(rts_cs_grid[:, 0] > ct['PixelNumXi'] - 1) or ...):
    
    # Clip values to valid range
    rts_cs_grid[rts_cs_grid < 0] = 0
    rts_cs_grid[rts_cs_grid[:, 0] > ct['PixelNumXi'] - 1, 0] = ct['PixelNumXi'] - 1
    ...
```

### After (Corrected Python)
```python
if (np.min(rts_cs_grid) < 1 or 
    np.max(rts_cs_grid[:, 0]) > (ct['PixelNumXi'] - 1) or ...):
    
    rts_cs_grid[rts_cs_grid < 1] = 1
    rts_cs_grid[rts_cs_grid[:, 0] > (ct['PixelNumXi'] - 1), 0] = ct['PixelNumXi'] - 1
    ...
```

### MATLAB Reference
```matlab
if (min(RTS_cs_grid(:))<1) | (max(RTS_cs_grid(:,1)) > (CT.PixelNumXi-1)) | ...
    
    RTS_cs_grid(RTS_cs_grid<1) = 1; 
    RTS_cs_grid(RTS_cs_grid(:,1)>(CT.PixelNumXi-1),1) = CT.PixelNumXi-1;
    ...
```

**Change**: Clamp to [1, NumPixels-1] instead of [0, NumPixels-1] to match MATLAB's 1-based indexing

---

## 5. Volume Creation (MOST SIGNIFICANT)

### Before (Original Python)
```python
# Create binary volume
rts_vol = np.zeros((ct['PixelNumXi'], ct['PixelNumYi'], ct['PixelNumZi']), dtype=bool)

# Group points by Y slice
unique_y = np.unique(rts_cs_grid[:, 1])
for y_slice in unique_y:
    slice_points = rts_cs_grid[rts_cs_grid[:, 1] == y_slice]
    
    if len(slice_points) > 2:
        # Use polygon to fill the contour
        x_coords = slice_points[:, 0]
        z_coords = slice_points[:, 2]
        
        try:
            rr, cc = polygon(x_coords, z_coords, shape=(ct['PixelNumXi'], ct['PixelNumZi']))
            rts_vol[rr, y_slice, cc] = True  # FILLS ENTIRE REGION!
        except:
            # If polygon fails, just mark the boundary points
            for point in slice_points:
                rts_vol[point[0], point[1], point[2]] = True
```

### After (Corrected Python)
```python
# Generate a zero-filled VOI
rts_vol = np.zeros(vol_shape)

# Convert MATLAB 1-based indices to Python 0-based indices for sub2ind equivalent
rts_cs_grid_0based = rts_cs_grid - 1

# Use ravel_multi_index to convert subscripts to linear indices
# This is the Python equivalent of MATLAB's sub2ind
rts_cs_grid_idxs = np.ravel_multi_index(
    (rts_cs_grid_0based[:, 0], rts_cs_grid_0based[:, 1], rts_cs_grid_0based[:, 2]),
    vol_shape
)

# Set the boundary points to 1 (ONLY BOUNDARY POINTS!)
rts_vol.flat[rts_cs_grid_idxs] = 1
```

### MATLAB Reference
```matlab
% Generate a zero-filled VOI and set the 1's at the boundary of the contour
RTS_cs_grid_idxs = sub2ind(size(CT.Image),RTS_cs_grid(:,1), RTS_cs_grid(:,2),RTS_cs_grid(:,3)); 
RTS_vol = zeros(size(CT.Image)); 
RTS_vol(RTS_cs_grid_idxs) = 1;  % ONLY BOUNDARY POINTS!
```

**Change**: Complete rewrite! Changed from polygon filling (which fills entire regions) to boundary marking only using `ravel_multi_index` (Python's `sub2ind` equivalent)

---

## Impact Analysis

### Original Python Issues:
1. ❌ Used 0-based interpolation range (0 to N-0.1) instead of MATLAB's 1-based (1 to N)
2. ❌ Missing outside grid limit validation entirely
3. ❌ Used 0-based indexing throughout instead of maintaining 1-based
4. ❌ Clamped to [0, NumPixels-1] instead of [1, NumPixels-1]
5. ❌ **FILLED ENTIRE CONTOUR REGIONS** instead of marking boundaries only
6. ❌ Used boolean array instead of numeric

### Corrected Python:
1. ✅ Uses 1-based interpolation range matching MATLAB
2. ✅ Includes 5-pixel outside grid limit validation
3. ✅ Maintains 1-based indexing throughout processing
4. ✅ Clamps to [1, NumPixels-1] matching MATLAB
5. ✅ **MARKS ONLY BOUNDARY POINTS** using `ravel_multi_index` (equivalent to `sub2ind`)
6. ✅ Uses numeric array matching MATLAB

### Output Difference:
The most significant difference is #5. The original Python version would produce **completely filled volumes** while MATLAB produces **hollow boundary markers**. This fundamental difference would cause all downstream processing to produce incorrect results.

For example, if you had a sphere contour:
- **Original Python**: Creates a filled sphere (all interior voxels set to 1)
- **MATLAB & Corrected Python**: Creates a hollow sphere shell (only surface voxels set to 1)

This difference would dramatically affect volume calculations, Dice coefficients, surface measurements, and all other metrics computed from these volumes.
