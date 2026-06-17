# WhatsApp Corpus-Miner (NLM-grounded) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the v1 WhatsApp→NotebookLM corpus-miner: render direct WhatsApp chats from local Postgres into native Google Docs (zero@ Workspace) via direct Drive API, classify counterparts (exclude team/partner/group) using `whatsapp_contacts.contact_type`, and run a grounded prompt-master query per client producing a verbatim-cited recap.

**Architecture:** Three pure-Python modules under `scripts/wa_corpus/`, each independently testable. A `CounterpartClassifier` filters which pairs become Docs. A `ChatDocRenderer` renders a chat and writes/updates a native Google Doc via the Service-Account-with-DWD Drive API (gate-proven), then shares it with the NLM operator account. A `QueryRunner` adds/syncs the Doc as an NLM drive source and runs the fixed 6-section prompt-master, returning a recap with mandatory `cited_text`. All read-only against the CRM (recap never auto-writes; human-in-the-loop). GATE proven both PASS 2026-06-04.

**Tech Stack:** Python 3.11 (backend-rag venv), psycopg2 (local `nuzantara_dev`), google-api-python-client + google-auth (Service Account DWD impersonating zero@balizero.com), nlm CLI 0.6.11 (profile `zero`, account antonellosiano@gmail.com), pytest.

**GATE findings baked into this plan (verified 2026-06-04):**

- Drive API direct write of native Doc works (mimeType `application/vnd.google-apps.document`, text/markdown media conversion). MCP google-workspace docs is NOT used.
- NLM `source sync --source-ids <id> -y` propagates NEW content; a post-sync query cites it verbatim.
- **F1:** nlm profile `zero` is logged as `antonellosiano@gmail.com`, NOT zero@. SA-owned Docs MUST be shared (writer, no notification) with antonellosiano@gmail.com or `source add` fails "Could not add drive source".
- **F2:** `nlm source stale` does NOT detect a real modifiedTime change → never rely on it; track our own watermark and sync explicitly by source-id.
- **F3 (NEW, data-driven):** `whatsapp_contacts.contact_type` real distribution is `contact`=8242, `linked`=166, `group`=81, `team`=42, `client_visa`=11, `partner`=6, `client`=2. Only 13 rows are client/client_visa. So the classifier is **exclusion-first** (drop team/partner/group), NOT inclusion-only on `contact_type='client'` (that would lose ~all real clients, which sit under `contact`).

**CRM recap destination (verified):** `clients` table has `strategic_recap` (text), `strategic_recap_updated_at`, `strategic_recap_source`, `ai_summary` (jsonb), `ai_summary_generated_at`, `ai_summary_file_hash`, `ai_summary_schema_version`. v1 produces the recap text only and writes nothing to the CRM (HITL); persistence is a fase-2 decision.

---

## File Structure

- `scripts/wa_corpus/__init__.py` — package marker.
- `scripts/wa_corpus/db.py` — DB access: `iter_pairs()`, `fetch_chat(team, counterpart)`, `count_distinct_names(...)`, classifier lookups. One responsibility: read local Postgres. Pure functions taking a connection.
- `scripts/wa_corpus/classifier.py` — `CounterpartClassifier`: given a counterpart phone + chat stats + `whatsapp_contacts` row, return a `Verdict` (`CLIENT` / `INTERNAL` / `MULTI_CLIENT` / `REVIEW`). No I/O — takes plain inputs, returns enum + reason.
- `scripts/wa_corpus/renderer.py` — `ChatDocRenderer`: render chat rows → markdown; `create_or_update_doc()` via Drive API; `share_with_nlm_account()`. Wraps the gate-proven Drive calls behind a small class. The only module that touches Google Drive.
- `scripts/wa_corpus/query_runner.py` — `QueryRunner`: `ensure_source(nb_id, file_id)`, `sync_source(nb_id, source_id)`, `run_prompt_master(nb_id, source_id)`. Shells out to the `nlm` CLI; parses JSON; enforces cited_text presence. The only module that touches NLM.
- `scripts/wa_corpus/prompt_master.py` — the fixed 6-section prompt template string + the recap validator (`has_required_sections`, `every_section_cited_or_not_mentioned`).
- `tests/wa_corpus/test_classifier.py`, `test_renderer_render.py`, `test_prompt_master.py` — unit tests (pure logic, no network).
- `tests/wa_corpus/test_integration_gate.py` — opt-in integration test (env-gated `WA_CORPUS_LIVE=1`) that re-runs the gate end-to-end against a throwaway NB. Skipped by default in CI.

Constants live in `scripts/wa_corpus/config.py`: SA key path, delegated user, NLM account email, NLM profile, DB DSN, the team/partner/group `contact_type` exclusion set.

---

### Task 1: Package skeleton + config

**Files:**

- Create: `scripts/wa_corpus/__init__.py`
- Create: `scripts/wa_corpus/config.py`
- Test: (none — pure constants)

- [ ] **Step 1: Create the package marker**

```python
# scripts/wa_corpus/__init__.py
"""WhatsApp → NotebookLM grounded corpus-miner (v1). See docs/superpowers/plans/2026-06-04-wa-corpus-miner-build.md"""
```

- [ ] **Step 2: Create config with gate-verified constants**

```python
# scripts/wa_corpus/config.py
"""Central config. Values verified empirically during the 2026-06-04 gate."""
from __future__ import annotations

SA_KEY_PATH = "/Users/nuzantara/.config/nuzantara/service-accounts/nuzantara-google-drive-sa-20260530.json"
DELEGATED_USER = "zero@balizero.com"          # SA impersonates this (DWD configured)
NLM_ACCOUNT_EMAIL = "antonellosiano@gmail.com"  # F1: nlm profile 'zero' is THIS account
NLM_PROFILE = "zero"
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]
DB_DSN = "postgresql://localhost:5432/nuzantara_dev"

# F3: exclusion-first. These contact_types are NEVER a 1-a-1 client profile.
EXCLUDED_CONTACT_TYPES = frozenset({"team", "partner", "group"})

# Heuristics for separating a 1-a-1 client from a multi-client operational channel.
MULTI_CLIENT_MIN_MSGS = 120        # high volume threshold
MULTI_CLIENT_MIN_DISTINCT_NAMES = 8  # many distinct client-like names mentioned
```

- [ ] **Step 3: Commit**

```bash
git add scripts/wa_corpus/__init__.py scripts/wa_corpus/config.py
git commit -m "feat(wa-corpus): package skeleton + gate-verified config"
```

---

### Task 2: Counterpart classifier (pure logic, TDD)

**Files:**

- Create: `scripts/wa_corpus/classifier.py`
- Test: `tests/wa_corpus/test_classifier.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/wa_corpus/test_classifier.py
from scripts.wa_corpus.classifier import CounterpartClassifier, Verdict

clf = CounterpartClassifier()

def test_team_contact_type_is_internal():
    v = clf.classify(contact_type="team", n_msgs=275, n_distinct_names=30)
    assert v.verdict is Verdict.INTERNAL
    assert "team" in v.reason

def test_partner_and_group_excluded():
    assert clf.classify(contact_type="partner", n_msgs=10, n_distinct_names=1).verdict is Verdict.INTERNAL
    assert clf.classify(contact_type="group", n_msgs=10, n_distinct_names=1).verdict is Verdict.INTERNAL

def test_explicit_client_type_is_client():
    v = clf.classify(contact_type="client", n_msgs=40, n_distinct_names=1)
    assert v.verdict is Verdict.CLIENT

def test_client_visa_type_is_client():
    assert clf.classify(contact_type="client_visa", n_msgs=40, n_distinct_names=1).verdict is Verdict.CLIENT

def test_unclassified_low_volume_is_client():
    # 'contact' default + low volume + one name -> treat as 1-a-1 client
    v = clf.classify(contact_type="contact", n_msgs=53, n_distinct_names=1)
    assert v.verdict is Verdict.CLIENT

def test_unclassified_high_volume_many_names_is_multi_client():
    # the +628120000009-style operational channel (but NOT marked team)
    v = clf.classify(contact_type="contact", n_msgs=275, n_distinct_names=30)
    assert v.verdict is Verdict.MULTI_CLIENT

def test_none_contact_type_low_volume_is_client():
    assert clf.classify(contact_type=None, n_msgs=20, n_distinct_names=1).verdict is Verdict.CLIENT

def test_borderline_goes_to_review():
    # high volume but few names, or many names but low volume -> needs a human
    v = clf.classify(contact_type="contact", n_msgs=200, n_distinct_names=2)
    assert v.verdict is Verdict.REVIEW
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/nuzantara/Desktop/nuzantara/.worktrees/ops-wacorpus-gate-firetest-20260604 && PYTHONPATH=. apps/backend-rag/.venv/bin/python -m pytest tests/wa_corpus/test_classifier.py -v`
Expected: FAIL — `ModuleNotFoundError: scripts.wa_corpus.classifier`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/wa_corpus/classifier.py
"""Classify a WhatsApp counterpart: client / internal / multi-client / review.

Exclusion-first (F3): contact_type in EXCLUDED_CONTACT_TYPES is never a client.
For the rest, contact_type in {client, client_visa} is a positive signal; the
large 'contact'/'linked'/None bucket is split by volume + distinct-name count.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass

from scripts.wa_corpus.config import (
    EXCLUDED_CONTACT_TYPES,
    MULTI_CLIENT_MIN_DISTINCT_NAMES,
    MULTI_CLIENT_MIN_MSGS,
)

_CLIENT_TYPES = frozenset({"client", "client_visa"})


class Verdict(enum.Enum):
    CLIENT = "client"            # load into NB, recap valid
    INTERNAL = "internal"        # team/partner/group — exclude
    MULTI_CLIENT = "multi_client"  # operational channel — exclude in v1
    REVIEW = "review"            # ambiguous — human decides


@dataclass(frozen=True)
class Classification:
    verdict: Verdict
    reason: str


class CounterpartClassifier:
    def classify(
        self,
        *,
        contact_type: str | None,
        n_msgs: int,
        n_distinct_names: int,
    ) -> Classification:
        ct = (contact_type or "").strip().lower()

        if ct in EXCLUDED_CONTACT_TYPES:
            return Classification(Verdict.INTERNAL, f"contact_type={ct} excluded")

        if ct in _CLIENT_TYPES:
            return Classification(Verdict.CLIENT, f"contact_type={ct} explicit client")

        # Unclassified bucket: contact / linked / None.
        high_vol = n_msgs >= MULTI_CLIENT_MIN_MSGS
        many_names = n_distinct_names >= MULTI_CLIENT_MIN_DISTINCT_NAMES

        if high_vol and many_names:
            return Classification(
                Verdict.MULTI_CLIENT,
                f"high volume ({n_msgs} msgs) + {n_distinct_names} distinct names",
            )
        if not high_vol and not many_names:
            return Classification(
                Verdict.CLIENT,
                f"low volume ({n_msgs} msgs), {n_distinct_names} name(s) -> 1-a-1",
            )
        # Exactly one signal fired -> ambiguous.
        return Classification(
            Verdict.REVIEW,
            f"ambiguous: {n_msgs} msgs, {n_distinct_names} distinct names",
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/nuzantara/Desktop/nuzantara/.worktrees/ops-wacorpus-gate-firetest-20260604 && PYTHONPATH=. apps/backend-rag/.venv/bin/python -m pytest tests/wa_corpus/test_classifier.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/wa_corpus/classifier.py tests/wa_corpus/test_classifier.py
git commit -m "feat(wa-corpus): exclusion-first counterpart classifier (TDD, 8 tests)"
```

---

### Task 3: DB access layer

**Files:**

- Create: `scripts/wa_corpus/db.py`
- Test: covered by the live integration test (Task 7); no unit test (thin SQL wrapper, would only re-mock the driver).

- [ ] **Step 1: Write the module**

```python
# scripts/wa_corpus/db.py
"""Read-only access to local Postgres for the corpus-miner.

Functions take an open psycopg2 connection so they are easy to use under a
single transaction and easy to point at a test DB.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime


def _digits(phone: str | None) -> str:
    return re.sub(r"[^0-9]", "", phone or "")


@dataclass(frozen=True)
class Pair:
    team_member_phone: str
    counterpart_phone: str
    n_msgs: int


@dataclass(frozen=True)
class ChatLine:
    direction: str
    message_date: datetime | None
    text: str


def iter_pairs(conn, *, min_msgs: int = 1) -> list[Pair]:
    """All direct (team, counterpart) pairs with >= min_msgs messages."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT team_member_phone, counterpart_phone, COUNT(*) AS n
        FROM whatsapp_message_context
        WHERE chat_type='direct'
          AND counterpart_phone IS NOT NULL
          AND team_member_phone IS NOT NULL
        GROUP BY team_member_phone, counterpart_phone
        HAVING COUNT(*) >= %s
        ORDER BY n DESC
        """,
        (min_msgs,),
    )
    return [Pair(t, c, n) for (t, c, n) in cur.fetchall()]


def fetch_chat(conn, team_phone: str, counterpart_phone: str) -> list[ChatLine]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT direction, message_date,
               COALESCE(NULLIF(body,''), NULLIF(message_text,''), '') AS txt
        FROM whatsapp_message_context
        WHERE chat_type='direct'
          AND team_member_phone=%s AND counterpart_phone=%s
        ORDER BY message_date NULLS LAST, id
        """,
        (team_phone, counterpart_phone),
    )
    return [ChatLine(d, m, t) for (d, m, t) in cur.fetchall()]


def get_contact_type(conn, counterpart_phone: str) -> str | None:
    """contact_type from whatsapp_contacts, matched by normalized digits."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT contact_type FROM whatsapp_contacts
        WHERE regexp_replace(phone_normalized,'[^0-9]','','g') = %s
        LIMIT 1
        """,
        (_digits(counterpart_phone),),
    )
    row = cur.fetchone()
    return row[0] if row else None


def count_distinct_names(conn, team_phone: str, counterpart_phone: str) -> int:
    """Rough count of distinct client-like names mentioned in the chat body.

    Heuristic proxy for 'is this one person or a channel'. Counts distinct
    capitalized first-name tokens of length >=3 across message bodies.
    """
    lines = fetch_chat(conn, team_phone, counterpart_phone)
    names: set[str] = set()
    for ln in lines:
        for tok in re.findall(r"\b[A-Z][a-z]{2,}\b", ln.text):
            names.add(tok)
    return len(names)


def latest_message_at(conn, team_phone: str, counterpart_phone: str) -> datetime | None:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT MAX(message_date) FROM whatsapp_message_context
        WHERE chat_type='direct' AND team_member_phone=%s AND counterpart_phone=%s
        """,
        (team_phone, counterpart_phone),
    )
    return cur.fetchone()[0]
```

- [ ] **Step 2: Smoke it against the real DB**

Run:

```bash
cd /Users/nuzantara/Desktop/nuzantara/.worktrees/ops-wacorpus-gate-firetest-20260604
PYTHONPATH=. apps/backend-rag/.venv/bin/python -c "
import psycopg2
from scripts.wa_corpus import db
from scripts.wa_corpus.config import DB_DSN
conn = psycopg2.connect(DB_DSN)
pairs = db.iter_pairs(conn, min_msgs=40)
print('pairs>=40:', len(pairs))
p = pairs[0]
print('sample pair:', p.team_member_phone, p.counterpart_phone, p.n_msgs)
print('contact_type:', db.get_contact_type(conn, p.counterpart_phone))
print('distinct names:', db.count_distinct_names(conn, p.team_member_phone, p.counterpart_phone))
print('chat lines:', len(db.fetch_chat(conn, p.team_member_phone, p.counterpart_phone)))
"
```

Expected: non-zero pairs, a printed contact_type, distinct-name count, chat-line count.

- [ ] **Step 3: Commit**

```bash
git add scripts/wa_corpus/db.py
git commit -m "feat(wa-corpus): read-only Postgres access layer"
```

---

### Task 4: Prompt-master template + recap validator (TDD)

**Files:**

- Create: `scripts/wa_corpus/prompt_master.py`
- Test: `tests/wa_corpus/test_prompt_master.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/wa_corpus/test_prompt_master.py
from scripts.wa_corpus.prompt_master import (
    PROMPT_MASTER, REQUIRED_SECTIONS, recap_is_valid,
)

def test_prompt_contains_all_six_sections():
    for sec in REQUIRED_SECTIONS:
        assert sec in PROMPT_MASTER

def test_prompt_demands_verbatim_and_english():
    assert "verbatim" in PROMPT_MASTER.lower()
    assert "english" in PROMPT_MASTER.lower()
    assert "not mentioned" in PROMPT_MASTER.lower()

def test_valid_recap_has_all_sections():
    recap = "\n".join(f"## {s}\nnot mentioned" for s in REQUIRED_SECTIONS)
    assert recap_is_valid(recap) is True

def test_recap_missing_a_section_is_invalid():
    recap = "\n".join(f"## {s}\nx" for s in list(REQUIRED_SECTIONS)[:-1])
    assert recap_is_valid(recap) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/nuzantara/Desktop/nuzantara/.worktrees/ops-wacorpus-gate-firetest-20260604 && PYTHONPATH=. apps/backend-rag/.venv/bin/python -m pytest tests/wa_corpus/test_prompt_master.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/wa_corpus/prompt_master.py
"""The fixed 6-section grounded prompt-master + a recap structure validator.

Tested manually during the pilot (session report §PROMPT-MASTER). Every section
MUST include a verbatim citation or the literal 'not mentioned'. Output ENGLISH,
max ~2000 chars.
"""
from __future__ import annotations

REQUIRED_SECTIONS = (
    "DEADLINES",
    "PAYMENTS",
    "DOCUMENTS & CASES",
    "PENDING ACTIONS",
    "RISKS & URGENCIES",
    "RELATIONSHIP STATUS",
)

PROMPT_MASTER = """You are reviewing one WhatsApp conversation between a Bali Zero \
team member and a single client. Produce a concise status recap STRICTLY grounded \
in the source. Output in ENGLISH, max 2000 characters.

For EACH of the following six sections, give the current state. For every claim you \
MUST quote the exact verbatim text from the source that supports it (cited_text). \
If a section has nothing in the source, write exactly "not mentioned" — never guess, \
never infer beyond the text.

## DEADLINES
(visa/KITAS/permit/tax dates, appointments)
## PAYMENTS
(amounts owed, paid, pending invoices)
## DOCUMENTS & CASES
(documents requested/received, case/practice references)
## PENDING ACTIONS
(what the team or client still needs to do)
## RISKS & URGENCIES
(complaints, blockers, time-critical items)
## RELATIONSHIP STATUS
(tone, satisfaction, last contact)

Do not include information about any person other than this one client. If the \
conversation appears to involve many different clients, say so in RELATIONSHIP \
STATUS and stop."""


def recap_is_valid(recap: str) -> bool:
    """Structural check: all six section headers present in the recap text."""
    upper = recap.upper()
    return all(sec in upper for sec in REQUIRED_SECTIONS)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/nuzantara/Desktop/nuzantara/.worktrees/ops-wacorpus-gate-firetest-20260604 && PYTHONPATH=. apps/backend-rag/.venv/bin/python -m pytest tests/wa_corpus/test_prompt_master.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/wa_corpus/prompt_master.py tests/wa_corpus/test_prompt_master.py
git commit -m "feat(wa-corpus): 6-section grounded prompt-master + recap validator"
```

---

### Task 5: Chat→Doc renderer (Drive API, gate-proven calls)

**Files:**

- Create: `scripts/wa_corpus/renderer.py`
- Test: `tests/wa_corpus/test_renderer_render.py` (markdown rendering only — pure, no network)

- [ ] **Step 1: Write the failing test (pure render)**

```python
# tests/wa_corpus/test_renderer_render.py
from datetime import datetime, timezone
from scripts.wa_corpus.db import ChatLine
from scripts.wa_corpus.renderer import render_markdown

def test_render_marks_team_and_counterpart():
    lines = [
        ChatLine("outbound", datetime(2026,5,29,tzinfo=timezone.utc), "Hello from team"),
        ChatLine("inbound", datetime(2026,5,29,tzinfo=timezone.utc), "Hi from client"),
    ]
    md = render_markdown("+62TEAM", "+33CP", lines)
    assert "TEAM:" in md and "COUNTERPART:" in md
    assert "Hello from team" in md and "Hi from client" in md
    assert "Message count: 2" in md

def test_render_skips_empty_bodies():
    lines = [ChatLine("inbound", None, ""), ChatLine("inbound", None, "real")]
    md = render_markdown("+62TEAM", "+33CP", lines)
    assert "real" in md
    assert md.count("COUNTERPART:") == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/nuzantara/Desktop/nuzantara/.worktrees/ops-wacorpus-gate-firetest-20260604 && PYTHONPATH=. apps/backend-rag/.venv/bin/python -m pytest tests/wa_corpus/test_renderer_render.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write implementation (render + Drive ops)**

```python
# scripts/wa_corpus/renderer.py
"""Render a chat to markdown and write it as a NATIVE Google Doc via Drive API.

Drive calls are exactly the ones proven in the 2026-06-04 gate:
  - files().create(mimeType=google-apps.document, media=text/markdown)  -> native Doc
  - files().update(media=text/markdown)                                 -> refresh
  - permissions().create(writer, antonellosiano@gmail.com)              -> F1 share
"""
from __future__ import annotations

import io
from datetime import datetime, timezone

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from scripts.wa_corpus.config import (
    DELEGATED_USER, DRIVE_SCOPES, NLM_ACCOUNT_EMAIL, SA_KEY_PATH,
)
from scripts.wa_corpus.db import ChatLine


def render_markdown(team_phone: str, counterpart_phone: str, lines: list[ChatLine]) -> str:
    out = [
        f"# WhatsApp chat — team {team_phone} ↔ counterpart {counterpart_phone}",
        "",
        f"Rendered: {datetime.now(timezone.utc).isoformat()}",
        f"Message count: {sum(1 for ln in lines if ln.text)}",
        "",
        "---",
        "",
    ]
    for ln in lines:
        if not ln.text:
            continue
        who = "TEAM" if ln.direction == "outbound" else "COUNTERPART"
        ts = ln.message_date.isoformat() if ln.message_date else "(no-date)"
        out.append(f"**[{ts}] {who}:** {ln.text}")
        out.append("")
    return "\n".join(out)


class ChatDocRenderer:
    def __init__(self) -> None:
        creds = service_account.Credentials.from_service_account_file(
            SA_KEY_PATH, scopes=DRIVE_SCOPES
        ).with_subject(DELEGATED_USER)
        self.svc = build("drive", "v3", credentials=creds, cache_discovery=False)

    def _media(self, markdown: str) -> MediaIoBaseUpload:
        return MediaIoBaseUpload(
            io.BytesIO(markdown.encode("utf-8")),
            mimetype="text/markdown",
            resumable=False,
        )

    def create_doc(self, name: str, markdown: str) -> str:
        created = self.svc.files().create(
            body={"name": name, "mimeType": "application/vnd.google-apps.document"},
            media_body=self._media(markdown),
            fields="id",
            supportsAllDrives=True,
        ).execute()
        file_id = created["id"]
        self.share_with_nlm_account(file_id)  # F1: must share or nlm can't see it
        return file_id

    def update_doc(self, file_id: str, markdown: str) -> None:
        self.svc.files().update(
            fileId=file_id,
            media_body=self._media(markdown),
            fields="id, modifiedTime",
            supportsAllDrives=True,
        ).execute()

    def share_with_nlm_account(self, file_id: str) -> None:
        self.svc.permissions().create(
            fileId=file_id,
            body={"type": "user", "role": "writer", "emailAddress": NLM_ACCOUNT_EMAIL},
            sendNotificationEmail=False,
            supportsAllDrives=True,
            fields="id",
        ).execute()

    def export_text(self, file_id: str) -> str:
        data = self.svc.files().export(fileId=file_id, mimeType="text/plain").execute()
        return data.decode("utf-8") if isinstance(data, bytes) else str(data)
```

- [ ] **Step 4: Run the render test to verify it passes**

Run: `cd /Users/nuzantara/Desktop/nuzantara/.worktrees/ops-wacorpus-gate-firetest-20260604 && PYTHONPATH=. apps/backend-rag/.venv/bin/python -m pytest tests/wa_corpus/test_renderer_render.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/wa_corpus/renderer.py tests/wa_corpus/test_renderer_render.py
git commit -m "feat(wa-corpus): chat->Doc renderer (Drive API, F1 auto-share)"
```

---

### Task 6: NLM query-runner (CLI wrapper, cited-text enforcement)

**Files:**

- Create: `scripts/wa_corpus/query_runner.py`
- Test: `tests/wa_corpus/test_query_runner_parse.py` (parsing only — no network)

- [ ] **Step 1: Write the failing test (JSON parse + cited enforcement)**

```python
# tests/wa_corpus/test_query_runner_parse.py
import json
from scripts.wa_corpus.query_runner import parse_query_result, RecapResult

SAMPLE = json.dumps({"value": {
    "answer": "## DEADLINES\nKITAS 2029-12-31 [1]\n## PAYMENTS\nnot mentioned",
    "conversation_id": "c1",
    "references": [{"source_id": "s1", "citation_number": 1, "cited_text": "KITAS appointment 2029-12-31"}],
}})

def test_parse_extracts_answer_and_citations():
    r = parse_query_result(SAMPLE)
    assert isinstance(r, RecapResult)
    assert "DEADLINES" in r.answer
    assert r.has_citations is True
    assert r.cited_texts == ["KITAS appointment 2029-12-31"]

def test_parse_no_citations_flagged():
    no_cite = json.dumps({"value": {"answer": "x", "references": []}})
    r = parse_query_result(no_cite)
    assert r.has_citations is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/nuzantara/Desktop/nuzantara/.worktrees/ops-wacorpus-gate-firetest-20260604 && PYTHONPATH=. apps/backend-rag/.venv/bin/python -m pytest tests/wa_corpus/test_query_runner_parse.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write implementation**

```python
# scripts/wa_corpus/query_runner.py
"""Drive the `nlm` CLI: add source, sync (explicit — F2), run prompt-master.

F2: never trust `nlm source stale`. Always sync the specific source-id of a Doc
we just refreshed.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass

from scripts.wa_corpus.config import NLM_PROFILE
from scripts.wa_corpus.prompt_master import PROMPT_MASTER


@dataclass(frozen=True)
class RecapResult:
    answer: str
    cited_texts: list[str]

    @property
    def has_citations(self) -> bool:
        return len(self.cited_texts) > 0


def parse_query_result(raw: str) -> RecapResult:
    data = json.loads(raw)
    value = data.get("value", data)
    answer = value.get("answer", "")
    refs = value.get("references", []) or []
    cited = [r.get("cited_text", "") for r in refs if r.get("cited_text")]
    return RecapResult(answer=answer, cited_texts=cited)


def _nlm(args: list[str], timeout: float = 300.0) -> str:
    proc = subprocess.run(
        ["nlm", *args, "-p", NLM_PROFILE],
        capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"nlm {' '.join(args)} failed: {proc.stderr.strip() or proc.stdout.strip()}")
    return proc.stdout


class QueryRunner:
    def ensure_source(self, nb_id: str, file_id: str, title: str) -> str:
        """Add the Drive Doc as a source; return its source_id.

        Note: caller is responsible for sharing the Doc with the nlm account
        first (renderer does this on create — F1)."""
        out = _nlm(["source", "add", nb_id, "--drive", file_id,
                    "--type", "doc", "--title", title, "--wait"])
        # nlm prints 'Source ID: <uuid>'
        for line in out.splitlines():
            if "Source ID:" in line:
                return line.split("Source ID:", 1)[1].strip()
        raise RuntimeError(f"could not parse source id from nlm output:\n{out}")

    def sync_source(self, nb_id: str, source_id: str) -> None:
        _nlm(["source", "sync", nb_id, "--source-ids", source_id, "-y"])

    def run_prompt_master(self, nb_id: str, source_id: str) -> RecapResult:
        out = _nlm(["notebook", "query", nb_id, PROMPT_MASTER,
                    "--source-ids", source_id, "--json", "-t", "150"])
        return parse_query_result(out)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/nuzantara/Desktop/nuzantara/.worktrees/ops-wacorpus-gate-firetest-20260604 && PYTHONPATH=. apps/backend-rag/.venv/bin/python -m pytest tests/wa_corpus/test_query_runner_parse.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/wa_corpus/query_runner.py tests/wa_corpus/test_query_runner_parse.py
git commit -m "feat(wa-corpus): nlm query-runner (explicit sync F2, cited enforcement)"
```

---

### Task 7: End-to-end pilot driver + live integration test

**Files:**

- Create: `scripts/wa_corpus/pilot.py` (CLI: pick one CLIENT pair, render → Doc → NB → sync → recap, print recap)
- Test: `tests/wa_corpus/test_integration_gate.py` (env-gated `WA_CORPUS_LIVE=1`)

- [ ] **Step 1: Write the pilot driver**

```python
# scripts/wa_corpus/pilot.py
"""One-shot pilot: pick a single CLIENT pair, build its Doc, query a recap.

Usage:
  PYTHONPATH=. apps/backend-rag/.venv/bin/python -m scripts.wa_corpus.pilot \
      --team +628120000001 --counterpart +33600000000 --nb <NB_ID>
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone

import psycopg2

from scripts.wa_corpus import db
from scripts.wa_corpus.classifier import CounterpartClassifier, Verdict
from scripts.wa_corpus.config import DB_DSN
from scripts.wa_corpus.prompt_master import recap_is_valid
from scripts.wa_corpus.query_runner import QueryRunner
from scripts.wa_corpus.renderer import ChatDocRenderer, render_markdown


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--team", required=True)
    ap.add_argument("--counterpart", required=True)
    ap.add_argument("--nb", required=True, help="target NB id (profile zero)")
    args = ap.parse_args()

    conn = psycopg2.connect(DB_DSN)
    ct = db.get_contact_type(conn, args.counterpart)
    lines = db.fetch_chat(conn, args.team, args.counterpart)
    n_names = db.count_distinct_names(conn, args.team, args.counterpart)

    verdict = CounterpartClassifier().classify(
        contact_type=ct, n_msgs=len(lines), n_distinct_names=n_names
    )
    print(f"[pilot] classify -> {verdict.verdict.value}: {verdict.reason}")
    if verdict.verdict is not Verdict.CLIENT:
        print("[pilot] not a 1-a-1 client; refusing to build a profile recap.")
        return 2

    md = render_markdown(args.team, args.counterpart, lines)
    renderer = ChatDocRenderer()
    name = f"WA-{args.counterpart}-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}"
    file_id = renderer.create_doc(name, md)
    print(f"[pilot] doc created + shared: {file_id}")

    qr = QueryRunner()
    source_id = qr.ensure_source(args.nb, file_id, title=name)
    qr.sync_source(args.nb, source_id)  # F2 explicit
    recap = qr.run_prompt_master(args.nb, source_id)

    print("=" * 60)
    print(recap.answer)
    print("=" * 60)
    print(f"[pilot] citations: {len(recap.cited_texts)} | structure valid: {recap_is_valid(recap.answer)}")
    if not recap.has_citations:
        print("[pilot] WARNING: recap has zero verbatim citations — do NOT trust.")
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Write the env-gated live integration test**

```python
# tests/wa_corpus/test_integration_gate.py
import os
import subprocess
import pytest

LIVE = os.environ.get("WA_CORPUS_LIVE") == "1"

@pytest.mark.skipif(not LIVE, reason="set WA_CORPUS_LIVE=1 to run live NLM/Drive test")
def test_pilot_end_to_end():
    nb = os.environ["WA_CORPUS_TEST_NB"]  # a throwaway NB id
    r = subprocess.run(
        ["apps/backend-rag/.venv/bin/python", "-m", "scripts.wa_corpus.pilot",
         "--team", "+628120000001", "--counterpart", "+33600000000", "--nb", nb],
        capture_output=True, text=True, env={**os.environ, "PYTHONPATH": "."},
        timeout=600,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "citations:" in r.stdout
```

- [ ] **Step 3: Run the unit suite (live test skipped)**

Run: `cd /Users/nuzantara/Desktop/nuzantara/.worktrees/ops-wacorpus-gate-firetest-20260604 && PYTHONPATH=. apps/backend-rag/.venv/bin/python -m pytest tests/wa_corpus/ -v`
Expected: all unit tests PASS, `test_pilot_end_to_end` SKIPPED.

- [ ] **Step 4: Run the live pilot once against the gate test NB**

Run:

```bash
cd /Users/nuzantara/Desktop/nuzantara/.worktrees/ops-wacorpus-gate-firetest-20260604
PYTHONPATH=. apps/backend-rag/.venv/bin/python -m scripts.wa_corpus.pilot \
  --team +628120000001 --counterpart +33600000000 \
  --nb f4dcb203-c6cf-45b1-b6a9-dd5e14bb4663
```

Expected: classify -> client; doc created+shared; a 6-section recap printed with >=1 citation; exit 0.

- [ ] **Step 5: Commit**

```bash
git add scripts/wa_corpus/pilot.py tests/wa_corpus/test_integration_gate.py
git commit -m "feat(wa-corpus): end-to-end pilot driver + env-gated live test"
```

---

## Self-Review

**Spec coverage:** §1 architecture → renderer + query_runner + classifier (Tasks 2,5,6). §2 naming (counterpart_phone stable, title=label) → renderer doc name uses counterpart_phone; rename-from-CRM is fase-2. §3 multi-membro cross-NB → fase-2 (v1 scope §7 is direct only; classifier flags MULTI_CLIENT). §4 query-runner → Task 6. §5 anti-hallucination → grounding (cited enforcement Task 6), scope (prompt Task 4), HITL (recap never writes CRM — pilot prints only). §6 sync → explicit source-id sync (F2, Task 6). §7bis classifier → Task 2 (exclusion-first per F3). §7ter CRM fields → documented, not written in v1. §8 incognite #1,#2 → closed by gate. #3 cross-source contamination → mitigated by `--source-ids` explicit in query (Task 6). #4 quota/retry → fase-2 (single-pilot v1).

**Placeholder scan:** none — every code step has full code.

**Type consistency:** `Verdict`/`Classification` (Task 2) used in pilot (Task 7). `ChatLine`/`Pair` (Task 3) used in renderer test + pilot. `RecapResult` (Task 6) used in pilot. `render_markdown` signature consistent across Task 5 test, impl, and pilot. `REQUIRED_SECTIONS`/`recap_is_valid` (Task 4) used in pilot. Consistent.

**Out of v1 scope (explicit):** group chats, auto rename-from-CRM, cross-NB merge for the 37 multi-member clients, quota/retry batch hardening, writing the recap into `clients.strategic_recap`. All deferred to fase-2 per spec §7.
