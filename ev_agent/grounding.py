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
_DEFAULT_FLOOR = 0.40


@dataclass(frozen=True)
class Grounding:
    checked: tuple[str, ...]
    found: tuple[str, ...]

    @property
    def share(self) -> float:
        if not self.checked:
            return 1.0
        return len(self.found) / len(self.checked)

    @property
    def missing(self) -> tuple[str, ...]:
        return tuple(term for term in self.checked if term not in self.found)


def distinctive_terms(text: str) -> list[str]:
    seen: list[str] = []
    for match in _TOKEN.finditer(text):
        token = match.group(0)
        lowered = token.lower()
        if lowered in _GENERIC or lowered in seen:
            continue
        seen.append(lowered)
    return seen


def check(claim: str, source: str) -> Grounding:
    haystack = source.lower()
    terms = distinctive_terms(claim)
    found = tuple(term for term in terms if term in haystack)
    return Grounding(checked=tuple(terms), found=found)


def is_grounded(claim: str, source: str, floor: float = _DEFAULT_FLOOR) -> bool:
    grounding = check(claim, source)
    if len(grounding.checked) < _MIN_TOKENS:
        return True
    return grounding.share >= floor
