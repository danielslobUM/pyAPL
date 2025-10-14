function StructOUT    =   read_dicomrtstruct(FileNameIN);
% --------------------------------------------------------------------------
% INPUT
%--------------------------------------------------------------------------
% NAME              TYPE        DESCRIPTION 
% FileNameIN        char        Filename of the DICOM RTSTRUCT file incl.
%                               path 
%--------------------------------------------------------------------------
% OUTPUT
%--------------------------------------------------------------------------
% NAME              TYPE        DESCRIPTION 

%--------------------------------------------------------------------------
% INTERNAL VARIABLE DEFINITION
%--------------------------------------------------------------------------
% NAME              TYPE        DESCRIPTION 
% 
%--------------------------------------------------------------------------
% FUNCTIONS & MEC files called
%--------------------------------------------------------------------------
% none

%--------------------------------------------------------------------------
% HISTORY
%--------------------------------------------------------------------------
% 
%--------------------------------------------------------------------------

DicomHeader                 =   dicominfo(FileNameIN,'UseVRHeuristic',false);
StructOUT.FileName          =   FileNameIN;
StructOUT.DicomHeader       =   DicomHeader;
StructOUT.StructNum         =   length(fieldnames(DicomHeader.StructureSetROISequence));

StructOUT.StudyUID          =   StructOUT.DicomHeader.StudyInstanceUID;

StructOUT.SOPInstanceUID    =   StructOUT.DicomHeader.SOPInstanceUID;
if isfield(DicomHeader,'SeriesDescription')
    StructOUT.PlanID            =   StructOUT.DicomHeader.SeriesDescription;
else
    StructOUT.PlanID = '';
end
StructOUT.ID                =   StructOUT.DicomHeader.PatientID;

if isfield(DicomHeader.PatientName,'FamilyName')
    StructOUT.LastName      =   StructOUT.DicomHeader.PatientName.FamilyName;
else
    StructOUT.LastName      =   ' ';
end
if isfield(DicomHeader.PatientName,'GivenName')
    StructOUT.FirstName     =   StructOUT.DicomHeader.PatientName.GivenName;
else
    StructOUT.FirstName     =   ' ';
end

if isfield(DicomHeader,'StructureSetDate')
    StructOUT.StructureSetDate   =   StructOUT.DicomHeader.StructureSetDate;
else
    StructOUT.StructureSetDate   =   ' ';
end
if isfield(DicomHeader,'StructureSetTime')
    StructOUT.StructureSetTime   =   StructOUT.DicomHeader.StructureSetTime;
else
    StructOUT.StructureSetTime   =   ' ';
end

if isfield(DicomHeader,'ReferencedFrameOfReferenceSequence')
    StructOUT.FrameOfReference   =   StructOUT.DicomHeader.ReferencedFrameOfReferenceSequence.Item_1.FrameOfReferenceUID;
    try        
        StructOUT.ReferencedCTSeriesUID   =   StructOUT.DicomHeader.ReferencedFrameOfReferenceSequence.Item_1.RTReferencedStudySequence.Item_1.RTReferencedSeriesSequence.Item_1.SeriesInstanceUID;
    catch
        StructOUT.ReferencedCTSeriesUID   = '';
    end
else
    StructOUT.FrameOfReference   =   ' ';
end



StructOUT.XiO         = 0;
StructOUT.TrueD       = 0;
StructOUT.Esoft       = 0;
StructOUT.MAASTRO_CON = 0;
try
    if strcmp(StructOUT.DicomHeader.ManufacturerModelName,'CMS, Inc.') || strcmp(StructOUT.DicomHeader.ManufacturerModelName,'XiO') 
        StructOUT.XiO = 1;
    else
        StructOUT.XiO = 0;
    end
catch
    StructOUT.XiO = 0;
end
try
    if strcmp(StructOUT.DicomHeader.ManufacturerModelName,'Syngo MI Applications') || strcmp(StructOUT.DicomHeader.ManufacturerModelName,'e.soft') 
        StructOUT.Esoft = 1;
    else
        StructOUT.Esoft = 0;
    end
catch
    StructOUT.Esoft = 0;
end
try
    if strfind(lower(DicomHeader.StructureSetLabel), 'trued') || strfind(lower(DicomHeader.SeriesDescription), 'trued') || strfind(lower(DicomHeader.StructureSetName), 'trued')
        StructOUT.TrueD = 1;
    else
        StructOUT.TrueD = 0;
    end
catch
    StructOUT.TrueD = 0;
end
try
    if strcmp(StructOUT.DicomHeader.ManufacturerModelName,'MAASTRO clinic') || strcmp(StructOUT.DicomHeader.ManufacturerModelName,'MAASTRO_CON')
        StructOUT.MAASTRO_CON = 1;
    else
        StructOUT.MAASTRO_CON = 0;
    end
catch
    StructOUT.MAASTRO_CON = 0;
end

HasForcedStructures = 0;
ForcedStructures = [];
for StructCur=1:StructOUT.StructNum
    StructCurItem   =   ['Item_',num2str(StructCur)];
    StructOUT.Struct(StructCur).Name    =   DicomHeader.StructureSetROISequence.(StructCurItem).ROIName;  
    StructOUT.Struct(StructCur).Number  =   DicomHeader.StructureSetROISequence.(StructCurItem).ROINumber;
                
    if isfield(DicomHeader.StructureSetROISequence.(StructCurItem),'ROIVolume')
        StructOUT.Struct(StructCur).Volume  =   DicomHeader.StructureSetROISequence.(StructCurItem).ROIVolume;
    else
        StructOUT.Struct(StructCur).Volume  = 0;
    end
    StructOUT.Struct(StructCur).Type = [];
    StructOUT.Struct(StructCur).Forced = 0;
    StructOUT.Struct(StructCur).RelativeElectronDensity = [];
    if isfield(DicomHeader,'RTROIObservationsSequence')
        if isfield(DicomHeader.RTROIObservationsSequence.(StructCurItem),'RTROIInterpretedType')
            StructOUT.Struct(StructCur).Type = DicomHeader.RTROIObservationsSequence.(StructCurItem).RTROIInterpretedType;
        end        
        if isfield(DicomHeader.RTROIObservationsSequence.(StructCurItem),'ROIPhysicalPropertiesSequence')
            for i = 1  : length(fields(DicomHeader.RTROIObservationsSequence.(StructCurItem).ROIPhysicalPropertiesSequence))
                if strcmp(DicomHeader.RTROIObservationsSequence.(StructCurItem).ROIPhysicalPropertiesSequence.(['Item_' num2str(i)]).ROIPhysicalProperty,'REL_ELEC_DENSITY')
                    HasForcedStructures = 1;
                    if isempty(ForcedStructures)
                        ForcedStructures = StructCur;
                    else
                        ForcedStructures(end+1) = StructCur;
                    end
                    StructOUT.Struct(StructCur).Forced = 1;
                    StructOUT.Struct(StructCur).RelativeElectronDensity = DicomHeader.RTROIObservationsSequence.(StructCurItem).ROIPhysicalPropertiesSequence.(['Item_' num2str(i)]).ROIPhysicalPropertyValue;
                end
            end
        end
    end
    
    try
        if strcmp(DicomHeader.ROIContourSequence.(StructCurItem).ContourSequence.Item_1.ContourGeometricType,'CLOSED_PLANAR')
            StructOUT.Struct(StructCur).ClosedPlanar = 1;
        else
            StructOUT.Struct(StructCur).ClosedPlanar = 0;
        end
        
        SliceCur        =   1;
        SliceCurItem    =   'Item_1';
        while isfield(DicomHeader.ROIContourSequence.(StructCurItem).ContourSequence,SliceCurItem)
            StructOUT.Struct(StructCur).Slice(SliceCur).X   =   DicomHeader.ROIContourSequence.(StructCurItem).ContourSequence.(SliceCurItem).ContourData(1:3:end)/10;
            StructOUT.Struct(StructCur).Slice(SliceCur).Y   =   DicomHeader.ROIContourSequence.(StructCurItem).ContourSequence.(SliceCurItem).ContourData(3:3:end)/10;
            StructOUT.Struct(StructCur).Slice(SliceCur).Z   =   -DicomHeader.ROIContourSequence.(StructCurItem).ContourSequence.(SliceCurItem).ContourData(2:3:end)/10;
            SliceCur        =   SliceCur+1;
            SliceCurItem    =   ['Item_',num2str(SliceCur)];
        end
        StructOUT.Struct(StructCur).SliceNum = SliceCur-1;
    catch
        StructOUT.Struct(StructCur).ClosedPlanar = 0;        
    end
end
StructOUT.HasForcedStructures = HasForcedStructures;
StructOUT.ForcedStructuresList = ForcedStructures;