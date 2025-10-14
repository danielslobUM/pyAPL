function [resultsTable] = quantifyContourDifferences(calcAllParameters, rootFolder)
% function [resultsTable] =  quantifyContourDifferences(calcAllParameters, rootFolder)
% This function can be used to quickly quantify differences between 
% contours delineated by two different methods/persons for one or more
% patients. The user is asked to select a (sub)folder with imaging data, a
% (sub)folder containing RTSTRUCTS for method/person 1 and a (sub)folder 
% containing RTSTRUCTS for method/person 2.
% 
%--------------------------------------------------------------------------
% INPUT
%--------------------------------------------------------------------------
% NAME              TYPE        DESCRIPTION
% calcAllParameters double      Switch on (1) or off (0) calculation of 
%                               added path length (APL) and surface DICE 
%                               calculation in addition to volumnetric DICE
%                               Default = 0, to speed up calculation times
% rootFolder        char        Optional input which specifies a 
%                               startfolder for subfolder selection
%                               (typically this should be the folder which
%                               contains the subfolders with imaging and 
%                               RTSTRUCT data. (Default = cd).
%--------------------------------------------------------------------------
% OUTPUT
%--------------------------------------------------------------------------
% NAME              TYPE        DESCRIPTION
% resultsTable      struct      Table with quantitative results
% .pNumber          cell        Patient number(s)
% .VOIName          cell        Structure name(s)
% .Dice             double      Volumetric DICE value(s)
% .APL              double      Added Path Length value(s)
% .SDSC             double      Surface DICE value(s)
%--------------------------------------------------------------------------
% INTERNAL VARIABLE DEFINITION
%--------------------------------------------------------------------------
% NAME                  TYPE        DESCRIPTION
% imagingDataFolder     cell        Pathname of the folder that contains
%                                   subfolders with imagingdata
% dirnamesImagingData   struct      ImagingData subfolder information
% structFolderMethod1   struct      RTSTRUCT file information method 1
% structFolderMethod2   struct      RTSTRUCT file information method 2
% RTSTRUCTfilesMethod1  cell        Full filenames RTSTRUCTS method 1  
% RTSTRUCTfilesMethod1  cell        Full filenames RTSTRUCTS method 2
% nImagingSets          double      Nr. of imaging series
% imagingSetNo          double      Counter (of imaging serie)
% hFig                  obj         handle to waitbar object
% folderImagingData     cell        Name of subfolder with imaging data
% imagingFiles          cell        Full filenames ImagingData
% jj                    double      Counter (of slice within imaging serie)
% pNumberStart          double      Index of first character in string
%                                   defining patientID
% pNumberEnd            double      Index of last character in string
%                                   defining patientID
% pNumber               double      PatientID
% RTSTRUCT1Index        double      Index of RTSTRUCTfile method 1
% RTSTRUCT1Filename     string      Full filename of RTSTUCTFILE method 1 
% RTSTRUCT1             struct      RTSTRUCT file content for method 1
% VOIs1                 cell        Structurenames in RTSTRUCT1
% nVOIs1                double      Number of structures in RTSTRUCT1
% RTSTRUCT2Index        double      Index of RTSTRUCTfile method 2
% RTSTRUCT2FileName     string      Full filename of RTSTUCTFILE method 2 
% RTSTRUCT2             struct      RTSTRUCT file content for method 2
% VOIs2                 cell        Structurenames in RTSTRUCT2
% nVOIs2                double      Number of structures in RTSTRUCT2
% VOI1                  struct      VOI structure for RTSTRUCT1
% VOI2                  struct      VOI structure for RTSTRUCT2
% tempPathLength        double      APL per slice
% APLTolerance          double      Tolerance in cm for APL calculation
% SDSCTolerance         double      Tolerance in cm for SDSC calculation
% toCompare             double      The indices of VOIs of RTSTRUCT1 which 
%                                   are also present in both RTSTRUCT2 and
%                                   can thus be compared
% nToCompare            double      The nr. of VOIs present in both 
%                                   RTSTRUCT1 and RTSTRUCT 2
% comparisonNo          double      Counter
%
%--------------------------------------------------------------------------
% FUNCTIONS & MEX files called
%--------------------------------------------------------------------------
% FROM https://bitbucket.org/maastro/contourcomparison/src/master/
% compose_struct_matrix
% bwdistsc
% calculateSurfaceDSC
% read_dicomrtstruct
% resampleContourSlices
% calculateDiceLogical (ADAPTED from calculateDice by Rik Hansen 17-2-2025)
% read_dicomct_light (ADAPTED from read_dicomct by Rik Hansen 17-2-2025)
% calculatePathLength(update by Femke Vaassen 27-1-2025)
% 
% 25/08/2025 created hasContourPointsLocal - check if VOI is empty and skip
% if so
%--------------------------------------------------------------------------
% HISTORY
%--------------------------------------------------------------------------
% 17/02/2025, Rik Hansen
% Creation
% 25/08/2025, Daniël Slob 
% created hasContourPointsLocal - check if VOI is empty and skip if so
% 
%--------------------------------------------------------------------------
% SAMPLE CALL
%--------------------------------------------------------------------------
% [resultsTable] = quantifyContourDifferences(0,'F:\Clinic\Fysica Innovatie\Rik\Autocontouring\Limbus\Consistency checkdata');
%--------------------------------------------------------------------------

if nargin==0||isempty(calcAllParameters)
    calcAllParameters = 1; %if not specified or empty --> default
end

if nargin<2||isempty(rootFolder)||~isfolder(rootFolder)
    rootFolder = cd; %if not specified, empty or no folder --> default
end

APLTolerance  = 0.1;
SDSCTolerance = 0.1;

%% Read dirnames of dirs with imaging data 
imagingDataFolder = uigetdir(rootFolder,'Select folder with imaging data');
dirnamesImagingData = dir(imagingDataFolder);
%(remove '.' and '..' from the folderlist)
dirnamesImagingData(strcmp({dirnamesImagingData.name}','.')) =[];
dirnamesImagingData(strcmp({dirnamesImagingData.name}','..'))=[];

%% Read filenames of RTSTRUCT files containing contours for method/person 1
structFolderMethod1  = uigetdir(rootFolder,'Select folder with RTSTRUCT data of method/person 1 (reference data)');
RTSTRUCTfilesMethod1 = dir(structFolderMethod1);
%(remove '.' and '..' from the filelist)
RTSTRUCTfilesMethod1(strcmp({RTSTRUCTfilesMethod1.name}','.')) =[];
RTSTRUCTfilesMethod1(strcmp({RTSTRUCTfilesMethod1.name}','..'))=[];

%% Read filenames of RTSTRUCT files containing contours for method/person 2
structFolderMethod2  = uigetdir(rootFolder,'Select folder with RTSTRUCT data of method/person 2 (new data)');
RTSTRUCTfilesMethod2 = dir(structFolderMethod2);
%(remove '.' and '..' from the filelist)
RTSTRUCTfilesMethod2(strcmp({RTSTRUCTfilesMethod2.name}','.')) =[];
RTSTRUCTfilesMethod2(strcmp({RTSTRUCTfilesMethod2.name}','..'))=[];

%% Perform contour differences quantification
nImagingSets = size(dirnamesImagingData,1);

hFig = waitbar(0,'Contour differences quantification in progress'); %waitbar
%Calculate difference metrics to check consistency
for imagingSetNo = 1:nImagingSets
    waitbar((imagingSetNo-1)/nImagingSets,hFig);

    % Read Imaging data
    disp('Reading imaging data')
    clear folderImagingData imagingFiles Filenames results
    
    folderImagingData = [dirnamesImagingData(imagingSetNo).folder filesep dirnamesImagingData(imagingSetNo).name];
    imagingFiles = dir(folderImagingData);
    %(remove '.' and '..' from the filelist)
    imagingFiles(strcmp({imagingFiles.name}','.')) = [];
    imagingFiles(strcmp({imagingFiles.name}','..')) = [];

    for jj = 1:size(imagingFiles,1)
        Filenames.ImagingData{jj} = fullfile(imagingFiles(jj).folder,imagingFiles(jj).name);
    end
    imagingData = read_dicomct_light(Filenames.ImagingData);
   
    pNumberStart = regexp(folderImagingData,'P\d{4}C');
    pNumberEnd = strfind(folderImagingData(pNumberStart:end),'_')+pNumberStart-2;
    pNumber = folderImagingData(pNumberStart:pNumberEnd);

    disp(['Calculating metrics for patient ' pNumber])
    disp('Reading struct files')
    
    % Read RTSTRUCT of old/current version
    RTSTRUCT1Index    = find(contains({RTSTRUCTfilesMethod1.name}',pNumber));
    RTSTRUCT1Filename = [RTSTRUCTfilesMethod1(RTSTRUCT1Index).folder filesep RTSTRUCTfilesMethod1(RTSTRUCT1Index).name];
    RTSTRUCT1         = read_dicomrtstruct(RTSTRUCT1Filename);

    VOIs1             = {RTSTRUCT1.Struct.Name}';
    nVOIs1            = size(VOIs1,1);

    % Read RTSTRUCT of new version
    RTSTRUCT2Index    = find(contains({RTSTRUCTfilesMethod2.name}',pNumber));
    RTSTRUCT2Filename = [RTSTRUCTfilesMethod2(RTSTRUCT2Index).folder filesep RTSTRUCTfilesMethod2(RTSTRUCT2Index).name];
    RTSTRUCT2         = read_dicomrtstruct(RTSTRUCT2Filename);
  
    VOIs2             = {RTSTRUCT2.Struct.Name}';
    nVOIs2            = size(VOIs2,1);

    %Calculate Added Path Length
    toCompare = find(ismember(VOIs1,VOIs2)); 
    nToCompare = length(toCompare);
    if nVOIs2<nVOIs1; warning(['There are less structures in the new RTSTRUCT set for patient: ' pNumber]); end
    if nToCompare<nVOIs1; warning(['The following structure(s) is/are missing in the new RTSTRUCT for patient: ' pNumber ': '  VOIs1{~ismember(VOIs1,VOIs2)}]); end

    % =================== SELECT OARs ONCE PER RUN ===================
    % Build list of VOIs that exist in BOTH RTSTRUCTs (keep VOIs1 order)
    commonVOIs = VOIs1(ismember(VOIs1, VOIs2));
    
    % If nothing in common, skip this patient
    if isempty(commonVOIs)
        warning('No common VOIs found for patient %s. Skipping patient.', pNumber);
        continue;
    end

    % Ask the user ONCE which OARs to include for ALL patients in this run
    if ~exist('selectedOARs','var')
        promptStr = sprintf('Select OARs to include for ALL patients in this run (patient: %s)', pNumber);
        [selIdx, ok] = listdlg( ...
            'PromptString', promptStr, ...
            'ListString',   commonVOIs, ...
            'SelectionMode','multiple', ...
            'ListSize',     [300 400]);
        if ok == 0 || isempty(selIdx)
            % If user cancels or selects nothing -> default to ALL common VOIs
            selectedOARs = commonVOIs;
            fprintf('No selection made. Using ALL common VOIs: %s\n', strjoin(selectedOARs', ', '));
        else
            selectedOARs = commonVOIs(selIdx);
            fprintf('Selected OARs: %s\n', strjoin(selectedOARs', ', '));
        end
    end

    % Filter the comparison set to only the selected OARs
    maskSel    = ismember(VOIs1(toCompare), selectedOARs);
    toCompare  = toCompare(maskSel);
    nToCompare = numel(toCompare);

    if nToCompare == 0
        warning('None of the selected OARs are present for patient %s. Skipping patient.', pNumber);
        continue;
    end
    % ====================================================================


    VOI1 = compose_struct_matrix(imagingData,RTSTRUCT1);
    VOI2 = compose_struct_matrix(imagingData,RTSTRUCT2);
    
    disp('Calculating metrics')
    
    for comparisonNo = 1:nToCompare
        method1StructNo = toCompare(comparisonNo);
        method2StructNo = find(strcmp(VOIs1(method1StructNo),VOIs2));
        
        thisVOIName = VOIs1{method1StructNo};

        % === Pre-check: empty VOIs? If yes, skip and notify ===
        isEmpty1 = ~hasContourPointsLocal(RTSTRUCT1.Struct(method1StructNo));
        isEmpty2 = ~hasContourPointsLocal(RTSTRUCT2.Struct(method2StructNo));

        if isEmpty1 || isEmpty2
            whichSide = 'both';
            if isEmpty1 && ~isEmpty2, whichSide = 'RTSTRUCT1'; end
            if ~isEmpty1 && isEmpty2, whichSide = 'RTSTRUCT2'; end
            warning('Skipping VOI "%s" for patient %s: empty contour in %s.', thisVOIName, pNumber, whichSide);
            continue;   % <-- only skip for empty-VOI cases
        end
        %PatName
        results.pNumber(comparisonNo,1) = {pNumber};
        
        %VOIName
        results.VOIName(comparisonNo,1) = VOIs1(method1StructNo);

        if calcAllParameters~=0
            % APL (current)
            tempPathLength = calculateDifferentPathLength_v2(imagingData, RTSTRUCT1, RTSTRUCT2, method1StructNo, method2StructNo, APLTolerance);
            results.APL(comparisonNo,1) = sum(tempPathLength);

            % Surface DSC (unchanged)
            results.SDSC(comparisonNo,1) = calculateSurfaceDSC(imagingData, RTSTRUCT1, RTSTRUCT2, method1StructNo, method2StructNo, SDSCTolerance);
        end

        
        %Volumetric DSCt
        results.Dice(comparisonNo,1) = calculateDiceLogical(VOI1,VOI2,method1StructNo,method2StructNo);
    end
    
    if exist('results','var') && isfield(results,'pNumber') && ~isempty(results.pNumber)
        tempResultsTable = struct2table(results, 'AsArray', true);
    else
        tempResultsTable = table; % empty table if all VOIs for this set were skipped
    end
    
end
close(hFig)
%sort rows based on VOIname
resultsTable = sortrows(tempResultsTable,"VOIName","ascend");
