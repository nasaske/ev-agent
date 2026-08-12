from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Iterable

PLACEHOLDER = "[redacted:{kind}]"

_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "private-key",
        re.compile(
            r"-----BEGIN[ A-Z]*PRIVATE KEY-----.*?-----END[ A-Z]*PRIVATE KEY-----",
            re.DOTALL,
        ),
    ),
    (
        "certificate",
        re.compile(r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", re.DOTALL),
    ),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("github-token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{16,}|github_pat_[A-Za-z0-9_]{20,})")),
    ("openrouter-key", re.compile(r"\bsk-or-v[0-9]-[A-Za-z0-9]{32,}")),
    ("openai-key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}")),
    ("anthropic-key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}")),
    ("slack-token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("aws-key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("google-key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("google-oauth", re.compile(r"\bya29\.[0-9A-Za-z_-]{20,}")),
    ("bearer", re.compile(r"(?i)\b(?:authorization\s*:\s*)?bearer\s+[A-Za-z0-9._~+/=-]{16,}")),
    ("basic-auth", re.compile(r"(?i)\bbasic\s+[A-Za-z0-9+/=]{16,}")),
    ("url-credentials", re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s/@:]+:[^\s/@]+@")),
    (
        "assigned-secret",
        re.compile(
            r"""(?ix)
            \b(
                (?:client|api|secret|access|refresh|private|auth|session|encryption)
                [_-]?
                (?:secret|key|token|id)
              | secret | token | password | passwd | pwd | passphrase | key
              | credential s? | authorization
            )
            \b \s* (?:[:=]|=>) \s*
            (["']?)
            ([^\s"',;}}\)]{8,})
            \2
            """
        ),
    ),
    ("cnpj", re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")),
    ("cpf", re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")),
)

_CANDIDATE = re.compile(r"\b[A-Za-z0-9+/_=-]{24,}\b")
_PLACEHOLDER_MATCH = re.compile(r"\[redacted:[a-z-]+\]")
_UUID = re.compile(r"\A[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z", re.I)
_HEX = re.compile(r"\A[0-9a-f]+\Z", re.I)

_ALLOWLIST = frozenset(
    {
        "requestid",
        "toolusetoolu",
        "application/json",
        "text/markdown",
    }
)

_ENTROPY_FLOOR = 3.6

_FORMAT_ONLY_RULES = frozenset({"cpf", "cnpj"})

_SEPARATORS = re.compile(r"[_.-]")
_PATH_CHARS = ("/", "\\")
_CONTENT_DIGEST_LENGTHS = frozenset({40, 64})
_KEYLIKE_HEX_LENGTH = 32


def _looks_like_a_path(token: str) -> bool:
    return any(char in token for char in _PATH_CHARS)


def _is_content_digest(token: str) -> bool:
    return _HEX.match(token) is not None and len(token) in _CONTENT_DIGEST_LENGTHS


def _looks_like_an_identifier(token: str) -> bool:
    segments = [segment for segment in _SEPARATORS.split(token) if segment]
    if len(segments) < 2:
        return False
    return all(segment.isalpha() or segment.isdigit() for segment in segments)


def _looks_random(token: str) -> bool:
    return any(char.isdigit() for char in token) and any(char.isalpha() for char in token)


def _shannon(value: str) -> float:
    if not value:
        return 0.0
    counts: dict[str, int] = {}
    for char in value:
        counts[char] = counts.get(char, 0) + 1
    size = len(value)
    return -sum((n / size) * math.log2(n / size) for n in counts.values())


def _is_opaque(token: str) -> bool:
    if token.lower() in _ALLOWLIST:
        return False
    if _UUID.match(token):
        return False
    if _looks_like_a_path(token):
        return False
    if _is_content_digest(token):
        return False
    if _HEX.match(token) and len(token) == _KEYLIKE_HEX_LENGTH:
        return True
    if _looks_like_an_identifier(token):
        return False
    if not _looks_random(token):
        return False
    return _shannon(token) >= _ENTROPY_FLOOR


@dataclass(frozen=True)
class ScrubResult:
    text: str
    hits: tuple[str, ...]
    residue: tuple[str, ...]

    @property
    def safe(self) -> bool:
        return not self.residue


def scrub(text: str) -> ScrubResult:
    hits: list[str] = []
    cleaned = text

    for kind, pattern in _RULES:
        def _replace(match: re.Match[str], _kind: str = kind) -> str:
            hits.append(_kind)
            if _kind == "assigned-secret":
                return f"{match.group(1)}={PLACEHOLDER.format(kind=_kind)}"
            return PLACEHOLDER.format(kind=_kind)

        cleaned = pattern.sub(_replace, cleaned)

    cleaned, entropy_hits = _sweep_entropy(cleaned)
    hits.extend(entropy_hits)

    return ScrubResult(text=cleaned, hits=tuple(hits), residue=tuple(verify(cleaned)))


def _sweep_entropy(text: str) -> tuple[str, list[str]]:
    hits: list[str] = []

    def _replace(match: re.Match[str]) -> str:
        token = match.group(0)
        if not _is_opaque(token):
            return token
        hits.append("high-entropy")
        return PLACEHOLDER.format(kind="high-entropy")

    return _CANDIDATE.sub(_replace, text), hits


def verify(text: str) -> list[str]:
    residue: list[str] = []
    text = _PLACEHOLDER_MATCH.sub(" ", text)
    for kind, pattern in _RULES:
        if kind in _FORMAT_ONLY_RULES:
            continue
        if pattern.search(text):
            residue.append(kind)
    for match in _CANDIDATE.finditer(text):
        token = match.group(0)
        if token.startswith("[redacted:"):
            continue
        if _is_opaque(token):
            residue.append(f"opaque:{token[:8]}...")
    return residue


def scrub_all(chunks: Iterable[str]) -> ScrubResult:
    return scrub("\n".join(chunks))
