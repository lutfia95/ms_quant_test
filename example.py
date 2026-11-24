import ms_quant

entry = ms_quant.get_term(name="LabelFreeQuantification")
print(entry.term)        # Empty until an equivalent CV term is confirmed
print(entry.name)        # LabelFreeQuantification
print(entry.definition)
print(entry.xrefs)       # Related references are separate from confirmed mappings

#entry_2 = ms_quant.get_term(name="ReferenceChannelNormalization")

#print(entry_2.definition)

for entry in ms_quant.terms():
    #if entry.term:
    print(f'{entry.term}\t{entry.name}')