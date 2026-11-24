from copy import deepcopy
import json
from pathlib import Path
import unittest

import ms_quant
from ms_quant import AmbiguousTermError, Vocabulary
from ms_quant.vocabulary import RDFS, RDF_TYPE, OWL_CLASS

ROOT = Path(__file__).resolve().parents[1]


class VocabularyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads((ROOT / "output/ontology.json").read_text())

    def test_export_and_bundle_match(self):
        self.assertEqual((ROOT / "output/ontology.json").read_bytes(),
                         (ROOT / "src/ms_quant/data/ontology.json").read_bytes())
        self.assertTrue(all(isinstance(n["term"], str) for n in self.document["nodes"]))
        self.assertEqual(len(ms_quant.terms(classes_only=True)), 263)

    def test_lookup_and_definition(self):
        entry = ms_quant.get_term(name="LabelFreeQuantification")
        self.assertEqual(ms_quant.get_term(entry.key), entry)
        self.assertEqual(entry.term, next(n["term"] for n in self.document["nodes"] if n["key"] == entry.key))
        self.assertIn("without introducing", entry.definition)
        self.assertIn("MS:1001834", entry.xrefs)
        self.assertEqual(ms_quant.get_term(name="labelfreequantification"), entry)

    def test_existing_roots(self):
        self.assertEqual({t.name for t in ms_quant.roots()},
                         {"ExperimentalDesign", "Method", "QuantifiedEntity", "Result", "Software"})

    def test_multiple_parents(self):
        entry = ms_quant.get_term(name="FoldChange")
        self.assertEqual({t.name for t in ms_quant.ancestors(entry.key) if t.name in {"RatioUnit", "RatioBasedEffectSize"}},
                         {"RatioUnit", "RatioBasedEffectSize"})
        ancestors = {t.name for t in ms_quant.ancestors(entry.key)}
        self.assertTrue({"RatioUnit", "RatioBasedEffectSize", "Result"} <= ancestors)
        for parent in ("RatioUnit", "RatioBasedEffectSize"):
            self.assertIn(entry, ms_quant.children(parent))

    def test_descendants(self):
        method = ms_quant.get_term(name="Method")
        self.assertIn(ms_quant.get_term(name="LabelFreeQuantification"), ms_quant.descendants(method.key))
        self.assertNotIn(method, ms_quant.descendants(method.key))

    def test_search(self):
        self.assertIn(ms_quant.get_term(name="IntensityMeasure"), ms_quant.search("INTENSITY"))
        self.assertEqual(ms_quant.search("not-a-real-ontology-term"), [])

    def test_missing_and_invalid_lookups(self):
        with self.assertRaises(KeyError):
            ms_quant.get_term("missing")
        with self.assertRaises(KeyError):
            ms_quant.get_term(name="missing")
        with self.assertRaises(ValueError):
            ms_quant.get_term()
        with self.assertRaises(ValueError):
            ms_quant.get_term("id", name="name")

    def test_filled_accession(self):
        document = deepcopy(self.document)
        identifier = ms_quant.get_term(name="LabelFreeQuantification").key
        for node in document["nodes"]:
            if node["key"] == identifier:
                node["term"] = "EXAMPLE:0001"
        vocabulary = Vocabulary(document)
        self.assertEqual(vocabulary.get_term("EXAMPLE:0001").key, identifier)
        self.assertEqual(vocabulary.get_term(identifier).term, "EXAMPLE:0001")

    def test_duplicate_accessions_rejected(self):
        document = deepcopy(self.document)
        named = [n for n in document["nodes"] if not n["key"].startswith("_:")]
        named[0]["term"] = named[1]["term"] = "EXAMPLE:0001"
        with self.assertRaisesRegex(ValueError, "Duplicate term accession"):
            Vocabulary(document)

    def test_duplicate_labels_require_identifier(self):
        document = deepcopy(self.document)
        named = [n for n in document["nodes"] if RDFS + "label" in n["properties"]]
        named[1]["properties"][RDFS + "label"] = deepcopy(named[0]["properties"][RDFS + "label"])
        vocabulary = Vocabulary(document)
        with self.assertRaises(AmbiguousTermError):
            vocabulary.get_term(name=named[0]["properties"][RDFS + "label"][0]["value"])

    def test_raw_restrictions_retained_and_not_class_parents(self):
        for node in self.document["nodes"]:
            if node["key"].startswith("_:"):
                self.assertEqual(ms_quant.get_node(node["key"]), node)
            else:
                self.assertFalse(hasattr(ms_quant.get_term(node["key"]), "parents"))
                self.assertFalse(hasattr(ms_quant.get_term(node["key"]), "id"))
        entry = ms_quant.get_term(name="FoldChange")
        properties = entry.properties
        properties.clear()
        self.assertTrue(entry.properties)

    def test_cycles_terminate(self):
        def node(identifier, parent):
            return {"key": identifier, "term": "", "properties": {
                RDF_TYPE: [{"kind": "iri", "value": OWL_CLASS}],
                RDFS + "subClassOf": [{"kind": "reference", "value": parent}]}}
        vocabulary = Vocabulary({"schema_version": 3, "nodes": [node("a", "b"), node("b", "a")]})
        self.assertEqual([t.key for t in vocabulary.ancestors("a")], ["b"])
        self.assertEqual([t.key for t in vocabulary.descendants("a")], ["b"])


if __name__ == "__main__":
    unittest.main()
