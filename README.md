# E.V Agent

Your coding agents solve the same problem twice because nothing survives the
session. E.V Agent reads the transcripts Claude Code and Codex already leave on
disk, keeps the few that contain a real lesson, and drafts them as notes you
review before they enter your knowledge base.

It never sends your sessions anywhere. The model runs on your machine.

```
$ ev scan
Scanning 118 transcripts (nothing leaves this machine)

  QUARANTINE  claude:8a3f21c9    47 hits  ~/.claude/projects/-home-daviparma/8a3f21c9.jsonl
              residue: opaque:kBfzsj9C...
  redacted    codex:019e2ce5     31 hits  ~/.codex/sessions/2026/05/15/rollout-...jsonl

  118 transcripts
  33 contained secrets (redacted locally)
  1 would be quarantined — never sent to any model
  14 carry a lesson worth extracting

$ ev run --days 7
7 to consider · 111 cached · model qwen3:4b

  wrote        pin-the-lockfile-before-deploying.md
  wrote        check-certificate-fingerprint-before-blaming-credentials.md

  2 candidates in ~/Documentos/Obsidian Vault/AI Brain/Skills Brain/_inbox
  0 quarantined · 5 without a lesson

$ ev promote pin-the-lockfile-before-deploying
promoted → ~/Documentos/Obsidian Vault/AI Brain/Skills Brain/pin-the-lockfile-before-deploying.md
```

## Why it works this way

**Transcripts are credential dumps.** Every file your agent reads lands in the
transcript verbatim — `.env` files, PEM blocks, tokens pasted into chat. On the
machine this was built for, 28% of transcripts contained something
credential-shaped. Any design that ships them to a hosted model is a leak
waiting to happen, and the free tiers are the ones that train on your prompts.

So the pipeline is built inside out:

```
transcript  →  distil  →  scrub  →  verify  →  local model  →  candidate note
                 │          │         │                            │
        drop file contents  │    fail closed:                 you review
        drop thinking       │    residue ⇒ quarantine,        before it
        keep intent,   redact known      never sent           counts
        errors, tools  secret shapes
```

**Distil before you scrub.** Dropping tool *results* removes most of the secret
surface at the source, because that is where read files live. It also takes
103 MB of transcripts down to a few megabytes — which is what makes a small
local model viable in the first place.

**Fail closed.** After redaction, the text is re-read looking for anything that
still looks like a credential: entropy, known prefixes, assignment shapes. Any
residue and the session is quarantined rather than sent. Losing a session costs
nothing. Leaking a key costs a rotation.

**The model extracts; you judge.** A 4B model on CPU is good at filling a
template and bad at deciding what matters. So it never decides. Everything
lands in `_inbox` and becomes real knowledge only when you promote it.

## Install

Requires Python 3.11+ and [Ollama](https://ollama.com).

```bash
git clone https://github.com/nasaske/ev-agent
cd ev-agent
pip install -e .

ollama pull qwen3:4b
```

There are no runtime dependencies. The whole thing is the standard library.

## Use

| Command | What it does |
|---|---|
| `ev scan` | Inventory transcripts and secret exposure. Local only, never calls a model. |
| `ev run` | Distil, scrub and draft candidates into the inbox. |
| `ev run --dry-run` | Show what would be sent, without sending it. |
| `ev list` | Candidates awaiting review. |
| `ev promote <slug>` | Move a reviewed candidate into the knowledge base. |
| `ev status` | Paths, model reachability, ledger. |

Useful flags: `--days N` to limit by age, `--limit N` to stop early, `--force`
to ignore the cache.

## Configuration

Everything is an environment variable with a working default.

| Variable | Default |
|---|---|
| `EV_VAULT` | `~/Documentos/Obsidian Vault` |
| `EV_SKILLS_DIR` | `$EV_VAULT/AI Brain/Skills Brain` |
| `EV_INBOX` | `$EV_SKILLS_DIR/_inbox` |
| `EV_CLAUDE_PROJECTS` | `~/.claude/projects` |
| `EV_CODEX_SESSIONS` | `~/.codex/sessions` |
| `EV_MODEL` | `qwen3:4b` |
| `EV_OLLAMA_URL` | `http://127.0.0.1:11434` |
| `EV_MAX_DIGEST_CHARS` | `12000` |
| `EV_CACHE` | `~/.cache/ev-agent` |

## Efficiency

The first run is the expensive one; every run after it is nearly free.

- Transcripts stream line by line — a 16 MB session never lands in memory.
- The ledger keys on `(size, mtime)`, so unchanged sessions are skipped with a
  single `stat` call and are never parsed, let alone sent to a model.
- Sessions without an error or a user correction are dropped before the model
  is involved. On a real corpus that is most of them.
- The digest is budgeted: intent and failures get 75% of the character
  allowance, trace and conclusions share the rest.
- Every request sets `keep_alive: 0`, so the model unloads instead of squatting
  in RAM for five minutes after a run.

## Running the tests

```bash
python -m unittest discover -s tests -v
```

The scrubber suite is the one that matters. It asserts that known secret
shapes never survive, that ordinary prose and session UUIDs are left alone,
and that anything unexplained trips the fail-closed check.

## License

MIT
