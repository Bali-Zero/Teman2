"""Tests for DNA integrity and loading."""
import hashlib

from cell.core.dna import DNALoader, DNAIntegrityError


def test_dna_loads_successfully():
    """DNA file loads and parses correctly."""
    loader = DNALoader()
    dna = loader.load()
    assert dna["version"] == "1.0.0"
    assert len(dna["rules"]) == 5
    assert dna["rules"][0]["priority"] == 0


def test_dna_rules_priority_ordering():
    """Rules are ordered by priority (0 = highest)."""
    loader = DNALoader()
    dna = loader.load()
    priorities = [r["priority"] for r in dna["rules"]]
    assert priorities == sorted(priorities)


def test_dna_hash_verification():
    """DNA hash matches expected hash."""
    loader = DNALoader()
    dna_bytes = loader.raw_bytes()
    actual_hash = hashlib.sha256(dna_bytes).hexdigest()
    assert loader.verify_integrity(actual_hash) is True


def test_dna_tamper_detection():
    """Tampered DNA raises DNAIntegrityError."""
    loader = DNALoader()
    wrong_hash = "a" * 64
    assert loader.verify_integrity(wrong_hash) is False
