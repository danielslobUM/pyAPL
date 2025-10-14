function dice = calculateDice(VOI1,VOI2,struct_num_1,struct_num_2)
% calculateDice calculates the Dice coefficient between two contours in
% terms of overlapping volume. 
%
% The build-in Matlab funcion bitget is used to get the correct contour
% within the VOI. 
% 
% dice = 2 |X ? Y|      using the volumes
%        ----------
%        |X| + |Y|   
%
% Inputs:       2 VOIs          2 volumes of interest of two structure sets. These VOIs include all 
%                               OARs/structures available in the RTSTRUCT that was used as input    
%               struct_num_1    the number of the OAR/structure within VOI1
%               struct_num_2    the number of the OAR/structure within VOI2
%
% Outputs:      dice            the dice similarity coefficient, represented as a fraction
%
%
%     Femke Vaassen @ MAASTRO.


disp('-   Calculating: Dice similarity coefficient');

% Taking the structure that is wanted (e.g. the heart) out of the VOI using bitget
VOI1 = bitget(VOI1,struct_num_1); 
VOI1 = double(VOI1);

VOI2 = bitget(VOI2,struct_num_2);
VOI2 = double(VOI2);

% Calculating the overlapping pixels and using that to calculate the dice
% similarity coefficient.
pixelDataOverlap = VOI1 & VOI2; 
dice = (2*sum(pixelDataOverlap(:))) / (sum(VOI1(:))+ sum(VOI2(:))); 

end