<p align="center">
  <img src="assets/ev-banner.svg" alt="E.V Agent — sessions in, reviewed knowledge out, nothing leaves the machine" width="100%">
</p>

Your coding agents solve the same problem twice because nothing survives the
session. E.V Agent reads the transcripts Claude Code and Codex already leave on
disk, keeps the few that contain a real lesson, and drafts them as notes you
review before they enter your knowledge base.

It never sends your sessions anywhere. The model runs on your machine.

<p align="center">
  <img src="assets/ev-scan.svg" alt="ev scan on a real corpus: 381 transcripts, 160 contained secrets, 4 quarantined, 248 carry a lesson" width="100%">
</p>

```bash
$ ev run --days 7
  wrote  pin-the-lockfile-before-deploying.md
  wrote  check-certificate-fingerprint-before-blaming-credentials.md

$ ev promote pin-the-lockfile-before-deploying
promoted → ~/Documentos/Obsidian Vault/AI Brain/Skills Brain/pin-the-lockfile-before-deploying.md
```

## Why it works this way

**Transcripts are credential dumps.** Every file your agent reads lands in the
transcript verbatim — `.env` files, PEM blocks, tokens pasted into chat. On the
corpus this was built against, 42% of transcripts contained something
credential-shaped, including the harness's own auth tokens. Any design that
ships them to a hosted model is a leak waiting to happen, and the free tiers are
the ones that train on your prompts.

So the pipeline is built inside out:

<p align="center">
  <img src="assets/ev-pipeline.svg" alt="Pipeline: transcript, distil, scrub, verify, local model, note — with secrets absorbed at scrub and residue diverted to quarantine" width="100%">
</p>

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

## What counts as worth keeping

Most sessions are not worth a note, and a tool that writes one for every
session is a tool you stop reading. Four gates run before the model is ever
called, cheapest first, and each one is plain code rather than a judgement
call handed to an LLM:

| Gate | Rejects |
|---|---|
| **Quarantine** | anything with credential residue after scrubbing |
| **Real work** | chat-only sessions: no edits and fewer than three tool calls |
| **Acceptance** | sessions you corrected, pushed back on, or where you refused an action |
| **Specificity** | routine work, measured against your own corpus |

Acceptance is read from the conversation, not guessed. Explicit praise
("perfeito", "funcionou", "that works") counts as approval; a correction
("na verdade", "ta errado", "actually") disqualifies the session even if
praise appeared earlier. A tool-use rejection is a refusal, not an error —
the distinction matters, because the same line in a transcript used to be
filed as a build failure.

Specificity is corpus-relative, and that is the point: it calibrates itself to
how much you already know. Terms are counted across every transcript you have,
so work that is routine *for you* scores low. Someone three weeks into their
first harness has a small, varied corpus and will see almost everything clear
the bar — which is correct, because at that stage almost everything is worth
writing down. Someone with a mature skill library sees most days filtered out.
The tool gets quieter as you get better without anyone tuning it.

Praise lowers the bar rather than bypassing it. A session you explicitly
approved clears at `EV_PRAISED_MIN_SPECIFICITY` (0.42) instead of
`EV_MIN_SPECIFICITY` (0.55), because saying "that worked" is direct evidence
of value and rarity is only a proxy for it.

Both floors are worth tuning: the score distribution is tight, so small changes
move a lot. On a 386-session corpus, 197 passed acceptance and 62 cleared
specificity.

## Watching it work

`ev drain` can spend minutes on a single session, so it reports what it is
doing rather than going quiet. `ev watch` renders the live state — no daemon,
no window, no dependency, just a file the run writes and the panel reads.

```
┌ E.V AGENT ────────────────────────────────────── ollama · qwen3:4b ┐
│                                                                    │
│ ● working   1 of 4   queue 3                                       │
│                                                                    │
│ claude:c74d6480   02:14                                            │
│ ◦ read  ◦ scrub  ◦ weigh  ● model  ◦ write   spec 0.65             │
│                                                                    │
│ 1 written                                                          │
│                                                                    │
│ recent                                                             │
│   written      reset-codex-sidebar-state.md                        │
│   routine      0.48 < 0.55                                         │
└────────────────────────────────────────────────────────────────────┘
```

Red marks what was stopped, blue marks what moved through — the same colour
grammar as the diagrams. `ev watch --once` prints a single frame, which is what
you want in a status bar or a cron report.

## Running it automatically

The point is not to remember to run it. A `Stop` hook queues each finished
session; a drain processes the queue when the machine is free.

```json
{
  "hooks": {
    "Stop": [{
      "matcher": "*",
      "hooks": [{
        "type": "command",
        "command": "/path/to/ev-agent/hooks/ev-enqueue.sh",
        "timeout": 5,
        "async": true
      }]
    }]
  }
}
```

Queueing is instant and never blocks the end of a session — the hook exits 0
even on malformed input. Draining is where the time goes, so run it when you
are not using the machine:

```bash
ev drain              # process everything queued
ev drain --limit 3    # or just a few
```

A lock file keeps two drains from running at once, which on a laptop means two
model loads competing for the same RAM. Because nothing is waiting on the
result, a slow local model stops being a problem: a queue that takes half an
hour overnight costs nothing.

Codex has no hook system, so Codex sessions are picked up by `ev run` in batch.

## The scrubber was tuned on real data

A redaction rule that fires on everything is the same as no rule at all — you
lose the ability to tell exposure from noise. The first version flagged 100% of
transcripts. Three rounds against a real corpus brought it down to something
that means something:

<p align="center">
  <img src="assets/ev-calibration.svg" alt="Calibration: false positives fell from 100% to 62% to 42% over three rounds" width="100%">
</p>

The remaining hits are genuine — Fernet tokens, OAuth refresh tokens, base64
keys — plus harmless over-redaction of things like Cloud Run hostnames. Over-
redacting a hostname costs a little context. Under-redacting a key costs a
rotation, so the bias is deliberate.

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
| `ev scan` | Inventory transcripts, secret exposure and specificity. Local only, never calls a model. |
| `ev run` | Process a batch of sessions. |
| `ev session <path>` | Process one transcript now. |
| `ev enqueue <path>` | Add a transcript to the queue. This is what the hook calls. |
| `ev drain` | Process the queue, one session at a time, under a lock. |
| `ev watch` | Live view of the agent working. `--once` prints one frame. |
| `ev index` | Rebuild the corpus vocabulary used for specificity. |
| `ev list` | Candidates awaiting review. |
| `ev promote <slug>` | Move a reviewed candidate into the knowledge base. |
| `ev status` | Backend, queue depth, ledger, specificity floor. |

Useful flags: `--days N` to limit by age, `--limit N` to stop early, `--force`
to ignore the cache, `--dry-run` to stop at the model boundary.

## Backends

Local by default. `EV_BACKEND=openrouter` sends the scrubbed digest to a hosted
model instead, for machines that cannot host one.

The same guarantees apply either way — distil, scrub, verify, quarantine happen
before any backend is chosen, which is what makes the choice safe to make. Two
rules are enforced in code rather than left to the operator: requests set
`provider: {"data_collection": "deny"}`, and a model ending in `:free` is
refused outright, because free tiers train on submitted prompts and that is the
exact thing this tool exists to prevent.

```bash
export OPENROUTER_API_KEY=...
EV_BACKEND=openrouter EV_OPENROUTER_MODEL=google/gemini-2.5-flash ev drain
```

### Choosing a model

Measured on one real 6,900-character digest, same prompt, same session:

| Model | Time | Wrote a reusable pattern? |
|---|---|---|
| `nvidia/nemotron-3-ultra-550b-a55b:free` | 13s | yes — generalised to any extension, named both SQLite stores |
| `nvidia/nemotron-3-nano-30b-a3b:free` | 9s | mostly |
| `openai/gpt-oss-20b:free` | 21s | mostly |
| `qwen3:4b` (local, CPU) | 8m 03s | partly |
| `qwen3:1.7b` (local, CPU) | 1m 03s | no — restated the case, and invented advice elsewhere |

The gap that matters is not speed, it is whether the PATTERN field generalises.
Small models restate what happened; the large ones state a rule you could apply
to a different extension next month. A 1.7B model on a laptop finishes every
time and is confidently wrong often enough to be a liability — one of its notes
claimed a shell prefix "avoids password prompts", which is the opposite of what
that prefix does.

Free endpoints are the fastest and the best here, and they cost your privacy:
OpenRouter files them under "Free model training", so `EV_ALLOW_FREE=1` flips
`data_collection` to `allow` and your scrubbed digests become training data.
That is a real trade, stated plainly rather than hidden behind a flag name.
Paid endpoints of similar quality run a few cents for a whole backlog.

## Configuration

Everything is an environment variable with a working default.

| Variable | Default |
|---|---|
| `EV_VAULT` | `~/Documentos/Obsidian Vault` |
| `EV_SKILLS_DIR` | `$EV_VAULT/AI Brain/Skills Brain` |
| `EV_INBOX` | `$EV_SKILLS_DIR/_inbox` |
| `EV_CLAUDE_PROJECTS` | `~/.claude/projects` |
| `EV_CODEX_SESSIONS` | `~/.codex/sessions` |
| `EV_BACKEND` | `ollama` |
| `EV_MODEL` | `qwen3:4b` |
| `EV_OLLAMA_URL` | `http://127.0.0.1:11434` |
| `EV_NUM_CTX` | `4096` |
| `EV_OPENROUTER_MODEL` | `google/gemini-2.5-flash` |
| `EV_MIN_SPECIFICITY` | `0.55` |
| `EV_PRAISED_MIN_SPECIFICITY` | `0.42` |
| `EV_COMMON_TERM_RATIO` | `0.04` |
| `EV_MAX_DIGEST_CHARS` | `8000` |
| `EV_TIMEOUT` | `600` |
| `EV_CACHE` | `~/.cache/ev-agent` |

## Efficiency

The first run is the expensive one; every run after it is nearly free.

- Transcripts stream line by line — a 16 MB session never lands in memory.
- The ledger keys on `(size, mtime)`, so unchanged sessions are skipped with a
  single `stat` call and are never parsed, let alone sent to a model.
- Four gates run before the model, cheapest first. On a 386-session corpus they
  reject 355 of them for free.
- The digest is budgeted: intent and fixed failures take 60% of the character
  allowance, the work trace and your responses share the rest.
- The model stays resident for the length of a run and is unloaded explicitly
  at the end. Reloading per session cost 15.8s each on the machine this was
  built on; holding it resident afterwards costs 3.9 GB.
- The corpus vocabulary is built once and cached. Rebuild with `ev index` when
  the corpus has grown a lot.

## Running the tests

```bash
python -m unittest discover -s tests -t .
```

The scrubber suite is the one that matters. It asserts that known secret
shapes never survive, that ordinary prose, file paths, camelCase names and git
SHAs are left alone, and that anything unexplained trips the fail-closed check.

## Design

The visual system is documented in
[design/ev-visual-philosophy.md](design/ev-visual-philosophy.md). Diagrams are
hand-written SVG with SMIL — no build step, no dependencies, same as the code.

## License

MIT
