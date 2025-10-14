function [pathLengthAdded_new,pathLengthOriginal,pathLengthNewContour,compare_deletedFromAutomatic,compare_addedToAdjusted,everySliceContoured,slicesAutomatic] = calculatePathLength_interpolated(CT,STRUCT_ref,STRUCT_new,struct_num_1,struct_num_2)
% calculatePathLength calculates path lengths of the contours and path length that were added or adjusted 
% between two contours. 
%
% Inputs:       CT
%               STRUCT_ref      the RTSTRUCT of the first/reference dataset you want to use
%               STRUCT_new      the RTSTRUCT of the second/new dataset you want to use     
%               struct_num_1    the number of the OAR/structure within STRUCT_ref
%               struct_num_2    the number of the OAR/structure within STRUCT_new
%
% Outputs:      pathLengthAdjusted_ref      path length that is adjusted in the first/original 
%                                           contour -> often an automatic contour
%               pathLengthAdded_new         path length that was added when comparing the adjusted 
%                                           with the original contour
%               pathLengthOriginal          path length of the original contour (automatic contour)
%               pathLengthNewContour        path length of the new contour (user-adjusted contour)
%
%
%     Femke Vaassen @ MAASTRO.


disp('-   Calculating: Added path length');

% Using the function "resampleContourSlices.m" to calculate the contour of
% the structure that is wanted (e.g. the heart), using the RTSTRUCT coordinates and the CT.
Contour1 = resampleContourSlices(STRUCT_ref.Struct(struct_num_1).Slice, CT, STRUCT_ref.Struct(struct_num_1).Name);
Contour2 = resampleContourSlices(STRUCT_new.Struct(struct_num_2).Slice, CT, STRUCT_new.Struct(struct_num_2).Name);

[x,y,z] = ind2sub(size(Contour1),find(Contour1));
uniqueSlices_C1 = unique(y);
[x,y,z] = ind2sub(size(Contour2),find(Contour2));
uniqueSlices_C2 = unique(y);

Contour2_adapted = zeros(size(Contour2));
for slice = 1:size(Contour2,2)
    if find(Contour1(:,slice,:))
        Contour2_adapted(:,slice,:) = Contour2(:,slice,:);
    elseif slice < uniqueSlices_C1(1) || slice > uniqueSlices_C1(end)
        Contour2_adapted(:,slice,:) = Contour2(:,slice,:);
    end
    
    if slice == uniqueSlices_C2(1) || slice == uniqueSlices_C2(end)
        Contour2_adapted(:,slice,:) = Contour2(:,slice,:);
    end
end

if find(Contour2 - Contour2_adapted)
    [x,y,z] = ind2sub(size(Contour2_adapted),find(Contour2_adapted));
    uniqueSlices_C2_adapted = unique(y);
    
    compare_same = intersect(uniqueSlices_C1,uniqueSlices_C2_adapted);
    compare_deletedFromAutomatic = length(setdiff(uniqueSlices_C1,compare_same));
    compare_addedToAdjusted = length(setdiff(uniqueSlices_C2_adapted,compare_same));
    
    everySliceContoured = 0;
else
    compare_same = intersect(uniqueSlices_C1,uniqueSlices_C2);
    compare_deletedFromAutomatic = length(setdiff(uniqueSlices_C1,compare_same));
    compare_addedToAdjusted = length(setdiff(uniqueSlices_C2,compare_same));
    
    everySliceContoured = 1;
end
slicesAutomatic = length(uniqueSlices_C1);

% The difference between two contours is computed. This results in the
% pixels that were only present in either the first or the second contour
% of the comparison
diffContours = Contour1-Contour2_adapted;

% The path lengths are computed, based on the amount of pixels that are
% different and the pixel size (the same in X and Z direction)
pathLengthOriginal = sum(Contour1(:) == 1)*(CT.PixelSpacingXi*10); %[mm]
pathLengthNewContour = sum(Contour2(:) == 1)*(CT.PixelSpacingXi*10); %[mm]
pathLengthAdded_new = sum(diffContours(:) == -1)*(CT.PixelSpacingXi*10); %[mm]

end