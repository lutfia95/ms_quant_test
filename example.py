import ms_quant



for entry in ms_quant.roots():
    print(entry.name)
# ExperimentalDesign
# Method
# QuantifiedEntity
# Result
# Software


    
AGGREGATION = ms_quant.get_term(name="AggregationMethod")  # or even Method
for entry in [AGGREGATION, *ms_quant.children(AGGREGATION.key)]:
    print("######################################")
    print(f'{entry.name} | {entry.term}')
    print(entry.definition)
    print(entry.properties)
    
    for child in ms_quant.children(entry.key):
        print(f"  - {child.name}")
        #print(f"{child.term}")
        #print(child.definition)

# import ms_quant

# entry = ms_quant.get_term(name="MaxQuant")
# print(entry.name)        # MaxQuant
# print(entry.term)        # MS:1001583
# print(entry.definition)
# print(entry.xrefs)

# entry = ms_quant.get_term("MS:1001583")
# matches = ms_quant.search("intensity")
# children = ms_quant.children("Method")
# ancestors = ms_quant.ancestors("FoldChange")
# descendants = ms_quant.descendants("Method")
# classes = ms_quant.terms(classes_only=True)
