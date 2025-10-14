function [surface_dsc] = calculateSurfaceDSC(CT,STRUCT_ref,STRUCT_new,struct_num_1,struct_num_2,tolerance)
% calculateSurfaceDSC calculates surface dsc between two contours in terms
% of overlapping surfaces.
%
% The funcion bwdistsc is used to calculate the Euclidean distance transform of a binary 3D image BW.
%
% surface dsc = 2 |X ? Y|   using the contours/surfaces
%               ----------
%               |X| + |Y|
%
% Inputs:       CT
%               STRUCT_ref      the RTSTRUCT of the first/reference dataset you want to use
%               STRUCT_new      the RTSTRUCT of the second/new dataset you want to use
%               struct_num_1    the number of the OAR/structure within STRUCT_ref
%               struct_num_2    the number of the OAR/structure within STRUCT_new
%               tolerance       defining the margin for when a contour would be acceptable
%                               (used when comparing manual to automatic segmentation)
%
% Outputs:      surface_dsc      the surface DSC, represented as a fraction
%
%
%     Femke Vaassen @ MAASTRO.


disp('-   Calculating: Surface DSC');

% Using the function "resampleContourSlices.m" to calculate the contour of
% the structure that is wanted (e.g. the heart), using the RTSTRUCT coordinates and the CT.
[Contour1,minmax_OC] = resampleContourSlices(STRUCT_ref.Struct(struct_num_1).Slice, CT, STRUCT_ref.Struct(struct_num_1).Name);
[Contour2,minmax_NC] = resampleContourSlices(STRUCT_new.Struct(struct_num_2).Slice, CT, STRUCT_new.Struct(struct_num_2).Name);


% Making sure unnecessary pixels (i.e. pixels that are outside of the two
% contours) are not taken into in the calculation to speed up the process.
% The maximal and minimal X and Z pixels are calculated, taking all slices
% into account. A margin is used to be sure.
range = 20;
minX = min(minmax_OC.minX, minmax_NC.minX)-range;
maxX = max(minmax_OC.maxX, minmax_NC.maxX)+range;
minZ = min(minmax_OC.minZ, minmax_NC.minZ)-range;
maxZ = max(minmax_OC.maxZ, minmax_NC.maxZ)+range;


% Compute the minimal distance of each pixel in a slice towards the reference contour
distance_C1 = bwdistsc(shiftdim(Contour1(minX:maxX,:,minZ:maxZ),2),[CT.PixelSpacingXi, CT.PixelSpacingZi, CT.PixelSpacingYi]);

% When taking a tolerance into account, contours that are within this
% tolerance are accepted as overlapping (comparing manual to
% automatic). When this tolerance is set to 0, only perfectly overlapping
% contours are accepted (comparing automatic to user-adjusted).
for tol_idx = 1:length(tolerance)
    diff1 = distance_C1 <= tolerance(tol_idx);
    
    % Compute the minimal distance of each pixel in a slice towards the new contour
    distance_C2 = bwdistsc(shiftdim(Contour2(minX:maxX,:,minZ:maxZ),2),[CT.PixelSpacingXi, CT.PixelSpacingZi, CT.PixelSpacingYi]); %(minX:maxX,:,minZ:maxZ)
    
    diff2 = distance_C2 <= tolerance(tol_idx);
    
    % Calculating the overlapping pixels within the surfaces and using that to calculate the surface dsc
    pixelDataOverlap1 = shiftdim(Contour1(minX:maxX,:,minZ:maxZ),2) & diff2;
    pixelDataOverlap2 = shiftdim(Contour2(minX:maxX,:,minZ:maxZ),2) & diff1;
    
    C1B2 = sum(pixelDataOverlap1(:));
    C2B1 = sum(pixelDataOverlap2(:));
    
    C1 = sum(Contour1(:));
    C2 = sum(Contour2(:));
    
    
    %surface_dsc(tol_idx) = (C1B2 + C2B1) / (C1 + C2);
    surface_dsc(tol_idx) = (2*C2B1) / (C1 + C2);
end
end