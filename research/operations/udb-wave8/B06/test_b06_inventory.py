"""Independent negative checks for the projected public-source inventory."""
import csv
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import pytest

BASE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("b06_inventory_tested", BASE/"b06_inventory.py")
inventory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)

def test_inventory_membership_counts_and_unknown_coverage():
    data = inventory.load_inventory()
    with (BASE/"fixtures/consumer-matrix-metadata.csv").open(newline="") as handle:
        ids = {r["consumer_id"] for r in csv.DictReader(handle)}
    assert {r["consumer_id"] for r in data["records"]} == ids
    stats = inventory.summary(data)
    assert stats["source_rows"] == 6029
    assert stats["traced_rows"] + stats["untraced_rows"] == 6029
    assert set(stats["family_candidates"]) == set(inventory.FAMILIES)
    assert all(v["traced_rows"] > 3 for v in stats["family_candidates"].values())
    assert stats["block_closed"] is False
    assert all(r["family_assignment"] != "CONFIRMED" for r in data["records"])

def _mutated(tmp_path, mutate):
    data = inventory.load_inventory()
    mutate(data)
    path = tmp_path/"inventory.gz"
    path.write_bytes(gzip.compress(json.dumps(data).encode(),mtime=0))
    manifest = tmp_path/"provenance.json"
    manifest.write_text(json.dumps({"projection_sha256":inventory.sha(path)}))
    return path, manifest

def test_projection_tamper_fails_closed(tmp_path):
    p = tmp_path/"inventory.gz"
    p.write_bytes((BASE/"fixtures/source-inventory.json.gz").read_bytes()+b"tamper")
    with pytest.raises(ValueError, match="B06_INVENTORY_PIN_MISMATCH"):
        inventory.load_inventory(p,BASE/"fixtures/source-inventory-provenance.json")

def test_duplicate_consumer_is_rejected_even_with_updated_projection_digest(tmp_path):
    p,m = _mutated(tmp_path,lambda d:d["records"].__setitem__(0,d["records"][1]))
    with pytest.raises(ValueError, match="B06_INVENTORY_MEMBERSHIP_INVALID"):
        inventory.load_inventory(p,m)

def test_non_public_source_is_rejected_even_with_updated_projection_digest(tmp_path):
    p,m = _mutated(tmp_path,lambda d:d["records"][0].__setitem__("source_path","../outside.py"))
    with pytest.raises(ValueError, match="B06_PUBLIC_PATH_INVALID"):
        inventory.load_inventory(p,m)

def test_store_outside_admitted_membership_is_rejected(tmp_path):
    p,m = _mutated(tmp_path,lambda d:d["records"][0].__setitem__("store_id","pg:unknown:invented"))
    with pytest.raises(ValueError, match="B06_STORE_MEMBERSHIP_INVALID"):
        inventory.load_inventory(p,m)

def test_loop_and_exception_anchors_do_not_claim_retries_or_runtime_effects():
    source = "async def sample(db):\n    for item in []:\n        try:\n            await db.execute('INSERT INTO synthetic VALUES (1)')\n        except Exception:\n            pass\n"
    traces,error = inventory.static_traces(source)
    assert error is None
    assert len(traces) == 1
    assert traces[0]["entry_line"] == 1
    assert traces[0]["operation_line"] == 4
    assert traces[0]["failure_try_line"] == 3
    assert traces[0]["failure_handler_lines"] == [5]
    assert traces[0]["loop_line"] == 2
    assert traces[0]["retry_semantics"] == "UNKNOWN_LOOP_IS_NOT_PROOF_OF_RETRY"
    assert traces[0]["effect"] == "STATIC_CALL_ONLY_RUNTIME_EFFECT_UNKNOWN"

def test_all_captured_source_hashes_and_line_anchors_match():
    root = BASE.parents[3]
    data = inventory.load_inventory()
    for row in data["records"]:
        if row["source_path"] is None:
            assert "SOURCE_NOT_PUBLIC_TRACKED_CODE" in row["unknowns"]
            continue
        p = root/row["source_path"]
        assert inventory.sha(p) == row["source_sha256"]
        count = len(p.read_text(encoding="utf-8",errors="replace").splitlines())
        for trace in row["traces"]:
            assert 1 <= trace["entry_line"] <= trace["operation_line"] <= count
            assert trace["operation_line"] <= trace["operation_end_line"] <= count

def test_generated_submissions_preserve_unknown_principals_and_operation_ids():
    data = inventory.load_inventory()
    records = inventory.operation_submissions(data)
    assert len(records) == inventory.summary(data)["operation_signals"]
    assert len(records) > 21
    for record in records:
        assert record["operation_id"] == "UNASSIGNED_B05"
        assert record["role"] == {"value":"UNKNOWN","status":"UNKNOWN","evidence_ref":None}
        assert record["principal"]["status"] == "UNKNOWN"
        assert record["retries"]["status"] == "UNKNOWN"
        assert record["failure"]["status"] == "UNKNOWN"
        assert record["status"] == "PARTIAL"
        assert "OPERATION_ID_PENDING_B05" in record["unknowns"]


def test_decorator_call_is_anchored_outside_function_body():
    traces,error = inventory.static_traces('@router.get("synthetic")\nasync def route():\n    return None\n')
    assert error is None
    assert traces[0]["entry_line"] == 1
    assert traces[0]["operation_line"] == 1
