"""
linkeddicom_helper - Helper functions for working with LinkedDICOM metadata

This module provides functions to parse LinkedDICOM TTL files and extract
relationships between CT scans and RTSTRUCT files using SPARQL queries.
"""

import os
import json
from rdflib import Graph


def get_structs_for_ct(patient_path):
    """
    Get RTSTRUCT files linked to CT series for a patient.
    
    This function reads the LinkedDICOM Turtle file for a patient and uses
    a SPARQL query to find all RTSTRUCT files that are linked to CT series.
    
    Parameters
    ----------
    patient_path : str
        Path to the patient folder containing linkeddicom.ttl
        
    Returns
    -------
    dict
        Dictionary with CT series as keys, containing:
        - UID: UID of the CT series
        - path: Path to the CT series folder
        - RTSTRUCT: Dictionary of RTSTRUCT objects linked to this CT, containing:
            - UID: UID of the RTSTRUCT
            - path: Path to the RTSTRUCT file
            - structure_names: List of structure names in the RTSTRUCT
            
    Example
    -------
    >>> ct_series = get_structs_for_ct("/path/to/patient")
    >>> for ct_uid, ct_data in ct_series.items():
    ...     print(f"CT: {ct_uid}")
    ...     for rt_uid, rt_data in ct_data['RTSTRUCT'].items():
    ...         print(f"  RTSTRUCT: {rt_uid}")
    ...         print(f"    Structures: {rt_data['structure_names']}")
    """
    # read LinkedDicom Turtle file
    ttl_file_path = os.path.join(patient_path, "linkeddicom.ttl")
    if not os.path.exists(ttl_file_path):
        print(f"Patient {patient_path} does not have a linkeddicom.ttl file!")
        return {}

    # load turtle file into graph
    graph = Graph()
    graph.parse(ttl_file_path)

    with open("ct_rtstruct.sparql", "r") as f:
        query = f.read()
    
    query_result = graph.query(query)

    ctSeries = {}
    for row in query_result:

        # add CT series if not exists
        if not str(row.ctSerie) in ctSeries:
            ctSeries[str(row.ctSerie)] = {
                "UID": str(row.ctSerie),
                "path": str(row.ctSeriePath),
                "RTSTRUCT": {}
            }

        # add RTSTRUCT if not exists
        if not str(row.rtStruct) in ctSeries[str(row.ctSerie)]["RTSTRUCT"]:
            ctSeries[str(row.ctSerie)]["RTSTRUCT"][str(row.rtStruct)] = {
                "UID": str(row.rtStruct),
                "path": str(row.rtStructPath),
                "structure_names": []
            }

        # add structureName if not exists
        if not str(row.structureName) in ctSeries[str(row.ctSerie)]["RTSTRUCT"][str(row.rtStruct)]["structure_names"]:
            ctSeries[str(row.ctSerie)]["RTSTRUCT"][str(row.rtStruct)]["structure_names"].append(str(row.structureName))

    return ctSeries


if __name__ == '__main__':
    import sys
    
    # Example usage
    if len(sys.argv) > 1:
        dicom_directory = sys.argv[1]
    else:
        dicom_directory = "/home/jovyan/r-drive/ICoNEA/DICOM"
    
    if os.path.isdir(dicom_directory):
        for folder_name in os.listdir(dicom_directory):
            current_dir = os.path.join(dicom_directory, folder_name)
            
            if not os.path.isdir(current_dir):
                continue
            
            ct_series = get_structs_for_ct(current_dir)
            if ct_series:
                print(json.dumps(ct_series, indent=4))
                break
    else:
        print(f"Directory not found: {dicom_directory}")
