 function [pathLengthOutside] = calculatePathLength(image,STRUCT_ref,STRUCT_new,struct_num_1,struct_num_2,tolerance)
% calculatePathLength calculates path lengths of the contours and path length that were added or adjusted
% between two contours.
%
% Inputs:       CT
%               STRUCT_ref      the RTSTRUCT of the first/reference dataset you want to use
%               STRUCT_new      the RTSTRUCT of the second/new dataset you want to use
%               struct_num_1    the number of the OAR/structure within STRUCT_ref
%               struct_num_2    the number of the OAR/structure within STRUCT_new
%               tolerance       tolerance between the two contours that is accepted
%
% Outputs:      pathLengthOutside           path length that is different in the second contour
%                                           compared to the first contour
%
%     Femke Vaassen @ MAASTRO.
%     17/08 Daniël Slob: added 'tolerance' to function. This is excluded in
%     the original script of Femke.

disp(['Analyzing Structure: ', STRUCT_ref.Struct(struct_num_1).Name]);
disp('-   Calculating: Added Path Length');

% Using the function "resampleContourSlices.m" to calculate the contour of
% the structure that is wanted (e.g. the heart), using the RTSTRUCT coordinates and the CT.
[Contour1,minmax_OC] = resampleContourSlices(STRUCT_ref.Struct(struct_num_1).Slice, image, STRUCT_ref.Struct(struct_num_1).Name);
[Contour2,minmax_NC] = resampleContourSlices(STRUCT_new.Struct(struct_num_2).Slice, image, STRUCT_new.Struct(struct_num_2).Name);


% Making sure unnecessary pixels (i.e. pixels that are outside of the two
% contours) are not taken into in the calculation to speed up the process.
% The maximal and minimal X and Z pixels are calculated, taking all slices
% into account. A margin is used to be sure.
margin = 15;
minX = min(minmax_OC.minX, minmax_NC.minX)-margin;
maxX = max(minmax_OC.maxX, minmax_NC.maxX)+margin;
minZ = min(minmax_OC.minZ, minmax_NC.minZ)-margin;
maxZ = max(minmax_OC.maxZ, minmax_NC.maxZ)+margin;

% Compute the minimal distance of each pixel in a slice towards the reference contour
distance_C1 = bwdistsc(shiftdim(Contour1(minX:maxX,:,minZ:maxZ),2),[image.PixelSpacingXi, image.PixelSpacingZi, image.PixelSpacingYi]);

% When taking a tolerance into account, contours that are within this
% tolerance are accepted as overlapping (comparing manual to
% automatic). When this tolerance is set to 0, only perfectly overlapping
% contours are accepted (comparing automatic to user-adjusted).

pathLengthOutside = zeros(image.PixelNumYi,length(tolerance));

Contour1_tol = distance_C1 <= tolerance;

% % Compute the minimal distance of each pixel in a slice towards the new contour
% distance_C2 = bwdistsc(shiftdim(Contour2(minX:maxX,:,minZ:maxZ),2),[CT.PixelSpacingXi, CT.PixelSpacingZi, CT.PixelSpacingYi]); %(minX:maxX,:,minZ:maxZ)
%
% diff2 = distance_C2 <= tolerance;


% FROM ADDED PATH LENGTH

% The difference between two contours is computed. This results in the
% pixels that were only present in either the first or the second contour
% of the comparison
diffContours = Contour1_tol-shiftdim(Contour2(minX:maxX,:,minZ:maxZ),2);

% The path lengths are computed, based on the amount of pixels that are
% different and the pixel size (the same in X and Z direction)

for ii = 1:image.PixelNumYi
    
    diff_slice_contour = diffContours(:,:,ii);
    slice_contour1 = Contour1(minX:maxX,ii,minZ:maxZ);
    slice_contour2 = Contour2(minX:maxX,ii,minZ:maxZ);
   
    
    pathLengthOutside(ii) = sum(diff_slice_contour(:) == -1)*(image.PixelSpacingXi*10); %( ((sqrt(2)*image.PixelSpacingXi*10)/2) + (image.PixelSpacingXi*10/2) );%(CT.PixelSpacingXi*10); %[mm] - pixels where the automatic is outside the GT+tolerance contour
    
    if sum(slice_contour1(:) == 1) == 0 && sum(slice_contour2(:) == 1) ~= 0
        %no pixels in GT
        disp(['    -- Slice ' num2str(ii) ' contains a GT contour but no automatic contour: all pixels are added to total'])
    end
    
    if sum(slice_contour1(:) == 1) ~= 0 && sum(slice_contour2(:) == 1) == 0
        %no pixels in GT
        disp(['    -- Slice ' num2str(ii) ' contains no GT contour but does contain an automatic contour'])
    end
    
end

end