"""Validate the editable JSON and refresh the bundled release snapshot."""

from pathlib import Path
import json
import re
import shutil
import sys
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ms_quant import Vocabulary


def to_jsonld(document):
    prefixes = {
        "rdf:": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "rdfs:": "http://www.w3.org/2000/01/rdf-schema#",
        "owl:": "http://www.w3.org/2002/07/owl#",
        "xsd:": "http://www.w3.org/2001/XMLSchema#",
    }

    def expand(value):
        if value.startswith("_:"):
            return value
        for prefix, iri in prefixes.items():
            if value.startswith(prefix):
                return iri + value[len(prefix):]
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", value):
            return value
        return "urn:ms-quant:" + quote(value, safe="")

    graph = []
    for node in document["nodes"]:
        exported = {"@id": expand(node["key"])}
        for predicate, values in node["properties"].items():
            exported_values = []
            for value in values:
                if value["kind"] in ("reference", "iri", "blank"):
                    exported_value = {"@id": expand(value["value"])}
                else:
                    exported_value = {"@value": value["value"]}
                    if "datatype" in value:
                        exported_value["@type"] = expand(value["datatype"])
                    if "language" in value:
                        exported_value["@language"] = value["language"]
                exported_values.append(exported_value)
            exported[expand(predicate)] = exported_values
        if node["term"]:
            exported["urn:ms-quant:accession"] = [{"@value": node["term"]}]
        graph.append(exported)
    return graph


def main():
    source = ROOT / "output" / "ontology.json"
    vocabulary = Vocabulary.from_file(source)
    document = json.loads(source.read_text(encoding="utf-8"))
    (ROOT / "output" / "ontology.jsonld").write_text(
        json.dumps(to_jsonld(document), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    target = ROOT / "src" / "ms_quant" / "data" / "ontology.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    print(f"Bundled {len(vocabulary.terms())} named entries; {len(vocabulary.terms(classes_only=True))} classes.")


if __name__ == "__main__":
    main()
