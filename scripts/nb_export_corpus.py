#!/usr/bin/env python3
"""nb_export_corpus.py — PII-safe NotebookLM corpus export (Coherence Guardian, Phase A).

WHY THIS EXISTS
---------------
The "Coherence Guardian" needs the regulatory ground-truth NBs on disk so a
long-context LLM (agy / Gemini) can cross-check them against published carousels
and regulatory deltas in a single pass. The NBs are NOT on disk — they live only
behind NotebookLM, reachable one source at a time. This script crawls a
WHITELISTED set of NBs and writes each source's full text to disk as a resumable,
checkpointed job.

THREE NON-NEGOTIABLE GUARDRAILS (CLAUDE.md §5, §14 / SYMBIOSIS Law 2)
---------------------------------------------------------------------
1. PII BOUNDARY (ABSOLUTE): only NBs on the explicit WHITELIST below are crawled.
   CRM, MATA GARUDA, Subhi, client-case NBs are NEVER exported — they may carry
   client PII (KTP/passport/NPWP/akta) which must never reach a third-party LLM.
   Adding a notebook_id here is a deliberate, reviewable act.
2. RESUMABLE: every source written updates a checkpoint file. Re-running skips
   already-exported sources. A 3600-source crawl WILL be interrupted; design for it.
3. GENTLE: a real rate-limit / 504 / auth-expiry will happen mid-crawl (CLAUDE.md
   NLM scars). Sleep between calls, retry with backoff, and CHECKPOINT before each
   call so an abort never re-does work.

RUN (on Pro or Mini, where the NLM auth lives — NOT M5):
    cd ~/Desktop/nuzantara
    source apps/nlm-bridge/.venv/bin/activate   # has notebooklm_tools + auth
    python scripts/nb_export_corpus.py --discover                  # fill the regulation id
    python scripts/nb_export_corpus.py --nb nb-intel-regulation    # Phase A: one NB
    python scripts/nb_export_corpus.py --all                       # Phase B: whole whitelist
    python scripts/nb_export_corpus.py --list                      # show whitelist, no crawl

Output: research/coherence-corpus/<nb-key>/<source_id>.json  (+ _manifest.json per NB)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# WHITELIST — regulatory / public NBs ONLY. PII NBs are deliberately absent.
# notebook_id values verified 2026-06-14 from tests/nlm_deep_research/
# test_notebook_ids.py + CLAUDE.md §15. The "tax" and "property" domains have
# TWO divergent notebooks each (pipeline vs backend-client, per test file
# lines 81-141) — we export the BACKEND-CLIENT one (what clients actually get
# served), since incoherence there is the dangerous kind.
# ---------------------------------------------------------------------------
WHITELIST: dict[str, dict[str, str]] = {
    "nb-intel-regulation": {
        # Phase-A default: smallest (41 sources) and most on-point for the Guardian.
        # id verified 2026-06-14 via --discover on the Pro (live NLM auth).
        "notebook_id": "a17f134e-b9ab-42d9-bfc2-5bbc45165c76",
        "note": "NB-INTEL Regulation — Daily Regulatory Intelligence (41 sources).",
    },
    "nb4-tax-backend": {
        "notebook_id": "837b620b-2aca-43ab-812e-97ca92bdad1d",
        "note": "NB-4 Tax — backend-client registry id (what clients are served).",
    },
    "nb5-property-backend": {
        "notebook_id": "568ec624-ceb8-47d1-a2a2-5b2f793ea7ed",
        "note": "NB-5 Property — backend-client registry id (divergent from curated NB-5).",
    },
    "nb5-property-curated": {
        # The CURATED property NB (145 sources, verified 2026-06-14 via --discover).
        # This is the real authored corpus, distinct from the backend-client id above.
        # ALREADY EXPORTED 2026-06-14: 3.7M chars, 102/145 substantive. Re-run = no-op (resumable).
        "notebook_id": "d9438180-5e63-4e2a-a473-6061101f6a8d",
        "note": "NB-5 Property & Real Estate Indonesia 2025 — curated (145 sources). DONE.",
    },
    # The remaining curated regulatory NBs — ids verified 2026-06-14 via --discover
    # on the live NLM account (Pro). These are the real Guardian corpus (~650 more
    # sources). NB-INTEL family deliberately EXCLUDED (Phase-A proved it's feed-stub noise).
    "nb3-company-curated": {
        "notebook_id": "933509f9-1561-403d-bd44-4a7a67a36df2",
        "note": "NB-3 Company Setup — Indonesia 2025 — curated (283 sources).",
    },
    "nb6-operations-curated": {
        "notebook_id": "85207af3-352f-4554-8d2a-18f42cc541ba",
        "note": "NB-6 Operations & Compliance Indonesia 2025 — curated (201 sources).",
    },
    "nb4-tax-curated": {
        # The PIPELINE/curated tax NB (165 sources). NOTE: the backend-client id
        # 837b620b… (nb4-tax-backend above) DIVERGES — itself a coherence smell.
        "notebook_id": "d4b2eedb-9863-4a1a-81ff-a11b0b45d853",
        "note": "NB-4 Tax & Fiscal Indonesia — curated/pipeline id (165 sources).",
    },
}

# Hard deny-list mirror — a second barrier. If any of these substrings appears in a
# requested notebook key/id, refuse outright. PII boundary defense-in-depth.
PII_DENY = ("crm", "mata", "garuda", "subhi", "client", "harari", "agents")

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = REPO_ROOT / "research" / "coherence-corpus"

SLEEP_BETWEEN = 1.5      # seconds between source fetches — gentle on NLM
MAX_RETRIES = 3
BACKOFF_BASE = 4.0       # seconds, exponential


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_client():
    """Build a warm NLM client from cached tokens — same pattern as the live
    nlm-bridge (apps/nlm-bridge/main.py:70-77). Fails loudly on M5 (no auth) or
    when no cached tokens exist (run `nlm login` on the Pro first) — by design.
    """
    try:
        from notebooklm_tools import NotebookLMClient  # type: ignore
        from notebooklm_tools.core.auth import load_cached_tokens  # type: ignore
    except ImportError:
        sys.exit(
            "FATAL: notebooklm_tools not importable. Run inside "
            "apps/nlm-bridge/.venv on the Pro/Mini (the M5 has no NLM auth)."
        )
    tokens = load_cached_tokens()
    if not tokens or not tokens.cookies:
        sys.exit(
            "FATAL: no cached NLM tokens (run 'nlm login' on the Pro first). "
            "The export needs a warm authenticated session."
        )
    return NotebookLMClient(
        cookies=tokens.cookies,
        csrf_token=tokens.csrf_token or "",
        session_id=getattr(tokens, "session_id", "") or "",
        build_label=getattr(tokens, "build_label", "") or "",
    )


def _assert_not_pii(key: str, notebook_id: str) -> None:
    blob = f"{key} {notebook_id}".lower()
    for bad in PII_DENY:
        if bad in blob:
            sys.exit(
                f"REFUSED: '{key}' ({notebook_id}) trips PII deny-list token "
                f"'{bad}'. PII NBs are never exported (CLAUDE.md §14 / Law 2)."
            )


def _checkpoint_path(nb_key: str) -> Path:
    return OUT_ROOT / nb_key / "_manifest.json"


def _load_checkpoint(nb_key: str) -> dict[str, Any]:
    p = _checkpoint_path(nb_key)
    if p.exists():
        return json.loads(p.read_text())
    return {"nb_key": nb_key, "started_at": _now(), "sources_done": {}, "errors": []}


def _save_checkpoint(nb_key: str, ckpt: dict[str, Any]) -> None:
    p = _checkpoint_path(nb_key)
    p.parent.mkdir(parents=True, exist_ok=True)
    ckpt["updated_at"] = _now()
    p.write_text(json.dumps(ckpt, ensure_ascii=False, indent=2))


def export_notebook(nb_key: str, client) -> None:
    spec = WHITELIST[nb_key]
    notebook_id = spec["notebook_id"]
    if notebook_id == "FILL_FROM_DISCOVER":
        sys.exit(
            f"'{nb_key}' has no notebook_id yet. Run --discover on the Pro to list "
            f"available NBs and their ids, then paste the regulation NB id into "
            f"WHITELIST. (We never crawl a guessed UUID.)"
        )
    _assert_not_pii(nb_key, notebook_id)

    print(f"[{_now()}] Listing sources for {nb_key} ({notebook_id}) …")
    # The listing call was OUTSIDE the try/retry below, so one bad NB (stale id,
    # RPCError "code 5: unknown" = NOT_FOUND, transient 5xx) killed the WHOLE
    # --all crawl and skipped every remaining NB. A single failing NB must NOT
    # abort the batch — record it and move on (the docstring's "crawl must survive
    # any single failure" promise applies to listing too, not just per-source).
    try:
        sources = client.get_notebook_sources_with_types(notebook_id)
    except Exception as exc:  # noqa: BLE001 — batch survives any single NB failure
        print(f"  ERROR listing {nb_key} ({notebook_id}): {str(exc)[:200]} — "
              f"skipping this NB, continuing with the rest.")
        ckpt = _load_checkpoint(nb_key)
        ckpt["errors"].append({"stage": "listing", "notebook_id": notebook_id,
                               "reason": str(exc)[:300], "at": _now()})
        _save_checkpoint(nb_key, ckpt)
        return
    if not sources:
        print(f"  WARN: 0 sources returned. Auth expired or empty NB? Skipping {nb_key}.")
        return
    print(f"  {len(sources)} sources found.")

    ckpt = _load_checkpoint(nb_key)
    done = ckpt["sources_done"]
    out_dir = OUT_ROOT / nb_key
    out_dir.mkdir(parents=True, exist_ok=True)

    for i, src in enumerate(sources, 1):
        sid = src.get("source_id") or src.get("id")
        if not sid:
            ckpt["errors"].append({"idx": i, "reason": "no source_id", "raw": str(src)[:200]})
            continue
        if sid in done:
            continue  # resumable: already exported

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                full = client.get_source_fulltext(sid)
                payload = {
                    "source_id": sid,
                    "nb_key": nb_key,
                    "notebook_id": notebook_id,
                    "title": full.get("title", src.get("title", "")),
                    "source_type": full.get("source_type", ""),
                    "char_count": full.get("char_count", 0),
                    "content": full.get("content", ""),
                    "exported_at": _now(),
                }
                (out_dir / f"{sid}.json").write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2)
                )
                done[sid] = {"title": payload["title"], "chars": payload["char_count"]}
                _save_checkpoint(nb_key, ckpt)  # checkpoint BEFORE next call
                print(f"  [{i}/{len(sources)}] ok: {payload['title'][:60]} "
                      f"({payload['char_count']} chars)")
                break
            except Exception as exc:  # noqa: BLE001 — crawl must survive any single failure
                if attempt == MAX_RETRIES:
                    ckpt["errors"].append({"source_id": sid, "reason": str(exc)[:300],
                                           "at": _now()})
                    _save_checkpoint(nb_key, ckpt)
                    print(f"  [{i}/{len(sources)}] FAIL after {MAX_RETRIES}: {str(exc)[:80]}")
                else:
                    wait = BACKOFF_BASE * (2 ** (attempt - 1))
                    print(f"  [{i}/{len(sources)}] retry {attempt} in {wait:.0f}s: "
                          f"{str(exc)[:60]}")
                    time.sleep(wait)
        time.sleep(SLEEP_BETWEEN)

    print(f"[{_now()}] {nb_key} done: {len(done)} sources, {len(ckpt['errors'])} errors.")


def discover(client) -> None:
    """List NBs visible to the current auth — to fill FILL_FROM_DISCOVER ids by hand."""
    print("Discovering notebooks (read-only). Match these against the whitelist:\n")
    # notebooklm_tools exposes a notebook-list; method name may vary by version.
    for meth in ("list_notebooks", "get_notebooks", "list_recent_notebooks"):
        fn = getattr(client, meth, None)
        if fn:
            try:
                for nb in fn():
                    print(f"  {nb}")
                return
            except Exception as exc:  # noqa: BLE001
                print(f"  ({meth} failed: {str(exc)[:80]})")
    print("  No list method worked — inspect notebooklm_tools API on the Pro.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--nb", choices=list(WHITELIST), help="export one whitelisted NB")
    g.add_argument("--all", action="store_true", help="export the whole whitelist")
    g.add_argument("--list", action="store_true", help="print whitelist, no crawl")
    g.add_argument("--discover", action="store_true", help="list live NBs to fill ids")
    args = ap.parse_args()

    if args.list:
        print("Whitelist (PII NBs deliberately absent):")
        for k, v in WHITELIST.items():
            print(f"  {k:24} {v['notebook_id']:40} — {v['note']}")
        return

    client = _load_client()

    if args.discover:
        discover(client)
        return
    if args.nb:
        export_notebook(args.nb, client)
    elif args.all:
        for k in WHITELIST:
            if WHITELIST[k]["notebook_id"] == "FILL_FROM_DISCOVER":
                print(f"SKIP {k}: no id yet (run --discover).")
                continue
            export_notebook(k, client)


if __name__ == "__main__":
    main()
