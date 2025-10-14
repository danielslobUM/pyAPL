function CTOUT   =   read_dicomct(FilenamesIN,varargin)
% function CTOUT   =   read_dicomct(FilenamesIN)
% Reads a CT and applies IEC convention
% This function reads the DICOM images from low to high Y and fills the
% structure CTOUT with the images according to the IEC convention.

% This CT is given in the image coordinate system
%               -----------         IEC
%              /|         /|         Z
%             / |        / |        /|\
%            /  |       /  |         |   /|\ Y
%           /   |      /   |         |   /
%          /    ------/----          |  /
%          ----/------    /          | /
%         |   /      |   /           |/
%         |  /       |  /     X------|----------------->
%         | /        | /            /|
%         |/         |/            / |
%         ------------
%
% PixelFirst coordinates will be the bottom-left-corner. The CT cube will
% be addressed in the following way CT.Image(1:Width,1:Depth,1:Height) Or
% CT.Image(X,Y,Z)
%--------------------------------------------------------------------------
% INPUT
%--------------------------------------------------------------------------
% NAME              TYPE        DESCRIPTION 
% FilenamesIN       cell        Full filenames of the CT dicom files
%--------------------------------------------------------------------------
% OUTPUT
%--------------------------------------------------------------------------
% NAME              TYPE        DESCRIPTION 
% CTOUT             struct      
% .Filenames        cell        Filenames of the dicom files
% .DicomHeader      struct      The dicomheader of the first slice
% .PixelSpacingXi   double      Pixel spacing in cm/pixel X in the i cs
% .PixelSpacingYi   double      Pixel spacing in cm/pixel Y in the i cs
% .PixelSpacingZi   double      Pixel spacing in cm/pixel Z in the i cs
% .PixelNumXi       double      Number of pixels X in the i cs
% .PixelNumYi       double      Number of pixels Y in the i cs
% .PixelNumZi       double      Number of pixels Z in the i cs
% .PixelFirstXi     double      X value of pixel 1 in cm in the i cs
% .PixelFirstYi     double      Y value of pixel 1 in cm the i cs
% .PixelFirstZi     double      Z value of pixel 1 in cm the i cs
% .RescaleIntercept double      Offset to convert to hounsfield units
% .RescaleSlope     double      Slope to convert to hounsfield units
% .Image            uint16      CT Image
%--------------------------------------------------------------------------
% INTERNAL VARIABLE DEFINITION
%--------------------------------------------------------------------------
% NAME              TYPE        DESCRIPTION 
% DicomFiles        struct      Dicom file info
% Filenames         cell        Dicom filenames
% SliceNum          double      Number of slices
% SliceCur          double      Currrent slice
% DicomHeader       struct      Dicom header
% Yi                double      Value of slice in the i cs
% SliceValueYSorted double      Slices sorted from low Y to high Y
% CouchTopCorr      double      Thickness of the couch top in cm
% TopTableIndex     double      Pixel indicating the top of the table
%
%--------------------------------------------------------------------------
% FUNCTIONS & MEX files called
%--------------------------------------------------------------------------
% none
%--------------------------------------------------------------------------
% HISTORY
%--------------------------------------------------------------------------
% 08/09/2005, Andre Dekker
% Creation
%
% 13/09/2005, Lucas Persoon & Andre Dekker
% Added zero pixel intensities beneath couch top part, this deletes the
% couch from the picture. At a later time we have to check if this
% correction is sufficient.
% 
% 15/09/2005, Andre Dekker
% Changed variable names and comment to comply to standard.
%
% 19/09/2005, Andre Dekker
% Changed of to switch statement.
%
% 20/09/2005, Andre Dekker
% Removed table pixels from CT to speed up program
%
% 28/09/2005, Andre Dekker
% Redefined PixelFirstXi and PixelFirstZi 
%
% 30/09/2005, Andre Dekker
% Removed couch pixel deletion, made a seperate function
%
% 21/10/2005, Andre Dekker
% Modified call of read_dicomct, form path to a cell with the filenames
%
% 23/12/2005, Lucas Persoon
% Added a fail safe when no CT is in the directory it does nothing instead 
% of erroring
% 
% 05/01/2006, Lucas Persoon
% Changed the column width to 80
% 
% 08/02/2006, Andre Dekker
% Corrected SAMPLE CALL
%
% 01/08/2006, Lucas Persoon
% Added comment by the rotation of the matrix
% rotate matrix around x axis -90 ccw
% is necessary for IEC convention means a flip in de slice and
% reverse of z axis
% see page 137-139 IEC 61217
%
% 15/08/2006, Lucas Persoon 
% Made the PixelFirst IEC conforming and confming the new XiO version
%
% 25/09/2006, Lucas Persoon
% Changed the transformations according to the IEC-DICOM manual of MAASTRO
% created by Bas Nijsten and Lucas Persoon
%
% 18/10/2006, Lucas Persoon 
% Addded the manufacturer, institutename, tableheigth en private tableheight
% to the struct
%
% 01/11/2006, Wouter van Elmpt
% Changed the PixelFirstZi with the correct function -> (PixelNumZi-1)*PixelSpacingZ
%
% 08/12/2010, Bas Nijsten
% Added the SOP instance UIDs to the struct
%
% 27/09/2012, Bas Nijsten
% Changed the ImageOrientationPatient tag handling
%--------------------------------------------------------------------------
% SAMPLE CALL
%--------------------------------------------------------------------------
% PathCT                      =   uigetdir('C:\',...
%                                 'Select directory with CT dicom files');
% DicomFiles                  =   dir([PathCT,'\*.dcm']);
% for i=1:length(DicomFiles)
%     Filenames{i}            =   fullfile(PathCT,DicomFiles(i).name);
% end
% CT                          =   read_dicomct(Filenames);
%--------------------------------------------------------------------------

SliceNum                 =   uint16(length(FilenamesIN));
if ~(SliceNum == 2 && ~isempty(strfind(FilenamesIN{1},'\.')) && ...
    ~isempty(strfind(FilenamesIN{2},'\..')))
%beginif
%read CT otherwise something is wrong in the filenames and nothing is done

% Sort the DICOM files from low to high slice Y value, and store filenames
% and SOP instance UIDs in structure
for SliceCur=1:SliceNum
    DicomHeader          =   dicominfo(FilenamesIN{SliceCur});
    Yi(SliceCur,:)       =   [double(SliceCur),...
                             DicomHeader.ImagePositionPatient(3)];
    UIDs{SliceCur,:}     =   DicomHeader.SOPInstanceUID;
end %for SliceCur
[~,I]                    =   unique(Yi(:,2));
Yi                       =   Yi(I,:);
SliceNum                 =   size(Yi,1);
SliceValueYSorted        =   sortrows(Yi,2);
CTOUT.Filenames          =   FilenamesIN(SliceValueYSorted(:,1));
CTOUT.UIDs               =   UIDs(SliceValueYSorted(:,1))';

% Read the first Dicom header and store in structure
CTOUT.DicomHeader        =   dicominfo(CTOUT.Filenames{1});

% Store information from the Dicom header in structure for later quick
% access
CTOUT.PixelSpacingXi     =   CTOUT.DicomHeader.PixelSpacing(1)/10; 
                             %/10 for mm to cm (IEC)
YSliceThicknesses        =   abs(unique(round((Yi(1:end-1,2)-Yi(2:end,2))*1000)/1000));
if ~ isempty(YSliceThicknesses)
    CTOUT.PixelSpacingYi =   YSliceThicknesses(1)/10;
else
    CTOUT.PixelSpacingYi =   CTOUT.DicomHeader.SliceThickness/10;
end 
                             %/10 for mm to cm (IEC)
CTOUT.PixelSpacingZi     =   CTOUT.DicomHeader.PixelSpacing(2)/10; 
                             %/10 for mm to cm (IEC)
CTOUT.PixelNumXi         =   double(CTOUT.DicomHeader.Width);
CTOUT.PixelNumYi         =   double(length(CTOUT.Filenames));
CTOUT.PixelNumZi         =   double(CTOUT.DicomHeader.Height);
% if CTOUT.DicomHeader.ImageOrientationPatient == [ -1 ; 0 ; 0 ; 0 ; -1 ; 0 ] 
%     CTOUT.PixelFirstXi     =(CTOUT.DicomHeader.ImagePositionPatient(1)/10)-...
%                             (CTOUT.PixelSpacingXi*CTOUT.PixelNumXi); 
%                              %/10 for mm to cm (IEC)
%     CTOUT.PixelFirstYi     =(CTOUT.DicomHeader.ImagePositionPatient(3)/10);
%                                 %/10 for mm to cm (IEC)
%     CTOUT.PixelFirstZi     =-((CTOUT.DicomHeader.ImagePositionPatient(2)/10) -...
%                             (CTOUT.PixelSpacingZi*(CTOUT.PixelNumZi-1)));    
% else 
%     CTOUT.PixelFirstXi     =CTOUT.DicomHeader.ImagePositionPatient(1)/10; 
%                                 %/10 for mm to cm (IEC)
%     CTOUT.PixelFirstYi     =CTOUT.DicomHeader.ImagePositionPatient(3)/10; 
%                                 %/10 for mm to cm (IEC)
%     CTOUT.PixelFirstZi     =(-CTOUT.DicomHeader.ImagePositionPatient(2)/10) -...
%                             (CTOUT.PixelSpacingZi*(CTOUT.PixelNumZi-1));
% end
if sum(abs(CTOUT.DicomHeader.ImageOrientationPatient - [ 1 ; 0 ; 0 ; 0 ; 1 ; 0 ]) > 0.025) == 0
    CTOUT.PixelFirstXi   =   (CTOUT.DicomHeader.ImagePositionPatient(1)/10)-...
                                (CTOUT.DicomHeader.ImageOrientationPatient(1) == -1)*...
                                (CTOUT.PixelSpacingXi*CTOUT.PixelNumXi); 
                                %/10 for mm to cm (IEC)
    CTOUT.PixelFirstYi   =   (CTOUT.DicomHeader.ImagePositionPatient(3)/10);
                                %/10 for mm to cm (IEC)
    CTOUT.PixelFirstZi   =   (-CTOUT.DicomHeader.ImagePositionPatient(2)/10)-...
                                CTOUT.DicomHeader.ImageOrientationPatient(5)*...
                                (CTOUT.PixelSpacingZi*(CTOUT.PixelNumZi-1)); 
                                %/10 for mm to cm (IEC)
else
    CTOUT.PixelFirstXi   =   [];
    CTOUT.PixelFirstYi   =   [];
    CTOUT.PixelFirstZi   =   [];
end
    
CTOUT.RescaleIntercept   =   CTOUT.DicomHeader.RescaleIntercept;
CTOUT.RescaleSlope       =   CTOUT.DicomHeader.RescaleSlope;
if isfield(CTOUT.DicomHeader,'ManufacturerModelName')
    CTOUT.Model          =   CTOUT.DicomHeader.ManufacturerModelName;
else
    CTOUT.Model          =   [];
end
CTOUT.Manufacturer       =   CTOUT.DicomHeader.Manufacturer;

CTOUT.Institute = '';
if isfield(CTOUT.DicomHeader,'InstitutionName');
    if strfind(CTOUT.DicomHeader.InstitutionName,'Maastro')
        CTOUT.Institute = 'Maastro';
    end
end

if isfield(CTOUT.DicomHeader,'TableHeight');
   CTOUT.TableHeight     =   CTOUT.DicomHeader.TableHeight;
else
   CTOUT.TableHeight     =   0;
end

CTOUT.PrivTableHeight    =   0;

if isfield(CTOUT.DicomHeader,'Private_1099_10xx_Creator'),
    if ischar(CTOUT.DicomHeader.Private_1099_1099)
        CTOUT.PrivTableHeight=str2num(CTOUT.DicomHeader.Private_1099_1099);
    else
        CTOUT.PrivTableHeight=str2num(char(CTOUT.DicomHeader.Private_1099_1099)');
    end
end
if isfield(CTOUT.DicomHeader,'Private_1199_11xx_Creator'),
    if ischar(CTOUT.DicomHeader.Private_1199_1199)
        CTOUT.PrivTableHeight=str2num(CTOUT.DicomHeader.Private_1199_1199);
    else
        CTOUT.PrivTableHeight=str2num(char(CTOUT.DicomHeader.Private_1199_1199)');
    end
end
if isfield(CTOUT.DicomHeader,'Private_1299_12xx_Creator'),
    if ischar(CTOUT.DicomHeader.Private_1299_1299)
        CTOUT.PrivTableHeight=str2num(CTOUT.DicomHeader.Private_1299_1299);
    else
        CTOUT.PrivTableHeight=str2num(char(CTOUT.DicomHeader.Private_1299_1299)');
    end
end
if isfield(CTOUT.DicomHeader,'Private_1399_13xx_Creator'),
    if ischar(CTOUT.DicomHeader.Private_1399_1399)
        CTOUT.PrivTableHeight=str2num(CTOUT.DicomHeader.Private_1399_1399);
    else
        CTOUT.PrivTableHeight=str2num(char(CTOUT.DicomHeader.Private_1399_1399)');
    end
end

if isfield(CTOUT.DicomHeader,'Private_1499_14xx_Creator'),
    if ischar(CTOUT.DicomHeader.Private_1499_1499)
        CTOUT.MachineName=deblank(CTOUT.DicomHeader.Private_1499_1499);
    else
        CTOUT.MachineName=deblank(char(CTOUT.DicomHeader.Private_1499_1499)');
    end
end 

if isfield(CTOUT.DicomHeader,'Private_1599_15xx_Creator') && strcmp(class(CTOUT.DicomHeader.Private_1599_1599),'uint8')
    HUToREDString = CTOUT.DicomHeader.Private_1599_1599';
    idxVect  = 1:8:length(HUToREDString);
    for i = 1:length(idxVect)
        SF         = typecast(uint8(HUToREDString(idxVect(i):idxVect(i)+7)), lower('double'));
        HUToRED(i) = SF;
    end
    CTOUT.HUToRED  = HUToRED;
else
    CTOUT.HUToRED = [];
end
    
% Read all slices in path, convert to Hounsfield 
% Units, apply IEC convention
if ~ (~ isempty(varargin) && ~ isempty(varargin{1}) && ~ isempty(varargin{2}) && ...
    strcmp(varargin{1},'readimagedata') && varargin{2}==false)
    CTOUT.Image             =   zeros(CTOUT.PixelNumZi,...
        CTOUT.PixelNumXi,CTOUT.PixelNumYi);
    
    % Apply RescaleSlope and RescaleIntercept
    for SliceCur = 1 : SliceNum
        CTOUT.Image(:,:,SliceCur) = ...
            double(dicomread(CTOUT.Filenames{SliceCur}))*CTOUT.RescaleSlope + ...
            CTOUT.RescaleIntercept;
    end
    
    % Change all pixel values smaller than -1024 to -1024
    CTOUT.Image(find(CTOUT.Image<-1024)) = -1024;
    
    %Set CT in IEC format
    CTOUT.Image(:,:,:)            =   CTOUT.Image(end:-1:1,:,:);
    CTOUT.Image                   =   permute(CTOUT.Image,[ 2 1 3 ]);
    CTOUT.Image                   =   permute(CTOUT.Image,[ 1 3 2 ]);
end
end%endif

