#!/usr/bin/env python3
"""L11 de-boilerplate pass — Terra rewrites cluster sentences with per-draft variety.

Input: _l11_clusters.json (sentence -> [codes], from the lint's own L11 logic).
For each affected draft, ONE codex call: rewrite ONLY the listed sentences in fresh
wording (identical facts), return the full editorial JSON. A rewrite is accepted only
if (a) it parses, (b) shape gates pass (via editorial_writer._shape_ok, floor relaxed
to the applier's 240), and (c) none of the listed sentences still appear verbatim.
Resumable: a draft whose sentences are already gone is skipped.

Run on the Pro (codex quota lives there):
  python3 scripts/kbli_triangle/l11_rewriter.py [--workers 2] [--model gpt-5.6-terra]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import editorial_writer as ew  # _extract_json, QUOTA_RE, DRAFTS

DRAFTS = ew.DRAFTS
CLUSTERS = HERE / "_l11_clusters.json"
LOG = HERE / "l11_rewriter.log"
_log_lock = Lock()

PROMPT = """You are the copy editor for the Bali Zero KBLI Navigator. The editorial
below repeats sentences that appear VERBATIM in other editorials of the same catalogue
(an anti-template gate flags any sentence shared by 5+ pages). Rewrite ONLY the listed
sentences so each reads fresh and natural in context — vary structure and word choice,
keep EVERY fact, number, percentage, status word and regulation citation IDENTICAL.
Do not touch any other sentence. Do not add or remove facts. Do not shorten the body.

SENTENCES TO REWRITE (verbatim, as they appear):
{sentences}

EDITORIAL (JSON):
{editorial}

Reply with ONLY the full corrected editorial JSON object on the last line."""


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    with _log_lock:
        print(line, flush=True)
        with LOG.open("a") as f:
            f.write(line + "\n")


def shape_ok_relaxed(ed: dict) -> str | None:
    """Writer's shape gate with the applier's 240 floor (post option-A)."""
    for k in ("headline", "standfirst", "body"):
        if not str(ed.get(k) or "").strip():
            return f"empty {k}"
    if len(ed["headline"]) > 90:
        return "headline too long"
    if len(ed["standfirst"]) > 220:
        return "standfirst too long"
    w = len(str(ed["body"]).split())
    if not (240 <= w <= 700):
        return f"body {w} words"
    return None


def rewrite_one(code: str, sentences: list[str], model: str) -> str:
    p = DRAFTS / f"{code}.json"
    d = json.loads(p.read_text())
    ed = d["editorial"]
    joined = " ".join(str(ed.get(k) or "") for k in ("headline", "standfirst", "body"))
    todo = [s for s in sentences if s in joined]
    if not todo:
        return "skip"
    prompt = PROMPT.format(
        sentences="\n".join(f"- {s}" for s in todo),
        editorial=json.dumps(ed, ensure_ascii=False),
    )
    for attempt in range(4):
        try:
            r = subprocess.run(
                ["codex", "exec", "--sandbox", "read-only", "--skip-git-repo-check",
                 "-m", model, prompt],
                capture_output=True, text=True, timeout=300,
            )
        except Exception:
            time.sleep(5)
            continue
        new = ew._extract_json(r.stdout)
        if new is None:
            out = (r.stdout or "") + "\n" + (r.stderr or "")
            if ew.QUOTA_RE.search(out):
                log(f"  {code}: quota — backoff 60s")
                time.sleep(60)
                continue
            log(f"  {code}: parse fail (attempt {attempt + 1})")
            time.sleep(2)
            continue
        bad = shape_ok_relaxed(new)
        new_joined = " ".join(str(new.get(k) or "") for k in ("headline", "standfirst", "body"))
        still = [s for s in todo if s in new_joined]
        if bad or still:
            log(f"  {code}: reject ({bad or f'{len(still)} sentences unchanged'}) attempt {attempt + 1}")
            time.sleep(2)
            continue
        d["editorial"] = new
        p.write_text(json.dumps(d, ensure_ascii=False, indent=2))
        return "ok"
    return "fail"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--model", default="gpt-5.6-terra")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    clusters: dict[str, list[str]] = json.loads(CLUSTERS.read_text())
    by_code: dict[str, list[str]] = {}
    for s, owners in clusters.items():
        for c in owners:
            by_code.setdefault(c, []).append(s)
    todo = sorted(by_code)
    if args.limit:
        todo = todo[: args.limit]
    log(f"l11 rewriter start: {len(todo)} drafts, model {args.model}, workers {args.workers}")

    counts = {"ok": 0, "skip": 0, "fail": 0}
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(rewrite_one, c, by_code[c], args.model): c for c in todo}
        n = 0
        for fut in as_completed(futs):
            counts[fut.result()] += 1
            n += 1
            if n % 20 == 0:
                log(f"  progress {n}/{len(todo)}  ok={counts['ok']} fail={counts['fail']} skip={counts['skip']}")
    log(f"l11 rewriter done: {counts}")


if __name__ == "__main__":
    main()
