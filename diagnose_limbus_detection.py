"""
Diagnostic script to investigate why certain patients are not correctly identifying
Limbus AI RTSTRUCT files.

This script will analyze the RTSTRUCT metadata for the specified patients to find
inconsistencies in how Limbus AI structures are being identified.
"""

import os
import pydicom
import pandas as pd
from typing import List, Dict

# Patients to investigate
PROBLEM_PATIENTS = [
    'P0728C0006I13353702',
    'P0728C0006I13357777',
    'P0728C0006I13394057',
    'P0728C0006I13394973',
    'P0728C0006I13395013',
    'P0728C0006I13395032',
    'P0728C0006I13395114',
    'P0728C0006I13396736'
]

DICOM_ROOT = r"Z:\ICoNEA\DICOM"


def analyze_rtstruct_metadata(patient_folder: str) -> List[Dict]:
    """
    Extract detailed metadata from all RTSTRUCT files in a patient folder.
    """
    rtstruct_folder = os.path.join(patient_folder, 'RTSTRUCT')
    if not os.path.isdir(rtstruct_folder):
        rtstruct_folder = patient_folder
    
    results = []
    
    for root, dirs, files in os.walk(rtstruct_folder):
        for file in files:
            if file.lower().endswith('.dcm'):
                filepath = os.path.join(root, file)
                try:
                    ds = pydicom.dcmread(filepath, stop_before_pixels=True, force=True)
                    if ds.get('Modality', '') != 'RTSTRUCT':
                        continue
                    
                    # Extract all potentially relevant metadata with safer access
                    def safe_get(ds, tag, default='N/A'):
                        try:
                            val = ds.get(tag, default)
                            return str(val) if val else default
                        except:
                            return default
                    
                    info = {
                        'Filename': file,
                        'Path': filepath,
                        'SOPInstanceUID': safe_get(ds, 'SOPInstanceUID')[-20:],
                        'SeriesInstanceUID': safe_get(ds, 'SeriesInstanceUID')[-20:],
                        'FrameOfReferenceUID': safe_get(ds, 'FrameOfReferenceUID')[-20:],
                        'Modality': safe_get(ds, 'Modality'),
                        'Manufacturer': safe_get(ds, 'Manufacturer'),
                        'ManufacturerModelName': safe_get(ds, 'ManufacturerModelName'),
                        'StationName': safe_get(ds, 'StationName'),
                        'InstitutionName': safe_get(ds, 'InstitutionName'),
                        'SoftwareVersions': safe_get(ds, 'SoftwareVersions'),
                        'StructureSetLabel': safe_get(ds, 'StructureSetLabel'),
                        'StructureSetName': safe_get(ds, 'StructureSetName'),
                        'StructureSetDescription': safe_get(ds, 'StructureSetDescription'),
                        'StructureSetDate': safe_get(ds, 'StructureSetDate'),
                        'StructureSetTime': safe_get(ds, 'StructureSetTime'),
                        'SeriesDescription': safe_get(ds, 'SeriesDescription'),
                        'OperatorsName': safe_get(ds, 'OperatorsName'),
                        'ReviewerName': safe_get(ds, 'ReviewerName'),
                    }
                    
                    # Check for approval status
                    try:
                        if (0x300E, 0x0002) in ds:
                            info['ApprovalStatus'] = str(ds[0x300E, 0x0002].value)
                        else:
                            info['ApprovalStatus'] = 'N/A'
                    except:
                        info['ApprovalStatus'] = 'N/A'
                    
                    # Extract referenced CT series UID
                    referenced_ct_series_uid = ''
                    try:
                        if (0x3006, 0x0010) in ds:  # ReferencedFrameOfReferenceSequence
                            for frame_ref in ds[0x3006, 0x0010]:
                                if (0x3006, 0x0012) in frame_ref:  # RTReferencedStudySequence
                                    for study_ref in frame_ref[0x3006, 0x0012]:
                                        if (0x3006, 0x0014) in study_ref:  # RTReferencedSeriesSequence
                                            for series_ref in study_ref[0x3006, 0x0014]:
                                                series_uid_val = str(series_ref.get('SeriesInstanceUID', ''))
                                                if series_uid_val:
                                                    referenced_ct_series_uid = series_uid_val
                                                    break
                    except:
                        pass
                    info['ReferencedCTSeriesUID'] = referenced_ct_series_uid[-20:] if referenced_ct_series_uid else 'N/A'
                    
                    # Count number of structures
                    try:
                        if (0x3006, 0x0020) in ds:  # StructureSetROISequence
                            info['NumStructures'] = len(ds[0x3006, 0x0020])
                        else:
                            info['NumStructures'] = 0
                    except:
                        info['NumStructures'] = 'Error'
                    
                    # Get structure names
                    struct_names = []
                    try:
                        if (0x3006, 0x0020) in ds:
                            for roi in ds[0x3006, 0x0020]:
                                name = str(roi.get('ROIName', 'Unknown'))
                                struct_names.append(name)
                    except:
                        pass
                    info['StructureNames'] = ', '.join(struct_names[:10]) + ('...' if len(struct_names) > 10 else '')
                    
                    # Determine if this looks like Limbus AI using CORRECT criteria:
                    # 1. SeriesDescription contains "Limbus" (e.g., "Limbus RTSS v1.8.0")
                    # 2. OR StructureSetLabel equals "Limbus RTStruct"
                    # 3. OR Manufacturer is "Limbus AI Inc."
                    # Note: ManufacturerModelName='ARIA RTM' is NOT reliable - both clinical
                    # and Limbus files can have this when exported via ARIA RTM
                    is_limbus = (
                        'Limbus' in info['SeriesDescription'] or
                        info['StructureSetLabel'] == 'Limbus RTStruct' or
                        info['Manufacturer'] == 'Limbus AI Inc.'
                    )
                    info['IsLimbusAI'] = 'YES' if is_limbus else 'NO'
                    
                    results.append(info)
                    
                except Exception as e:
                    # Even if full parsing fails, try to get basic info
                    print(f"  Warning: Full parse failed for {file}: {str(e)}")
                    try:
                        ds = pydicom.dcmread(filepath, stop_before_pixels=True, force=True)
                        if ds.get('Modality', '') == 'RTSTRUCT':
                            series_desc = str(ds.get('SeriesDescription', 'N/A'))
                            struct_label = str(ds.get('StructureSetLabel', 'N/A'))
                            manufacturer = str(ds.get('Manufacturer', 'N/A'))
                            
                            is_limbus = (
                                'Limbus' in series_desc or
                                struct_label == 'Limbus RTStruct' or
                                manufacturer == 'Limbus AI Inc.'
                            )
                            info = {
                                'Filename': file,
                                'Path': filepath,
                                'Modality': str(ds.get('Modality', 'N/A')),
                                'ManufacturerModelName': str(ds.get('ManufacturerModelName', 'N/A')),
                                'Manufacturer': manufacturer,
                                'StructureSetLabel': struct_label,
                                'SeriesDescription': series_desc,
                                'SOPInstanceUID': str(ds.get('SOPInstanceUID', 'N/A'))[-20:],
                                'NumStructures': 'ParseError',
                                'IsLimbusAI': 'YES' if is_limbus else 'NO'
                            }
                            results.append(info)
                            print(f"    -> Partial info extracted: Model={info['ManufacturerModelName']}, IsLimbus={info['IsLimbusAI']}")
                    except Exception as e2:
                        print(f"  Error: Could not read {file} at all: {str(e2)}")
    
    return results


def analyze_rtplan_metadata(patient_folder: str) -> List[Dict]:
    """
    Extract metadata from all RTPLAN files in a patient folder.
    """
    rtplan_folder = os.path.join(patient_folder, 'RTPLAN')
    if not os.path.isdir(rtplan_folder):
        rtplan_folder = patient_folder
    
    results = []
    
    for root, dirs, files in os.walk(rtplan_folder):
        for file in files:
            if file.lower().endswith('.dcm'):
                filepath = os.path.join(root, file)
                try:
                    ds = pydicom.dcmread(filepath, stop_before_pixels=True)
                    if ds.get('Modality', '') != 'RTPLAN':
                        continue
                    
                    info = {
                        'Filename': file,
                        'SOPInstanceUID': str(ds.get('SOPInstanceUID', 'N/A'))[-20:],
                        'RTPlanLabel': str(ds.get('RTPlanLabel', 'N/A')),
                        'RTPlanName': str(ds.get('RTPlanName', 'N/A')),
                    }
                    
                    # Get approval status
                    if (0x300E, 0x0002) in ds:
                        info['ApprovalStatus'] = str(ds[0x300E, 0x0002].value)
                    else:
                        info['ApprovalStatus'] = 'N/A'
                    
                    # Get referenced RTSTRUCT SOP Instance UID
                    ref_rtstruct_sop_uid = ''
                    if (0x300C, 0x0060) in ds:  # ReferencedStructureSetSequence
                        ref_struct_seq = ds[0x300C, 0x0060]
                        if hasattr(ref_struct_seq, 'value') and len(ref_struct_seq.value) > 0:
                            ref_rtstruct_sop_uid = str(ref_struct_seq.value[0].get('ReferencedSOPInstanceUID', ''))
                    info['ReferencedRTSTRUCT_SOP'] = ref_rtstruct_sop_uid[-20:] if ref_rtstruct_sop_uid else 'N/A'
                    
                    results.append(info)
                    
                except Exception as e:
                    print(f"  Error reading RTPLAN {file}: {str(e)}")
    
    return results


def main():
    print("=" * 100)
    print("LIMBUS AI DETECTION DIAGNOSTIC")
    print("=" * 100)
    print(f"\nAnalyzing {len(PROBLEM_PATIENTS)} patients with identification issues\n")
    
    all_rtstruct_data = []
    all_rtplan_data = []
    
    for patient_id in PROBLEM_PATIENTS:
        patient_folder = os.path.join(DICOM_ROOT, patient_id)
        
        print(f"\n{'='*100}")
        print(f"PATIENT: {patient_id}")
        print(f"{'='*100}")
        
        if not os.path.isdir(patient_folder):
            print(f"  ERROR: Patient folder not found: {patient_folder}")
            continue
        
        # Analyze RTSTRUCT files
        print("\n  RTSTRUCT FILES:")
        print("  " + "-" * 96)
        rtstruct_data = analyze_rtstruct_metadata(patient_folder)
        
        if not rtstruct_data:
            print("    No RTSTRUCT files found!")
        else:
            for idx, info in enumerate(rtstruct_data):
                print(f"\n  [{idx + 1}] {info['Filename']}")
                print(f"      ManufacturerModelName: {info['ManufacturerModelName']}")
                print(f"      Manufacturer:          {info['Manufacturer']}")
                print(f"      IsLimbusAI:            {info['IsLimbusAI']}")
                print(f"      StructureSetLabel:     {info['StructureSetLabel']}")
                print(f"      StructureSetName:      {info['StructureSetName']}")
                print(f"      SeriesDescription:     {info['SeriesDescription']}")
                print(f"      SoftwareVersions:      {info['SoftwareVersions']}")
                print(f"      StationName:           {info['StationName']}")
                print(f"      ApprovalStatus:        {info['ApprovalStatus']}")
                print(f"      NumStructures:         {info['NumStructures']}")
                print(f"      FrameOfReferenceUID:   ...{info['FrameOfReferenceUID']}")
                print(f"      ReferencedCTSeriesUID: ...{info['ReferencedCTSeriesUID']}")
                print(f"      StructureSetDate:      {info['StructureSetDate']}")
                print(f"      Structures:            {info['StructureNames']}")
                
                info['PatientID'] = patient_id
                all_rtstruct_data.append(info)
        
        # Analyze RTPLAN files
        print("\n  RTPLAN FILES:")
        print("  " + "-" * 96)
        rtplan_data = analyze_rtplan_metadata(patient_folder)
        
        if not rtplan_data:
            print("    No RTPLAN files found!")
        else:
            for idx, info in enumerate(rtplan_data):
                print(f"\n  [{idx + 1}] {info['Filename']}")
                print(f"      RTPlanName:              {info['RTPlanName']}")
                print(f"      RTPlanLabel:             {info['RTPlanLabel']}")
                print(f"      ApprovalStatus:          {info['ApprovalStatus']}")
                print(f"      ReferencedRTSTRUCT_SOP:  ...{info['ReferencedRTSTRUCT_SOP']}")
                
                info['PatientID'] = patient_id
                all_rtplan_data.append(info)
    
    # Summary statistics
    print("\n" + "=" * 100)
    print("SUMMARY - MANUFACTURER MODEL NAMES FOUND")
    print("=" * 100)
    
    model_names = {}
    for info in all_rtstruct_data:
        model = info['ManufacturerModelName']
        if model not in model_names:
            model_names[model] = 0
        model_names[model] += 1
    
    for model, count in sorted(model_names.items()):
        print(f"  {model}: {count} files")
    
    # Save to CSV for detailed analysis (avoid openpyxl dependency)
    if all_rtstruct_data:
        df_rtstruct = pd.DataFrame(all_rtstruct_data)
        df_rtstruct.to_csv('limbus_detection_rtstruct_analysis.csv', index=False)
        print(f"\n  RTSTRUCT analysis saved to: limbus_detection_rtstruct_analysis.csv")
    
    if all_rtplan_data:
        df_rtplan = pd.DataFrame(all_rtplan_data)
        df_rtplan.to_csv('limbus_detection_rtplan_analysis.csv', index=False)
        print(f"  RTPLAN analysis saved to: limbus_detection_rtplan_analysis.csv")


if __name__ == '__main__':
    main()
