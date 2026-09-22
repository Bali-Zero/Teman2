#!/usr/bin/env python3
"""P2b benchmark judge + score, as ONE command.

    python3 scripts/kbli_bench/run_p2b.py \\
        --answers scripts/kbli_bench/results/<run>/p2b_answers.jsonl \\
        --out     scripts/kbli_bench/results/<date>-<tag> \\
        --judgings 3

What it does, in order: emit one judge prompt per question (`score_p2b.py prompts`), run the
judge `--judgings` times over every prompt, score the lot (`score_p2b.py score`), and write a
manifest that identifies every input by sha256.

WHAT IT DOES NOT DO — and this is deliberate, not a gap to be filled in silently. It does not
SERVE the corpus. The answers come from the macOS app's own harness (`Tests/benchrunner`) in
the KBLI Navigator app repo, which is where the production path lives: the package builder,
`KBLICodexRunner` with its own pinned argv, and the real `KBLIAnswerGate.check`. A serving
step re-implemented here would measure this script instead of the product, which is the one
thing the benchmark must never do. `--answers` therefore takes the JSONL that harness wrote.
Runbook for the serving half: `scripts/kbli_bench/README.md`.

The judge rides the ChatGPT seat through the `codex` CLI (OAuth). No per-token API key of any
vendor is read, written or required by this script.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCORER = HERE / "score_p2b.py"
DEFAULT_CORPUS = HERE / "p2b_corpus.json"
JUDGE_MODEL = "gpt-5.6-sol"


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def sanitized_codex_home(dest: Path) -> tuple[Path, str]:
    """A private CODEX_HOME whose config the installed codex can actually parse.

    Measured on Pro 2026-09-22 with codex-cli 0.149.0: every `codex exec` died at
    `Error loading config.toml: invalid type: map, expected a boolean in features`, because
    `~/.codex/config.toml` carries a `[features.context_management]` sub-table while this
    version expects every key under `[features]` to be a boolean. The whole seat reads as
    dead from the outside — the fleet probe reports `seat codex: UNKNOWN_ERR` — which is how
    a config defect gets mistaken for a quota wall for eight hours.

    So the benchmark stops depending on the shape of somebody's interactive config: it copies
    the credential file and a config with the nested `[features.*]` tables dropped into a
    0700 temp dir of its own. The user's real `~/.codex` is never written to. Nothing here
    prints, logs or returns the credential; only the number of dropped tables is reported.
    """
    src = Path.home() / ".codex"
    dest.mkdir(parents=True, exist_ok=True)
    os.chmod(dest, 0o700)
    lines = (src / "config.toml").read_text().splitlines()
    keep, skipping, dropped = [], False, 0
    for ln in lines:
        if ln.startswith("["):
            skipping = ln.startswith("[features.")
            dropped += 1 if skipping else 0
        if not skipping:
            keep.append(ln)
    (dest / "config.toml").write_text("\n".join(keep) + "\n")
    os.chmod(dest / "config.toml", 0o600)
    for name in ("auth.json",):
        if (src / name).exists():
            shutil.copyfile(src / name, dest / name)
            os.chmod(dest / name, 0o600)
    return dest, f"{dropped} nested [features.*] table(s) dropped"


JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def judge_one(prompt: Path, model: str, codex_home: Path, timeout: int) -> dict:
    """One judging of one question. Returns the verdict payload or an `error` envelope.

    A judge that fails is recorded as a failure, never as a verdict. An `error` envelope
    carries no `verdicts`, so `load_judgings` in the scorer simply does not count it — and a
    question judged fewer times than asked shows up in `judgings_per_row.min`.
    """
    env = dict(os.environ, CODEX_HOME=str(codex_home))
    try:
        proc = subprocess.run(
            ["codex", "exec", "--sandbox", "read-only", "--skip-git-repo-check",
             "--ephemeral", "-m", model, "-"],
            input=prompt.read_text(), capture_output=True, text=True,
            timeout=timeout, env=env, check=False,
        )
    except subprocess.TimeoutExpired:
        return {"error": "timeout", "qid": prompt.stem}
    if proc.returncode != 0:
        return {"error": f"rc={proc.returncode}", "detail": proc.stderr[-400:], "qid": prompt.stem}
    m = JSON_BLOCK.search(proc.stdout)
    if not m:
        return {"error": "no json in output", "detail": proc.stdout[-400:], "qid": prompt.stem}
    try:
        payload = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        return {"error": f"bad json: {e}", "detail": m.group(0)[:400], "qid": prompt.stem}
    payload.setdefault("qid", prompt.stem)
    if payload["qid"] != prompt.stem:
        # The judge naming a different question is not a verdict about this one.
        return {"error": f"qid mismatch: judge said {payload['qid']}", "qid": prompt.stem}
    return payload


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--answers", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    ap.add_argument("--judgings", type=int, default=3,
                    help="independent judge passes over every question (default 3; 1 is the "
                         "pre-2026-09-22 protocol and cannot separate judge variance from a "
                         "verdict)")
    ap.add_argument("--model", default=JUDGE_MODEL)
    ap.add_argument("--parallel", type=int, default=4)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--only", default="", help="comma-separated qids, for a targeted re-judge")
    args = ap.parse_args()

    if args.judgings < 1:
        sys.exit("--judgings must be >= 1")
    for p in (args.answers, args.corpus):
        if not p.exists():
            sys.exit(f"missing input: {p}")

    args.out.mkdir(parents=True, exist_ok=True)
    prompts = args.out / "judge_prompts"
    started = datetime.now(timezone.utc).isoformat()
    t0 = time.time()

    print(f"[1/3] prompts -> {prompts}", flush=True)
    subprocess.run([sys.executable, str(SCORER), "prompts", str(args.corpus),
                    str(args.answers), str(prompts)], check=True)

    wanted = {q.strip() for q in args.only.split(",") if q.strip()}
    files = sorted(p for p in prompts.glob("*.txt") if not wanted or p.stem in wanted)
    if not files:
        sys.exit(f"no judge prompts selected (--only {args.only!r})")

    tmp_home = Path(tempfile.mkdtemp(prefix="p2b-codex-home-"))
    codex_home, home_note = sanitized_codex_home(tmp_home)
    print(f"[2/3] judging {len(files)} question(s) x {args.judgings} "
          f"on {args.model} ({home_note})", flush=True)

    errors: list[dict] = []
    try:
        for k in range(1, args.judgings + 1):
            outdir = args.out / "judgings" / f"j{k}"
            outdir.mkdir(parents=True, exist_ok=True)
            with concurrent.futures.ThreadPoolExecutor(max_workers=args.parallel) as pool:
                futures = {pool.submit(judge_one, f, args.model, codex_home, args.timeout): f
                           for f in files}
                for fut in concurrent.futures.as_completed(futures):
                    f = futures[fut]
                    payload = fut.result()
                    (outdir / f"{f.stem}.json").write_text(
                        json.dumps(payload, ensure_ascii=False, indent=1))
                    if "error" in payload:
                        errors.append({"judging": k, "qid": f.stem, "error": payload["error"]})
                        print(f"  j{k} {f.stem}: ERROR {payload['error']}", flush=True)
            done = len(list(outdir.glob("*.json")))
            print(f"  judging {k}/{args.judgings}: {done} file(s)", flush=True)
    finally:
        shutil.rmtree(tmp_home, ignore_errors=True)

    print("[3/3] scoring", flush=True)
    score_p = args.out / "p2b_score.json"
    with score_p.open("w") as fh:
        subprocess.run([sys.executable, str(SCORER), "score", str(args.corpus),
                        str(args.answers), str(args.out / "judgings")],
                       check=True, stdout=fh)
    report = json.loads(score_p.read_text())

    manifest = {
        "started_utc": started,
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_s": round(time.time() - t0, 1),
        "corpus": {"path": str(args.corpus), "sha256": sha256_file(args.corpus)},
        "answers": {"path": str(args.answers), "sha256": sha256_file(args.answers)},
        "dataset": report.get("dataset"),
        "judge": {
            "model": args.model,
            "judgings_requested": args.judgings,
            "questions": [f.stem for f in files],
            "codex_version": subprocess.run(["codex", "--version"], capture_output=True,
                                            text=True, check=False).stdout.strip(),
            "errors": errors,
        },
        "floors": {k: v["value"] for k, v in report["floors"].items()},
        "gate": report["gate"],
        "judging_decisive": report["judging_decisive"]["pass"],
    }
    (args.out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))

    print(json.dumps(manifest["floors"], indent=1))
    print(f"gate={report['gate']} decisive={report['judging_decisive']['pass']} "
          f"judge_errors={len(errors)}")
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
