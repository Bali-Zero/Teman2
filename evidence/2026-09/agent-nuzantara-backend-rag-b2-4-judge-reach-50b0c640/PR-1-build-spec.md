# PR-1 build spec — daemon judges the claimed job before generating (inert on Fly)

Authority: I96 + I97 (shape approved). Design: `B2-4-design.md` (same dir). Read it first.
Worktree: `/Users/nuzantara/nuzantara/.worktrees/backend-rag-b2-4-judge-reach` — work ONLY there.
Python: `apps/backend-rag/.venv/bin/python` if present in the worktree, else the main checkout's
`/Users/nuzantara/nuzantara/apps/backend-rag/.venv/bin/python`; run pytest from `apps/backend-rag`
with `PYTHONPATH=.`. NEVER run `npm install`, never `git stash`, never `rm` (use `mv` to the
scratchpad), never `--no-verify`. Do NOT commit, push or open a PR — the Dux does that.
One short command per Bash call; no compound git commands.

## Files and exact changes

### 1. `apps/backend-rag/backend/services/rag/agentic/_support_signal.py`

- `CodexSupportJudge.__init__(self, *, model=MODEL_TERRA, timeout_s=_CODEX_TIMEOUT_S, client: CodexExecClient | None = None)`:
  `self._client = client if client is not None else CodexExecClient(model=model, timeout_s=timeout_s)`.
  Nothing else in the class changes (`_vote_once` already passes model + timeout per call).
- New pure function, added to `__all__`:
  `def support_inputs_from_wire(wire: str) -> tuple[str, str]`
  Parses the sealed package wire (canonical JSON with keys history/chunks/...) and returns
  `(query, context)` EXACTLY as `wa_package_builder.build_context_package` builds the judge input
  today (L623-624): `query = history[-1]["content"] if history else ""`,
  `context = "\n\n".join(chunk["text"] for chunk in chunks)`.
  Raises `ValueError` (message without any wire content) when: not JSON, not an object, `history`
  not a list, last history item not a dict with a `str` `content`, `chunks` not a list, any chunk
  not a dict with `str` `text`. Module stays stdlib + `backend.llm.codex_exec_client` only (it is
  installed into the Pro runtime tree, which has stdlib + httpx only). No logging of content.

### 2. NEW `apps/backend-rag/backend/services/integrations/wa_completion_envelope.py`

Imports: stdlib (`hashlib`, `hmac`, `json`, `re`, `dataclasses`) + `from backend.services.rag.agentic._support_signal import SupportVerdict, majority`. Nothing else.

```python
ENVELOPE_VERSION = 1
_KEY_CONTEXT = b"wa-completion-envelope/v1"
_FIELDS = frozenset({"v", "package_hash", "verdict", "votes", "judge", "answer", "mac"})
_JUDGE_RE = re.compile(r"^(codex|ollama):[A-Za-z0-9._:-]{1,60}$")
_ANSWERABLE = {SUPPORTED, NOT_SUPPORTED, UNKNOWN}

@dataclass(frozen=True)
class SupportCompletion:
    verdict: SupportVerdict
    votes: tuple[SupportVerdict, ...]
    judge: str
    answer: str | None

def encode_completion(*, key: str, package_hash: str, verdict: SupportVerdict,
                      votes: tuple[SupportVerdict, ...], judge: str, answer: str | None) -> str
def decode_completion(text: str | None, *, key: str | None, package_hash: str) -> SupportCompletion | None
```

- Derived key: `k = hmac.new(key.encode("utf-8"), _KEY_CONTEXT, hashlib.sha256).digest()`.
- Canonical form: `json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))`.
- `mac = hmac.new(k, canonical(body_without_mac).encode("utf-8"), hashlib.sha256).hexdigest()`;
  the returned string is `canonical(body | {"mac": mac})`.
- `encode_completion` raises `ValueError` when: key empty; package_hash empty; verdict not in the
  three answerable values (UNAVAILABLE is never enveloped — it travels as an error_class);
  `len(votes) != 3` or a vote not a `SupportVerdict`; `majority(votes) is not verdict`; judge fails
  `_JUDGE_RE`; `answer` is not a non-empty (after strip) `str` when verdict is SUPPORTED; `answer`
  is not `None` when verdict is not SUPPORTED.
- `decode_completion` NEVER raises and returns `None` on ANY of: key None/empty; text None; not
  JSON; not a dict; key set != `_FIELDS`; `v != 1` (reject bool); non-str package_hash/judge/mac;
  `mac` mismatch (`hmac.compare_digest`) — check the MAC before trusting any other field value;
  `package_hash` != argument (`hmac.compare_digest`); verdict not answerable; votes not a list of
  exactly 3 strings each in the 4-value vocabulary; `majority(votes) != verdict`; judge fails
  `_JUDGE_RE`; answer rule violated. It logs nothing (the caller logs).
- Module docstring: why a MAC (old daemon returns raw model text; codex has read-only shell and
  could hash its prompt, so `package_hash` binding alone is forgeable; the key never reaches the
  codex child). Keep it short.

### 3. `apps/backend-rag/backend/services/integrations/wa_codex_daemon.py`

- Imports: `from backend.services.integrations.wa_completion_envelope import encode_completion` and
  `from backend.services.rag.agentic._support_signal import CodexSupportJudge, SupportVerdict, majority, support_inputs_from_wire`.
- Constants (module level, with a one-line comment each): `_JUDGE_BUDGET_CAP_S = 20.0`,
  `_JUDGE_BUDGET_FRACTION = 0.45`. The Dux may retune them after the C1 measurement — keep them
  as the ONLY place the numbers live.
- In `_execute_and_complete`, AFTER the existing `budget_s <= 0` check and BEFORE the generate
  block, insert the support stage:
  1. `started = time.monotonic()` moves up to here (exec_ms covers judge + generation).
  2. `try: query, context = support_inputs_from_wire(claim.package)` / `except ValueError:` log ERROR
     `"wa-codex-daemon: package for job %s is not a readable wire — support judge cannot rule"`,
     complete with `error_class="support_judge_unavailable"`, `exec_ms` measured, return.
  3. `judge_budget = min(_JUDGE_BUDGET_CAP_S, budget_s * _JUDGE_BUDGET_FRACTION)`;
     `judge = CodexSupportJudge(timeout_s=judge_budget, client=self._codex)` (model stays the
     default `MODEL_TERRA` REGARDLESS of `config.model` — the judge is the measured I26 seat).
  4. `votes = await judge.vote_repetitions(query, context)` inside `try/except Exception` →
     on exception `votes = (SupportVerdict.UNAVAILABLE,) * 3` and log ERROR with the type name only.
     `verdict = majority(votes)`.
  5. `UNAVAILABLE` → log ERROR `"wa-codex-daemon: support judge ABSENT for job %s (judge=%s votes=%s) — reported as support_judge_unavailable, nothing generated"`
     (votes as comma-joined enum values), set `self._last_exec_ms`, complete with
     `error_class="support_judge_unavailable"`, return.
  6. `NOT_SUPPORTED`/`UNKNOWN` → `envelope = encode_completion(key=self._config.broker_key, package_hash=claim.package_hash, verdict=verdict, votes=votes, judge=judge.name, answer=None)`;
     log INFO `"wa-codex-daemon: support verdict %s for job %s (judge=%s votes=%s) — nothing generated"`;
     complete with `result_text=envelope`; return.
  7. `SUPPORTED` → `remaining = budget_s - (time.monotonic() - started)`; if `remaining <= 0`
     complete `error_class="exec_timeout"` and return. Else the EXISTING generate block runs with
     `timeout_s=remaining` and its exception mapping unchanged. On a returned result: the existing
     `empty_output` and NUL checks apply to the RAW `result.text`; then
     `envelope = encode_completion(..., verdict=SupportVerdict.SUPPORTED, votes=votes, judge=judge.name, answer=text)`;
     the existing `_RESULT_TEXT_MAX` and `_RESULT_BYTES_MAX` checks apply to `envelope` (the bytes
     actually sent) → `oversized_output`; else `result_text = envelope`. Log INFO naming verdict,
     judge and votes for the SUPPORTED path too.
- Update the module docstring's flow description in 2-4 lines (judge stage, envelope). Do not
  rewrite unrelated prose.

### 4. `apps/backend-rag/backend/services/integrations/wa_broker.py`

Add `"support_judge_unavailable",  # daemon's support judge could not rule (B2.4) — nothing generated`
to `ALLOWED_ERROR_CLASSES`. Class-audit: `git grep -n "policy_refusal\|ALLOWED_ERROR_CLASSES\|quota_exhausted"`
across the repo (scripts, sentinels, tests, docs specs) and update any exact-set assertion or
vocabulary mirror; report every hit and what you did with it. Do NOT change fold semantics.

### 5. `scripts/provision_zantara_codex.sh` (section 3 only)

- Add `"${PKG}/services/rag" "${PKG}/services/rag/agentic"` to the `install -d` line.
- Add `"${PKG}/services/rag/__init__.py" "${PKG}/services/rag/agentic/__init__.py"` to the empty
  `__init__.py` touch loop (empty markers, NOT copies — the real ones import heavy modules).
- Two new `install -o root -g wheel -m 0644` lines: `_support_signal.py` →
  `${PKG}/services/rag/agentic/_support_signal.py`; `wa_completion_envelope.py` →
  `${PKG}/services/integrations/wa_completion_envelope.py`.
- `bash -n scripts/provision_zantara_codex.sh` must pass. Do not touch other sections.

### 6. `infra/home-fork/declared-pairs.json`

Two new pairs next to the `wa_codex_daemon.py` / `codex_exec_client.py` pairs, same shape
(`live`, `repo`, `machines: ["pro"]`, `_note`): the two new runtime modules. `_note`: installed by
provisioning §3 since B2.4, re-run provisioning after changing the repo twin (W107), the two new
empty `__init__.py` markers deliberately undeclared (same reason as the existing four). Validate
the JSON parses; run any existing test that loads this file (`git grep -ln declared-pairs -- '*test*'`).

## Tests (write them first where practical; guilt AND innocence)

- NEW `apps/backend-rag/backend/tests/unit/services/integrations/test_wa_completion_envelope.py`
  (check the directory convention used by neighbouring tests first; `test_wa_codex_daemon.py`
  lives in `backend/tests/unit/services/` — put the new file beside it if that is the convention):
  round-trip SUPPORTED (unicode + JSON-looking answer byte-exact), NOT_SUPPORTED, UNKNOWN;
  guilt → `None`: wrong key, empty key, hash mismatch, tampered answer / verdict / votes / judge,
  mac removed, extra key, missing key, raw non-JSON text, JSON array, a hand-forged envelope with a
  plausible but wrong mac, SUPPORTED with null answer, NOT_SUPPORTED with an answer, majority
  mismatch (votes S,N,N with verdict SUPPORTED), `v` true/2; encode raises on UNAVAILABLE,
  inconsistent majority, bad judge, blank answer.
- `test_support_signal.py`: client injection is the client used (fake client records calls);
  `support_inputs_from_wire` equals the builder formula on a wire produced by
  `wa_package_builder._canonical_wire` (import it) for (a) normal history+chunks, (b) empty history,
  (c) zero chunks; malformed wires raise `ValueError`.
- `test_wa_codex_daemon.py` (reuse its fakes; read the file first): judge SUPPORTED → exactly 3
  judge calls + 1 generate call, generate `timeout_s` < budget and > 0, completion `result_text`
  decodes with `config.broker_key` + `claim.package_hash` to SUPPORTED with the generated answer;
  NOT_SUPPORTED majority → generate NEVER called, envelope answer None; UNKNOWN majority same;
  UNAVAILABLE majority (fake raises CodexExecUnavailableError) → `error_class="support_judge_unavailable"`,
  generate never called; split S/N/U → NOT_SUPPORTED, no generation; malformed package →
  `support_judge_unavailable`; the judge prompt equals `RUBRIC.format(query=<history[-1].content>, context=<joined chunk texts>)`;
  judge model is `MODEL_TERRA` even when `config.model` is another allowed model; an answer whose
  ENVELOPE exceeds the byte cap → `oversized_output`; a judge that consumes the whole budget →
  `exec_timeout` without generating. Existing tests that assumed "claim → generate directly" must be
  adapted to feed a readable wire and a SUPPORTED judge — change as little as possible and list
  every existing test you touched and why.
- `test_wa_broker.py` / `test_wa_broker_router.py`: the router accepts `support_judge_unavailable`.

## Verification you run and paste in your report (commands + exit codes + tail of output)

1. `PYTHONPATH=. <venv python> -m pytest backend/tests/unit/services/test_wa_codex_daemon.py backend/tests/unit/services/rag/agentic/test_support_signal.py backend/tests/unit/services/test_wa_broker.py backend/tests/unit/routers/test_wa_broker_router.py <new envelope test> -q`
2. `PYTHONPATH=. <venv python> -m pytest backend/tests/unit/services/integrations -q -k "codex_leg or package or envelope"` (no regressions in neighbours)
3. `<venv python> -m ruff check` and `ruff format --check` on every changed/new Python file.
4. `bash -n scripts/provision_zantara_codex.sh`; `python3 -m json.tool infra/home-fork/declared-pairs.json > /dev/null`.
5. Runtime-tree import smoke that mimics Pro: build a temp dir under the session scratchpad with
   ONLY the files provisioning installs (empty `__init__.py` markers + codex_exec_client.py +
   wa_codex_daemon.py + _support_signal.py + wa_completion_envelope.py), then
   `PYTHONPATH=<tmp> python3 -c "import backend.services.integrations.wa_codex_daemon"` with a
   system python3 that has httpx (or a throwaway venv with only httpx) — it must import with no
   other backend module present. Paste the command and result.
6. `git diff --stat` and net line count.

Report: files changed, every existing test touched and why, class-audit hits, the six outputs
above, and anything in this spec you had to deviate from (with the reason). Do not claim anything
you did not run in this session.
