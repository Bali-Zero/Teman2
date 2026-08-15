#!/usr/bin/env python3
"""BOT-V2 gate: static lint for the WA-bot's OpenAI provider surface.

Mandate: task #14 (BOT-V2, "mandato 5"), team-lead spec 2026-08-15. Turns
the §Gate V2 spec (G1..G20) drafted in `research/operations/2026-08-15-
bot-openai-provider-threat-model.md` (verifier lane V1, branch
`agent/air-m5/ops/bot-provider-verifier`) into an EXECUTABLE lint, scoped to
what is statically checkable today — see `NOT_STATICALLY_CHECKABLE` below
for the rest, with the reason each is excluded rather than faked.

Pure stdlib, no repo import, no backend venv needed — same shape as
`scripts/ci/quarantine_lint.py` (the stated precedent).

BUILT-NOT-ARMED: this script is not wired into any GitHub Actions workflow
by this PR (team-lead instruction #5 — tests.yml is hot post-#4181, and
CI-wiring is deliberately a follow-up PR, not bundled here).

── Scope ────────────────────────────────────────────────────────────────
`SCOPE_DIRS` below — the bot-adapter perimeter per team-lead's mandate:
`backend/llm/`, `backend/services/rag/agentic/`, `backend/channels/`,
`backend/scripts/bot/`. Declared as one constant, not hardcoded per-check.
`backend/scripts/bot/` does not exist on `origin/main` yet (the two files
citing it — `build_deid_corpus.py`, `wa_blind_bench.py` — are uncommitted
WIP in the implementer's sibling worktree per the threat model's §Live diff
review) — a missing scope dir is scanned as zero files, not an error, so
this check activates automatically once that directory lands.

── Exemptions (declared, per team-lead instruction #4) ─────────────────
- Only `*.py` files are scanned — `research/`, `docs/`, and any `*.md` are
  categorically out of scope. The verifier's own threat-model document
  QUOTES every one of these forbidden patterns verbatim as a worked
  example — if this lint scanned `.md` files it would trip on its own
  source spec. Restricting to `.py` under the 4 declared source dirs
  achieves this without a second, ad-hoc doc-exclusion list.
- `tests/` directories anywhere under a scope dir are excluded — a test
  FIXTURE legitimately contains the guilty string as literal test data
  (see this script's own `test_bot_provider_gate.py`, which uses tmp_path
  synthetic trees precisely so its corpus never touches the real tree and
  never needs this exemption in the first place).
- `scripts/ci/` (this script's own directory) is not one of the 4 scope
  dirs and is never scanned — no self-trip is possible by construction.

── ANTHROPIC_API_KEY — deliberately NOT re-implemented here ─────────────
Verified this session: `.github/workflows/catE-sovereignty-lint.yml`
already bans, repo-wide, `Anthropic(api_key=...)` construction and
`ANTHROPIC_API_KEY=<value>` assignment (2026-06-11 audit, #40/#40b). Per
team-lead's explicit instruction, re-implementing that ban here would be a
second, drifting copy of an existing gate — this script instead assumes
that check stands and does not duplicate it. `CLAUDE_CODE_OAUTH_TOKEN`
specifically AS A WA-BOT RUNTIME CREDENTIAL is a distinct, narrower
invariant (the bot's LLM backend must never be a `claude` CLI subprocess)
and IS checked below (G-claude-cli).

Exit codes: 0 = clean. 1 = violation(s) found. 2 = usage/scan error.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# ── Scope: the bot-adapter perimeter, one declared constant ─────────────────
SCOPE_DIRS: tuple[str, ...] = (
    "apps/backend-rag/backend/llm",
    "apps/backend-rag/backend/services/rag/agentic",
    "apps/backend-rag/backend/channels",
    "apps/backend-rag/backend/scripts/bot",
)

EXCLUDED_DIR_PARTS = {"tests", "__pycache__", ".venv", "node_modules"}

# The ONE pre-existing, sanctioned consumer of CLAUDE_CODE_OAUTH_TOKEN that
# legitimately lives inside a scope dir — found by the live dry-run against
# origin/main this session, not assumed in advance. `llm/claude_oauth_client.py`
# is CLAUDE.md §5's canonical "sole sanctioned path" for CLAUDE integrations
# generally (its own docstring names its 3 consumers: article_composer,
# coreference, multi_ai_adapter.ClaudeAdapter — none of them the WA-bot/
# OpenAI-adapter surface this gate exists to fence). Banning that token
# bare-substring INSIDE the one module whose entire job is reading it
# correctly would be exactly the scar-#3 over-match this script's docstring
# warns against elsewhere — the real risk (a NEW WA-bot-adapter file reading
# this token, or shelling out to `claude` as its own LLM backend) is what
# G1's other sub-patterns and G-claude-cli independently catch; this
# allowlist entry narrows ONLY the bare-token-mention sub-check, not G1 as a
# whole, and not this file's other lines.
PRE_EXISTING_CLAUDE_OAUTH_TOKEN_CONSUMERS = frozenset({"apps/backend-rag/backend/llm/claude_oauth_client.py"})

# ── Patterns NOT statically checkable here — declared, not faked ────────────
# Each is a runtime/dataflow property (call-graph, semantic response-shape
# comparison, or a behavioral-default audit V1's own doc already tracks
# separately) that a regex/AST-free lint cannot verify without false
# positives or false negatives it cannot bound. Contract tests on the real
# hooks (separate deliverable, not this script) cover several of these on
# origin/main already — see this task's earlier session work.
NOT_STATICALLY_CHECKABLE: dict[str, str] = {
    "G3": "tool-call arguments pass through _strip_reserved_args before "
    "tool.execute() — a call-graph property, not a textual pattern; "
    "already covered by a real contract test "
    "(backend/tests/unit/services/rag/agentic/test_tool_executor.py).",
    "G4": "every tool-call passes through tool_authorizer.authorize() — "
    "same call-graph limitation as G3; already covered by "
    "backend/tests/unit/agents/test_tool_authorizer.py.",
    "G6": "citation normalization to the {source_ref,...} dict contract — "
    "requires executing _normalize_citations against real inputs, not a "
    "grep; already covered by "
    "backend/tests/services/rag/agentic/test_rag_agentic_pipeline.py.",
    "G8": "logging/tracing calls never interpolate raw user_id/phone/query "
    "— an f-string content-flow property; a bare regex over call sites "
    "would both miss indirect interpolation and false-positive on "
    "legitimate opaque-id logging. Covered instead by a direct unit "
    "test on the real redaction function "
    "(backend/tests/unit/services/integrations/test_bot_v2_pii_log_redaction.py).",
    "G9": "zero direct cache-write call sites outside NotebookLMCacheService"
    ".set() — requires a real call-graph across the whole adapter module, "
    "not reliably expressible as a regex without over- or under-matching.",
    "G10": "/api/agentic-rag/query response schema identity across "
    "providers — a runtime schema-equality property, not static text.",
    "G12": "an `available`/readiness property re-reads its source live vs. "
    "caching at construction — requires understanding property semantics "
    "(what does the body actually call?), not just presence of a docstring "
    "claim; a false claim of 'live' next to cached code is exactly the "
    "kind of docstring/behavior mismatch a lint can't safely arbitrate.",
    "G13": "asyncio.create_task(...) is stored in a tracked set with a "
    "concurrency cap — a bare 'unassigned create_task(' regex would "
    "false-positive on legitimate patterns (e.g. `tasks = [asyncio."
    "create_task(c) for c in coros]`) and cannot verify a semaphore exists "
    "elsewhere in the module; needs real dataflow analysis.",
    "G14": "a shadow/comparison branch receives the SAME assembled context "
    "(history, tools) as the primary call — a cross-call-site data-parity "
    "property, not a single-file pattern.",
    "G18": "orchestrator_streaming_core.py's `getattr(state, "
    "'trusted_tools_used', True)` fail-open default — ALREADY FOUND and "
    "recorded by the V1 threat model (§Gate V2 spec, G18) as a "
    "pre-existing defect on origin/main, deliberately scoped OUT of the "
    "OpenAI-adapter PR into its own follow-up (flipping a default read by "
    "the live Gemini path is a behavior change to production traffic, not "
    "a bot-adapter credential/pattern check). Re-detecting it here would "
    "conflate two different gate categories; tracked instead in this "
    "PR's body as a pointer back to that finding.",
    "G19": "OpenAI Responses refusal/incomplete terminal states map to the "
    "same abstain/handoff contract as a Gemini abstain — requires running "
    "the adapter against a real or synthetic response payload, not text "
    "matching.",
}

# ── G1: OAuth-session-consumer credential ban (verified 0 baseline in scope,
# EXCEPT the one pre-existing sanctioned consumer allowlisted below) ────────
_CLAUDE_TOKEN_LABEL = "CLAUDE_CODE_OAUTH_TOKEN as a WA-bot runtime credential"
OAUTH_CONSUMER_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("CODEX_HOME env pointed at a runtime secret store", re.compile(r"\bCODEX_HOME\b")),
    (
        "codex exec/login subprocess invocation (ChatGPT/Codex OAuth-session credential)",
        re.compile(r"[\"']codex[\"']\s*,\s*[\"'](exec|login)[\"']|\bcodex\s+(exec|login)\b"),
    ),
    ("~/.codex/auth.json read at runtime", re.compile(r"\.codex[/\\]auth\.json")),
    (
        "chat.openai.com / platform.openai.com session-cookie surface",
        re.compile(r"chat\.openai\.com|platform\.openai\.com"),
    ),
    (_CLAUDE_TOKEN_LABEL, re.compile(r"\bCLAUDE_CODE_OAUTH_TOKEN\b")),
)

# ── G-claude-cli: the bot's LLM backend must never shell out to `claude` ────
CLAUDE_CLI_PATTERN = re.compile(
    r"subprocess\.[A-Za-z_]+\(\s*\[[^\]]*[\"']claude[\"']|"
    r"[\"']claude[\"']\s*,\s*[\"'](--print|exec)[\"']"
)

# ── G2/G20: bare shared-key ban — the WA-bot perimeter's ONLY sanctioned name
# is settings.openai_wa_provider_api_key / OPENAI_WA_PROVIDER_API_KEY ────────
BANNED_KEY_READ_RE = re.compile(
    r"settings\.openai_api_key\b"
    r"|os\.environ\[\s*[\"']OPENAI_API_KEY[\"']\s*\]"
    r"|os\.environ\.get\(\s*[\"']OPENAI_API_KEY[\"']"
    r"|os\.getenv\(\s*[\"']OPENAI_API_KEY[\"']"
)
# Word-boundary guard (scar #3 substring-trap, per team-lead's explicit
# warning): OPENAI_WA_PROVIDER_API_KEY must NEVER be mistaken for a hit on
# the bare OPENAI_API_KEY pattern above. BANNED_KEY_READ_RE's own anchors
# (`settings.openai_api_key\b`, quoted-literal `"OPENAI_API_KEY"`) already
# cannot match inside `openai_wa_provider_api_key` / `OPENAI_WA_PROVIDER_
# API_KEY` — pinned explicitly by test_g2_innocence_dedicated_key_name_
# never_matches_bare_ban in the test corpus, not just asserted here.

# ── G16 (positive-allowlist spirit, checked as a targeted ban): OpenAI-native
# tool types — verified 0 baseline in scope (repo's own "web_search" registry
# lives under services/agents/, not services/rag/agentic/) ─────────────────
BANNED_NATIVE_TOOL_TYPES = ("web_search", "file_search", "mcp", "image_generation", "computer_use_preview")
TOOL_TYPE_RE = re.compile(r"[\"']type[\"']\s*:\s*[\"'](" + "|".join(BANNED_NATIVE_TOOL_TYPES) + r")[\"']")

# ── G17: AsyncOpenAI(base_url=...) pinning ───────────────────────────────────
ALLOWED_BASE_URL_PREFIXES = ("https://api.openai.com", "https://api.deepseek.com", "http://localhost:11434")
BASE_URL_CALL_RE = re.compile(r"AsyncOpenAI\([^)]*base_url\s*=\s*[\"']([^\"']+)[\"']", re.DOTALL)

# ── G11: every Responses-API payload sets "store": false ────────────────────
RESPONSES_CREATE_CALL_RE = re.compile(r"\.responses\.create\(")
STORE_KEY_RE = re.compile(r"[\"']store[\"']\s*:")
G11_WINDOW_CHARS = 800  # bounded lookahead from the call site, not full-file

# ── G15: a docstring/comment citing a research/operations/*.md path that
# does not exist on disk (phantom-ADR ban, scar family #6) ─────────────────
RESEARCH_DOC_CITATION_RE = re.compile(r"research/operations/[A-Za-z0-9_.\-]+\.md")


@dataclass(frozen=True)
class Finding:
    rule: str
    path: str
    line: int
    detail: str

    def render(self) -> str:
        return f"[{self.rule}] {self.path}:{self.line}: {self.detail}"


def _iter_py_files(scope_dir: Path) -> list[Path]:
    if not scope_dir.is_dir():
        return []
    out: list[Path] = []
    for p in scope_dir.rglob("*.py"):
        if any(part in EXCLUDED_DIR_PARTS for part in p.parts):
            continue
        out.append(p)
    return out


def _all_scope_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for scope in SCOPE_DIRS:
        files.extend(_iter_py_files(repo_root / scope))
    return files


def check_g1_oauth_consumer(files: list[Path], repo_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = str(path.relative_to(repo_root))
        is_pre_existing_claude_oauth_consumer = rel in PRE_EXISTING_CLAUDE_OAUTH_TOKEN_CONSUMERS
        for lineno, line in enumerate(text.splitlines(), start=1):
            for label, pattern in OAUTH_CONSUMER_PATTERNS:
                if label == _CLAUDE_TOKEN_LABEL and is_pre_existing_claude_oauth_consumer:
                    continue  # see PRE_EXISTING_CLAUDE_OAUTH_TOKEN_CONSUMERS docstring
                if pattern.search(line):
                    findings.append(Finding("G1", rel, lineno, f"OAuth-consumer pattern ({label}): {line.strip()[:160]}"))
            if CLAUDE_CLI_PATTERN.search(line):
                findings.append(
                    Finding(
                        "G-claude-cli",
                        rel,
                        lineno,
                        f"bot LLM backend shells out to the `claude` CLI (banned runtime shape): {line.strip()[:160]}",
                    )
                )
    return findings


def check_g2_g20_key_reuse(files: list[Path], repo_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = str(path.relative_to(repo_root))
        for lineno, line in enumerate(text.splitlines(), start=1):
            if BANNED_KEY_READ_RE.search(line):
                findings.append(
                    Finding(
                        "G2/G20",
                        rel,
                        lineno,
                        "bot perimeter reads the shared embeddings/voice OPENAI_API_KEY directly — "
                        "must use settings.openai_wa_provider_api_key / OPENAI_WA_PROVIDER_API_KEY: "
                        f"{line.strip()[:160]}",
                    )
                )
    return findings


def check_g16_native_tool_types(files: list[Path], repo_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = str(path.relative_to(repo_root))
        for lineno, line in enumerate(text.splitlines(), start=1):
            for m in TOOL_TYPE_RE.finditer(line):
                findings.append(
                    Finding(
                        "G16",
                        rel,
                        lineno,
                        f"OpenAI-native tool type {m.group(1)!r} in tool schema (G5/G16, retrieval/authorizer bypass): "
                        f"{line.strip()[:160]}",
                    )
                )
    return findings


def check_g17_base_url_pin(files: list[Path], repo_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = str(path.relative_to(repo_root))
        for m in BASE_URL_CALL_RE.finditer(text):
            base_url = m.group(1)
            if not any(base_url.startswith(p) for p in ALLOWED_BASE_URL_PREFIXES):
                lineno = text.count("\n", 0, m.start()) + 1
                findings.append(
                    Finding(
                        "G17",
                        rel,
                        lineno,
                        f"AsyncOpenAI(base_url={base_url!r}) not in the pinned allowlist {ALLOWED_BASE_URL_PREFIXES}",
                    )
                )
    return findings


def check_g11_store_false(files: list[Path], repo_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = str(path.relative_to(repo_root))
        for m in RESPONSES_CREATE_CALL_RE.finditer(text):
            window = text[m.end() : m.end() + G11_WINDOW_CHARS]
            if not STORE_KEY_RE.search(window):
                lineno = text.count("\n", 0, m.start()) + 1
                findings.append(
                    Finding(
                        "G11",
                        rel,
                        lineno,
                        f'.responses.create(...) call with no "store" key in the following '
                        f"{G11_WINDOW_CHARS} chars — every Responses API payload must explicitly "
                        f'set "store": false (regression tripwire, see threat model G11).',
                    )
                )
    return findings


def check_g15_phantom_adr(files: list[Path], repo_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = str(path.relative_to(repo_root))
        for m in RESEARCH_DOC_CITATION_RE.finditer(text):
            cited = m.group(0)
            if not (repo_root / cited).exists():
                lineno = text.count("\n", 0, m.start()) + 1
                findings.append(
                    Finding(
                        "G15",
                        rel,
                        lineno,
                        f"cites {cited!r} as authority but that file does not exist on disk "
                        f"(phantom-citation ban, scar family #6 / threat-model Finding 0 / G15)",
                    )
                )
    return findings


def run(repo_root: Path) -> list[Finding]:
    files = _all_scope_files(repo_root)
    findings: list[Finding] = []
    findings.extend(check_g1_oauth_consumer(files, repo_root))
    findings.extend(check_g2_g20_key_reuse(files, repo_root))
    findings.extend(check_g16_native_tool_types(files, repo_root))
    findings.extend(check_g17_base_url_pin(files, repo_root))
    findings.extend(check_g11_store_false(files, repo_root))
    findings.extend(check_g15_phantom_adr(files, repo_root))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".", help="repo root, defaults to cwd")
    parser.add_argument(
        "--list-not-checkable",
        action="store_true",
        help="print the NOT_STATICALLY_CHECKABLE table and exit 0",
    )
    args = parser.parse_args(argv)

    if args.list_not_checkable:
        for rule, reason in NOT_STATICALLY_CHECKABLE.items():
            print(f"{rule}: {reason}")
        return 0

    repo_root = Path(args.repo_root).resolve()
    missing_scope = [s for s in SCOPE_DIRS if not (repo_root / s).is_dir()]
    for s in missing_scope:
        print(f"::notice::scope dir not present yet (scanned as 0 files): {s}", file=sys.stderr)

    findings = run(repo_root)
    if findings:
        print(f"::error::bot_provider_gate found {len(findings)} violation(s):", file=sys.stderr)
        for f in findings:
            print(f"::error::{f.render()}", file=sys.stderr)
        return 1

    scanned = len(_all_scope_files(repo_root))
    print(f"OK: bot_provider_gate — 0 violations across {scanned} files under {SCOPE_DIRS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
