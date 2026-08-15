---
date: 2026-08-15
domain: visa
client_case: none
sources:
  - path: /Users/balizero/.local/share/uv/tools/notebooklm-mcp-cli/lib/python3.11/site-packages/notebooklm_tools/core/conversation.py
    lines: "350-469 (query()), 68-102 (_build_conversation_history())"
    package: notebooklm-mcp-cli 0.9.8 (uv tool install, local)
  - path: /Users/balizero/.local/share/uv/tools/notebooklm-mcp-cli/lib/python3.11/site-packages/notebooklm_tools/cli/commands/notebook.py
    lines: "148-189 (query_notebook())"
  - path: /Users/balizero/nuzantara/visa-oracle-adjudication/output-A/run_p0.py
    note: "prior art — the defective runner; never passes -c"
  - path: /Users/balizero/nuzantara/visa-oracle-adjudication/output-A/batch-p0.jsonl
    note: "empirical evidence cited by adjudication-report.md §9: 10/10 P0 answers share conversation_id 3e8fe6db-8873-4689-9bff-226ee875c09d"
  - path: /Users/balizero/nuzantara/.worktrees/ops-visaoracle-adjudication/visa-oracle-adjudication/adjudication-report.md
    lines: "§9"
adversarial_review: pending
---

# QW-1 STEP 0 — NB-2 transport root-cause + fresh-conversation isolation proof

Plan reference: `visa-oracle-adjudication/execution-plan.md` §1 QW-1 ("STEP 0 — root-cause del
transport: … primo gate = PROVARE che una conversation fresca è ottenibile via `nlm`").
Adjudication reference: `adjudication-report.md` §9 (empirical evidence, P0 batch executed by
blueprint A).

## Root-cause (verified at source level this session, not re-derived from the plan text)

`nlm` CLI, package `notebooklm-mcp-cli` v0.9.8, installed at
`~/.local/share/uv/tools/notebooklm-mcp-cli/lib/python3.11/site-packages/notebooklm_tools/`.

`core/conversation.py::ConversationManager.query()`, lines ~392-403:

```python
is_new_conversation = conversation_id is None
if is_new_conversation:
    # Try to get the persistent conversation ID from the server first.
    # This is what makes CLI/MCP chats appear in the web UI's chat history.
    server_conv_id = self.get_conversation_id(notebook_id)
    if server_conv_id:
        conversation_id = server_conv_id
        # Build history from local cache if we have it
        conversation_history = self._build_conversation_history(conversation_id)
    else:
        conversation_id = str(uuid.uuid4())
        conversation_history = None
else:
    # Check if we have cached history for this conversation
    assert conversation_id is not None
    conversation_history = self._build_conversation_history(conversation_id)
```

When `--conversation-id` is omitted, the CLI does not mint a fresh id first — it asks the
server for the notebook's **persistent** conversation id (`get_conversation_id(notebook_id)`)
and reuses it, by design, "so CLI/MCP chats appear in the web UI's chat history". That single
persistent id is shared across every invocation of `nlm` against that notebook that omits
`-c`, from any process, on any machine. This is exactly why two independent harnesses —
blueprint A's executed P0 batch (`output-A/run_p0.py`, which never passes `-c` — confirmed by
reading the script: its `subprocess.run` argv is
`["nlm", "notebook", "query", notebook_id, full_question, "--json", "-t", "100"]`, no `-c`
anywhere) and blueprint C's live probes — both landed in the same conversation
`3e8fe6db-8873-4689-9bff-226ee875c09d` and observed cross-context contamination ("As we
discussed in our previous evaluation…", per `adjudication-report.md` §9).

## Cure (client-side; verified by reading the code path, not assumed)

`cli/commands/notebook.py::query_notebook()`, lines 148-189, forwards an explicit
`--conversation-id`/`-c` value straight into `ConversationManager.query(conversation_id=...)`.
When `conversation_id` is not `None`, `is_new_conversation` is `False`, so the code takes the
**else** branch and skips the server-side persistent-id lookup entirely:

```python
else:
    assert conversation_id is not None
    conversation_history = self._build_conversation_history(conversation_id)
```

`_build_conversation_history()` (lines 68-102) looks the id up in
`self._conversation_cache`, an in-memory `OrderedDict` that lives only for the lifetime of the
Python process. Every `nlm` CLI invocation is a **fresh process** — the cache starts empty
every time. So for a `uuid.uuid4()` minted immediately before the call and never seen before
(by construction: freshly generated, not persisted anywhere), the cache lookup always misses
→ `turns = []` → `_build_conversation_history()` returns `None` (line 92-93: `if not turns:
return None`) → `conversation_history = None` is what is actually sent to the server as
`params[2]` in the batchexecute payload (line 423: `conversation_history, # None for new,
history array for follow-ups`). The server therefore has no stored history to attach to an
unrecognized conversation id, and cannot inject cross-context contamination.

**Practical cure**: always invoke `nlm notebook query <nb> <question> --json -c <fresh
uuid4> -t <timeout>` — never omit `-c`. This is what `research/visa/doctrine-factory/tools/nb2_query.py::run_one_query()`
does unconditionally (it has no code path that omits `-c`).

## Live proof (2 queries, fresh UUID4 each, run through `tools/nb2_query.py`)

Both probes ran against NB-2 (`cff93ab0-813a-42f2-a8de-36987e724271`, 131 sources — frozen
same session in `sources/nb2-source-snapshot-2026-08-15.json`). Raw JSONL records appended to
`nb2-answers/response-log.jsonl` (query_id `step0-probe-a-pong`,
`step0-probe-b-history-leak`).

Commands (as actually run):

```bash
cd research/visa/doctrine-factory/tools
python3 nb2_query.py query --query-id "step0-probe-a-pong" \
  --question "Reply with exactly the word PONG." --timeout 90

python3 nb2_query.py query --query-id "step0-probe-b-history-leak" \
  --question "List everything we have discussed previously in this conversation. If there is no previous discussion in THIS conversation, say exactly: NO PRIOR DISCUSSION." \
  --timeout 90
```

### Probe A — isolation ("Reply with exactly the word PONG.")

```json
{
  "conversation_id_sent": "8a32e3b6-7e54-4209-b6b4-31e7067599f4",
  "conversation_id_returned": "8a32e3b6-7e54-4209-b6b4-31e7067599f4",
  "answer": "PONG",
  "status": "OK",
  "returncode": 0
}
```

### Probe B — history-leak check

```json
{
  "conversation_id_sent": "e794d18a-cd11-4cf1-b020-9faef666a7f7",
  "conversation_id_returned": "e794d18a-cd11-4cf1-b020-9faef666a7f7",
  "answer": "NO PRIOR DISCUSSION.",
  "status": "OK",
  "returncode": 0
}
```

## STEP 0 gate verdict: PASS

All three assertions the mandate requires hold, verified directly against the two live
records above:

1. **Both `conversation_id`s are distinct**: `8a32e3b6-7e54-4209-b6b4-31e7067599f4` !=
   `e794d18a-cd11-4cf1-b020-9faef666a7f7`. ✅
2. **Neither equals the known-contaminated id** `3e8fe6db-8873-4689-9bff-226ee875c09d`. ✅
   (Also enforced structurally: `nb2_query.py::build_record()` checks this and would mark the
   record `ISOLATION_MISMATCH` + raise `IsolationMismatchError` if it ever did.)
3. **Probe B shows no leaked history**: the answer is exactly `"NO PRIOR DISCUSSION."` — no
   mention of probe A, PONG, or any prior turn. ✅

`conversation_id_returned == conversation_id_sent` on both probes: the server accepted and
echoed back the exact fresh UUID4 we minted, confirming the client-side cure is sufficient —
no server-side cooperation or additional parameter was needed.

**Consequence for the rest of QW-1**: the fresh-UUID approach isolates conversations as
designed. No cure-design change is required. The B0 canary (5 NB queries + 1 local audit) can
proceed on the same `tools/nb2_query.py` runner — see
`2026-08-15-qw1-b0-canary.md`.

## Budget accounting

STEP 0 consumed 2 of the 10 allowed live NB-2 `notebook query` calls for this task
(`step0-probe-a-pong`, `step0-probe-b-history-leak`). The source-snapshot freeze
(`nlm source list`) is a read-only listing, not a `notebook query` call, and is not counted
against this budget per the mandate's constraint wording ("only `nlm notebook query` and
read-only listing … Budget: max 10 live NB-2 queries").
