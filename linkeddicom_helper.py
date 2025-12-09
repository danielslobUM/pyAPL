import os
from LinkedDicom import LinkedDicom
from LinkedDicom.rt import dvh
from rdflib import Graph
import sys
import json

def dvh_per_patient(patient_path):
    # read LinkedDicom Turtle file
    ttl_file_path = os.path.join(patient_path, "linkeddicom.ttl")
    print(ttl_file_path)
    if not os.path.exists(ttl_file_path):
        print(f"Patient {patient_path} does not have a linkeddicom.ttl file!")
    dvh_factory = dvh.DVH_dicompyler(ttl_file_path)
    dictionary_dvh = dvh_factory.calculate_dvh(patient_path, reference_type=dvh.RT_Query_Type.DICOM_STUDY)

def get_structs_for_ct(patient_path):
    # read LinkedDicom Turtle file
    ttl_file_path = os.path.join(patient_path, "linkeddicom.ttl")
    if not os.path.exists(ttl_file_path):
        print(f"Patient {patient_path} does not have a linkeddicom.ttl file!")

    # load turtle file into graph
    graph = Graph()
    graph.parse(ttl_file_path)

    with open("ct_rtstruct.sparql", "r") as f:
        query = f.read()
    
    query_result = graph.query(query)

    ctSeries = { }
    for row in query_result:

        # add CT series if not exists
        if not str(row.ctSerie) in ctSeries:
            ctSeries[str(row.ctSerie)] = {
                "UID": str(row.ctSerie),
                "path": str(row.ctSeriePath),
                "RTSTRUCT": { }
            }

        # add RTSTRUCT if not exists
        if not str(row.rtStruct) in ctSeries[str(row.ctSerie)]["RTSTRUCT"]:
            ctSeries[str(row.ctSerie)]["RTSTRUCT"][str(row.rtStruct)] = {
                "UID": str(row.rtStruct),
                "path": str(row.rtStructPath),
                "structure_names": [ ]
            }

        # add structureName if not exists
        if not str(row.structureName) in ctSeries[str(row.ctSerie)]["RTSTRUCT"][str(row.rtStruct)]["structure_names"]:
            ctSeries[str(row.ctSerie)]["RTSTRUCT"][str(row.rtStruct)]["structure_names"].append(str(row.structureName))

    return ctSeries


if __name__ == '__main__':
    dicom_directory = "/home/jovyan/r-drive/ICoNEA/DICOM"
    for folder_name in os.listdir(dicom_directory):
        current_dir = os.path.join(dicom_directory, folder_name)
    
        #dvh_per_patient(current_dir)
        ct_series = get_structs_for_ct(current_dir)
        print(json.dumps(ct_series, indent=4))
        break
