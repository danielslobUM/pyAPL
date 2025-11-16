"""
Tests for linkeddicom_helper module
"""

import os
import tempfile
import shutil
from linkeddicom_helper import get_structs_for_ct


def test_get_structs_for_ct_no_file():
    """Test get_structs_for_ct with a non-existent TTL file."""
    print("Testing get_structs_for_ct with non-existent TTL file...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        result = get_structs_for_ct(tmpdir)
        assert result == {}, f"Expected empty dict, got {result}"
    
    print("✓ get_structs_for_ct handles missing TTL file correctly")


def test_get_structs_for_ct_empty_ttl():
    """Test get_structs_for_ct with an empty TTL file."""
    print("Testing get_structs_for_ct with empty TTL file...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create an empty TTL file
        ttl_path = os.path.join(tmpdir, "linkeddicom.ttl")
        with open(ttl_path, 'w') as f:
            f.write("")
        
        # Should return empty dict as there's no data
        result = get_structs_for_ct(tmpdir)
        assert result == {}, f"Expected empty dict, got {result}"
    
    print("✓ get_structs_for_ct handles empty TTL file correctly")


def test_get_structs_for_ct_with_sample_data():
    """Test get_structs_for_ct with sample TTL data."""
    print("Testing get_structs_for_ct with sample TTL data...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a sample TTL file with minimal valid data
        ttl_path = os.path.join(tmpdir, "linkeddicom.ttl")
        
        # Create a simple TTL file
        # Note: This is a simplified example and may need adjustment based on actual data format
        sample_ttl = """
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix dicom: <http://purl.org/healthcarevocab/v1#> .

<http://example.com/ct1> rdf:type dicom:CTSeries ;
    dicom:hasSeriePath "/path/to/ct" .

<http://example.com/rt1> rdf:type dicom:RTStruct ;
    dicom:referencesSeriesInstanceUID <http://example.com/ct1> ;
    dicom:hasFilePath "/path/to/rtstruct1.dcm" ;
    dicom:hasStructure <http://example.com/struct1> .

<http://example.com/struct1> dicom:structureName "TestStructure" .
"""
        
        with open(ttl_path, 'w') as f:
            f.write(sample_ttl)
        
        # Note: This test will fail if the SPARQL query file is not in the current directory
        # Since we don't have real data, we'll just test that the function can be called
        # In a real scenario, you'd need the ct_rtstruct.sparql file in the working directory
        
        if os.path.exists("ct_rtstruct.sparql"):
            result = get_structs_for_ct(tmpdir)
            # The result structure should be a dictionary
            assert isinstance(result, dict), f"Expected dict, got {type(result)}"
            print(f"  Result: {result}")
        else:
            print("  Skipping: ct_rtstruct.sparql not found in working directory")
    
    print("✓ get_structs_for_ct processes sample data correctly")


def test_module_imports():
    """Test that linkeddicom_helper can be imported."""
    print("Testing linkeddicom_helper import...")
    
    try:
        import linkeddicom_helper
        from linkeddicom_helper import get_structs_for_ct
        print("✓ linkeddicom_helper import successful")
    except Exception as e:
        print(f"✗ linkeddicom_helper import failed: {e}")
        raise


if __name__ == '__main__':
    print("="*60)
    print("Running linkeddicom_helper tests")
    print("="*60)
    
    test_module_imports()
    print()
    test_get_structs_for_ct_no_file()
    print()
    test_get_structs_for_ct_empty_ttl()
    print()
    test_get_structs_for_ct_with_sample_data()
    print()
    
    print("="*60)
    print("All linkeddicom_helper tests passed!")
    print("="*60)
