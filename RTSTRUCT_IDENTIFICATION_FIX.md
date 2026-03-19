# RTSTRUCT Identification Issue - Analysis and Recommendations

## Problem Statement

For 1 in 10 patients, RTSTRUCTs are incorrectly identified:
- **Current behavior**: ARIA RADonc (clinically approved) → RTSTRUCT1, Limbus AI (deep learning) → RTSTRUCT2
- **Desired behavior**: Limbus AI (deep learning) → RTSTRUCT1, ARIA RADonc (clinically approved) → RTSTRUCT2

## Root Cause Analysis

### 1. Current Sorting Method
In `quantifycontourdifferences_P0728.py` (line 459):
```python
available_rtstructs.sort(key=lambda x: x[1])  # Sorts by path only
```

This sorts RTSTRUCTs **alphabetically by file path**, which typically includes dates. The assumption is that sorting by path/date will give a consistent ordering, but **this doesn't distinguish between AI-generated vs clinically approved structures**.

### 2. Missing Metadata in SPARQL Query
The current `ct_rtstruct.sparql` query retrieves:
- RTSTRUCT UID
- File path
- Structure names
- Linked RTPLAN

But **does NOT retrieve** distinguishing metadata such as:
- Manufacturer (might contain "Limbus AI" or "Varian")
- Series Description
- Structure Set Label
- Structure Set Name
- Approval Status
- Software Versions

### 3. No Validation Logic
There's no logic to verify which RTSTRUCT is which based on metadata - just blind sorting by path.

## Recommended Solution

### Step 1: Identify Distinguishing Metadata

Run the comparison script to identify metadata differences:
```bash
python compare_rtstruct_pair.py "path/to/limbus_ai_rtstruct.dcm" "path/to/aria_radonc_rtstruct.dcm"
```

Look for fields that consistently differ between the two types. Common possibilities:
- **Manufacturer**: "Limbus AI" vs "Varian Medical Systems"
- **Series Description**: Might contain "AI" or "Limbus"
- **Structure Set Label**: Might indicate source
- **Approval Status**: Clinically approved might have "APPROVED" status
- **Software Versions**: Different software versions
- **ROI Generation Algorithm**: AI structures often marked as "AUTOMATIC"

### Step 2: Enhanced SPARQL Query

I've created `ct_rtstruct_enhanced.sparql` that retrieves additional metadata:
```sparql
OPTIONAL { ?rtStructInstance ldcm:T0008103E ?seriesDescription . }     # Series Description
OPTIONAL { ?rtStructInstance ldcm:T00080070 ?manufacturer . }          # Manufacturer
OPTIONAL { ?rtStructInstance ldcm:T30060002 ?structureSetLabel . }     # Structure Set Label
OPTIONAL { ?rtStructInstance ldcm:T30060004 ?structureSetName . }      # Structure Set Name
OPTIONAL { ?rtStructInstance ldcm:T300E0002 ?approvalStatus . }        # Approval Status
```

### Step 3: Update linkeddicom_helper.py

Modify `get_structs_for_ct()` to store the additional metadata:
```python
ctSeries[str(row.ctSerie)]["RTSTRUCT"][str(row.rtStruct)] = {
    "UID": str(row.rtStruct),
    "path": str(row.rtStructPath),
    "structure_names": [ ],
    "RTPLAN": None,
    # NEW: Add metadata fields
    "SeriesDescription": str(row.seriesDescription) if hasattr(row, 'seriesDescription') else None,
    "Manufacturer": str(row.manufacturer) if hasattr(row, 'manufacturer') else None,
    "StructureSetLabel": str(row.structureSetLabel) if hasattr(row, 'structureSetLabel') else None,
    "StructureSetName": str(row.structureSetName) if hasattr(row, 'structureSetName') else None,
    "ApprovalStatus": str(row.approvalStatus) if hasattr(row, 'approvalStatus') else None,
}
```

### Step 4: Update Sorting Logic in quantifycontourdifferences_P0728.py

Replace the simple path-based sorting with intelligent identification:

```python
def identify_rtstruct_source(rt_data):
    """
    Identify if RTSTRUCT is from Limbus AI or ARIA RADonc.
    
    Returns:
        'limbus_ai', 'aria_radonc', or 'unknown'
    """
    # Check Manufacturer
    manufacturer = rt_data.get('Manufacturer', '').lower()
    if 'limbus' in manufacturer:
        return 'limbus_ai'
    if 'varian' in manufacturer or 'aria' in manufacturer:
        return 'aria_radonc'
    
    # Check Series Description
    series_desc = rt_data.get('SeriesDescription', '').lower()
    if 'limbus' in series_desc or 'ai' in series_desc:
        return 'limbus_ai'
    if 'aria' in series_desc or 'radonc' in series_desc:
        return 'aria_radonc'
    
    # Check Structure Set Label
    struct_label = rt_data.get('StructureSetLabel', '').lower()
    if 'limbus' in struct_label:
        return 'limbus_ai'
    if 'aria' in struct_label or 'approved' in struct_label:
        return 'aria_radonc'
    
    # Check Approval Status
    approval = rt_data.get('ApprovalStatus', '')
    if approval == 'APPROVED':
        return 'aria_radonc'
    
    return 'unknown'

# Then in the main code, replace the sort with:
limbus_ai_rtstructs = []
aria_radonc_rtstructs = []
unknown_rtstructs = []

for rt_uid, rt_path, rt_data in available_rtstructs:
    source = identify_rtstruct_source(rt_data)
    if source == 'limbus_ai':
        limbus_ai_rtstructs.append((rt_uid, rt_path, rt_data))
    elif source == 'aria_radonc':
        aria_radonc_rtstructs.append((rt_uid, rt_path, rt_data))
    else:
        unknown_rtstructs.append((rt_uid, rt_path, rt_data))

# Select RTSTRUCT1 (Limbus AI) and RTSTRUCT2 (ARIA RADonc)
if limbus_ai_rtstructs and aria_radonc_rtstructs:
    rtstruct1_uid, rtstruct1_path, rtstruct1_data = limbus_ai_rtstructs[0]
    rtstruct2_uid, rtstruct2_path, rtstruct2_data = aria_radonc_rtstructs[0]
else:
    # Fallback to old behavior with warning
    print("  WARNING: Could not identify RTSTRUCT sources, using path-based sorting")
    available_rtstructs.sort(key=lambda x: x[1])
    rtstruct1_uid, rtstruct1_path, rtstruct1_data = available_rtstructs[0]
    rtstruct2_uid, rtstruct2_path, rtstruct2_data = available_rtstructs[-1]
```

## Alternative: Read DICOM Metadata Directly

If the TTL file doesn't contain the necessary metadata, you can read it directly from the DICOM files:

```python
import pydicom

for rt_uid, rt_path, rt_data in available_rtstructs:
    # Read DICOM file to get metadata
    ds = pydicom.dcmread(rt_path, stop_before_pixels=True)
    rt_data['Manufacturer'] = ds.get('Manufacturer', '')
    rt_data['SeriesDescription'] = ds.get('SeriesDescription', '')
    rt_data['StructureSetLabel'] = ds.get('StructureSetLabel', '')
    rt_data['ApprovalStatus'] = ds.get('ApprovalStatus', '')
```

## Next Steps

1. **Run the comparison script** on a patient where the issue occurs to identify distinguishing fields
2. **Test the enhanced SPARQL query** to see if it retrieves the metadata
3. **Update the code** based on which metadata fields reliably distinguish the two types
4. **Validate** on multiple patients to ensure the fix works consistently

## Files Created

1. `compare_rtstruct_pair.py` - Compare two RTSTRUCT files side-by-side
2. `ct_rtstruct_enhanced.sparql` - Enhanced SPARQL query with additional metadata
3. `inspect_rtstruct_metadata.py` - Inspect RTSTRUCT metadata from patient folders
