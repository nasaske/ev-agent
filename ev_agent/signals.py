from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

APPROVAL = "approval"
REJECTION = "rejection"
CORRECTION = "correction"

_APPROVAL_PHRASES = (
    "perfeito",
    "isso mesmo",
    "era isso",
    "ficou bom",
    "ficou otimo",
    "ficou ótimo",
    "funcionou",
    "deu certo",
    "ta certo",
    "tá certo",
    "excelente",
    "muito bom",
    "valeu",
    "obrigado",
    "obrigada",
    "exatamente",
    "exactly",
    "that works",
    "it works",
    "works now",
    "looks good",
    "nice work",
    "thanks",
    "thank you",
)

_APPROVAL_TERSE = frozenset(
    {
        "isso",
        "boa",
        "show",
        "top",
        "otimo",
        "ótimo",
        "certo",
        "ok",
        "okay",
        "beleza",
        "massa",
        "perfect",
        "great",
        "good",
        "nice",
        "yes",
    }
)

_CORRECTION_PHRASES = (
    "na verdade",
    "mentira",
    "não é isso",
    "nao e isso",
    "nao é isso",
    "errado",
    "ta errado",
    "tá errado",
    "corrige",
    "corrija",
    "refaz",
    "refaça",
    "desfaz",
    "desfaça",
    "volta atras",
    "volta atrás",
    "nao era isso",
    "não era isso",
    "prefiro",
    "actually",
    "that's wrong",
    "thats wrong",
    "not what i",
    "revert",
    "undo that",
)

_TOOL_REJECTION_MARKERS = (
    "the user doesn't want to proceed",
    "the user doesn't want to take this action",
    "tool use was rejected",
    "user rejected",
)

_PROBE_COMMANDS = re.compile(
    r"\b(command -v|which |type -|test -|\[ -[fdez]|grep -q|pgrep|pidof|hash )",
    re.IGNORECASE,
)

_BENIGN_ERROR_TEXT = (
    "command not found",
    "no such file or directory",
    "not found",
    "no matches found",
    "nao encontrado",
    "não encontrado",
)

_EXIT_CODE = re.compile(r"\bexit code (\d+)", re.IGNORECASE)
_TERSE_LIMIT = 24


class ErrorKind(str, Enum):
    REAL = "real"
    PROBE = "probe"
    USER_REJECTION = "user-rejection"


@dataclass(frozen=True)
class Verdict:
    approvals: int
    corrections: int
    rejections: int

    @property
    def accepted(self) -> bool:
        return self.approvals > 0 and self.corrections == 0 and self.rejections == 0

    @property
    def refused(self) -> bool:
        return self.corrections > 0 or self.rejections > 0

    @property
    def label(self) -> str:
        if self.refused:
            return "reworked"
        if self.accepted:
            return "praised"
        return "unremarked"


def classify_error(text: str, command: str = "") -> ErrorKind:
    lowered = text[:600].lower()

    if any(marker in lowered for marker in _TOOL_REJECTION_MARKERS):
        return ErrorKind.USER_REJECTION

    if _PROBE_COMMANDS.search(command) or _PROBE_COMMANDS.search(lowered):
        return ErrorKind.PROBE

    if any(benign in lowered for benign in _BENIGN_ERROR_TEXT) and _is_low_exit(lowered):
        return ErrorKind.PROBE

    return ErrorKind.REAL


def _is_low_exit(lowered: str) -> bool:
    match = _EXIT_CODE.search(lowered)
    if not match:
        return True
    return int(match.group(1)) <= 4


def classify_user_message(text: str) -> str:
    stripped = " ".join(text.split())
    lowered = stripped.lower()

    if any(phrase in lowered for phrase in _CORRECTION_PHRASES):
        return CORRECTION

    if any(phrase in lowered for phrase in _APPROVAL_PHRASES):
        return APPROVAL

    if len(stripped) <= _TERSE_LIMIT:
        words = {word.strip(".,!;:") for word in lowered.split()}
        if words & _APPROVAL_TERSE:
            return APPROVAL

    return ""


def verdict_from(approvals: int, corrections: int, rejections: int) -> Verdict:
    return Verdict(approvals=approvals, corrections=corrections, rejections=rejections)
