function CTOUT   =   read_dicomct_light(FilenamesIN,varargin)
% CTOUT   =   read_dicomct_light(FilenamesIN,varargin) is a lightweight
% version of read_dicomct. Compared to that function it does not readout 
% the actual imaging data and also skips header information for all slices 
% except the slice with the lowest Y value. 
% 
%--------------------------------------------------------------------------
% HISTORY
%--------------------------------------------------------------------------
% 17/02/2025, Rik Hansen
% Creation
%--------------------------------------------------------------------------

SliceNum                 =   uint16(length(FilenamesIN));
if ~(SliceNum == 2 && ~isempty(strfind(FilenamesIN{1},'\.')) && ...
        ~isempty(strfind(FilenamesIN{2},'\..')))
    %beginif
    %read CT otherwise something is wrong in the filenames and nothing is done

    %read first two slices for slice-spacing derivation
    for SliceCur=1:SliceNum
        obj = images.internal.dicom.DICOMFile(FilenamesIN{SliceCur});
        imagePositionPatient = obj.getAttributeByName('ImagePositionPatient');
        % imagePositionPatient =   getAttribute(FilenamesIN{SliceCur},"ImagePositionPatient");
        Yi(SliceCur,:)       =   [double(SliceCur),imagePositionPatient(3)];
    end %for SliceCur
    [~,I]                    =   unique(Yi(:,2));
    Yi                       =   Yi(I,:);
    SliceNum                 =   size(Yi,1);
    SliceValueYSorted        =   sortrows(Yi,2);
    CTOUT.Filenames          =   FilenamesIN(SliceValueYSorted(:,1));
    
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

    % Create empty image place holder
    if ~ (~ isempty(varargin) && ~ isempty(varargin{1}) && ~ isempty(varargin{2}) && ...
            strcmp(varargin{1},'readimagedata') && varargin{2}==false)
        CTOUT.Image             =   zeros(CTOUT.PixelNumXi,...
            CTOUT.PixelNumYi,CTOUT.PixelNumZi);
    end
end%endif

