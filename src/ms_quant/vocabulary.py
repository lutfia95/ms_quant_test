"""Read the ontology without fetching data or running an RDF reasoner."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

RDF_TYPE = "rdf:type"
RDFS = "rdfs:"
OWL_CLASS = "owl:Class"
DEFINITION = "definition"
SYNONYMS = ("has_synonym", "has_exact_synonym")


class AmbiguousTermError(LookupError):
    """A name refers to more than one ontology entry."""


@dataclass(frozen=True)
class Term:
    """A local vocabulary entry with an optional confirmed CV accession."""

    key: str
    term: str
    name: str
    labels: tuple[str, ...]
    definition: str | None
    xrefs: tuple[str, ...]
    synonyms: tuple[str, ...]
    types: tuple[str, ...]
    _properties_json: str

    @property
    def is_class(self) -> bool:
        return OWL_CLASS in self.types

    @property
    def properties(self) -> dict[str, Any]:
        """Properties using readable local references and standard RDF prefixes."""
        return json.loads(self._properties_json)


class Vocabulary:
    def __init__(self, document: dict[str, Any]):
        self.schema_version = document["schema_version"]
        if self.schema_version != 3:
            raise ValueError("Expected vocabulary schema version 3")
        self._nodes: dict[str, dict[str, Any]] = {}
        self._terms: dict[str, Term] = {}
        self._accessions: dict[str, str] = {}
        self._names: dict[str, set[str]] = {}
        self._children: dict[str, set[str]] = {}
        self._parents: dict[str, tuple[str, ...]] = {}
        for node in document["nodes"]:
            identifier = node["key"]
            if identifier in self._nodes:
                raise ValueError(f"Duplicate node key: {identifier}")
            self._nodes[identifier] = deepcopy(node)
            if identifier.startswith("_:"):
                continue
            accession = node.get("term", "")
            if not isinstance(accession, str) or accession != accession.strip():
                raise ValueError(f"term must be a trimmed string: {identifier}")
            properties = node["properties"]

            def values(predicate: str, kind: str | None = None) -> tuple[str, ...]:
                return tuple(v["value"] for v in properties.get(predicate, [])
                             if kind is None or v["kind"] == kind)

            labels = values(RDFS + "label", "literal")
            definitions = values(DEFINITION, "literal")
            entry = Term(
                key=identifier, term=accession,
                name=labels[0] if labels else identifier,
                labels=labels, definition=definitions[0] if definitions else None,
                xrefs=values(RDFS + "seeAlso"),
                synonyms=tuple(value for predicate in SYNONYMS for value in values(predicate, "literal")),
                types=values(RDF_TYPE, "iri"),
                _properties_json=json.dumps(properties),
            )
            self._terms[identifier] = entry
            self._parents[identifier] = values(RDFS + "subClassOf", "reference")
            if accession:
                if accession in self._accessions:
                    raise ValueError(f"Duplicate term accession: {accession}")
                self._accessions[accession] = identifier
            for label in labels:
                self._names.setdefault(label.casefold(), set()).add(identifier)
            for parent in self._parents[identifier]:
                if parent.startswith("_:"):
                    continue
                self._children.setdefault(parent, set()).add(identifier)
        for accession, identifier in self._accessions.items():
            if accession in self._terms and accession != identifier:
                raise ValueError(f"Accession collides with a local key: {accession}")
        for node in self._nodes.values():
            for values in node["properties"].values():
                for value in values:
                    if value["kind"] == "reference" and value["value"] not in self._nodes:
                        raise ValueError(f"Unknown local reference: {value['value']}")

    @classmethod
    def from_file(cls, path: str | Path) -> Vocabulary:
        with open(path, encoding="utf-8") as source:
            return cls(json.load(source))

    def get_term(self, identifier: str | None = None, *, name: str | None = None) -> Term:
        """Look up a local key/CV accession, or an exact case-insensitive label."""
        if (identifier is None) == (name is None):
            raise ValueError("Supply either an identifier or name, exclusively")
        if name is not None:
            matches = self._names.get(name.casefold(), set())
            if not matches:
                raise KeyError(f"Unknown term name: {name}")
            if len(matches) > 1:
                raise AmbiguousTermError(f"Ambiguous name {name!r}; use a local key: {sorted(matches)}")
            return self._terms[next(iter(matches))]
        key = self._accessions.get(identifier, identifier)
        try:
            return self._terms[key]
        except KeyError:
            raise KeyError(f"Unknown term identifier: {identifier}") from None

    def get_node(self, identifier: str) -> dict[str, Any]:
        """Read any local node, including an anonymous OWL restriction."""
        return deepcopy(self._nodes[identifier])

    def _sorted(self, identifiers) -> list[Term]:
        return sorted((self._terms[i] for i in identifiers if i in self._terms),
                      key=lambda t: (t.name.casefold(), t.key))

    def terms(self, *, classes_only: bool = False) -> list[Term]:
        return self._sorted(i for i, t in self._terms.items() if not classes_only or t.is_class)

    def search(self, query: str, *, classes_only: bool = False) -> list[Term]:
        """Case-insensitive substring search in identifiers, names, synonyms and definitions."""
        query = query.casefold()
        return [t for t in self.terms(classes_only=classes_only)
                if any(query in text.casefold() for text in
                       (t.key, t.term, *t.labels, *t.synonyms, t.definition or ""))]

    def roots(self) -> list[Term]:
        """Named classes without any asserted rdfs:subClassOf statement."""
        return self._sorted(t.key for t in self._terms.values()
                            if t.is_class and not t.properties.get(RDFS + "subClassOf"))

    def children(self, identifier: str) -> list[Term]:
        entry = self.get_term(identifier)
        return self._sorted(self._children.get(entry.key, ()))

    def _walk(self, identifier: str, *, upwards: bool) -> list[Term]:
        entry = self.get_term(identifier)
        seen = {entry.key}
        pending = [entry.key]
        found: set[str] = set()
        while pending:
            current = pending.pop()
            neighbors = (self._parents[current] if upwards
                         else self._children.get(current, ()))
            for neighbor in neighbors:
                if neighbor not in seen:
                    seen.add(neighbor)
                    if neighbor in self._terms:
                        found.add(neighbor)
                        pending.append(neighbor)
        return self._sorted(found)

    def ancestors(self, identifier: str) -> list[Term]:
        return self._walk(identifier, upwards=True)

    def descendants(self, identifier: str) -> list[Term]:
        return self._walk(identifier, upwards=False)
