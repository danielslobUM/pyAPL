function [N_voxels_outside] = ...
    calculateVoxelDiffCounts(CT, STRUCT_ref, STRUCT_new, struct_num_1, struct_num_2, tolerance)

[Contour1, mmOC] = resampleContourSlices(STRUCT_ref.Struct(struct_num_1).Slice, CT, STRUCT_ref.Struct(struct_num_1).Name);
[Contour2, mmNC] = resampleContourSlices(STRUCT_new.Struct(struct_num_2).Slice, CT, STRUCT_new.Struct(struct_num_2).Name);

range = 20;
minX = min(mmOC.minX, mmNC.minX) - range;  maxX = max(mmOC.maxX, mmNC.maxX) + range;
minZ = min(mmOC.minZ, mmNC.minZ) - range;  maxZ = max(mmOC.maxZ, mmNC.maxZ) + range;
minX = max(1, minX);  maxX = min(CT.PixelNumXi, maxX);
minZ = max(1, minZ);  maxZ = min(CT.PixelNumZi, maxZ);
if minX > maxX || minZ > maxZ
    warning('Empty crop after clamping; returning zeros.');
    N_voxels_outside = zeros(1, numel(tolerance)); return;
end

bw_ref_crop = shiftdim(Contour1(minX:maxX, :, minZ:maxZ), 2);
bw_new_crop = shiftdim(Contour2(minX:maxX, :, minZ:maxZ), 2);

DT = bwdistsc(bw_ref_crop, [CT.PixelSpacingXi, CT.PixelSpacingZi, CT.PixelSpacingYi]); % spacings in cm

nT = numel(tolerance);
N_voxels_outside = zeros(1, nT);
for t = 1:nT
    ref_tol = DT <= tolerance(t);                       % tolerance in cm
    diffC   = ref_tol - bw_new_crop;                    % +1 ref-only, -1 auto-only
    N_voxels_outside(t) = sum(diffC(:) == -1);          % <-- true 3-D voxel count
end
end