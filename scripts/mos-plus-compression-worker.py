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

Scheduled: every 10min via launchd. NOT inline.
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

CLAUDE_BIN = os.path.expanduser("~/.local/bin/claude")
AGY_BIN = os.path.expanduser("~/.local/bin/agy")
CODEX_BIN = "/opt/homebrew/bin/codex"
OLLAMA_URL = "http://localhost:11434/api/generate"

BATCH_SIZE = 20
MAX_RUN_SEC = 300
DAILY_CAP_CLOUD = 50
BATCH_LONG_CTX_THRESHOLD = 50
LLM_TIMEOUT = 90

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
            [CLAUDE_BIN, "--model", "claude-haiku-4-5-20251001", "-p", prompt],
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
        r = subprocess.run(
            [AGY_BIN, "-p", "--print-timeout", "2m"],
            input=prompt, capture_output=True, text=True, timeout=LLM_TIMEOUT,
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
        return call_ollama(prompt)
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

    promoted = skipped = failed = 0
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
            continue

        counter[tier] = counter.get(tier, 0) + 1
        summary = parse_summary(output)
        if not summary:
            _log(f"sid={sid[:8]} tier={tier} parse fail")
            failed += obs_count
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
    _log(f"done: promoted={promoted} skipped={skipped} failed={failed} elapsed={int(time.time()-t0)}s counter={counter}")
    sys.exit(0)


if __name__ == "__main__":
    main()
