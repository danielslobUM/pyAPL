function [tf] = hasContourPointsLocal(StructEntry)
%HASCONTOURPOINTSLOCAL  True if the structure has at least one slice with points.
% Works with either .ContourData (flat [x y z ...]) or .X/.Y/.Z triplets.

    tf = false;

    if ~isfield(StructEntry, 'Slice') || isempty(StructEntry.Slice)
        return;
    end

    S = StructEntry.Slice;

    % Case 1: DICOM-typical flat vector
    if isfield(S, 'ContourData')
        tf = any(arrayfun(@(s) ~isempty(s.ContourData), S));
        if tf, return; end
    end

    % Case 2: separate X/Y/Z vectors
    if all(isfield(S, {'X','Y','Z'}))
        tf = any(arrayfun(@(s) ~isempty(s.X) && ~isempty(s.Y) && ~isempty(s.Z), S));
    end
end
