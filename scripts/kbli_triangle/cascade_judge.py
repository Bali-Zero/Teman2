"""KBLI Triangle — Layer-2 via multi-LLM cascade (Codex GPT-5.5 propose + Gemini refute).

Why not the Workflow engine: it runs agent() on the Claude MAX model, which hit the
5h session limit twice on 277 fields. This script shells out to Codex (ChatGPT Ultra,
separate quota) for PROPOSE and Gemini agy (Google AI Ultra, separate quota) for
REFUTE — generator≠grader is now also cross-LLM (stronger). Claude/Opus stays the
final L3 gate, run separately.

Per field we send a SLIM record (code, judul, pma_status, pma_max_asing, l4_bali,
the field text) — not the 5MB dataset — so each call is small and fast. The model
returns a single JSON line we parse. Concurrency via a thread pool; failures are
recorded, never crash the batch. Resumable: skips fields already in _out/cascade-results.jsonl.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
OUT = Path(__file__).resolve().parent / "_out"
REDO = OUT / "redo-fields.json"
RESULTS = OUT / "cascade-results.jsonl"

WORKERS = 6  # parallel subprocess calls


def load_rows() -> dict:
    raw = json.loads(DATASET.read_text())
    rows = raw["data"] if isinstance(raw, dict) and "data" in raw else raw
    return {str(r.get("kode_kbli_2025")): r for r in rows}


def slim(rec: dict, field: str) -> dict:
    f = field.split(".")[-1]
    return {
        "code": str(rec.get("kode_kbli_2025")),
        "judul": rec.get("judul"),
        "pma_status": rec.get("pma_status"),
        "pma_max_asing": rec.get("pma_max_asing"),
        "l4_bali": rec.get("l4_bali"),
        "field_name": f,
        "field_text": (rec.get("intel_2026") or {}).get(f, ""),
    }


def _extract_json(text: str) -> dict | None:
    # find the last {...} block the model emitted
    m = re.findall(r"\{.*\}", text, re.S)
    for blob in reversed(m):
        try:
            return json.loads(blob)
        except Exception:
            continue
    return None


def codex_propose(s: dict) -> dict | None:
    prompt = (
        "You are a KBLI editorial-truth analyzer. Here is a slim KBLI record as JSON:\n"
        + json.dumps(s, ensure_ascii=False)
        + "\n\nThe deterministic layer flagged field '"
        + s["field_name"]
        + "' as possibly misleading: it may promise a foreign-owned PT PMA setup on a code whose structural verdict (l4_bali.blocked) forbids a PT PMA in Bali. "
        "Decide: is the text genuinely MISLEADING? Rules: 'open nationally' is TRUE and not misleading by itself; only an UNQUALIFIED Bali-PMA go-ahead is. If the text already names the Bali block, it is NOT misleading. "
        "Reply with ONLY one JSON object on the last line: "
        '{"is_misleading": true|false, "reason": "...", "suggested_value": "corrected text citing only regulations in the record (l4_bali.reason, moratorium.source, pma_source) — never invented", "confidence": "HIGH|MEDIUM|LOW"}'
    )
    try:
        p = subprocess.run(
            ["codex", "exec", "--sandbox", "read-only", "--skip-git-repo-check", prompt],
            capture_output=True, text=True, timeout=180,
        )
        return _extract_json(p.stdout)
    except Exception as e:
        return {"_error": f"codex: {e}"}


def gemini_refute(s: dict, proposal: dict) -> dict | None:
    prompt = (
        "You are a KBLI adversarial refuter. A prior analyzer claims field '"
        + s["field_name"]
        + "' on code "
        + s["code"]
        + " is MISLEADING and proposes a replacement. Here is the slim record:\n"
        + json.dumps(s, ensure_ascii=False)
        + "\n\nProposal: " + json.dumps(proposal, ensure_ascii=False)
        + "\n\nTry to REFUTE. Check: is the code REALLY blocked for a PT PMA in Bali (l4_bali.blocked, pma_status, no Besar scale)? Does the cited regulation actually support the claim? Is the original text already fine (already qualifies the Bali block)? "
        "Default to refuted=true if you are NOT confident the original is genuinely misleading. "
        'Reply with ONLY one JSON object on the last line: {"refuted": true|false, "reason": "..."}'
    )
    try:
        p = subprocess.run(
            ["agy", "-p", "--print-timeout", "3m"],
            input=prompt, capture_output=True, text=True, timeout=240,
        )
        return _extract_json(p.stdout)
    except Exception as e:
        return {"_error": f"gemini: {e}"}


def judge(item: dict, rows: dict) -> dict:
    code, field = item["code"], item["field"]
    rec = rows.get(code, {})
    s = slim(rec, field)
    prop = codex_propose(s)
    out = {"code": code, "field": field, "propose": prop}
    if prop and prop.get("is_misleading") and not prop.get("_error"):
        out["refute"] = gemini_refute(s, prop)
    else:
        out["refute"] = {"refuted": False, "reason": "no claim or propose-error"}
    return out


def main() -> None:
    rows = load_rows()
    todo = json.loads(REDO.read_text())
    done = set()
    if RESULTS.exists():
        for line in RESULTS.read_text().splitlines():
            if line.strip():
                try:
                    r = json.loads(line)
                    done.add((r["code"], r["field"]))
                except Exception:
                    pass
    todo = [t for t in todo if (t["code"], t["field"]) not in done]
    print(f"to judge: {len(todo)} (skipping {len(done)} already done)")

    n = 0
    with RESULTS.open("a") as f, ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(judge, it, rows): it for it in todo}
        for fut in as_completed(futs):
            r = fut.result()
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.flush()
            n += 1
            if n % 10 == 0:
                print(f"  {n}/{len(todo)} judged")
    print(f"done: {n} judged this run")


if __name__ == "__main__":
    main()
