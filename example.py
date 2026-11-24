import ms_quant


AGGREGATION = ms_quant.get_term(name="AggregationMethod")
for entry in [AGGREGATION, *ms_quant.children(AGGREGATION.key)]:
    print("######################################")
    print(f'{entry.name} | {entry.term}')
    print(entry.definition)
    print(entry.properties)
    
    for child in ms_quant.children(entry.key):
        print(f"  - {child.name}")
        #print(f"{child.term}")
        #print(child.definition)

    
    
