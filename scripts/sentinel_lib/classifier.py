"""Failure classifier: deterministic rules first, Haiku LLM fallback."""
import re
import os
import json
import urllib.request
import urllib.parse
from typing import Optional

TRANSIENT_PATTERNS = [
    r"HTTP 5\d\d",
    r"connection refused",
    r"ETIMEDOUT",
    r"temporarily unavailable",
    r"service unavailable",
    r"Connection reset",
    r"timeout expired",
    r"SIGTERM",
    # OpenClaw delivery noise: the agent ran successfully, Telegram announce failed.
    # Retrying the full job won't fix a transient API blip.
    r"Message failed",
    r"Delivering to .* requires",
    r"Channel is required",
    # LLM API outage (observed in run history): all models unavailable, will self-recover.
    r"All models failed",
    # Gateway-side timeout: job was too slow, not a code error.
    r"cron: job execution timed out",
    # OpenClaw 1-2 consecutive errors — transient blip, safe to retry.
    r"consecutiveErrors=[12][,\s]",
]

# These are NEVER retried — retrying would just repeat the same failure.
# Escalate directly to the correct fix tier.
DETERMINISTIC_PATTERNS = [
    (r"SyntaxError", "syntax_error"),
    (r"ImportError|ModuleNotFoundError", "import_error"),
    (r"Permission denied", "permission_error"),
    (r"No such file or directory", "missing_file"),
    (r"NameError|AttributeError|TypeError", "code_bug"),
    (r"dict\[.*\] \| None", "py39_type_syntax"),
    (r"lsof: command not found", "missing_binary"),
    (r"SMTP.*[Ff]ailed|Authentication.*[Ff]ailed", "smtp_auth"),
    # OpenClaw job config errors: wrong payload type or missing API key in the agent env.
    (r"isolated job requires payload\.kind=agentTurn", "job_config_error"),
    (r"No API key found for provider", "missing_api_key"),
    # OpenClaw persistent failure: 3+ consecutive errors → restart needed.
    (r"consecutiveErrors=(?:[3-9]|[1-9]\d+)[,\s]", "openclaw_persistent_error"),
]

FIX_PATTERNS = {
    "py39_type_syntax": {
        "description": "Python 3.9 type union syntax — requires 3.10+",
        "fix_instruction": "Replace all `X | Y` type annotations with `Optional[X]` or `Union[X, Y]` from typing",
        "confidence": 0.95,
    },
    "import_error": {
        "description": "Missing Python package or wrong import path",
        "fix_instruction": "Check virtualenv activation and install missing package. Check absolute import paths.",
        "confidence": 0.85,
    },
    "missing_binary": {
        "description": "Required binary not in PATH",
        "fix_instruction": "Install missing tool via brew or replace with stdlib equivalent",
        "confidence": 0.90,
    },
    "smtp_auth": {
        "description": "SMTP authentication failure",
        "fix_instruction": "Check SMTP_LOGIN and SMTP_PASS environment variables",
        "confidence": 0.85,
    },
    "missing_api_key": {
        "description": "API key not configured in agent auth-profiles.json",
        "fix_instruction": (
            "Run `openclaw agents add <agent-id>` to configure auth, "
            "or copy auth-profiles.json from the main agent dir to the cron agent dir."
        ),
        "confidence": 0.90,
    },
    "job_config_error": {
        "description": "OpenClaw job payload type mismatch",
        "fix_instruction": (
            "Edit the job via `openclaw cron edit <id> --message <text>` "
            "to ensure payload.kind=agentTurn, or change sessionTarget."
        ),
        "confidence": 0.95,
    },
    "openclaw_persistent_error": {
        "description": "OpenClaw job failing 3+ consecutive times — restart needed",
        "fix_instruction": (
            "Trigger the job manually via the OpenClaw UI or: "
            "openclaw cron run <openclaw_id> --timeout 30000. "
            "If it fails again, check ~/.openclaw/workspace/logs/ for the agent turn error."
        ),
        "confidence": 0.90,
    },
}


def classify(error_text: str, retry_count: int = 0) -> dict:
    """
    Returns dict with keys: type (TRANSIENT|DETERMINISTIC|UNKNOWN),
    subtype (str), fix_pattern (dict|None), confidence (float).
    """
    if not error_text:
        return {"type": "UNKNOWN", "subtype": "no_error_text", "fix_pattern": None, "confidence": 0.0}

    # Check transient first
    for pattern in TRANSIENT_PATTERNS:
        if re.search(pattern, error_text, re.IGNORECASE):
            # If same error repeats 2+ times, escalate to DETERMINISTIC
            if retry_count >= 2:
                return {"type": "DETERMINISTIC", "subtype": "repeated_transient", "fix_pattern": None, "confidence": 0.8}
            return {"type": "TRANSIENT", "subtype": "network_or_service", "fix_pattern": None, "confidence": 0.9}

    # Check deterministic
    for pattern, subtype in DETERMINISTIC_PATTERNS:
        if re.search(pattern, error_text, re.IGNORECASE):
            fix = FIX_PATTERNS.get(subtype)
            return {
                "type": "DETERMINISTIC",
                "subtype": subtype,
                "fix_pattern": fix,
                "confidence": fix["confidence"] if fix else 0.7,
            }

    # Fallback: unknown — treat as TRANSIENT once, then escalate
    return {"type": "UNKNOWN", "subtype": "unclassified", "fix_pattern": None, "confidence": 0.0}


def classify_with_llm(error_text: str, job_name: str) -> dict:
    """
    Call Claude Haiku to classify failure when rules return UNKNOWN.
    Returns same shape as classify(). Falls back to UNKNOWN if API fails.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"type": "UNKNOWN", "subtype": "no_api_key", "fix_pattern": None, "confidence": 0.0}

    prompt = f"""You are diagnosing a failed automation job named "{job_name}".
Error output (last 20 lines):
{error_text[-2000:]}

Classify this failure as one of:
- TRANSIENT: network issue, service temporarily down, timeout — safe to retry
- DETERMINISTIC: code bug, missing file, permission error — retrying won't help
- UNKNOWN: cannot determine

Respond with JSON only:
{{"type": "TRANSIENT|DETERMINISTIC|UNKNOWN", "subtype": "one_word_reason", "fix_suggestion": "one sentence fix", "confidence": 0.0-1.0}}"""

    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 256,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()

    try:
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read())
            text = body["content"][0]["text"]
            result = json.loads(text)
            return {
                "type": result.get("type", "UNKNOWN"),
                "subtype": result.get("subtype", "llm_classified"),
                "fix_pattern": {"fix_instruction": result.get("fix_suggestion"), "confidence": result.get("confidence", 0.5)} if result.get("fix_suggestion") else None,
                "confidence": result.get("confidence", 0.5),
            }
    except Exception:
        return {"type": "UNKNOWN", "subtype": "llm_failed", "fix_pattern": None, "confidence": 0.0}
