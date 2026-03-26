"""Log Anomaly detector reflex — 50ms latency budget.
Regex-based pattern detection. No LLM."""
import re
from dataclasses import dataclass, field

ERROR_PATTERN = re.compile(r"(Error|Exception|Failure|Panic|Timeout|OOM)", re.IGNORECASE)
FATAL_KEYWORDS = ("SIGKILL", "FATAL", "SEGV", "SIGSEGV", "SIGTERM")

@dataclass
class LogAnomaly:
    anomaly: bool = False
    reason: str = ""
    critical_keywords: list[str] = field(default_factory=list)

def detect_anomaly(lines: list[str], recent_window: int = 10) -> LogAnomaly:
    """Detect anomalies in log lines."""
    result = LogAnomaly()
    for line in lines:
        for keyword in FATAL_KEYWORDS:
            if keyword in line:
                result.anomaly = True
                if keyword not in result.critical_keywords:
                    result.critical_keywords.append(keyword)
    if result.critical_keywords:
        result.reason = f"Critical keywords found: {', '.join(result.critical_keywords)}"
        return result
    recent = lines[-recent_window:] if len(lines) >= recent_window else lines
    error_count = sum(1 for line in recent if ERROR_PATTERN.search(line))
    if error_count > 2:
        result.anomaly = True
        result.reason = f"Error spike: {error_count} errors in last {recent_window} lines"
    return result
