"""Incident detector — groups related failures into single incidents.

Algorithm: Sliding Window Fingerprinting (Gemini recommendation, validated).
1. Normalize: strip timestamps, hex IDs, PIDs from error messages
2. Fingerprint: MD5 hash of normalized string
3. Window: if same fingerprint appears N+ times within T minutes across
   different jobs, cluster into one incident
4. Report: "Incident #N: X jobs failing with 'Y' on Node:Z"

Alternative for v2: drain3 (pip install drain3) — production-grade log
template mining. Consider if regex fingerprinting proves too coarse.
"""
import hashlib
import re
import time

# Normalization regexes — strip volatile parts of error messages
STRIP_PATTERNS = [
    (r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[.\d]*[Z]?", "TIMESTAMP"),
    (r"0x[0-9a-fA-F]+", "HEX"),
    (r"PID[= ]\d+", "PID"),
    (r"pid=\d+", "PID"),
    (r"port[= ]\d+", "PORT"),
    (r"consecutiveErrors=\d+", "consecutiveErrors=N"),
    (r"attempt \d+/\d+", "attempt N/M"),
    (r"\d+\.\d+\.\d+\.\d+", "IP"),
]

MIN_CLUSTER_SIZE = 3
WINDOW_S = 600  # 10 minutes


def normalize_error(error: str) -> str:
    """Strip volatile parts from error message for fingerprinting."""
    result = error
    for pattern, replacement in STRIP_PATTERNS:
        result = re.sub(pattern, replacement, result)
    return result.strip()


def fingerprint(error: str) -> str:
    """MD5 hash of normalized error."""
    normalized = normalize_error(error)
    return hashlib.md5(normalized.encode()).hexdigest()[:12]


def detect_incidents(failures: list, window_s: int = WINDOW_S) -> list:
    """Group failures into incidents.

    Args:
        failures: list of {"job": str, "error": str, "ts": float}

    Returns:
        list of incidents: {"fingerprint": str, "normalized_error": str,
                           "jobs": list[str], "count": int, "first_ts": float}
    """
    now = time.time()
    recent = [f for f in failures if now - f.get("ts", 0) < window_s]

    clusters: dict = {}
    for f in recent:
        err = f.get("error", "")
        if not err or len(err) < 10:
            continue
        fp = fingerprint(err)
        if fp not in clusters:
            clusters[fp] = {
                "fingerprint": fp,
                "normalized_error": normalize_error(err)[:200],
                "jobs": [],
                "count": 0,
                "first_ts": f.get("ts", now),
            }
        clusters[fp]["jobs"].append(f.get("job", "?"))
        clusters[fp]["count"] += 1

    return [c for c in clusters.values() if c["count"] >= MIN_CLUSTER_SIZE]
