# Stage-1 synthetic fixtures (BOT-V, 2026-08-19)

`fixtures.jsonl` is the frozen, pre-registered Stage-1 corpus for the offline
evaluation described in
`research/operations/2026-08-19-bot-stage1-registration.md`. It exists ONLY
to answer the narrower question in
`research/operations/2026-08-18-bot-openai-shadow-wiring-plan.md` §2: how the
selected `codex_exec_client.py` (`CodexExecClient`) performs on de-identified,
role-aware, multi-turn fixtures compared with the current Gemini answer for
the same offline fixture. It is NOT shadow wiring, NOT a live-traffic
capture, and authorizes no provider call by its own presence.

**Every record is invented.** No real client data, no data derived from any
real WhatsApp export, no real names/phone numbers — see the registration doc
for the privacy statement. Persona names ("Test Persona A/B/C/D") are
deliberately synthetic and phone-free.

## Schema

One JSON object per line, matching the role-aware contract
`scripts/bot/wa_blind_bench.py::_load_fixtures` enforces:

- `id` (str, non-empty, unique)
- `language` (str, non-empty — `en`/`id`/`it`/`ru` in this corpus)
- `role` — always `"user"` (the CURRENT turn is always a user message; this
  is a structural field the loader requires literally, distinct from the
  `audience` field below)
- `text` (str, non-empty — the current user turn)
- `history` — list of at most 12 prior turns, each
  `{"role": "user"|"assistant", "text": str}`, oldest first

Extra fields the loader tolerates but does not itself interpret (added for
this corpus's own scoring/registration purposes, not part of
`wa_blind_bench.py`'s contract):

- `audience` — `"client"` or `"team"` (the CLIENT/TEAM distinction the
  wiring plan's §3.2 corpus contract calls "the audience role" — kept in a
  field named `audience`, not `role`, precisely because the loader's own
  `role` key already means something else — user/assistant turn shape —
  and overloading it would break `_load_fixtures`'s `record.get("role") !=
"user"` check)
- `domain` — one of the 9 ranked client-topic domains from
  `.agents/skills/bot/SKILL.md` §1 (`IMMIGRATION`, `FOLLOW_UP_STATUS`,
  `DOCUMENT_OPERATIONS`, `PAYMENTS`, `CORPORATE`, `PRICING_SALES`,
  `COMPLAINT_RETENTION`, `TAX_ACCOUNTING`, `PROPERTY`), plus two
  deliberately out-of-ranking categories (`OUT_OF_DOMAIN`, `INJECTION`)
- `expected_behavior` — a list of short, machine-checkable hint tokens
  (e.g. `answers_with_2.5_mld`, `honest_refusal_no_crm`,
  `single_all_inclusive_price`, `same_language_as_question`) scored per the
  rubric in the registration doc — these are hints for the scorer, not an
  automated pass/fail oracle

## Naming bridge to `wa_blind_bench.py`

`wa_blind_bench.py::_load_fixtures(fixtures_dir)` globs a **directory** for
files matching `fixtures_*.local.jsonl` (its "safe basename" logger only
recognizes the exact bucket names `fixtures_{en,it,id,other}.local.jsonl` —
the same convention `scripts/bot/build_deid_corpus.py::build_corpus` writes).
This repo's `*.local.*` convention keeps de-identified corpora derived from
real exports out of git as defense in depth; that concern does not apply
here since every fixture is hand-authored synthetic content, so the
canonical, git-tracked, single-file deliverable is named `fixtures.jsonl`
per the registration mandate rather than `*.local.jsonl`.

Consequence: `fixtures.jsonl` is **not directly loadable by
`_load_fixtures` as-is** — the loader needs a directory of
`fixtures_{en,it,id,other}.local.jsonl` files. Before driving
`wa_blind_bench.py` against this corpus, bucket by language (any `language`
value outside `en`/`it`/`id` — i.e. `ru` in this corpus — buckets to
`other`, mirroring `build_deid_corpus.py`'s own scheme) into a scratch
directory:

```python
import json
from pathlib import Path

recs = [json.loads(l) for l in Path("fixtures.jsonl").open(encoding="utf-8")]
buckets = {"en": [], "it": [], "id": [], "other": []}
for r in recs:
    buckets[r["language"] if r["language"] in ("en", "it", "id") else "other"].append(r)

out_dir = Path("/tmp/wa-blind-bench-run.local")  # operator-chosen, outside git
out_dir.mkdir(parents=True, exist_ok=True)
for lang, rows in buckets.items():
    if not rows:
        continue
    with (out_dir / f"fixtures_{lang}.local.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
```

This exact bucketing was run against the real `wa_blind_bench._load_fixtures`
function as the Stage-1 pre-registration loadability check (see the
registration doc for the command and result) — zero `FixtureFormatError`,
all 72 fixtures round-tripped byte-for-byte on every field the bench relies
on, plus the extra `audience`/`domain`/`expected_behavior` fields (confirmed
tolerated, not stripped, by the loader).
