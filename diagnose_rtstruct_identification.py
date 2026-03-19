"""
Quick diagnostic tool to check RTSTRUCT identification for a patient
"""
import os
import sys
import pydicom
from pathlib import Path

def diagnose_patient_rtstructs(patient_folder):
    """
    Diagnose RTSTRUCT files in a patient folder to identify which is which.
    """
    print(f"{'='*80}")
    print(f"RTSTRUCT DIAGNOSTIC TOOL")
    print(f"{'='*80}")
    print(f"Patient folder: {patient_folder}\n")
    
    # Find RTSTRUCT files
    rtstruct_folder = os.path.join(patient_folder, 'RTSTRUCT')
    
    if not os.path.isdir(rtstruct_folder):
        print(f"ERROR: No RTSTRUCT folder found at {rtstruct_folder}")
        return
    
    rtstruct_files = []
    for root, dirs, files in os.walk(rtstruct_folder):
        for file in files:
            if file.lower().endswith('.dcm'):
                rtstruct_files.append(os.path.join(root, file))
    
    if not rtstruct_files:
        print("ERROR: No RTSTRUCT .dcm files found")
        return
    
    print(f"Found {len(rtstruct_files)} RTSTRUCT file(s)\n")
    
    # Analyze each file
    results = []
    for idx, rtstruct_path in enumerate(rtstruct_files, 1):
        print(f"{'-'*80}")
        print(f"RTSTRUCT #{idx}: {os.path.relpath(rtstruct_path, patient_folder)}")
        print(f"{'-'*80}")
        
        try:
            ds = pydicom.dcmread(rtstruct_path, stop_before_pixels=True)
            
            # Extract key metadata
            metadata = {
                'path': rtstruct_path,
                'relative_path': os.path.relpath(rtstruct_path, patient_folder),
                'manufacturer': str(ds.get('Manufacturer', 'N/A')),
                'series_desc': str(ds.get('SeriesDescription', 'N/A')),
                'struct_label': str(ds.get('StructureSetLabel', 'N/A')),
                'struct_name': str(ds.get('StructureSetName', 'N/A')),
                'approval_status': str(ds.get('ApprovalStatus', 'N/A')),
                'software_versions': str(ds.get('SoftwareVersions', 'N/A')),
                'station_name': str(ds.get('StationName', 'N/A')),
                'series_date': str(ds.get('SeriesDate', 'N/A')),
                'series_time': str(ds.get('SeriesTime', 'N/A')),
            }
            
            # Identify source
            source = 'UNKNOWN'
            confidence = []
            
            # Check manufacturer
            if 'limbus' in metadata['manufacturer'].lower():
                source = 'LIMBUS AI'
                confidence.append('Manufacturer contains "limbus"')
            elif 'varian' in metadata['manufacturer'].lower():
                source = 'ARIA RADonc'
                confidence.append('Manufacturer contains "varian"')
            
            # Check series description
            if 'limbus' in metadata['series_desc'].lower() or 'ai' in metadata['series_desc'].lower():
                if source == 'UNKNOWN':
                    source = 'LIMBUS AI'
                confidence.append('Series Description suggests AI/Limbus')
            elif 'aria' in metadata['series_desc'].lower():
                if source == 'UNKNOWN':
                    source = 'ARIA RADonc'
                confidence.append('Series Description suggests ARIA')
            
            # Check structure set label
            if 'limbus' in metadata['struct_label'].lower():
                if source == 'UNKNOWN':
                    source = 'LIMBUS AI'
                confidence.append('Structure Set Label contains "limbus"')
            elif 'aria' in metadata['struct_label'].lower() or 'approved' in metadata['struct_label'].lower():
                if source == 'UNKNOWN':
                    source = 'ARIA RADonc'
                confidence.append('Structure Set Label suggests ARIA/approved')
            
            # Check approval status
            if metadata['approval_status'] == 'APPROVED':
                if source == 'UNKNOWN':
                    source = 'ARIA RADonc (likely)'
                confidence.append('Approval Status is APPROVED')
            
            # Print metadata
            print(f"Manufacturer:           {metadata['manufacturer']}")
            print(f"Series Description:     {metadata['series_desc']}")
            print(f"Structure Set Label:    {metadata['struct_label']}")
            print(f"Structure Set Name:     {metadata['struct_name']}")
            print(f"Approval Status:        {metadata['approval_status']}")
            print(f"Software Versions:      {metadata['software_versions']}")
            print(f"Station Name:           {metadata['station_name']}")
            print(f"Series Date:            {metadata['series_date']}")
            print(f"Series Time:            {metadata['series_time']}")
            
            print(f"\n🔍 IDENTIFIED AS:        {source}")
            if confidence:
                print(f"   Confidence factors:")
                for factor in confidence:
                    print(f"     • {factor}")
            else:
                print(f"   ⚠ No identifying features found!")
            
            # Get a few structure names
            if hasattr(ds, 'StructureSetROISequence') and ds.StructureSetROISequence:
                struct_names = [roi.ROIName for roi in ds.StructureSetROISequence[:5]]
                print(f"\n   First 5 structures: {', '.join(struct_names)}")
            
            metadata['source'] = source
            metadata['confidence_factors'] = confidence
            results.append(metadata)
            
        except Exception as e:
            print(f"ERROR reading file: {str(e)}")
    
    # Summary
    print(f"\n{'='*80}")
    print(f"SUMMARY & RECOMMENDATIONS")
    print(f"{'='*80}\n")
    
    limbus_count = sum(1 for r in results if 'LIMBUS' in r['source'])
    aria_count = sum(1 for r in results if 'ARIA' in r['source'])
    unknown_count = sum(1 for r in results if 'UNKNOWN' in r['source'])
    
    print(f"Total RTSTRUCTs found:     {len(results)}")
    print(f"  Identified as Limbus AI: {limbus_count}")
    print(f"  Identified as ARIA:      {aria_count}")
    print(f"  Unknown:                 {unknown_count}\n")
    
    if limbus_count == 1 and aria_count == 1:
        print("✓ Good! Found exactly 1 Limbus AI and 1 ARIA RADonc RTSTRUCT")
        
        limbus_file = next(r for r in results if 'LIMBUS' in r['source'])
        aria_file = next(r for r in results if 'ARIA' in r['source'])
        
        print(f"\nRTSTRUCT1 (Limbus AI) should be:     {limbus_file['relative_path']}")
        print(f"RTSTRUCT2 (ARIA RADonc) should be:   {aria_file['relative_path']}\n")
        
        # Check if current sorting by path would get it right
        sorted_results = sorted(results, key=lambda x: x['path'])
        if sorted_results[0]['source'] == limbus_file['source'] and sorted_results[-1]['source'] == aria_file['source']:
            print("✓ Path-based sorting would correctly identify these files")
        else:
            print("✗ Path-based sorting would INCORRECTLY identify these files")
            print(f"  Path sorting would assign:")
            print(f"    RTSTRUCT1: {sorted_results[0]['relative_path']} ({sorted_results[0]['source']})")
            print(f"    RTSTRUCT2: {sorted_results[-1]['relative_path']} ({sorted_results[-1]['source']})")
    
    elif unknown_count > 0:
        print("⚠ WARNING: Could not identify all RTSTRUCTs")
        print("\nTo fix this, you need to:")
        print("1. Manually compare the RTSTRUCT files above")
        print("2. Identify which metadata fields differ between Limbus AI and ARIA RADonc")
        print("3. Update the identification logic in this script or the main code")
    
    else:
        print(f"⚠ Unexpected configuration: {limbus_count} Limbus AI, {aria_count} ARIA RADonc")
    
    # Key fields to use for identification
    print(f"\n{'-'*80}")
    print("KEY FIELDS FOR IDENTIFICATION (based on this patient):")
    print(f"{'-'*80}")
    
    if len(results) >= 2:
        # Compare fields across RTSTRUCTs
        fields_to_check = ['manufacturer', 'series_desc', 'struct_label', 'approval_status', 'software_versions']
        
        for field in fields_to_check:
            values = [r[field] for r in results]
            if len(set(values)) > 1:  # Field has different values
                print(f"\n✓ {field.upper()} differs across RTSTRUCTs:")
                for idx, r in enumerate(results, 1):
                    print(f"    RTSTRUCT #{idx}: {r[field]}")
            else:
                print(f"\n  {field.upper()}: Same for all RTSTRUCTs ({values[0]})")


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python diagnose_rtstruct_identification.py <patient_folder>")
        print("\nExample:")
        print("  python diagnose_rtstruct_identification.py Z:\\...\\DICOM\\P0728C0006I13346699")
        sys.exit(1)
    
    patient_folder = sys.argv[1]
    
    if not os.path.exists(patient_folder):
        print(f"ERROR: Patient folder not found: {patient_folder}")
        sys.exit(1)
    
    diagnose_patient_rtstructs(patient_folder)
