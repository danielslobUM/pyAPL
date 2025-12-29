from linkeddicom_helper import get_structs_for_ct
import json

# Check a few patients
patients = [
    'Z:\\Projects\\phys\\p0728-automation\\ICoNEA\\DICOM\\P0728C0006I13346699',
    'Z:\\Projects\\phys\\p0728-automation\\ICoNEA\\DICOM\\P0728C0006I13396787'
]

for patient_path in patients:
    print(f"\n{'='*80}")
    print(f"Patient: {patient_path.split('\\')[-1]}")
    print(f"{'='*80}")
    
    try:
        result = get_structs_for_ct(patient_path)
        
        if not result:
            print("  No CT series found")
            continue
            
        for ct_uid, ct_data in result.items():
            print(f"\nCT Series: {ct_uid}")
            print(f"  Path: {ct_data['path']}")
            
            if ct_data['RTSTRUCT']:
                print(f"  Found {len(ct_data['RTSTRUCT'])} RTSTRUCT file(s):")
                for rt_uid, rt_data in ct_data['RTSTRUCT'].items():
                    print(f"\n  RTSTRUCT: {rt_uid}")
                    print(f"    Path: {rt_data['path']}")
                    print(f"    Structures: {', '.join(rt_data['structure_names'])}")
            else:
                print("  No RTSTRUCT files found")
                
    except Exception as e:
        print(f"  Error: {e}")
