"""Map unambiguous class names against an explicitly supplied PSI-MS OBO file."""

import argparse
from collections import Counter, defaultdict
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ms_quant import Vocabulary

CV_URL = "https://raw.githubusercontent.com/HUPO-PSI/psi-ms-CV/master/psi-ms-core.obo"
POLICY = (
    "Unique active PSI-MS preferred-name or EXACT-synonym match to a local class "
    "label or exact synonym, ignoring case, spacing and punctuation. Related "
    "references are not equivalence mappings. Nonclass entries are left unassigned. "
    "Existing nonempty assignments are preserved."
)


def parse_obo(text):
    records = {}
    stanza = None
    record = defaultdict(list)
    for line in [*text.splitlines(), "[End]"]:
        if line.startswith("["):
            if stanza == "[Term]" and record.get("id"):
                records[record["id"][0]] = dict(record)
            stanza, record = line.strip(), defaultdict(list)
        elif stanza == "[Term]" and ": " in line:
            field, value = line.split(": ", 1)
            record[field].append(value)
    return records


def normalize(text):
    return re.sub(r"[^a-z0-9]", "", text.casefold())


def map_document(document, raw):
    text = raw.decode("utf-8")
    cv = parse_obo(text)
    if not cv:
        raise ValueError("No [Term] records found in CV")
    version = re.search(r"^data-version: (.+)$", text, re.M)
    source = {
        "name": "PSI-MS", "version": version[1].strip() if version else "",
        "url": CV_URL, "sha256": hashlib.sha256(raw).hexdigest(),
        "checked_on": date.today().isoformat(),
    }
    index = defaultdict(set)
    for accession, fields in cv.items():
        if not accession.startswith("MS:") or fields.get("is_obsolete") == ["true"]:
            continue
        names = list(fields.get("name", []))
        for synonym in fields.get("synonym", []):
            match = re.match(r'"(.*?)" EXACT ', synonym)
            if match:
                names.append(match[1])
        for name in names:
            if normalize(name):
                index[normalize(name)].add(accession)

    existing = Counter(n["term"] for n in document["nodes"] if n["term"])
    entries = []
    proposals = Counter()
    for node in document["nodes"]:
        properties = node["properties"]
        if not any(v["value"] == "owl:Class" for v in properties.get("rdf:type", [])):
            continue
        names = [v["value"] for p in ("rdfs:label", "has_exact_synonym")
                 for v in properties.get(p, []) if v["kind"] == "literal"]
        candidates = sorted(set().union(*(index[normalize(name)] for name in names)))
        suggested = candidates[0] if len(candidates) == 1 else ""
        if suggested and not node["term"]:
            proposals[suggested] += 1
        references = [v["value"] for v in properties.get("rdfs:seeAlso", [])
                      if re.fullmatch(r"MS:\d+", v["value"])]
        entries.append((node, candidates, suggested, references))

    report = []
    for node, candidates, suggested, references in entries:
        if node["term"]:
            status = "exact_name_match" if node["term"] == suggested else "existing_assignment"
        elif suggested and proposals[suggested] == 1 and not existing[suggested]:
            node["term"] = suggested
            status = "exact_name_match"
        else:
            status = "ambiguous" if candidates else "unresolved"
        assigned = cv.get(node["term"])
        report.append({
            "key": node["key"], "term": node["term"], "status": status,
            "candidates": candidates,
            "assigned_term_active": bool(assigned and assigned.get("is_obsolete") != ["true"]),
            "existing_cv_references": [
                {"term": r, "exists": r in cv, "name": cv.get(r, {}).get("name", [""])[0],
                 "obsolete": cv.get(r, {}).get("is_obsolete") == ["true"]}
                for r in references],
        })
    document["cv_source"] = source
    Vocabulary(document)
    return {"cv_source": source, "policy": POLICY,
            "summary": dict(Counter(r["status"] for r in report)), "entries": report}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cv", type=Path, help="Local psi-ms-core.obo file")
    args = parser.parse_args()
    source = ROOT / "output/ontology.json"
    document = json.loads(source.read_text(encoding="utf-8"))
    report = map_document(document, args.cv.read_bytes())
    for path, data in ((source, document), (ROOT / "output/cv_mapping.json", report)):
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(report["summary"])


if __name__ == "__main__":
    main()
