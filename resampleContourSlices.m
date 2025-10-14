function [RTS_vol,minmax] = resampleContourSlices(RTS_cs, CT, st_name)
% resampleContourSlices resamples a contour using the RTSTRUCT coordinates and the CT. 
% The coordinates are upsampled to prevent open contours and then used to
% create a binary image of the contour.
%
% Inputs:       RTS_cs          ContourSequence values
%               CT
%               st_name         the name of the structure
%
% Outputs:      RTS_vol         a binary image of the upsampled coordinates
%                               of the structure
%               minmax          structure with the minimal and maximal
%                               pixel value containing contour information
%
%
%     Jose A. Baeza & Femke Vaassen @ MAASTRO.



% Upsampling the ContourSequence values to prevent open contours and
% regrouping them in one single matrix for performance.
RTS_cs_aux = [];
for i = 1:length(RTS_cs)
    if ~isempty(RTS_cs(i).X)
        current_sampling = 1:length(RTS_cs(i).X); 
        new_sampling = 1:0.1:length(RTS_cs(i).X);   
        RTS_cs_upsamp_X = interp1(current_sampling,RTS_cs(i).X,new_sampling);
        RTS_cs_upsamp_Y = interp1(current_sampling,RTS_cs(i).Y,new_sampling);
        RTS_cs_upsamp_Z = interp1(current_sampling,RTS_cs(i).Z,new_sampling);
        RTS_cs_aux = vertcat(RTS_cs_aux, [RTS_cs_upsamp_X' RTS_cs_upsamp_Y' RTS_cs_upsamp_Z']); 
    end
end

% Convert spatial positions in pixel values
RTS_cs_grid(:,1) = round((RTS_cs_aux(:,1)-CT.PixelFirstXi)./CT.PixelSpacingXi)+1;
RTS_cs_grid(:,2) = round((RTS_cs_aux(:,2)-CT.PixelFirstYi)./CT.PixelSpacingYi)+1;
RTS_cs_grid(:,3) = round((RTS_cs_aux(:,3)-CT.PixelFirstZi)./CT.PixelSpacingZi)+1;

% It may occur that RTSTRUCTs are far off the GRID. This is probably due to 
% an error, then pixels are considered invalid
outside_grid_limit = 5; % in pixels

non_valid = (RTS_cs_grid(:,1)<-outside_grid_limit) | (RTS_cs_grid(:,2)<-outside_grid_limit) | (RTS_cs_grid(:,3)<-outside_grid_limit)...
    | (RTS_cs_grid(:,1) > CT.PixelNumXi+outside_grid_limit) ...
     | (RTS_cs_grid(:,2) > CT.PixelNumYi+outside_grid_limit) ...
      | (RTS_cs_grid(:,3) > CT.PixelNumZi+outside_grid_limit); 

RTS_cs_grid = RTS_cs_grid(~non_valid,:);   
 
% Sometimes the RTSTRUCT is outside the CT grid (i.e. in BODY). 
% Pixels are forced to be between [1...PixelNum]
if (min(RTS_cs_grid(:))<1) | (max(RTS_cs_grid(:,1)) > (CT.PixelNumXi-1)) |...
        (max(RTS_cs_grid(:,2)) > (CT.PixelNumYi-1)) | (max(RTS_cs_grid(:,3)) > (CT.PixelNumZi-1)) 
    
    RTS_cs_grid(RTS_cs_grid<1) = 1; 
    RTS_cs_grid(RTS_cs_grid(:,1)>(CT.PixelNumXi-1),1) = CT.PixelNumXi-1; 
    RTS_cs_grid(RTS_cs_grid(:,2)>(CT.PixelNumYi-1),2) = CT.PixelNumYi-1; 
    RTS_cs_grid(RTS_cs_grid(:,3)>(CT.PixelNumZi-1),3) = CT.PixelNumZi-1; 
    
    fprintf(['\n PAS OP! RTSTRUCT "', st_name, '" includes points outside the current GRID \n'])
end

minmax.minX = min(RTS_cs_grid(:,1));
minmax.maxX = max(RTS_cs_grid(:,1));
minmax.minZ = min(RTS_cs_grid(:,3));
minmax.maxZ = max(RTS_cs_grid(:,3));

% Generate a zero-filled VOI and set the 1's at the boundary of the contour
RTS_cs_grid_idxs = sub2ind(size(CT.Image),RTS_cs_grid(:,1), RTS_cs_grid(:,2),RTS_cs_grid(:,3)); 
RTS_vol = zeros(size(CT.Image)); 
RTS_vol(RTS_cs_grid_idxs) = 1; 
 
end