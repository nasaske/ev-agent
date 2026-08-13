from __future__ import annotations

from .focus import EN, PT

_STRINGS: dict[str, dict[str, str]] = {
    "title": {EN: "E.V AGENT", PT: "E.V AGENT"},
    "tagline": {
        EN: "Sessions in, reviewed knowledge out. Nothing leaves this machine.",
        PT: "Sessões entram, conhecimento revisado sai. Nada sai desta máquina.",
    },
    "fig_inbox": {EN: "awaiting review", PT: "para revisar"},
    "preferences": {EN: "Preferences", PT: "Preferências"},
    "focus_lede": {
        EN: "Tick what you want kept. This is not only about software — add any "
            "subject you take notes on, and the agent will look for lessons in it.",
        PT: "Marque o que você quer guardar. Isto não é só sobre software — "
            "adicione qualquer assunto sobre o qual você anota, e o agente "
            "procura lições nele.",
    },
    "working": {EN: "working", PT: "trabalhando"},
    "idle": {EN: "idle", PT: "parado"},
    "of": {EN: "of", PT: "de"},
    "queue": {EN: "queue", PT: "fila"},
    "run_drain": {EN: "run: ev drain", PT: "rode: ev drain"},
    "nothing_yet": {EN: "nothing run yet", PT: "nada rodado ainda"},
    "stage_reading": {EN: "read", PT: "ler"},
    "stage_scrubbing": {EN: "scrub", PT: "limpar"},
    "stage_weighing": {EN: "weigh", PT: "pesar"},
    "stage_asking": {EN: "model", PT: "modelo"},
    "stage_writing": {EN: "write", PT: "escrever"},
    "specificity": {EN: "spec", PT: "espec"},
    "recent": {EN: "recent", PT: "recentes"},
    "focus": {EN: "What the agent looks for", PT: "O que o agente procura"},
    "focus_everything": {
        EN: "Nothing selected — every kind of lesson is kept.",
        PT: "Nada marcado — toda lição é mantida.",
    },
    "focus_saved": {EN: "saved", PT: "salvo"},
    "add_your_own": {EN: "add your own", PT: "adicionar o seu"},
    "add": {EN: "Add", PT: "Adicionar"},
    "remove": {EN: "remove", PT: "remover"},
    "note_language": {EN: "Notes written in", PT: "Notas escritas em"},
    "interface_language": {EN: "Interface", PT: "Interface"},
    "outcome_written": {EN: "written", PT: "escritas"},
    "outcome_quarantined": {EN: "quarantined", PT: "quarentena"},
    "outcome_routine": {EN: "routine", PT: "rotina"},
    "outcome_ungrounded": {EN: "ungrounded", PT: "sem lastro"},
    "outcome_no-work": {EN: "no work", PT: "sem trabalho"},
    "outcome_reworked": {EN: "reworked", PT: "retrabalhada"},
    "outcome_model-skip": {EN: "skipped", PT: "pulada"},
    "outcome_failed": {EN: "failed", PT: "falhou"},
    "local_only": {
        EN: "Local only. Nothing on this page has left your machine.",
        PT: "Só local. Nada nesta página saiu da sua máquina.",
    },
}

_LANGUAGES = (EN, PT)

NOTE_LANGUAGES: dict[str, str] = {
    EN: "English",
    PT: "Brazilian Portuguese",
}


def normalise(language: str) -> str:
    wanted = (language or "").strip().lower()
    if wanted.startswith("pt"):
        return PT
    return EN


def translate(key: str, language: str) -> str:
    entry = _STRINGS.get(key)
    if not entry:
        return key
    return entry.get(normalise(language)) or entry[EN]


def table(language: str) -> dict[str, str]:
    return {key: translate(key, language) for key in _STRINGS}


def note_language(language: str) -> str:
    return NOTE_LANGUAGES[normalise(language)]


def languages() -> tuple[str, ...]:
    return _LANGUAGES
