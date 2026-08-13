from __future__ import annotations

import re
from dataclasses import dataclass

_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9_.:/-]{3,}")

_GENERIC = frozenset(
    """
    this that with from have been were will would could should about which their
    there they them then than when what where because while into over under after
    before session user agent file files line lines code test tests error errors
    command commands run running runs used using use make made need needs first
    then also more most some such only same other another both each every
    without within during through against between among across
    problem issue result results change changes changed fix fixed fixing
    ensure ensures ensuring avoid avoids prevent prevents stop stops
    """.split()
)

_MIN_TOKENS = 4
DEFAULT_FLOOR = 0.40

_MIN_IDENTIFIERS = 2
IDENTIFIERS = "identifiers"
PROSE = "prose"

_PUNCTUATION = "._:/-"
_INNER_CAPS = re.compile(r"[a-z][A-Z]")
_DIGIT = re.compile(r"\d")
_MIN_TERM = 4

_SUFFIXES = ("ing", "ions", "ment", "ion", "ers", "ed", "es", "ly", "er", "s")
_MIN_STEM = 4


@dataclass(frozen=True)
class Grounding:
    checked: tuple[str, ...]
    found: tuple[str, ...]
    basis: str = PROSE

    @property
    def share(self) -> float:
        if not self.checked:
            return 1.0
        return len(self.found) / len(self.checked)

    @property
    def missing(self) -> tuple[str, ...]:
        return tuple(term for term in self.checked if term not in self.found)


def _tokens(text: str) -> list[str]:
    seen: list[str] = []
    for match in _TOKEN.finditer(text):
        token = match.group(0).rstrip(_PUNCTUATION)
        if len(token) >= _MIN_TERM and token.lower() not in seen:
            seen.append(token.lower())
    return seen


def _is_identifier(token: str) -> bool:
    if token.isdigit():
        return False
    return (
        any(char in token for char in _PUNCTUATION)
        or _DIGIT.search(token) is not None
        or _INNER_CAPS.search(token) is not None
    )


def identifiers(text: str) -> list[str]:
    raw = [match.group(0).rstrip(_PUNCTUATION) for match in _TOKEN.finditer(text)]
    seen: list[str] = []
    for token in raw:
        if len(token) < _MIN_TERM or not _is_identifier(token):
            continue
        if token.lower() not in seen:
            seen.append(token.lower())
    return seen


def distinctive_terms(text: str) -> list[str]:
    return [token for token in _tokens(text) if token not in _GENERIC]


def _stem(token: str) -> str:
    if any(char in token for char in _PUNCTUATION):
        return token
    for suffix in _SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= _MIN_STEM:
            return token[: -len(suffix)]
    return token


def check(claim: str, source: str) -> Grounding:
    haystack = source.lower()

    named = identifiers(claim)
    if len(named) >= _MIN_IDENTIFIERS:
        found = tuple(term for term in named if term in haystack)
        return Grounding(checked=tuple(named), found=found, basis=IDENTIFIERS)

    terms = distinctive_terms(claim)
    found = tuple(term for term in terms if term in haystack or _stem(term) in haystack)
    return Grounding(checked=tuple(terms), found=found, basis=PROSE)


def is_grounded(claim: str, source: str, floor: float = DEFAULT_FLOOR) -> bool:
    grounding = check(claim, source)
    if len(grounding.checked) < _MIN_TOKENS and grounding.basis == PROSE:
        return True
    return grounding.share >= floor
