"""
Inspect a linkeddicom.ttl file to see its contents and structure.
"""

from rdflib import Graph
import sys

def inspect_linkeddicom(ttl_file_path):
    """
    Inspect a linkeddicom.ttl file and print its contents.
    
    Parameters
    ----------
    ttl_file_path : str
        Path to the linkeddicom.ttl file
    """
    print(f"Inspecting: {ttl_file_path}")
    print("="*80)
    
    # Load the TTL file
    graph = Graph()
    graph.parse(ttl_file_path, format='ttl')
    
    print(f"\nTotal triples in graph: {len(graph)}")
    
    # Print all triples (subject, predicate, object)
    print("\n" + "="*80)
    print("ALL TRIPLES IN FILE:")
    print("="*80)
    for i, (subject, predicate, obj) in enumerate(graph):
        print(f"\n[{i}] Subject  : {subject}")
        print(f"    Predicate: {predicate}")
        print(f"    Object   : {obj}")
    
    # Look specifically for RTPLAN-related tags
    print("\n" + "="*80)
    print("SEARCHING FOR RTPLAN TAGS:")
    print("="*80)
    
    # Tag 300C,0060 - Referenced Structure Set Sequence
    print("\nLooking for tag T300C0060 (Referenced Structure Set Sequence)...")
    found_300C0060 = False
    for subject, predicate, obj in graph:
        if 'T300C0060' in str(predicate):
            print(f"  ✓ FOUND: {subject} -> {predicate} -> {obj}")
            found_300C0060 = True
    if not found_300C0060:
        print("  ✗ NOT FOUND")
    
    # Tag 0008,1155 - Referenced SOP Instance UID
    print("\nLooking for tag T00081155 (Referenced SOP Instance UID)...")
    found_00081155 = False
    for subject, predicate, obj in graph:
        if 'T00081155' in str(predicate):
            print(f"  ✓ FOUND: {subject} -> {predicate} -> {obj}")
            found_00081155 = True
    if not found_00081155:
        print("  ✗ NOT FOUND")
    
    # Look for RTPLAN objects
    print("\nLooking for Radiotherapy_Plan_Object...")
    found_rtplan = False
    for subject, predicate, obj in graph:
        if 'Radiotherapy_Plan_Object' in str(obj):
            print(f"  ✓ FOUND RTPLAN: {subject}")
            found_rtplan = True
            
            # Show all properties of this RTPLAN
            print(f"    Properties of this RTPLAN:")
            for s2, p2, o2 in graph:
                if str(s2) == str(subject):
                    print(f"      {p2} -> {o2}")
    if not found_rtplan:
        print("  ✗ NOT FOUND")
    
    # Look for RTSTRUCT objects
    print("\nLooking for Radiotherapy_Structure_Object...")
    found_rtstruct = False
    for subject, predicate, obj in graph:
        if 'Radiotherapy_Structure_Object' in str(obj):
            print(f"  ✓ FOUND RTSTRUCT: {subject}")
            found_rtstruct = True
            
            # Show SOP Instance UID (0008,0018)
            for s2, p2, o2 in graph:
                if str(s2) == str(subject) and 'T00080018' in str(p2):
                    print(f"    SOP Instance UID (0008,0018): {o2}")
    if not found_rtstruct:
        print("  ✗ NOT FOUND")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        ttl_file = sys.argv[1]
    else:
        # Default path - change this to your file
        ttl_file = r"Z:\Projects\phys\p0728-automation\ICoNEA\DICOM\P0728C0006I13396399\linkeddicom.ttl"
    
    inspect_linkeddicom(ttl_file)
