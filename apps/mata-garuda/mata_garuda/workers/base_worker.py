"""
Mata Garuda — Base worker for Redis Stream consumers.

Workers read from garuda:raw, process items, and write to garuda:enriched.
Uses redis-cli subprocess — no redis-py dependency (stack-minimal, CLAUDE.md §1).

Cross-host topology (2026-05-06): when GARUDA_REDIS_HOST is set, every
redis-cli call is routed to that host (with optional GARUDA_REDIS_PORT).

Stage 1 single-writer cure (2026-06-29, spec mata-garuda-stage1-single-writer,
3-LLM panel + Zero G1=Pro): there is ONE canonical Redis = Pro. The old silent
localhost fallback (which caused the split-brain: each host talked to its own
local Redis) is replaced by an EXPLICIT canonical default. Resolution order for
the host:
  1. GARUDA_REDIS_HOST (explicit override — e.g. a future replica) wins.
  2. else GARUDA_CANONICAL_REDIS_HOST (the declared canonical; set in every plist).
  3. a canonical of ''/localhost/127.0.0.1 means "this IS Pro / opt-out" → no -h.
This makes "explicit beats implicit" structural (red-team #2): an off-Pro cron
that forgets GARUDA_REDIS_HOST still hits the canonical, never its own localhost.

redis-cli is resolved to an ABSOLUTE path (_resolve_redis_cli) so cron/non-login
shells with a stripped PATH stop failing mutely — the 'watchdog unarmed' bug,
verified live on Pro 2026-06-29.
"""
from __future__ import annotations

import hashlib
import logging
import os
import shutil
import subprocess
import time

logger = logging.getLogger("mata_garuda.workers")

# Hosts that mean "connect to the local Redis" → emit no -h flag.
_LOCAL_HOST_SENTINELS = frozenset({"", "localhost", "127.0.0.1", "::1"})

# Where redis-cli typically lives when PATH is stripped (launchd/cron, non-login).
_REDIS_CLI_FALLBACKS = (
    "/opt/homebrew/bin/redis-cli",
    "/usr/local/bin/redis-cli",
    "/usr/bin/redis-cli",
)


def _resolve_redis_cli() -> str:
    """Resolve redis-cli to an absolute path; fall back to bare name as last resort.

    Cron/launchd shells strip PATH, so a bare 'redis-cli' raises FileNotFoundError
    and the worker dies mutely. Prefer shutil.which, then known install paths.
    """
    found = shutil.which("redis-cli")
    if found:
        return found
    for candidate in _REDIS_CLI_FALLBACKS:
        if os.path.exists(candidate):
            return candidate
    return "redis-cli"


REDIS_CLI = _resolve_redis_cli()


def _resolve_redis_host() -> str:
    """The effective Redis host: explicit override, else declared canonical."""
    explicit = (os.environ.get("GARUDA_REDIS_HOST") or "").strip()
    if explicit:
        return explicit
    return (os.environ.get("GARUDA_CANONICAL_REDIS_HOST") or "").strip()


def _redis_host_args() -> list[str]:
    """Return ['-h', host] (and optional ['-p', port]) for the effective host.

    A local sentinel (''/localhost/127.0.0.1/::1) emits no -h (redis-cli default).
    GARUDA_REDIS_PORT is honored only when a real host is in play.
    """
    host = _resolve_redis_host()
    if host in _LOCAL_HOST_SENTINELS:
        return []
    args = ["-h", host]
    port = (os.environ.get("GARUDA_REDIS_PORT") or "").strip()
    if port:
        args += ["-p", port]
    return args


def _redis_env() -> dict[str, str] | None:
    """Return a subprocess env carrying REDISCLI_AUTH when a password is set.

    Stage 1 cutover (2026-06-29): the canonical Pro Redis is exposed on the
    Tailscale interface and requires a password. We pass it via REDISCLI_AUTH
    (redis-cli reads it natively) rather than `-a <pw>` on argv, which would
    leak the secret into `ps`/argv (cicatrix #4: secret in the clear).
    Returns None when no password is set, so the default env is used.
    """
    pw = (os.environ.get("GARUDA_REDIS_PASSWORD") or "").strip()
    if not pw:
        return None
    env = dict(os.environ)
    env["REDISCLI_AUTH"] = pw
    return env


def redis_cmd(*args: str, timeout: int = 10, retries: int = 2) -> str:
    """Execute a redis-cli command and return output.

    Retries on TimeoutExpired only (transient host-load scheduling delay,
    not a real network/redis fault — 2026-07-08 intel-bridge investigation
    found 100% publish failures correlating with Mini load average 25-38,
    all timing out at the default 10s with zero retry). A short fixed
    backoff between attempts lets a scheduling spike clear rather than
    hammering an already-loaded host immediately. retries=2 means up to
    3 total attempts; set retries=0 to preserve the old single-shot
    behavior for any caller that wants a strict fail-fast.
    """
    cmd = [REDIS_CLI] + _redis_host_args() + list(args)
    attempts = retries + 1
    last_timeout = timeout
    for attempt in range(attempts):
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout, env=_redis_env()
            )
            if result.returncode != 0:
                return f"[ERROR] redis-cli: {result.stderr.strip()}"
            return result.stdout.strip()
        except FileNotFoundError:
            return "[ERROR] redis-cli not found"
        except subprocess.TimeoutExpired:
            last_timeout = timeout
            if attempt < attempts - 1:
                time.sleep(1.5 * (attempt + 1))
                continue
    return f"[ERROR] redis-cli timeout after {last_timeout}s ({attempts} attempts)"


def stream_read_new(
    stream: str,
    group: str,
    consumer: str,
    count: int = 10,
    block_ms: int = 0,
) -> list[dict]:
    """Read new items from a Redis Stream consumer group.

    Creates the group if it doesn't exist.
    Returns list of {id, data} dicts.
    """
    # Ensure group exists
    redis_cmd("XGROUP", "CREATE", stream, group, "0", "MKSTREAM")

    args = ["XREADGROUP", "GROUP", group, consumer, "COUNT", str(count)]
    if block_ms > 0:
        args += ["BLOCK", str(block_ms)]
    args += ["STREAMS", stream, ">"]

    result = redis_cmd(*args)
    if not result or result.startswith("[ERROR]"):
        return []

    return _parse_xreadgroup(result, stream)


def stream_ack(stream: str, group: str, msg_id: str) -> bool:
    """Acknowledge a message in a consumer group.

    Returns True if XACK confirmed the message was in PEL and got acked,
    False if Redis returned 0 (msg not in PEL — silent failure, e.g. the
    cleaner already drained it, or msg_id was wrong) or the redis-cli
    invocation errored.

    Callers that don't care about ack failure can ignore the return value;
    backward-compatible. Callers that DO care (e.g. graceful PEL-overflow
    detection) can act on False.

    W14 (2026-05-22): added return value + WARNING log on silent ack-zero
    to make PEL stuck-orphan issues visible from worker logs without
    requiring a separate XPENDING audit. See W13 cicatrix for the
    accumulation pattern this catches.
    """
    result = redis_cmd("XACK", stream, group, msg_id)
    if result.startswith("[ERROR]"):
        logger.warning(
            "[stream_ack] redis-cli error acking %s/%s/%s: %s",
            stream, group, msg_id, result,
        )
        return False
    try:
        acked = int(result.strip())
    except ValueError:
        logger.warning(
            "[stream_ack] unparseable XACK reply for %s/%s/%s: %r",
            stream, group, msg_id, result,
        )
        return False
    if acked == 0:
        logger.warning(
            "[stream_ack] XACK returned 0 for %s/%s/%s — msg not in PEL "
            "(already drained, wrong id, or race)",
            stream, group, msg_id,
        )
        return False
    return True


def stream_publish(stream: str, data: dict) -> str:
    """Publish data to a Redis Stream. Returns message ID."""
    fields = []
    for k, v in data.items():
        fields.extend([k, str(v) if not isinstance(v, str) else v])

    # MAXLEN ~ N: approximate-trim the stream on every publish (council fix —
    # bounded RAM, O(1)). Multiple consumer groups stay safe: ~ trims only whole
    # macro-nodes and never below entries a group still needs within the cap.
    from mata_garuda.config import STREAM_MAXLEN
    result = redis_cmd("XADD", stream, "MAXLEN", "~", str(STREAM_MAXLEN), "*", *fields)
    return result


def content_hash(text: str) -> str:
    """SHA256 hash for deduplication."""
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _is_msg_id(line: str) -> bool:
    """True if `line` looks like a Redis Stream message ID (timestamp-seq).

    Empty/whitespace lines return False (so they are NOT mistaken for IDs
    and can flow through as legitimate empty values in the field stream).
    """
    if not line:
        return False
    if not line[0].isdigit():
        return False
    if "-" not in line:
        return False
    # Defensive: confirm timestamp-seq shape (digits-digits)
    parts = line.split("-", 1)
    return len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit()


def _parse_xreadgroup(raw: str, stream: str) -> list[dict]:
    """Parse XREADGROUP output into list of {id, data} dicts.

    redis-cli output format is not JSON — it's a flat list of alternating
    keys and values. We parse it line by line.

    Empty values (e.g. ``entity_nip`` blank for an Organization gap) are
    PRESERVED as empty strings, not silently dropped. The previous
    implementation stripped empty lines wholesale, which shifted every
    key/value pair after the first empty value and silently corrupted
    `gap_type`, `attribute`, etc. Discovered 2026-05-16 during Pilastro 1
    reflection regression debug — see research/symbiosis/.../dispatch-alias.
    """
    items = []
    # Preserve empty lines (they may be empty values); only rstrip the
    # trailing whitespace + \r introduced by redis-cli line-buffering.
    lines = [line.rstrip() for line in raw.split("\n")]

    i = 0
    while i < len(lines):
        line = lines[i]
        if _is_msg_id(line):
            msg_id = line
            data = {}
            # Read key-value pairs until the next message ID. Empty lines
            # between two non-ID lines are real values, not separators.
            j = i + 1
            while j < len(lines) and not _is_msg_id(lines[j]):
                if j + 1 < len(lines):
                    key = lines[j]
                    val = lines[j + 1]
                    if key:  # field names are always non-empty
                        data[key] = val
                    j += 2
                else:
                    break
            if data:
                items.append({"id": msg_id, "data": data})
            i = j
        else:
            i += 1

    return items
