import os
#os.environ["LANG"] = "en_US.UTF-8"
#setenv LANG en_US.UTF-8

from LinkedDicom import LinkedDicom
from LinkedDicom.rt import dvh
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


if __name__ == '__main__':
    dicom_directory = "/home/jovyan/r-drive/ICoNEA/DICOM"
    for folder_name in os.listdir(dicom_directory):
        current_dir = os.path.join(dicom_directory, folder_name)
    
        dvh_per_patient(current_dir)