function Matrix = compose_struct_matrix(Scan,RTStructFile)
% function Matrix = compose_struct_matrix(Scan,RTStructFile)
% Builds a matrix of zeros and adds to all voxels within the nth contour
% the value 2^(n-1). So if a voxel lies within the firt, third and 5th
% contour its value is 2^0 + 2^2 + 2^4 = 21. It goes wrong if there are
% more than 31 contours!!
% -------------------------------------------------------------------------
% INPUT
%--------------------------------------------------------------------------
% NAME              TYPE        DESCRIPTION
% RTStructFile      char/struct RTstructFile or Struct read with
%                               read_dicomrtstruct
% Scan                struct    PT/Scan scan read with read_dicompet / read_dicomct
%--------------------------------------------------------------------------
% OUTPUT
% Matrix            uint16      Contains the contours in matrix
%                               representation
%--------------------------------------------------------------------------
% NAME              TYPE        DESCRIPTION

%--------------------------------------------------------------------------
% INTERNAL VARIABLE DEFINITION
%--------------------------------------------------------------------------
% NAME              TYPE        DESCRIPTION
%--------------------------------------------------------------------------
% FUNCTIONS & MEC files called
%--------------------------------------------------------------------------

%--------------------------------------------------------------------------
% HISTORY
%--------------------------------------------------------------------------
% 29/06/2009, Steven Petit, creation
% 09/09/2009, Steven Petit, replace uint16 with uint32. The maximum number
% of contours is now 31.
% 10/09/09, Steven Petit, adpated the code such that a VOI is also generated
%           from the patient contour
% 16/09/09, Steven Petit, removed VOI from the patient contour
% 18/09/2009, Steven Petit. Removed the rouding at the transformation of
%                          structure coordinates to grid indeces, needed for
%                          poly2maks. The rouding caused a small offset
%                          between the contour and the mask.
% 18/09/2009, Steven Petit : added comments and to changed name CT to Scan,
%                            beacuse method works also with a PET scan
% 18/11/2009, W. van Elmpt, make use of bitset/bitget for speed and
%                           indexing up to 64 structures.
%                           Removed some obsolete coding
% 27/09/2011, Ralph Leijenaar, speed improvement
%   - removed obsolete coding
%   - per-slice direct indexing with bitset into variable Matrix
%--------------------------------------------------------------------------


disp('Composing VOI of structures')
% warning off
if ischar(RTStructFile)
    StructIN = read_dicomrtstruct(RTStructFile);
elseif isstruct(RTStructFile)
    StructIN = RTStructFile;
end

yct = Scan.PixelFirstYi + (0:Scan.PixelNumYi-1)*Scan.PixelSpacingYi;

% Matrix = uint32(zeros(size(Scan.Image)));
if StructIN.StructNum <= 16
    Matrix = zeros(size(Scan.Image),'uint16');
elseif StructIN.StructNum > 16 && StructIN.StructNum <= 32
    Matrix = zeros(size(Scan.Image),'uint32');
elseif StructIN.StructNum > 32 && StructIN.StructNum <= 64
    Matrix = zeros(size(Scan.Image),'uint64');
elseif StructIN.StructNum > 65
    disp('-   Too many structs Only doing first 64 -');
    %     return;
    Matrix = zeros(size(Scan.Image),'uint64');
    StructIN.StructNum = 64;
end


for i=1:StructIN.StructNum
    %     if ~strcmp(StructIN.Struct(i).Name,'Patient')
    %     disp(['-   Calculating: ',StructIN.Struct(i).Name]);
    if  length(StructIN.Struct(i).Slice)>1
        Warning1 = 0;
        Warning2 = 0;
        for j=1:length(StructIN.Struct(i).Slice)
            DoProcess = 0;
            if ~isempty(StructIN.Struct(i).Slice(j).Y) %25-03-2020 Femke: added this to account for problems with empty rows
                Xsamp = (StructIN.Struct(i).Slice(j).X - Scan.PixelFirstXi)/ Scan.PixelSpacingXi  +1;
                Zsamp = (StructIN.Struct(i).Slice(j).Z - Scan.PixelFirstZi)/ Scan.PixelSpacingZi  +1;
                Ysamp = (StructIN.Struct(i).Slice(j).Y(1) - Scan.PixelFirstYi)/ Scan.PixelSpacingYi  +1;
                
                if ~isempty(find(abs(yct-StructIN.Struct(i).Slice(j).Y(1))<0.0001, 1))
                    DoProcess = 1;
                elseif StructIN.Struct(i).Slice(j).Y(1) < min(yct) || ...
                        StructIN.Struct(i).Slice(j).Y(1) > max(yct)
                    Warning1 = 1;
                    %break; %14-04-2020 Femke: commented because otherwise errors for Spinal Cord for some patients
                elseif ~isempty(find(abs(yct-StructIN.Struct(i).Slice(j).Y(1))<=0.11, 1))
                    Warning2 = 1;
                    DoProcess = 1;
                else
                    disp('-   Discrepancy between y-position slice and contour')
                    break;
                end
                
                if DoProcess
                    %   get linear indices, because bitset is extremely slow with
                    %   logical indices..
                    [z,x] = find(poly2mask(Zsamp,Xsamp,Scan.PixelNumXi,Scan.PixelNumZi));
                    ind3d = sub2ind(size(Scan.Image),z,repmat(round(Ysamp),size(x)),x);
                    Matrix(ind3d) = bitset(Matrix(ind3d),i,1);
                end
            end
        end
        if Warning1
            disp('-   Warning: span y-pos contour is larger than image')
        end
        if Warning2
            disp('-   Warning: 1 mm discrepancy is allowed between slice and contour y-position!')
        end
    end
    %     end
end




