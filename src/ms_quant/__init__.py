"""Offline access to the bundled quantification ontology."""

from functools import lru_cache
from importlib.resources import files
import json

from .vocabulary import AmbiguousTermError, Term, Vocabulary

__version__ = "0.1.0"
__all__ = ["AmbiguousTermError", "Term", "Vocabulary", "get_term", "get_node",
           "search", "terms", "roots", "children", "ancestors", "descendants"]


@lru_cache(maxsize=1)
def _default() -> Vocabulary:
    data = files(__package__).joinpath("data/ontology.json").read_text(encoding="utf-8")
    return Vocabulary(json.loads(data))


def get_term(identifier: str | None = None, *, name: str | None = None) -> Term:
    return _default().get_term(identifier, name=name)


def get_node(identifier: str) -> dict:
    return _default().get_node(identifier)


def terms(*, classes_only: bool = False) -> list[Term]:
    return _default().terms(classes_only=classes_only)


def search(query: str, *, classes_only: bool = False) -> list[Term]:
    return _default().search(query, classes_only=classes_only)


def roots() -> list[Term]:
    return _default().roots()


def children(identifier: str) -> list[Term]:
    return _default().children(identifier)


def ancestors(identifier: str) -> list[Term]:
    return _default().ancestors(identifier)


def descendants(identifier: str) -> list[Term]:
    return _default().descendants(identifier)
