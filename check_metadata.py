import pydicom

data = pydicom.dcmread('z:\Projects\phys\p0728-automation\ICoNEA\DICOM\P0728C0006I13395320\RTPLAN\20250307\\1.3.6.1.4.1.32722.728.6.5107923184697080298316553187259354515622.dcm')
print(data)