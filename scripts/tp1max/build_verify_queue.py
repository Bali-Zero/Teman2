#!/usr/bin/env python3
"""L-CODE stage B queue (TP1MAX-20261005): every stage-A row with findings becomes one verify job for a
DIFFERENT model family, which sees the same numbered file text plus the findings and rules on each item.
Usage: build_verify_queue.py <stage-A queue.jsonl> <out queue.jsonl> <stage-A results.jsonl>...
Rebuild is cheap and deterministic; the runner's idempotency skips verify jobs already answered."""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROMPT = """You are an independent second reviewer. Another model (a different family) audited the file below and reported the defects listed under FINDINGS.
For EACH finding (by index n), check the code at and around the cited line and rule:
- CONFIRMED: the defect is real and the description is accurate;
- PARTIAL: real, but the severity or the mechanism is wrong (say what is right);
- REFUTED: not a defect (misread code, guarded elsewhere in the shown text, intentional and documented, or purely theoretical).
Be strict: style, "could be improved" and speculation about code not shown are REFUTED. Quote the decisive code.
Reply with ONLY a JSON object: {{"verdicts":[{{"n":<int>,"verdict":"CONFIRMED|PARTIAL|REFUTED","severity":"high|medium|low","evidence":"<decisive code>","note":"<one sentence>"}}]}}

FINDINGS ({path}):
{findings}

FILE TEXT AS AUDITED:
-----
{text}
-----"""


def main(argv: "list[str]") -> int:
    if len(argv) < 3:
        sys.stderr.write(__doc__)
        return 2
    queue_a, out, results = argv[0], argv[1], argv[2:]
    texts = {}
    for line in open(queue_a, encoding="utf-8"):
        j = json.loads(line)
        body = j["prompt"].split("\n-----\n", 1)[1].rsplit("\n-----", 1)[0]
        texts[j["id"]] = body
    jobs, seen = [], set()
    for res in results:
        if not Path(res).exists():
            continue
        for line in open(res, encoding="utf-8"):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            defects = ((r.get("parsed") or {}).get("defects") or []) if r.get("status") == "ok" else []
            if not defects or r["id"] not in texts:
                continue
            vid = f"verify:{r['model']}:{r['id']}"
            if vid in seen:
                continue
            seen.add(vid)
            items = [{"n": i, **{k: d.get(k) for k in ("line", "severity", "class", "defect", "evidence")}}
                     for i, d in enumerate(defects, 1)]
            jobs.append({"id": vid, "lane": "L-CODE-verify", "finder": r["model"],
                         "prompt": PROMPT.format(path=r["id"].split(":", 1)[1], text=texts[r["id"]],
                                                 findings=json.dumps(items, ensure_ascii=False, indent=1))})
    tmp = Path(out).with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(j, ensure_ascii=False) + "\n" for j in jobs), encoding="utf-8")
    tmp.replace(out)
    print(json.dumps({"verify_jobs": len(jobs)}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
