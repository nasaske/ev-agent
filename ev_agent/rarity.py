from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

_INDEX_FILE = "vocabulary.json"
_TOKEN = re.compile(r"[a-z][a-z0-9_.:-]{3,}")
_MAX_TERMS_PER_SESSION = 400

_STOPWORDS = frozenset(
    """
    that this with from have been were will would could should about which their there
    they them then than when what where because while into over under after before
    session asked said user agent file files line lines code test tests error errors
    para pelo pela como mais isso esse essa aqui esta este isto nao sim mas por que
    com sem sobre entre depois antes quando onde porque tudo todo toda muito bem
    fazer feito faz vai vou ter tem tinha foi ser sendo estar esta pode posso
    """.split()
)


@dataclass(frozen=True)
class Vocabulary:
    documents: int
    frequencies: dict[str, int]

    def rarity_of(self, term: str) -> float:
        if self.documents <= 0:
            return 1.0
        return 1.0 - (self.frequencies.get(term, 0) / self.documents)

    def specificity(self, text: str, common_ratio: float = 0.04) -> float:
        terms = terms_of(text)
        if not terms:
            return 0.0
        ceiling = max(1, int(self.documents * common_ratio))
        rare = sum(1 for term in terms if self.frequencies.get(term, 0) <= ceiling)
        return rare / len(terms)

    def to_json(self) -> str:
        return json.dumps(
            {"documents": self.documents, "frequencies": self.frequencies},
            sort_keys=True,
        )

    @classmethod
    def from_json(cls, raw: str) -> "Vocabulary":
        payload = json.loads(raw)
        return cls(
            documents=int(payload.get("documents", 0)),
            frequencies=dict(payload.get("frequencies", {})),
        )


def terms_of(text: str) -> set[str]:
    found = {
        token
        for token in _TOKEN.findall(text.lower())
        if token not in _STOPWORDS and not token.startswith("[redacted")
    }
    if len(found) <= _MAX_TERMS_PER_SESSION:
        return found
    return set(sorted(found)[:_MAX_TERMS_PER_SESSION])


def build(texts: list[str]) -> Vocabulary:
    frequencies: Counter[str] = Counter()
    for text in texts:
        frequencies.update(terms_of(text))
    return Vocabulary(documents=len(texts), frequencies=dict(frequencies))


def load(cache_dir: Path) -> Vocabulary | None:
    path = cache_dir / _INDEX_FILE
    try:
        return Vocabulary.from_json(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def save(cache_dir: Path, vocabulary: Vocabulary) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / _INDEX_FILE
    tmp = path.with_suffix(".tmp")
    tmp.write_text(vocabulary.to_json(), encoding="utf-8")
    tmp.replace(path)
    return path
