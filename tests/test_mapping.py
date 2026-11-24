from copy import deepcopy
import json
from pathlib import Path
import runpy
import unittest

ROOT = Path(__file__).resolve().parents[1]
map_document = runpy.run_path(str(ROOT / "scripts/map_cv.py"))["map_document"]
to_jsonld = runpy.run_path(str(ROOT / "scripts/sync_data.py"))["to_jsonld"]


def node(key, name=None, term="", refs=()):
    return {"key": key, "term": term, "properties": {
        "rdf:type": [{"kind": "iri", "value": "owl:Class"}],
        "rdfs:label": [{"kind": "literal", "value": name or key}],
        "rdfs:seeAlso": [{"kind": "literal", "value": ref} for ref in refs],
    }}


CV = b'''data-version: test
[Term]
id: MS:1
name: Example software
synonym: "ES" EXACT []
[Term]
id: MS:2
name: broader concept
synonym: "related label" RELATED []
[Term]
id: MS:3
name: retired concept
is_obsolete: true
[Typedef]
id: has_relation
name: relation name
'''


class MappingTests(unittest.TestCase):
    def map_nodes(self, nodes, cv=CV):
        document = {"schema_version": 3, "nodes": nodes}
        report = map_document(document, cv)
        return document, report

    def test_normalized_name_and_exact_synonym(self):
        for label in ("ExampleSoftware", "ES"):
            document, report = self.map_nodes([node("example", label)])
            self.assertEqual(document["nodes"][0]["term"], "MS:1")
            self.assertEqual(report["entries"][0]["status"], "exact_name_match")

    def test_related_reference_does_not_assign_accession(self):
        document, report = self.map_nodes([node("narrower", refs=("MS:2", "MS:999"))])
        self.assertEqual(document["nodes"][0]["term"], "")
        refs = report["entries"][0]["existing_cv_references"]
        self.assertTrue(refs[0]["exists"])
        self.assertEqual(refs[0]["name"], "broader concept")
        self.assertFalse(refs[1]["exists"])

    def test_obsolete_and_related_synonyms_not_assigned(self):
        for label in ("retired concept", "related label", "relation name"):
            document, _ = self.map_nodes([node(label)])
            self.assertEqual(document["nodes"][0]["term"], "")

    def test_ambiguous_cv_name(self):
        cv = CV + b'\n[Term]\nid: MS:4\nname: Example software\n'
        document, report = self.map_nodes([node("example", "ExampleSoftware")], cv)
        self.assertEqual(document["nodes"][0]["term"], "")
        self.assertEqual(report["entries"][0]["status"], "ambiguous")

    def test_same_accession_cannot_map_two_local_entries(self):
        document, report = self.map_nodes([node("a", "ExampleSoftware"), node("b", "ES")])
        self.assertTrue(all(n["term"] == "" for n in document["nodes"]))
        self.assertEqual(report["summary"], {"ambiguous": 2})

    def test_preserve_filled_accession(self):
        document, report = self.map_nodes([node("custom", term="CUSTOM:1")])
        self.assertEqual(document["nodes"][0]["term"], "CUSTOM:1")
        self.assertEqual(report["entries"][0]["status"], "existing_assignment")
        self.assertFalse(report["entries"][0]["assigned_term_active"])

    def test_current_mappings_and_unresolved_reference(self):
        document = json.loads((ROOT / "output/ontology.json").read_text())
        by_key = {n["key"]: n for n in document["nodes"]}
        self.assertEqual(by_key["MaxQuant"]["term"], "MS:1001583")
        self.assertEqual(by_key["QuantifiedProtein"]["term"], "")
        self.assertEqual(by_key["LabelFreeQuantification"]["term"], "")
        self.assertEqual(sum(bool(n["term"]) for n in document["nodes"]), 23)

    def test_jsonld_export_includes_mappings_and_standard_predicates(self):
        document = json.loads((ROOT / "output/ontology.json").read_text())
        exported = json.loads((ROOT / "output/ontology.jsonld").read_text())
        self.assertEqual(to_jsonld(document), exported)
        maxquant = next(n for n in exported if n["@id"] == "urn:ms-quant:MaxQuant")
        self.assertEqual(maxquant["urn:ms-quant:accession"], [{"@value": "MS:1001583"}])
        self.assertIn("http://www.w3.org/2000/01/rdf-schema#seeAlso", maxquant)
        triples = sum(len(v) for n in document["nodes"] for v in n["properties"].values())
        exported_triples = sum(len(v) for n in exported for p, v in n.items()
                               if p not in ("@id", "urn:ms-quant:accession"))
        self.assertEqual(exported_triples, triples)

    def test_broken_local_references_rejected(self):
        from ms_quant import Vocabulary
        document = {"schema_version": 3, "nodes": [node("a")]}
        document["nodes"][0]["properties"]["rdfs:subClassOf"] = [
            {"kind": "reference", "value": "missing"}]
        with self.assertRaisesRegex(ValueError, "Unknown local reference"):
            Vocabulary(document)


if __name__ == "__main__":
    unittest.main()
