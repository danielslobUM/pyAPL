"""
linkeddicom_helper - Helper functions for working with LinkedDICOM metadata

This module provides utility functions to parse LinkedDICOM TTL files
and extract relationships between CT scans and RTSTRUCT files.
"""

import os
import warnings
from rdflib import Graph, Namespace, RDF, RDFS, URIRef
import pydicom
from pydicom.errors import InvalidDicomError


def get_structs_for_ct(patient_folder):
    """
    Parse linkeddicom.ttl file to extract CT series and their linked RTSTRUCT files.
    
    This function reads the linkeddicom.ttl file in the patient folder and builds
    a dictionary mapping CT series to their associated RTSTRUCT files. This preserves
    the relationships defined in the LinkedDICOM metadata.
    
    Parameters
    ----------
    patient_folder : str
        Path to the patient folder containing linkeddicom.ttl file
        
    Returns
    -------
    dict
        Dictionary where keys are CT Series Instance UIDs (as URIs) and values are dicts containing:
        - 'UID': CT Series Instance UID (as URI)
        - 'path': Path to CT series folder
        - 'RTSTRUCT': Dictionary of linked RTSTRUCTs, where keys are RTSTRUCT UIDs and values contain:
            - 'UID': RTSTRUCT Instance UID (as URI)
            - 'path': Path to RTSTRUCT file
            - 'structure_names': List of structure names in the RTSTRUCT (if available)
            
    Examples
    --------
    >>> ct_series_dict = get_structs_for_ct('/data/patient_folder')
    >>> for ct_uid, ct_data in ct_series_dict.items():
    ...     print(f"CT: {ct_data['path']}")
    ...     for rt_uid, rt_data in ct_data['RTSTRUCT'].items():
    ...         print(f"  RTSTRUCT: {rt_data['path']}")
    """
    ttl_file = os.path.join(patient_folder, 'linkeddicom.ttl')
    
    if not os.path.exists(ttl_file):
        warnings.warn(f"LinkedDICOM TTL file not found: {ttl_file}")
        return {}
    
    try:
        # Parse the TTL file
        g = Graph()
        g.parse(ttl_file, format='ttl')
        
        # Define namespaces
        SCHEMA = Namespace("http://schema.org/")
        DICOM = Namespace("http://purl.org/healthcarevocab/v1#")
        
        # Dictionary to store CT series and their RTSTRUCTs
        ct_series_dict = {}
        
        # Find all CT Image series
        # Look for instances that are CT Images
        for subject in g.subjects(RDF.type, None):
            # Get the types for this subject
            types = list(g.objects(subject, RDF.type))
            type_strings = [str(t).lower() for t in types]
            
            # Check if this is a CT series by looking at SOP Class UID
            # CT Image Storage SOP Class: 1.2.840.10008.5.1.4.1.1.2
            is_ct_image = any('ct' in ts for ts in type_strings) or \
                         any('computedtomography' in ts.replace(' ', '') for ts in type_strings)
            
            if is_ct_image:
                # Get Series Instance UID (this groups individual CT images into a series)
                # SeriesInstanceUID tag is (0020,000E)
                series_uid_pred = URIRef("https://johanvansoest.nl/ontologies/LinkedDicom/T0020000E")
                series_uids = list(g.objects(subject, series_uid_pred))
                
                if series_uids:
                    series_uid_uri = series_uids[0]
                    series_uid_str = str(series_uid_uri)
                    
                    # Get the file path for this CT image
                    file_paths = list(g.objects(subject, SCHEMA.contentUrl))
                    
                    if file_paths:
                        file_path = str(file_paths[0])
                        # Get the directory containing this file (should be the series folder)
                        series_folder = os.path.dirname(file_path)
                        
                        # Initialize CT series entry if not exists
                        if series_uid_str not in ct_series_dict:
                            ct_series_dict[series_uid_str] = {
                                'UID': series_uid_str,
                                'path': series_folder,
                                'RTSTRUCT': {}
                            }
        
        # Now find RTSTRUCT files and link them to CT series
        # RTSTRUCT SOP Class UID: 1.2.840.10008.5.1.4.1.1.481.3
        for subject in g.subjects(RDF.type, None):
            types = list(g.objects(subject, RDF.type))
            type_strings = [str(t).lower() for t in types]
            
            is_rtstruct = any('rtstruct' in ts for ts in type_strings) or \
                         any('rtstructureset' in ts.replace(' ', '') for ts in type_strings)
            
            if is_rtstruct:
                # Get the SOP Instance UID for this RTSTRUCT
                sop_instance_uid_pred = URIRef("https://johanvansoest.nl/ontologies/LinkedDicom/T00080018")
                sop_instance_uids = list(g.objects(subject, sop_instance_uid_pred))
                
                if sop_instance_uids:
                    rtstruct_uid = str(sop_instance_uids[0])
                    
                    # Get file path
                    file_paths = list(g.objects(subject, SCHEMA.contentUrl))
                    
                    if file_paths:
                        rtstruct_path = str(file_paths[0])
                        
                        # Get Referenced Series UID (which CT series this RTSTRUCT references)
                        # This is in ReferencedFrameOfReferenceSequence -> RTReferencedStudySequence -> RTReferencedSeriesSequence -> SeriesInstanceUID
                        # Tag (0020,000E) for Series Instance UID
                        # We need to find which CT series this RTSTRUCT references
                        
                        # Try to read the RTSTRUCT file to get referenced series
                        referenced_series = []
                        structure_names = []
                        
                        try:
                            if os.path.exists(rtstruct_path):
                                # Read DICOM file - use force=True only if initial read fails
                                try:
                                    ds = pydicom.dcmread(rtstruct_path)
                                except (InvalidDicomError, KeyError, ValueError) as e:
                                    # Fallback to force=True for non-standard DICOM files
                                    # Only catch specific DICOM parsing errors
                                    ds = pydicom.dcmread(rtstruct_path, force=True)
                                    warnings.warn(f"Used force=True to read non-standard DICOM file {rtstruct_path}: {str(e)}")
                                
                                # Get structure names
                                if hasattr(ds, 'StructureSetROISequence'):
                                    structure_names = [roi.ROIName for roi in ds.StructureSetROISequence]
                                
                                # Get referenced series
                                if hasattr(ds, 'ReferencedFrameOfReferenceSequence'):
                                    for ref_frame in ds.ReferencedFrameOfReferenceSequence:
                                        if hasattr(ref_frame, 'RTReferencedStudySequence'):
                                            for ref_study in ref_frame.RTReferencedStudySequence:
                                                if hasattr(ref_study, 'RTReferencedSeriesSequence'):
                                                    for ref_series in ref_study.RTReferencedSeriesSequence:
                                                        if hasattr(ref_series, 'SeriesInstanceUID'):
                                                            referenced_series.append(ref_series.SeriesInstanceUID)
                        except (IOError, OSError) as e:
                            warnings.warn(f"Could not access RTSTRUCT file {rtstruct_path}: {str(e)}")
                        except Exception as e:
                            warnings.warn(f"Error reading RTSTRUCT file {rtstruct_path}: {str(e)}")
                        
                        # Link RTSTRUCT to all referenced CT series
                        if referenced_series:
                            for ref_series_uid in referenced_series:
                                # Find matching CT series in our dict
                                for ct_uid, ct_data in ct_series_dict.items():
                                    # Check if the referenced series matches this CT series
                                    # The CT UID in our dict is a URI, so we need to check if it contains the series UID
                                    if ref_series_uid in ct_uid:
                                        ct_data['RTSTRUCT'][rtstruct_uid] = {
                                            'UID': rtstruct_uid,
                                            'path': rtstruct_path,
                                            'structure_names': structure_names
                                        }
                        else:
                            # If we couldn't determine referenced series, link to all CT series as fallback
                            # This is a conservative approach to ensure RTSTRUCTs are not lost
                            # WARNING: This may create incorrect associations
                            warnings.warn(
                                f"Could not determine referenced CT series for RTSTRUCT {rtstruct_path}. "
                                f"Linking to all available CT series as fallback. "
                                f"This may result in incorrect CT-RTSTRUCT associations.",
                                UserWarning,
                                stacklevel=2
                            )
                            for ct_uid, ct_data in ct_series_dict.items():
                                ct_data['RTSTRUCT'][rtstruct_uid] = {
                                    'UID': rtstruct_uid,
                                    'path': rtstruct_path,
                                    'structure_names': structure_names
                                }
        
        return ct_series_dict
    
    except Exception as e:
        warnings.warn(f"Error parsing LinkedDICOM TTL file {ttl_file}: {str(e)}")
        return {}
