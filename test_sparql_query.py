from rdflib import Graph

# Load the TTL file
g = Graph()
g.parse('Z:\\Projects\\phys\\p0728-automation\\ICoNEA\\DICOM\\P0728C0006I13346699\\linkeddicom.ttl')
print(f'Graph loaded with {len(g)} triples')

# Run the query
query = open('ct_rtstruct.sparql').read()
result = list(g.query(query))
print(f'Query returned {len(result)} results')

# Print first few results
for i, row in enumerate(result[:5]):
    print(f'\nResult {i+1}:')
    print(f'  CT Series: {row.ctSerie}')
    print(f'  CT Path: {row.ctSeriePath}')
    print(f'  RTSTRUCT: {row.rtStruct}')
    print(f'  RTSTRUCT Path: {row.rtStructPath}')
    print(f'  Structure: {row.structureName}')
