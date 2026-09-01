#!/usr/bin/env python3
"""MOS+ F2 — AI compression worker.

Reads pending raw_observations, groups by session_id, prompts LLM for synthesis,
INSERTs compressed memory + links via compressed_to_memory_id.

Routing matrix v2.1 (Antonello correction — peer-tier, not degraded):
  osint_sensitive=1   → Ollama qwen3.5:9b LOCAL    (Law 2 sovranità)
  default routine     → claude haiku OAuth          (cheap, fast, peer)
  batch >50 obs       → agy Gemini 3.1 Pro 1M ctx   (long context, peer)
  code-heavy          → codex GPT-5.5               (strong code, peer)
  all cloud fail      → Ollama qwen3.5:9b           (last resort, importance ≤5)

Importance caps:
  cloud peer-tier (haiku/agy/codex): ≤7
  ollama local (sovranità OR fallback): ≤5

Safeguards:
  - Idle short-circuit: exit immediately if no pending observations
  - Daily counter: cap 50 cloud calls/day (haiku+agy+codex combined)
  - Redactor pre-LLM: scrub password/token/key patterns BEFORE LLM call
  - JSON validation: skip if response missing required fields
  - TTL cleanup: discard raw>7d unpromoted
  - Retry cap: a row failing synthesis MAX_ROW_RETRIES times is discarded
    instead of retried forever (cascade-fix 2026-08-13)
  - Ollama-down alert: pages via tg_notify after
    OLLAMA_ALERT_AFTER_CONSECUTIVE_FAILS consecutive local-tier failures
    (cascade-fix 2026-08-13)

Ollama endpoint: MOS_PLUS_OLLAMA_URL env override, default is Mini's
Tailscale IP — see the OLLAMA_HOST comment below for why (cascade-fix
2026-08-13; this worker used to default to localhost, contended by
translate-articles.py's cron on the same machine).

Scheduled: every 10min via launchd. NOT inline.

Headless claude invocation (perf, 2026-09-01, D-006): the claude_haiku call runs
with `--setting-sources "" --strict-mcp-config` — a bare headless `claude -p` run
from `~/scripts` still pays full harness bootstrap (SessionStart hooks + CLAUDE.md
+ MCP schemas), measured at ~350K input tokens/call vs ~13K with these flags
(tokenaudit 2026-09-01, ~/.tokenaudit/reports/04-rightsizing.md). This compression
prompt needs no tools, no hooks, no MCP — it is a single-turn synthesis call.
"""
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import gzip
import base64
import pathlib

DB_PATH = os.path.expanduser("~/.claude/memory.db")
ERR_LOG = os.path.expanduser("~/.claude/state/mos-plus-compression.log")
COUNTER_FILE = os.path.expanduser("~/.claude/state/mos-plus-daily-calls.json")
OLLAMA_HEALTH_FILE = os.path.expanduser("~/.claude/state/mos-plus-ollama-health.json")

CLAUDE_BIN = os.path.expanduser("~/.local/bin/claude")
AGY_BIN = os.path.expanduser("~/.local/bin/agy")
CODEX_BIN = "/opt/homebrew/bin/codex"

# Cascade-fix 2026-08-13 (superscar #1+#2): was hardcoded to localhost, which
# Pro's Ollama cannot serve under load — `aisingapore/…-32B-IT:q4_k_m` sits
# resident at 24.6GB/48GB, reloaded hourly by scripts/translate-articles.py's
# cron (contention flagged, NOT fixed here — different surface). Measured
# 2026-08-13: Pro times out at 180s+ on a 3-word prompt; Mini (the fleet's
# dedicated Ollama workhorse per CLAUDE.md §Machines "Modo B") answers the
# same qwen3.5:9b model in ~2.4s. Same env-override pattern already used by
# WR2_IMAGE_VLM_URL / MATA_GARUDA_KG_BASE_URL (infra/home-fork/declared-
# pairs.json) — a dedicated var, not the shared OLLAMA_HOST some other
# scripts read, so setting one never silently retargets the other.
OLLAMA_HOST = os.environ.get("MOS_PLUS_OLLAMA_URL", "http://100.93.236.6:11434")
OLLAMA_URL = f"{OLLAMA_HOST}/api/generate"

BATCH_SIZE = 20
MAX_RUN_SEC = 300
DAILY_CAP_CLOUD = 50
BATCH_LONG_CTX_THRESHOLD = 50
LLM_TIMEOUT = 90

# Cascade-fix 2026-08-13 (superscar #2 — was: unbounded retry, `failed +=
# obs_count; continue` retried the SAME sid forever. Measured: raw_observations
# backlog 5,022→7,162 in one day while a single sid retried every tick for
# ~18h straight). A row that fails synthesis this many times stops being
# retried and is discarded instead — see _discard_rows_over_retry_cap().
MAX_ROW_RETRIES = 10

# Cascade-fix 2026-08-13: page after this many CONSECUTIVE failed calls to
# the local Ollama tier (ollama_local or ollama_fallback) — ~30min at the
# plist's StartInterval=600s. Below this, a single blip stays silent (not
# every transient timeout is an outage); at/above it, the failure that was
# invisible for 18h+ gets a voice. See _record_ollama_health().
OLLAMA_ALERT_AFTER_CONSECUTIVE_FAILS = 3

TIER_IMPORTANCE_CAP = {
    "claude_haiku": 7,
    "agy_gemini": 7,
    "codex_gpt55": 7,
    "ollama_local": 5,
    "ollama_fallback": 5,
}

REDACT_PATTERNS = [
    (r"(?i)password\s*[=:]\s*[^\s\"';]+", "password=[REDACTED]"),
    (r"(?i)token\s*[=:]\s*[^\s\"';]+", "token=[REDACTED]"),
    (r"(?i)api[_-]?key\s*[=:]\s*[^\s\"';]+", "api_key=[REDACTED]"),
    (r"AKIA[A-Z0-9]{16}", "[AWS_KEY_REDACTED]"),
    (r"-----BEGIN [A-Z ]+PRIVATE KEY-----.*?-----END [A-Z ]+PRIVATE KEY-----", "[PRIVATE_KEY_REDACTED]"),
    (r"\bsk-[a-zA-Z0-9]{32,}", "[OPENAI_KEY_REDACTED]"),
    (r"\bfm2_[a-zA-Z0-9_=]{20,}", "[FLY_TOKEN_REDACTED]"),
    (r"\bxoxb-[a-zA-Z0-9-]+", "[SLACK_TOKEN_REDACTED]"),
    (r"\bghp_[a-zA-Z0-9]{36}", "[GH_PAT_REDACTED]"),
    (r"\b[A-Za-z0-9+/]{60,}={0,2}\b", "[BASE64_REDACTED]"),
]

PROMPT_TEMPLATE = """Synthesize these raw tool observations from a Claude Code session into ONE memory entry. Output STRICTLY this JSON, no preamble, no markdown:
{{"type":"<decision|discovery|fact|unresolved|pattern>","content":"<1-3 sentence summary>","importance":<1-10>,"tags":"<comma,separated>"}}

Rules:
- type=decision: structural choice made
- type=discovery: empirical finding (file path, schema, behavior)
- type=fact: stable reference info
- type=unresolved: open question or blocker
- type=pattern: recurring workflow detected
- importance: 7 if cross-session relevant, 5-6 if session-local, lower for noise
- If observations are trivial noise (e.g. ls, cd, basic reads), output:
  {{"type":"fact","content":"SKIP","importance":1,"tags":"noise"}}

Observations:
{obs_block}
"""


def _log(msg: str) -> None:
    try:
        pathlib.Path(ERR_LOG).parent.mkdir(parents=True, exist_ok=True)
        with open(ERR_LOG, "a") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def _decompress(payload: str) -> str:
    if payload.startswith("GZIP:"):
        try:
            return gzip.decompress(base64.b64decode(payload[5:])).decode()
        except Exception:
            return payload
    return payload


def redact(text: str) -> str:
    """F2 amendment: mandatory pre-LLM redaction."""
    for pat, repl in REDACT_PATTERNS:
        text = re.sub(pat, repl, text, flags=re.DOTALL)
    return text


def load_counter() -> dict:
    today = time.strftime("%Y-%m-%d")
    if os.path.exists(COUNTER_FILE):
        try:
            c = json.load(open(COUNTER_FILE))
            if c.get("date") == today:
                return c
        except Exception:
            pass
    return {"date": today, "claude_haiku": 0, "agy_gemini": 0, "codex_gpt55": 0, "ollama_local": 0, "ollama_fallback": 0}


def save_counter(c: dict) -> None:
    try:
        json.dump(c, open(COUNTER_FILE, "w"))
    except Exception as e:
        _log(f"counter save: {e}")


def call_claude_haiku(prompt: str) -> str | None:
    try:
        r = subprocess.run(
            [
                CLAUDE_BIN, "--model", "claude-haiku-4-5-20251001",
                "--setting-sources", "", "--strict-mcp-config",
                "-p", prompt,
            ],
            capture_output=True, text=True, timeout=LLM_TIMEOUT,
            env={**os.environ, "ANTHROPIC_API_KEY": ""},
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
        if any(kw in r.stderr.lower() for kw in ["quota", "rate.limit", "exhausted", "out of"]):
            _log("claude_haiku quota exhaust signal")
        return None
    except Exception as e:
        _log(f"claude_haiku: {e}")
        return None


def call_agy_gemini(prompt: str) -> str | None:
    try:
        # agy has NO stdin path (measured 2026-08-13, matches the fix already
        # live in infra/launchagents/wrappers/*.sh and scripts/ai-dispatch.sh):
        # `-p` immediately followed by `--print-timeout` binds "--print-timeout"
        # as the literal prompt argv and leaves "2m" a stray positional; a piped
        # `input=` is never read. RC 0, garbage/empty output, quota spent for
        # nothing. Prompt must be `-p`'s own argv value.
        r = subprocess.run(
            [AGY_BIN, "-p", prompt, "--print-timeout", "2m"],
            capture_output=True, text=True, timeout=LLM_TIMEOUT,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
        return None
    except Exception as e:
        _log(f"agy_gemini: {e}")
        return None


def call_codex_gpt55(prompt: str) -> str | None:
    try:
        r = subprocess.run(
            [CODEX_BIN, "exec", "--sandbox", "read-only", "--skip-git-repo-check", prompt],
            capture_output=True, text=True, timeout=LLM_TIMEOUT,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
        return None
    except Exception as e:
        _log(f"codex_gpt55: {e}")
        return None


def call_ollama(prompt: str) -> str | None:
    import urllib.request
    body = json.dumps({
        "model": "qwen3.5:9b",
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {"temperature": 0.3, "num_predict": 400},
    }).encode()
    try:
        req = urllib.request.Request(OLLAMA_URL, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read())
            return data.get("response", "").strip()
    except Exception as e:
        _log(f"ollama: {e}")
        return None


# ---------------------------------------------------------------------------
# Cascade-fix 2026-08-13: Ollama consecutive-failure tracking + alert.
# The two functions below are pure (dict in, dict/bool out) — no disk, no
# network — so guilt/innocence tests exercise them directly without mocking
# subprocess or sqlite. _record_ollama_health() is the only caller that
# touches OLLAMA_HEALTH_FILE / the gateway.
# ---------------------------------------------------------------------------

# The gateway's verdict is parsed by the ONE canonical extractor, never by a
# private regex here. The first draft of this file carried its own
# `re.compile(r"tg_notify:\s*(\S+)")` + `.search()`, and the class guard
# scripts/tests/test_gateway_callers_read_the_verdict.py caught it — rightly,
# and for a better reason than the token name: `search()` takes the FIRST
# match, so a human diagnostic line that merely contains the prefix would have
# been read as the verdict, while extract_gateway_verdict() takes the LAST
# line that is EXACTLY a canonical verdict and returns None otherwise. Two
# parsers of one contract is superscar #9; this is the shared one.
#
# Resolved the same way as the gateway itself below: repo-relative first, then
# the deployed checkout, because this worker also runs as a HOME-fork copy
# under ~/scripts on Pro (#1). An import failure must NEVER kill the worker —
# family #2 — so it degrades to an explicit, logged unknown.
for _cand in (pathlib.Path(__file__).resolve().parents[1], pathlib.Path.home() / "nuzantara"):
    if (_cand / "scripts" / "tg_gateway_verdict.py").exists():
        sys.path.insert(0, str(_cand))
        break
try:
    from scripts.tg_gateway_verdict import extract_gateway_verdict, gateway_delivered
    _VERDICT_PARSER_AVAILABLE = True
except ImportError:  # pragma: no cover - deployment gap, reported not swallowed
    _VERDICT_PARSER_AVAILABLE = False

    def extract_gateway_verdict(stderr):  # type: ignore[misc]
        return None

    def gateway_delivered(verdict):  # type: ignore[misc]
        return False


def _next_ollama_health_state(state: dict, success: bool) -> dict:
    """Pure transition: success resets the streak, failure extends it."""
    if success:
        return {"consecutive_fails": 0}
    return {"consecutive_fails": state.get("consecutive_fails", 0) + 1}


def _should_alert_ollama_down(consecutive_fails: int) -> bool:
    """Pure predicate — the guilt/innocence boundary the tests pin."""
    return consecutive_fails >= OLLAMA_ALERT_AFTER_CONSECUTIVE_FAILS


def _load_ollama_health() -> dict:
    if os.path.exists(OLLAMA_HEALTH_FILE):
        try:
            return json.load(open(OLLAMA_HEALTH_FILE))
        except Exception:
            pass
    return {"consecutive_fails": 0}


def _save_ollama_health(state: dict) -> None:
    try:
        pathlib.Path(OLLAMA_HEALTH_FILE).parent.mkdir(parents=True, exist_ok=True)
        json.dump(state, open(OLLAMA_HEALTH_FILE, "w"))
    except Exception as e:
        _log(f"ollama health state save: {e}")


def _send_ollama_down_alert(consecutive_fails: int) -> None:
    """Best-effort page via the ONE Telegram gateway (scripts/tg_notify.py,
    cicatrix-superscar #3 anti-regrowth: never call the raw Telegram API).
    Absolute interpreter (sys.executable — the binary this process is
    actually running under, not python3 re-resolved via PATH after sourcing
    a venv, cicatrix W108), rc + gateway outcome always logged, and this
    function must NEVER raise into the caller — family #2: a broken alert
    must not become a second reason the worker dies silently."""
    gateway = pathlib.Path(__file__).resolve().parent / "tg_notify.py"
    if not gateway.exists():  # HOME-fork copy running ahead of a repo sync (#1)
        gateway = pathlib.Path.home() / "nuzantara" / "scripts" / "tg_notify.py"
    text = (
        f"mos-plus-compression: Ollama tier unreachable for {consecutive_fails} "
        f"consecutive attempts (endpoint={OLLAMA_HOST}). raw_observations "
        f"backlog is growing — check Mini reachability / model load."
    )
    argv = [
        sys.executable, str(gateway),
        "--tier", "p0", "--source", "mos-plus-compression",
        "--dedup-key", "mos-plus-ollama-tier-down",
    ]
    try:
        r = subprocess.run(argv, input=text, capture_output=True, text=True, timeout=30)
        verdict = extract_gateway_verdict(r.stderr)
        # rc==0 covers six outcomes and THREE of them mean the page did not
        # reach Telegram (deduped / p0_overflow_spooled / p0_unsent_spooled),
        # so the log names delivery vs refusal rather than the exit code (W104).
        if gateway_delivered(verdict):
            _log(f"ollama-down alert DELIVERED (tg_notify: {verdict})")
        elif verdict is not None:
            _log(f"ollama-down alert NOT DELIVERED — gateway refused/deferred it "
                 f"(tg_notify: {verdict}) — the owner has NOT been paged")
        else:
            _log("ollama-down alert verdict UNKNOWN — no canonical 'tg_notify: "
                 f"<verdict>' line on stderr (rc={r.returncode}, "
                 f"parser_available={_VERDICT_PARSER_AVAILABLE}) — treat as NOT paged")
    except Exception as e:
        _log(f"ollama-down alert subprocess error: {e}")


def _record_ollama_health(success: bool) -> None:
    """Call once per ollama-tier attempt (local or fallback). Updates the
    persisted streak and fires the alert exactly when the streak crosses
    OLLAMA_ALERT_AFTER_CONSECUTIVE_FAILS — never below it."""
    state = _next_ollama_health_state(_load_ollama_health(), success)
    _save_ollama_health(state)
    if not success and _should_alert_ollama_down(state["consecutive_fails"]):
        _send_ollama_down_alert(state["consecutive_fails"])


def _discard_rows_over_retry_cap(conn: sqlite3.Connection, ids: list[int]) -> int:
    """A row that has failed synthesis MAX_ROW_RETRIES times stops being
    retried forever (was: unconditional `continue`, family #2 — the same
    sid got requeued and retried on every 10min tick with no ceiling).
    Returns how many rows this call discarded, for the caller's own log."""
    if not ids:
        return 0
    placeholders = ",".join("?" * len(ids))
    rows = conn.execute(
        f"SELECT id FROM raw_observations WHERE id IN ({placeholders}) AND retry_count >= ?",
        (*ids, MAX_ROW_RETRIES),
    ).fetchall()
    over_ids = [r["id"] for r in rows]
    if over_ids:
        conn.executemany(
            "UPDATE raw_observations SET discarded_at=datetime('now'), "
            "discard_reason='max_retries_exceeded' WHERE id=?",
            [(i,) for i in over_ids],
        )
        conn.commit()
    return len(over_ids)


def _bump_retry_and_discard_over_cap(conn: sqlite3.Connection, obs_use: list, sid: str, reason: str) -> int:
    """Shared tail of both failure branches in main()'s per-session loop
    (unreachable/timed-out tier, and a tier that answered but unparseably) —
    same cap, same discard, one place instead of two copies drifting apart."""
    ids = [o["id"] for o in obs_use]
    conn.executemany(
        "UPDATE raw_observations SET retry_count = retry_count + 1 WHERE id=?",
        [(i,) for i in ids],
    )
    conn.commit()
    n_discarded = _discard_rows_over_retry_cap(conn, ids)
    if n_discarded:
        _log(f"sid={sid[:8]} discarded {n_discarded} row(s) over retry cap ({MAX_ROW_RETRIES}, reason={reason})")
    return n_discarded


def detect_code_heavy(obs_block: str) -> bool:
    """Heuristic: more than 2 Bash tool calls with code-like content."""
    bash_count = obs_block.count("post_tool_use/Bash:")
    code_signals = sum(1 for kw in ["def ", "class ", "function ", "import ", "fly deploy", "alembic"] if kw in obs_block)
    return bash_count > 2 and code_signals >= 2


def choose_tier(obs_count: int, osint_sensitive: bool, obs_block: str, counter: dict, force_local: bool) -> str:
    """Returns tier name based on routing matrix v2.1."""
    if osint_sensitive:
        return "ollama_local"
    if force_local:
        return "ollama_fallback"

    cloud_used = counter["claude_haiku"] + counter["agy_gemini"] + counter["codex_gpt55"]
    if cloud_used >= DAILY_CAP_CLOUD:
        return "ollama_fallback"

    if obs_count > BATCH_LONG_CTX_THRESHOLD:
        return "agy_gemini"
    if detect_code_heavy(obs_block):
        return "codex_gpt55"
    return "claude_haiku"


def call_tier(tier: str, prompt: str) -> str | None:
    if tier == "claude_haiku":
        return call_claude_haiku(prompt)
    if tier == "agy_gemini":
        return call_agy_gemini(prompt)
    if tier == "codex_gpt55":
        return call_codex_gpt55(prompt)
    if tier in ("ollama_local", "ollama_fallback"):
        result = call_ollama(prompt)
        # Cascade-fix 2026-08-13: this is the ONE call site both the direct
        # choice AND the ollama_fallback retry (below, in main()) go through,
        # so a single hook here sees every ollama-tier attempt.
        _record_ollama_health(result is not None)
        return result
    return None


def parse_summary(output: str) -> dict | None:
    """Parse JSON summary. Strip markdown fences if present."""
    if not output:
        return None
    txt = output.strip()
    if "```" in txt:
        m = re.search(r"```(?:json)?\s*(.+?)```", txt, re.DOTALL)
        if m:
            txt = m.group(1).strip()
    try:
        start = txt.find("{")
        end = txt.rfind("}") + 1
        if start < 0 or end <= start:
            return None
        s = json.loads(txt[start:end])
        if not {"type", "content", "importance"}.issubset(s.keys()):
            return None
        if s["type"] not in ("decision", "discovery", "fact", "unresolved", "pattern"):
            return None
        return s
    except Exception:
        return None


def main():
    t0 = time.time()
    force_local = False

    # Connect
    try:
        conn = sqlite3.connect(DB_PATH, timeout=5.0)
        conn.row_factory = sqlite3.Row
    except sqlite3.Error as e:
        _log(f"db connect: {e}")
        sys.exit(1)

    # Cascade-fix 2026-08-13: per-row retry counter (idempotent — sqlite has
    # no `ADD COLUMN IF NOT EXISTS`; catch the duplicate-column error instead
    # of doing our own schema-version bookkeeping for one column).
    try:
        conn.execute(
            "ALTER TABLE raw_observations ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0"
        )
        conn.commit()
    except sqlite3.OperationalError as e:
        if "duplicate column" not in str(e).lower():
            raise

    # F6 amendment: TTL cleanup first (raw>7d unpromoted)
    try:
        conn.execute("""
            UPDATE raw_observations
            SET discarded_at = datetime('now'), discard_reason = 'ttl_7d'
            WHERE compressed_to_memory_id IS NULL
              AND discarded_at IS NULL
              AND captured_at < datetime('now', '-7 days')
        """)
        conn.commit()
    except Exception as e:
        _log(f"ttl cleanup: {e}")

    # F6 amendment: idle short-circuit
    pending = conn.execute("""
        SELECT COUNT(*) FROM raw_observations
        WHERE compressed_to_memory_id IS NULL AND discarded_at IS NULL
    """).fetchone()[0]
    if pending == 0:
        _log("idle (no pending), exit clean")
        conn.close()
        sys.exit(0)

    _log(f"start: pending={pending}")
    counter = load_counter()

    # Pull batch (max 3 sessions per run)
    rows = conn.execute("""
        SELECT id, session_id, source, tool_name, payload_json, captured_at, osint_sensitive
        FROM raw_observations
        WHERE compressed_to_memory_id IS NULL AND discarded_at IS NULL
        ORDER BY session_id, captured_at
        LIMIT ?
    """, (BATCH_SIZE * 3,)).fetchall()

    sessions: dict[str, list] = {}
    for r in rows:
        sessions.setdefault(r["session_id"], []).append(r)

    promoted = skipped = failed = discarded_retry_cap = 0
    for sid, obs in sessions.items():
        if time.time() - t0 > MAX_RUN_SEC:
            _log(f"MAX_RUN_SEC hit, exit partial (promoted={promoted})")
            break

        # Use only first BATCH_SIZE obs per session this run
        obs_use = obs[:BATCH_SIZE]
        obs_count = len(obs_use)
        any_sensitive = any(o["osint_sensitive"] == 1 for o in obs_use)

        # Build obs block (truncate + redact each)
        obs_block_parts = []
        for o in obs_use:
            decoded = _decompress(o["payload_json"])[:500]
            redacted = redact(decoded)
            obs_block_parts.append(f"[{o['captured_at']}] {o['source']}/{o['tool_name']}: {redacted}")
        obs_block = "\n".join(obs_block_parts)

        tier = choose_tier(obs_count, any_sensitive, obs_block, counter, force_local)
        _log(f"sid={sid[:8]} obs={obs_count} sensitive={any_sensitive} → tier={tier}")

        prompt = PROMPT_TEMPLATE.format(obs_block=obs_block)
        output = call_tier(tier, prompt)

        if not output and tier != "ollama_fallback":
            _log(f"sid={sid[:8]} tier={tier} fail, falling to ollama_fallback")
            tier = "ollama_fallback"
            output = call_tier(tier, prompt)

        if not output:
            failed += obs_count
            discarded_retry_cap += _bump_retry_and_discard_over_cap(conn, obs_use, sid, "call fail")
            continue

        counter[tier] = counter.get(tier, 0) + 1
        summary = parse_summary(output)
        if not summary:
            _log(f"sid={sid[:8]} tier={tier} parse fail")
            failed += obs_count
            discarded_retry_cap += _bump_retry_and_discard_over_cap(conn, obs_use, sid, "parse fail")
            continue

        if summary.get("content", "").strip().upper() == "SKIP":
            ids = [o["id"] for o in obs_use]
            conn.executemany(
                "UPDATE raw_observations SET discarded_at=datetime('now'), discard_reason='noise_skip' WHERE id=?",
                [(i,) for i in ids],
            )
            conn.commit()
            skipped += len(ids)
            continue

        # Apply importance cap
        importance = min(int(summary.get("importance", 5)), TIER_IMPORTANCE_CAP[tier])

        # Insert compressed memory
        tags = (summary.get("tags", "") or "") + f",auto_compressed,{tier}"
        cur = conn.execute(
            "INSERT INTO memories (session_id, type, content, importance, tags) "
            "VALUES (?, ?, ?, ?, ?)",
            (sid, summary["type"], summary["content"], importance, tags.lstrip(",")),
        )
        mem_id = cur.lastrowid

        # Link raw observations
        ids = [o["id"] for o in obs_use]
        conn.executemany(
            "UPDATE raw_observations SET compressed_to_memory_id=? WHERE id=?",
            [(mem_id, i) for i in ids],
        )
        conn.commit()
        promoted += len(ids)
        _log(f"sid={sid[:8]} promoted mem_id={mem_id} importance={importance} type={summary['type']}")

    save_counter(counter)
    conn.close()
    _log(
        f"done: promoted={promoted} skipped={skipped} failed={failed} "
        f"discarded_retry_cap={discarded_retry_cap} elapsed={int(time.time()-t0)}s counter={counter}"
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
