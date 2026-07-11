"""KBLI Triangle — LOOP-2 editorial WRITER via Codex (GPT-5.5), durable + resumable.

WHY THIS EXISTS (and why it is a committed repo script, not a scratchpad one):
  The first pass of this work lived only in the session scratchpad and evaporated on a
  session teardown — ~1559 drafts + the writer + the v2 prompt, all gone. The lesson
  (modus / scar #2 "armed != durable"): hours of cross-LLM quota must land on a TRACKED
  path. So this writer writes to scripts/kbli_triangle/editorial_drafts/<code>.json
  (NOT _out/, which is gitignored), so a teardown cannot wipe it and the drafts can be
  committed as a checkpoint.

WHAT IT WRITES: the intel_2026.editorial object the /kbli/<code> page leads with, in the
  exact shape kbli_apply_editorials.py gates and KBLIEditorial.tsx renders:
    {"code": "<code>", "editorial": {headline, standfirst, body, pullQuote, byTheNumbers[]}}

ENGINE: Codex (ChatGPT Pro OAuth, pre-authorized, separate quota from Claude MAX). The
  Claude weekly cap + Gemini (agy) auth flakiness on M5 make Codex the working writer.
  Generator (Codex) != grader (the applier gates + lint SSOT + a later independent pass).

WRITER v2 RULES (baked in — these ARE the fix for the 91%-reject corpus):
  The v1 corpus was 91% rejected because it style-transferred *fabricated sibling-code
  details* from the gold exemplars and invented youllAlsoNeed names. v2 forbids that at
  the source: cite ONLY facts present in the slim record; never describe another KBLI
  code; never invent an obligation, a permit, a threshold, or a related-code name.

Resumable: skips codes whose draft already exists. Thread pool. Failures recorded, never
  crash the batch. Quota-detect backs off. Per-code slim record (small, fast calls).

Usage:
  python3 scripts/kbli_triangle/editorial_writer.py [--limit N] [--only 56101,47222]
                                                     [--workers K] [--codes-file F]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "data/source_documents/KBLI_2025_FINAL_CLEAN.json"
DRAFTS = Path(__file__).resolve().parent / "editorial_drafts"  # TRACKED, not _out/
LOG = Path(__file__).resolve().parent / "editorial_writer.log"

QUOTA_RE = re.compile(
    r"out of extra usage|usage limit|quota exceeded|rate.?limit|429|exhausted|"
    r"too many requests|token_revoked|refresh_token_reused",
    re.I,
)

_log_lock = Lock()


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    with _log_lock:
        print(line, flush=True)
        with LOG.open("a") as f:
            f.write(line + "\n")


def load_rows() -> dict:
    raw = json.loads(DATASET.read_text())
    rows = raw["data"] if isinstance(raw, dict) and "data" in raw else raw
    return {str(r.get("kode_kbli_2025")): r for r in rows}


def _scales(rec: dict) -> list:
    out = []
    for v in rec.get("per_skala") or []:
        for sc in v.get("skala_usaha") or []:
            if sc not in out:
                out.append(sc)
    return out


def _scope_text(rec: dict) -> str:
    # Indonesian scope prose the writer synthesises from (top uraian + first ruang_lingkup)
    parts = []
    if rec.get("uraian"):
        parts.append(str(rec["uraian"]))
    for rl in (rec.get("ruang_lingkup") or [])[:2]:
        u = rl.get("uraian")
        if u and u not in parts:
            parts.append(str(u))
    return "\n".join(parts)[:1600]


def slim(rec: dict) -> dict:
    l4 = rec.get("l4_bali") or {}
    mor = l4.get("moratorium") or {}
    return {
        "code": str(rec.get("kode_kbli_2025")),
        "judul": rec.get("judul"),
        "scope_id": _scope_text(rec),
        "pma_status": rec.get("pma_status"),
        "pma_max_asing": rec.get("pma_max_asing"),
        "pma_source": rec.get("pma_source"),
        "scales_open_to": _scales(rec),
        "l4_bali_status": l4.get("status"),
        "l4_bali_blocked": bool(l4.get("blocked")),
        "l4_bali_reason": l4.get("reason"),
        "bali_moratorium_rule": mor.get("rule"),
        "bali_moratorium_source": mor.get("source"),
    }


PROMPT_HEAD = """You are the senior editorial writer for the Bali Zero KBLI Navigator — a national reference used by founders setting up businesses in Indonesia. For ONE KBLI 2025 activity code you write a short magazine-grade editorial: intelligent, precise, quietly authoritative. Never salesy, never a listicle.

You are given a SLIM RECORD as JSON. It is the ONLY source of truth. Everything you write must be traceable to a field in it.

⛔ ABSOLUTE PROHIBITIONS (violating any = the draft is discarded):
1. NEVER describe, name, number, or characterise any OTHER KBLI code. This code stands alone. Do not write "unlike 47112", "its sibling 85312 covers…", "pairs with 46201". The #1 cause of discarded drafts is inventing details about neighbouring codes.
2. NEVER invent an obligation, permit, licence, threshold, tax, timeline, or minimum-capital figure. If a fact is not in the slim record, it does not exist for you.
3. NEVER invent numbers. `byTheNumbers` values must come verbatim from the record (pma_max_asing, scales, pma_source, the Bali status). Do not compute or estimate.
3b. NEVER INVENT a Bali-side figure or condition — but DO state one that is literally present in `l4_bali_reason`. The national foreign-ownership percentage is `pma_max_asing`. Bali may ALSO carry its own figure/condition, and it lives ONLY inside `l4_bali_reason` (e.g. a reason of "PMA max 95% (kemitraan dengan masyarakat setempat)" means Bali caps the foreign stake at 95% and requires a local-community partnership — that is a REAL fact you SHOULD state, in clean English). Rules: (a) if `l4_bali_reason` contains a percentage or a partnership/condition, state it plainly in English (translate the Indonesian — do NOT quote the raw "the reason field reads '…'" verbatim); (b) if `l4_bali_reason` contains NO such figure, do NOT manufacture one — describe Bali only by its status word + the reason's meaning; (c) never contradict the record: `pma_max_asing` is the national ceiling, the l4_bali figure is the Bali-specific one, and they can legitimately differ.
4. NO dates in prose in dd/mm/yyyy or ISO form. Spell any date out ("May 2026").
5. NO banned stock sentences: do not write "Let me walk you through what it means for a foreign-owned setup." or "Here is the honest national-vs-Bali picture…".

WHAT THE EDITORIAL IS ABOUT: what this activity actually is (translate/synthesise scope_id, which is Indonesian, into clear English), who registers it and at what scales (scales_open_to), and — the real substance — the HONEST national-vs-Bali picture: nationally it may be foreign-open (pma_status / pma_max_asing) yet BLOCKED for PMA registration in Bali (l4_bali_blocked + l4_bali_reason + the moratorium). If pma_max_asing < 100 the foreign stake is capped — say so plainly. If l4_bali_blocked is true, the honest lede is that a foreigner cannot register this in Bali today. If neither, it is genuinely open — say that cleanly, don't manufacture a caveat.

LENGTH GATES (hard — drafts outside these are discarded):
- headline: ≤ 90 characters, a real title (not the raw judul).
- standfirst: ≤ 220 characters, one-sentence dek.
- body: aim for 400–600 words (never below 350, never above 680), markdown, 3–4 short paragraphs. A thin body is discarded — develop the what-it-is, the who-registers-it, and the national-vs-Bali picture fully.
- pullQuote: one natural, quotable sentence drawn from the body's argument (not a robotic fragment).
- byTheNumbers: 2–4 {label, value} pairs, values verbatim from the record. Render a foreign-ownership ceiling as a percentage (e.g. "100%", "67%"), not a bare number.

OUTPUT: reply with ONLY one JSON object on the LAST line, no prose around it:
{"headline": "...", "standfirst": "...", "body": "...markdown...", "pullQuote": "...", "byTheNumbers": [{"label": "...", "value": "..."}]}

SLIM RECORD:
"""


def _extract_json(text: str) -> dict | None:
    m = re.findall(r"\{.*\}", text, re.S)
    for blob in reversed(m):
        try:
            obj = json.loads(blob)
            if isinstance(obj, dict) and "headline" in obj and "body" in obj:
                return obj
        except Exception:
            continue
    return None


def _shape_ok(ed: dict) -> str | None:
    """Cheap pre-gate mirroring the applier's G2 so we retry instead of emit a reject.
    Returns a reason string if the draft is malformed, else None."""
    for k in ("headline", "standfirst", "body"):
        if not str(ed.get(k) or "").strip():
            return f"empty {k}"
    if len(ed["headline"]) > 90:
        return f"headline {len(ed['headline'])}c > 90"
    if len(ed["standfirst"]) > 220:
        return f"standfirst {len(ed['standfirst'])}c > 220"
    w = len(str(ed["body"]).split())
    # Hard retry band == the applier's G2 gate (300-700). The PROMPT aims higher
    # (400-600) for depth, but a genuinely thin code should get an honest short
    # editorial, never be retried into fabricated padding (the v1 corpus disease).
    if not (300 <= w <= 700):
        return f"body {w} words outside 300-700"
    return None


MODEL = ""  # optional codex model override (e.g. gpt-5.6-terra); "" = CLI default


def codex_write(s: dict) -> tuple[dict | None, str]:
    """Return (editorial|None, status). status in {ok, quota, parse, error, shape}."""
    prompt = PROMPT_HEAD + json.dumps(s, ensure_ascii=False)
    cmd = ["codex", "exec", "--sandbox", "read-only", "--skip-git-repo-check"]
    if MODEL:
        cmd += ["-m", MODEL]
    cmd.append(prompt)
    try:
        p = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=300,
        )
    except subprocess.TimeoutExpired:
        return None, "error"
    except Exception:
        return None, "error"
    out = (p.stdout or "") + "\n" + (p.stderr or "")
    if QUOTA_RE.search(out):
        return None, "quota"
    ed = _extract_json(p.stdout)
    if ed is None:
        return None, "parse"
    bad = _shape_ok(ed)
    if bad:
        return ed, "shape"
    return ed, "ok"


def write_one(code: str, rec: dict, backoff_state: dict) -> str:
    dest = DRAFTS / f"{code}.json"
    if dest.exists():
        return "skip"
    s = slim(rec)
    last_shape: dict | None = None
    for attempt in range(5):
        ed, status = codex_write(s)
        if status == "ok":
            dest.write_text(json.dumps({"code": code, "editorial": ed},
                                       ensure_ascii=False, indent=2))
            return "ok"
        if status == "quota":
            n = backoff_state.get("n", 0) + 1
            backoff_state["n"] = n
            wait = min(30 * n, 180)
            log(f"  {code}: quota — backoff {wait}s (#{n})")
            time.sleep(wait)
            continue
        if status == "shape":
            # gate-failing draft: keep the best one, retry for an in-band one
            last_shape = ed
            log(f"  {code}: shape reject — retry (attempt {attempt + 1})")
            time.sleep(2)
            continue
        # parse/error: one quick retry, then give up on this code
        log(f"  {code}: {status} (attempt {attempt + 1})")
        time.sleep(2)
    # exhausted retries: write the best shape-reject if we have one (applier is the
    # real gate; a near-miss draft is better than none and is auditable), else fail.
    if last_shape is not None:
        dest.write_text(json.dumps({"code": code, "editorial": last_shape},
                                   ensure_ascii=False, indent=2))
        log(f"  {code}: wrote best shape-reject after retries (applier will gate)")
        return "ok"
    return "fail"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", default="")
    ap.add_argument("--codes-file", default="")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--model", default="",
                    help="codex model override (e.g. gpt-5.6-terra); empty = CLI default")
    args = ap.parse_args()

    global MODEL
    MODEL = args.model

    DRAFTS.mkdir(exist_ok=True)
    rows = load_rows()
    all_codes = list(rows.keys())

    if args.only:
        codes = [c.strip() for c in args.only.split(",") if c.strip()]
    elif args.codes_file:
        codes = [c.strip() for c in Path(args.codes_file).read_text().split() if c.strip()]
    else:
        codes = all_codes

    todo = [c for c in codes if c in rows and not (DRAFTS / f"{c}.json").exists()]
    if args.limit:
        todo = todo[: args.limit]
    done_already = sum(1 for c in codes if (DRAFTS / f"{c}.json").exists())
    log(f"writer start: {len(todo)} to write ({done_already} already on disk), workers={args.workers}")

    backoff_state: dict = {}
    counts = {"ok": 0, "skip": 0, "fail": 0}
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(write_one, c, rows[c], backoff_state): c for c in todo}
        n = 0
        for fut in as_completed(futs):
            r = fut.result()
            counts[r] = counts.get(r, 0) + 1
            n += 1
            if n % 10 == 0:
                log(f"  progress {n}/{len(todo)}  ok={counts['ok']} fail={counts['fail']}")
    log(f"writer done: ok={counts['ok']} fail={counts['fail']} skip={counts['skip']}")


if __name__ == "__main__":
    main()
