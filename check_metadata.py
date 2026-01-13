import pydicom

data = pydicom.dcmread('Z:\\Projects\\phys\\p0728-automation\\ICoNEA\\DICOM\\P0728C0006I13394547\\CT\\20250217\\1.3.6.1.4.1.32722.728.6.9695105652532562127512339040524135891113.dcm')
print(data)