from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

_FILE = "preferences.json"
_SLUG_STRIP = re.compile(r"[^a-z0-9]+")
_MAX_CUSTOM = 12
_MAX_LABEL = 48

EN = "en"
PT = "pt-BR"


@dataclass(frozen=True)
class Area:
    slug: str
    en: str
    pt: str
    hint: str

    def label(self, language: str) -> str:
        return self.pt if language == PT else self.en


BUILTIN: tuple[Area, ...] = (
    Area(
        "architecture",
        "Architecture",
        "Arquitetura",
        "how a system is structured — boundaries, coupling, data flow, and the "
        "trade-off that made one design win over another",
    ),
    Area(
        "debugging",
        "Debugging",
        "Depuração",
        "finding the true cause of a failure — what the symptom hid, and the "
        "evidence that settled it",
    ),
    Area(
        "infra",
        "Infrastructure & deploy",
        "Infra e deploy",
        "shipping and running software — builds, containers, CI, servers, "
        "rollbacks, and what broke in production",
    ),
    Area(
        "data",
        "Data",
        "Dados",
        "schemas, queries, migrations and pipelines — how stored data is shaped "
        "and what that shape cost later",
    ),
    Area(
        "product",
        "Product & UX",
        "Produto e UX",
        "what to build and how it should behave for the person using it",
    ),
    Area(
        "process",
        "Process & team",
        "Processo e time",
        "how work is organised — reviews, planning, conventions, and the way "
        "people coordinate",
    ),
    Area(
        "tooling",
        "Tooling",
        "Ferramentas",
        "editors, CLIs, automation and the configuration that makes them behave",
    ),
)

_BY_SLUG = {area.slug: area for area in BUILTIN}


def slugify(label: str) -> str:
    return _SLUG_STRIP.sub("-", label.lower()).strip("-")


@dataclass(frozen=True)
class Focus:
    chosen: tuple[str, ...] = ()
    custom: tuple[str, ...] = ()

    @property
    def everything(self) -> bool:
        return not self.chosen and not self.custom

    def areas(self) -> tuple[Area, ...]:
        picked = [_BY_SLUG[slug] for slug in self.chosen if slug in _BY_SLUG]
        made = [Area(slugify(text), text, text, text) for text in self.custom]
        return tuple(picked + made)

    def hints(self) -> tuple[str, ...]:
        return tuple(area.hint for area in self.areas())

    def to_json(self) -> str:
        return json.dumps(
            {"chosen": list(self.chosen), "custom": list(self.custom)},
            ensure_ascii=False,
            indent=1,
            sort_keys=True,
        )

    @classmethod
    def from_json(cls, raw: str) -> "Focus":
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise TypeError("focus file is not an object")
        return cls.of(payload.get("chosen"), payload.get("custom"))

    @classmethod
    def of(cls, chosen: object, custom: object) -> "Focus":
        return cls(chosen=_known(chosen), custom=_free_text(custom))


def _known(values: object) -> tuple[str, ...]:
    if not isinstance(values, list):
        return ()
    kept: list[str] = []
    for value in values:
        slug = str(value).strip()
        if slug in _BY_SLUG and slug not in kept:
            kept.append(slug)
    return tuple(kept)


def _free_text(values: object) -> tuple[str, ...]:
    if not isinstance(values, list):
        return ()
    kept: list[str] = []
    for value in values:
        label = " ".join(str(value).split())[:_MAX_LABEL]
        if label and slugify(label) and label not in kept:
            kept.append(label)
    return tuple(kept[:_MAX_CUSTOM])


@dataclass(frozen=True)
class Preferences:
    focus: Focus = Focus()
    note_language: str = ""

    def to_json(self) -> str:
        return json.dumps(
            {
                "chosen": list(self.focus.chosen),
                "custom": list(self.focus.custom),
                "note_language": self.note_language,
            },
            ensure_ascii=False,
            indent=1,
            sort_keys=True,
        )

    @classmethod
    def from_json(cls, raw: str) -> "Preferences":
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise TypeError("preferences file is not an object")
        return cls(
            focus=Focus.of(payload.get("chosen"), payload.get("custom")),
            note_language=str(payload.get("note_language") or ""),
        )


def load(config_dir: Path) -> Preferences:
    try:
        return Preferences.from_json((config_dir / _FILE).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return Preferences()


def save(config_dir: Path, preferences: Preferences) -> Path:
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / _FILE
    tmp = path.with_suffix(".tmp")
    tmp.write_text(preferences.to_json(), encoding="utf-8")
    tmp.replace(path)
    return path
