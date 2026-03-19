"""
Compare two RTSTRUCT files side by side to identify distinguishing features
"""
import os
import sys
import pydicom

def compare_rtstructs(rtstruct1_path, rtstruct2_path):
    """
    Compare two RTSTRUCT files side by side.
    """
    print(f"{'='*80}")
    print(f"RTSTRUCT COMPARISON")
    print(f"{'='*80}\n")
    
    try:
        ds1 = pydicom.dcmread(rtstruct1_path, stop_before_pixels=True)
        ds2 = pydicom.dcmread(rtstruct2_path, stop_before_pixels=True)
        
        fields_to_compare = [
            # Basic identification
            ('SOPInstanceUID', 'SOP Instance UID'),
            ('SeriesInstanceUID', 'Series Instance UID'),
            
            # Descriptive fields
            ('SeriesDescription', 'Series Description'),
            ('StructureSetLabel', 'Structure Set Label'),
            ('StructureSetName', 'Structure Set Name'),
            ('StructureSetDescription', 'Structure Set Description'),
            
            # Date/Time
            ('StructureSetDate', 'Structure Set Date'),
            ('StructureSetTime', 'Structure Set Time'),
            ('SeriesDate', 'Series Date'),
            ('SeriesTime', 'Series Time'),
            
            # Manufacturer/Software
            ('Manufacturer', 'Manufacturer'),
            ('ManufacturerModelName', 'Manufacturer Model Name'),
            ('SoftwareVersions', 'Software Versions'),
            ('StationName', 'Station Name'),
            
            # Approval
            ('ApprovalStatus', 'Approval Status'),
        ]
        
        print(f"{'Field':<40} | {'RTSTRUCT 1':<35} | {'RTSTRUCT 2':<35}")
        print(f"{'-'*40}-+-{'-'*35}-+-{'-'*35}")
        
        differences = []
        
        for tag, label in fields_to_compare:
            val1 = str(ds1.get(tag, 'N/A'))
            val2 = str(ds2.get(tag, 'N/A'))
            
            # Truncate long values
            val1_display = val1[:33] + '..' if len(val1) > 35 else val1
            val2_display = val2[:33] + '..' if len(val2) > 35 else val2
            
            marker = ' *' if val1 != val2 else ''
            print(f"{label:<40} | {val1_display:<35} | {val2_display:<35}{marker}")
            
            if val1 != val2 and val1 != 'N/A' and val2 != 'N/A':
                differences.append((label, val1, val2))
        
        # Check for ROI Generation Algorithm
        print(f"\n{'='*80}")
        print(f"ROI GENERATION ALGORITHMS (first 5 structures)")
        print(f"{'='*80}\n")
        
        print(f"{'ROI Name':<30} | {'RTSTRUCT 1 Algorithm':<23} | {'RTSTRUCT 2 Algorithm':<23}")
        print(f"{'-'*30}-+-{'-'*23}-+-{'-'*23}")
        
        if hasattr(ds1, 'StructureSetROISequence') and hasattr(ds2, 'StructureSetROISequence'):
            # Get ROI names from both
            rois1 = {roi.ROIName: roi.get('ROIGenerationAlgorithm', 'N/A') 
                    for roi in ds1.StructureSetROISequence}
            rois2 = {roi.ROIName: roi.get('ROIGenerationAlgorithm', 'N/A') 
                    for roi in ds2.StructureSetROISequence}
            
            # Find common ROI names
            common_rois = set(rois1.keys()) & set(rois2.keys())
            
            for idx, roi_name in enumerate(list(common_rois)[:5]):
                alg1 = rois1.get(roi_name, 'N/A')
                alg2 = rois2.get(roi_name, 'N/A')
                marker = ' *' if alg1 != alg2 else ''
                print(f"{roi_name[:28]:<30} | {str(alg1)[:21]:<23} | {str(alg2)[:21]:<23}{marker}")
        
        print(f"\n{'='*80}")
        print(f"KEY DIFFERENCES (Fields marked with *)")
        print(f"{'='*80}\n")
        
        if differences:
            for label, val1, val2 in differences:
                print(f"\n{label}:")
                print(f"  RTSTRUCT 1: {val1}")
                print(f"  RTSTRUCT 2: {val2}")
        else:
            print("No differences found in compared fields")
        
        print(f"\n{'='*80}")
        print(f"RECOMMENDATIONS")
        print(f"{'='*80}\n")
        print("To distinguish Limbus AI (should be RTSTRUCT1) from ARIA RADonc (should be RTSTRUCT2):")
        print("1. Check Manufacturer field - might contain 'Limbus' or vendor name")
        print("2. Check Software Versions - might indicate the software used")
        print("3. Check Series Description or Structure Set Label - might indicate source")
        print("4. Check ROI Generation Algorithm - AI structures often marked as 'AUTOMATIC'")
        print("5. Check dates - Limbus AI structures might be newer/older depending on workflow")
        print("\nBased on the differences above, determine which field(s) can reliably")
        print("distinguish between the two types of RTSTRUCTs.")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python compare_rtstruct_pair.py <rtstruct1_path> <rtstruct2_path>")
        print("\nExample:")
        print("  python compare_rtstruct_pair.py Z:\\...\\RTSTRUCT\\20250101\\RS.dcm Z:\\...\\RTSTRUCT\\20250202\\RS.dcm")
        sys.exit(1)
    
    rtstruct1_path = sys.argv[1]
    rtstruct2_path = sys.argv[2]
    
    if not os.path.exists(rtstruct1_path):
        print(f"Error: File not found: {rtstruct1_path}")
        sys.exit(1)
    
    if not os.path.exists(rtstruct2_path):
        print(f"Error: File not found: {rtstruct2_path}")
        sys.exit(1)
    
    compare_rtstructs(rtstruct1_path, rtstruct2_path)
