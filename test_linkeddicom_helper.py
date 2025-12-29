from linkeddicom_helper import get_structs_for_ct
import json

patient_path = 'Z:\\Projects\\phys\\p0728-automation\\ICoNEA\\DICOM\\P0728C0006I13346699'
result = get_structs_for_ct(patient_path)

print(json.dumps(result, indent=2))
