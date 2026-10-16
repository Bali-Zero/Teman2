"""Pinned public-code inventory; source hints never establish business-domain coverage."""
from __future__ import annotations
import argparse
import ast
import csv
import gzip
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess

SOURCE_SHA = "c09e14328f391d2615d320b6dc4218bf35a37e76fb847c46659a8db0f9326118"
FAMILIES = {
    "D04": ("crm", "client", "practice", "visa", "company", "tax", "property"),
    "D05": ("pricing", "invoice", "payment", "billing", "garuda"),
    "D06": ("channel", "conversation", "whatsapp", "telegram", "outbox", "chat"),
    "D07": ("rag", "kbli", "knowledge_graph", "qdrant", "embedding", "retrieval"),
    "D08": ("document", "intake", "drive", "upload", "asset", "ocr"),
    "D09": ("wr2", "wr3", "war_room", "news", "editorial", "post_publish"),
    "D10": ("research", "intel", "memory", "agent"),
}
METHODS = {"execute", "executemany", "fetch", "fetchrow", "fetchval", "upsert",
           "insert", "update", "delete", "set", "get", "publish", "send",
           "send_message", "write_text", "write_bytes", "commit", "rollback"}
DETAILS = ("principal", "role", "tenant", "authorization", "transaction",
           "effects", "retries", "idempotency", "failure", "retention", "recovery")
BASE = Path(__file__).resolve().parent

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def approved_path(path, tracked):
    p = Path(path)
    return (path in tracked and not p.is_absolute() and ".." not in p.parts
            and p.parts[0] in {"apps", "scripts", "packages", "libs"}
            and p.suffix in {".py", ".ts", ".tsx", ".js", ".sql", ".sh"}
            and not p.name.startswith(".env"))

def family_candidates(path):
    # Tokenize after removing the common backend-rag package prefix.
    scope = path.removeprefix("apps/backend-rag/backend/")
    return [key for key, terms in FAMILIES.items()
            if any(term in scope.lower() for term in terms)]

def static_traces(text):
    """Capture syntax anchors, never SQL literals, argument values or identifiers."""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return [], "STATIC_PARSER_UNAVAILABLE"
    parent = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent[child] = node
    traces = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        method = node.func.attr
        if method not in METHODS:
            continue
        ancestors = []
        cursor = parent.get(node)
        while cursor is not None:
            ancestors.append(cursor)
            cursor = parent.get(cursor)
        fn = next((n for n in ancestors if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.lineno <= node.lineno), None)
        attempt = next((n for n in ancestors if isinstance(n, ast.Try)), None)
        loop = next((n for n in ancestors if isinstance(n, (ast.For, ast.While, ast.AsyncFor))), None)
        verb = "CALL_" + method.upper()
        if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            match = re.match(r"\s*(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP)\b",
                             node.args[0].value, re.IGNORECASE)
            if match:
                verb = "SQL_" + match.group(1).upper()
        traces.append({
            "entry_line": fn.lineno if fn else 1,
            "entry_end_line": fn.end_lineno if fn else getattr(tree, "end_lineno", None),
            "operation_line": node.lineno, "operation_end_line": node.end_lineno,
            "operation_signal": verb,
            "effect": "STATIC_CALL_ONLY_RUNTIME_EFFECT_UNKNOWN",
            "failure_try_line": attempt.lineno if attempt else None,
            "failure_handler_lines": [h.lineno for h in attempt.handlers] if attempt else [],
            "loop_line": loop.lineno if loop else None,
            "retry_semantics": "UNKNOWN_LOOP_IS_NOT_PROOF_OF_RETRY",
        })
    return sorted(traces, key=lambda item: (item["operation_line"], item["operation_signal"])), None

def capture(root, matrix, bindings, catalog, output):
    if sha(matrix) != SOURCE_SHA:
        raise ValueError("B06_SOURCE_PIN_MISMATCH")
    tracked = set(subprocess.check_output(["git", "-C", str(root), "ls-files"], text=True).splitlines())
    with matrix.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 6029 or len({r["consumer_id"] for r in rows}) != 6029:
        raise ValueError("B06_CONSUMER_MEMBERSHIP_INVALID")
    with bindings.open(newline="") as handle:
        stores = {r["consumer_id"]: r["store_id"] for r in csv.DictReader(handle)}
    store_ids = {s["store_id"] for s in json.loads(catalog.read_text())["stores"]}
    store_ids.add("unknown:unknown:unknown")
    result = []
    for row in rows:
        cid = row["consumer_id"]
        if not re.fullmatch(r"[A-Za-z0-9_-]+", cid):
            raise ValueError("B06_CONSUMER_ID_REJECTED")
        raw = row["entry_point"]
        path = raw.split(":")[0]
        approved = approved_path(path, tracked) and (root/path).is_file()
        candidates = family_candidates(path) if approved else []
        item = {
            "consumer_id": cid, "source_path": path if approved else None,
            "entry_identity_sha256": hashlib.sha256(raw.encode()).hexdigest(),
            "family_candidates": candidates,
            "family_assignment": "PATH_INFERENCE_NOT_BUSINESS_MEMBERSHIP" if candidates else "UNKNOWN",
            "store_id": stores.get(cid, "unknown:unknown:unknown"),
            "store_membership": "B04_CATALOG" if stores.get(cid) in store_ids and stores.get(cid) != "unknown:unknown:unknown" else "UNRESOLVED",
            "source_sha256": sha(root/path) if approved else None,
            "traces": [], "unknowns": ["STATIC_SOURCE_ONLY", "RUNTIME_EFFECT_UNOBSERVED",
                "ACTOR_IDENTITY_UNRESOLVED", "OPERATION_ID_PENDING_B05",
                "FAILURE_RETRY_SEMANTICS_UNVERIFIED", "BUSINESS_DOMAIN_MEMBERSHIP_UNVERIFIED",
                "CALL_TARGET_SEMANTICS_UNVERIFIED", "STORE_BINDING_NOT_CALL_TARGET_PROOF"],
        }
        if item["store_id"] not in store_ids:
            item["store_id"] = "unknown:unknown:unknown"
        if approved and candidates and path.endswith(".py"):
            item["traces"], error = static_traces((root/path).read_text(encoding="utf-8", errors="replace"))
            if error:
                item["unknowns"].append(error)
        if not approved:
            item["unknowns"].append("SOURCE_NOT_PUBLIC_TRACKED_CODE")
        if not item["traces"]:
            item["unknowns"].append("OPERATION_TRACE_UNAVAILABLE")
        result.append(item)
    data = {"schema": "b06-public-code-inventory-v1", "source_csv_sha256": SOURCE_SHA,
            "source_rows": 6029, "source_version": subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip(),
            "evidence_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "bindings_sha256": sha(bindings), "catalog_sha256": sha(catalog),
            "valid_store_ids": sorted(store_ids), "records": result}
    output.write_bytes(gzip.compress((json.dumps(data, sort_keys=True, separators=(",", ":"))+"\n").encode(), mtime=0))
    return data

def load_inventory(path=BASE/"fixtures/source-inventory.json.gz", manifest=BASE/"fixtures/source-inventory-provenance.json"):
    pin = json.loads(manifest.read_text())
    if sha(path) != pin["projection_sha256"]:
        raise ValueError("B06_INVENTORY_PIN_MISMATCH")
    data = json.loads(gzip.decompress(path.read_bytes()))
    if data["source_csv_sha256"] != SOURCE_SHA or data["source_rows"] != 6029:
        raise ValueError("B06_SOURCE_IDENTITY_INVALID")
    records = data["records"]
    if len(records) != 6029 or len({r["consumer_id"] for r in records}) != 6029:
        raise ValueError("B06_INVENTORY_MEMBERSHIP_INVALID")
    for row in records:
        path_value = row["source_path"]
        if path_value and (Path(path_value).is_absolute() or ".." in Path(path_value).parts
                           or Path(path_value).parts[0] not in {"apps", "scripts", "packages", "libs"}):
            raise ValueError("B06_PUBLIC_PATH_INVALID")
        if row["store_id"] not in data["valid_store_ids"]:
            raise ValueError("B06_STORE_MEMBERSHIP_INVALID")
    return data

def summary(data):
    records = data["records"]
    return {"source_rows": len(records), "public_source_rows": sum(bool(r["source_path"]) for r in records),
            "traced_rows": sum(bool(r["traces"]) for r in records),
            "operation_signals": sum(len(r["traces"]) for r in records),
            "untraced_rows": sum(not r["traces"] for r in records),
            "family_candidates": {f: {"candidate_rows": sum(f in r["family_candidates"] for r in records),
                "traced_rows": sum(f in r["family_candidates"] and bool(r["traces"]) for r in records)}
                for f in FAMILIES},
            "count_semantics": "Overlapping public-path candidate sets, not business-domain denominators",
            "block_closed": False}

def operation_submissions(data):
    result = []
    for row in data["records"]:
        for trace in row["traces"]:
            ref = row["source_path"]+":"+str(trace["operation_line"])
            record = {
                "consumer_id": row["consumer_id"], "operation_id": "UNASSIGNED_B05",
                "store_id": row["store_id"], "source_version": data["source_version"],
                "evidence_timestamp": data["evidence_timestamp"], "evidence_sha256": row["source_sha256"],
                "status": "PARTIAL", "unknowns": list(row["unknowns"]),
            }
            if row["store_id"] == "unknown:unknown:unknown":
                record["unknowns"].append("STORE_ID_PROPOSED:unknown:unknown:unknown")
            for field in DETAILS:
                record[field] = {"value": "UNKNOWN", "status": "UNKNOWN", "evidence_ref": None}
            record["effects"] = {"value": trace["operation_signal"]+"; runtime effect UNKNOWN",
                                  "status": "PARTIAL", "evidence_ref": ref}
            record.update({"x_family_candidates": row["family_candidates"], "x_entry_point": row["source_path"],
                           "x_static_trace": trace, "x_family_assignment": row["family_assignment"]})
            result.append(record)
    return result

def read_captured_source_bytes(root, row, source_version):
    """Verify the recorded revision, using local Git objects only after tree drift."""
    path = Path(row["source_path"])
    root = Path(root).resolve()
    if (path.is_absolute() or ".." in path.parts or not path.parts
            or path.parts[0] not in {"apps", "scripts", "packages", "libs"}):
        raise ValueError("B06_CAPTURE_SOURCE_PATH_REJECTED")
    if not re.fullmatch(r"[a-f0-9]{40}", source_version):
        raise ValueError("B06_CAPTURE_SOURCE_VERSION_REJECTED")
    expected = row["source_sha256"]
    if not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected):
        raise ValueError("B06_CAPTURE_SOURCE_IDENTITY_REJECTED")
    current = root/path
    if current.is_file() and current.resolve().is_relative_to(root):
        raw = current.read_bytes()
        if hashlib.sha256(raw).hexdigest() == expected:
            return raw
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "show", source_version + ":" + path.as_posix()],
            capture_output=True,
        )
    except OSError:
        raise ValueError("B06_CAPTURE_SOURCE_CONTEXT_UNAVAILABLE") from None
    if result.returncode or hashlib.sha256(result.stdout).hexdigest() != expected:
        raise ValueError("B06_CAPTURE_SOURCE_CONTEXT_UNAVAILABLE")
    return result.stdout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", action="store_true")
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--matrix", type=Path)
    parser.add_argument("--bindings", type=Path)
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--output", type=Path, default=BASE/"fixtures/source-inventory.json.gz")
    parser.add_argument("--emit-instances", type=Path)
    parser.add_argument("--emit-validation-payload", type=Path)
    args = parser.parse_args()
    if args.capture:
        data = capture(args.repo_root, args.matrix, args.bindings, args.catalog, args.output)
        provenance = {"schema": "b06-inventory-provenance-v1", "source_csv_sha256": SOURCE_SHA,
            "projection_sha256": sha(args.output), "producer_source_sha256": sha(Path(__file__)),
            "source_head": subprocess.check_output(["git", "-C", str(args.repo_root), "rev-parse", "HEAD"], text=True).strip(),
            "source_is_original_c09": True, "projection_is_not_original_bytes": True,
            "native_probe_executed": False,
            "command": "python -I -B b06_inventory.py --capture --repo-root REPO --matrix PINNED_C09 --bindings B04_BINDINGS --catalog B04_CATALOG"}
        (BASE/"fixtures/source-inventory-provenance.json").write_text(json.dumps(provenance, indent=2)+"\n")
    else:
        data = load_inventory()
    if args.emit_instances:
        args.emit_instances.write_text(json.dumps(operation_submissions(data), separators=(",", ":"))+"\n")
    if args.emit_validation_payload:
        payload = {"original": json.loads((BASE/"domain-operation-instances.json").read_text()), "additional": operation_submissions(data), "valid_consumer_ids": [r["consumer_id"] for r in data["records"]]}
        args.emit_validation_payload.write_bytes(gzip.compress(json.dumps(payload, separators=(",", ":")).encode(), mtime=0))
    print(json.dumps(summary(data), sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
