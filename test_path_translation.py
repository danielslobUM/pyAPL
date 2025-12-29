import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from quantifycontourdifferences_P0728 import translate_linkeddicom_path

# Test the path translation
ttl_path = "/home/jovyan/r-drive/ICoNEA/DICOM/P0728C0006I13346699/CT/20250318"
dicom_root = "Z:\\Projects\\phys\\p0728-automation\\ICoNEA\\DICOM"

translated = translate_linkeddicom_path(ttl_path, dicom_root)
print(f"Original path: {ttl_path}")
print(f"Translated path: {translated}")
print(f"Path exists: {os.path.exists(translated)}")

if os.path.exists(translated):
    # List contents
    files = os.listdir(translated)
    print(f"Number of files in directory: {len(files)}")
    if len(files) > 0:
        print(f"First few files: {files[:5]}")
