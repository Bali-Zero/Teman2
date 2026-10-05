#!/usr/bin/env python3
"""tp1_batch_runner.py — durable, resumable batch runner over the TP1 (Alibaba Token Plan) door.

WHY THIS EXISTS: scripts/tp1_call.py is a one-shot door, and a multi-day TP1
campaign (mission TP1MAX-20261005: use the plan's remaining quota on work worth
having before the 2026-10-12 reset) cannot hang off one chat session. This runs
a JSONL queue through the SAME door — same credential resolver, same answer
parser, same scrubber, imported from tp1_call.py — with adaptive concurrency,
and writes one JSON result row per job outside the repository.

SAFETY, by construction rather than by configuration:
  * One endpoint. TP1_CHAT_COMPLETIONS_URL is the Token Plan gateway, and
    assert_token_plan_endpoint() refuses to start on any other host. There is
    no fallback door in this module and nothing here can buy quota.
  * The first hard quota/auth error (HTTP 401/402/403, or a body that says the
    quota/credit/plan is exhausted) stops dispatch. So does a 429 that survives
    backoff at concurrency 1 for --max-rate-strikes rounds: an exhausted plan
    whose error wording nobody has seen yet still stops the run.
  * Dispatch also stops at --stop-at, on the kill file, and at --token-budget.
  * Idempotent: an id already present in results.jsonl is never sent again (an
    HTTP 200 was paid for). --retry-failed re-sends only rows whose status is
    not "ok". A job stopped by a quota or rate error writes no row (it was not
    answered), so the next run picks it up.
  * The proof is rows, not a PID: heartbeat.json counts result rows and tokens.

Queue row:  {"id": str, "prompt": str, "lane"?: str, "model"?: str}
Result row: {"id", "lane", "model", "status", "answer", "parsed", "usage",
             "secs", "attempts", "error", "ts"}

Exit codes: 0 queue drained · 2 credential unavailable · 3 stopped by
deadline / kill file / token budget · 5 stopped by a quota or auth error.

Usage:
    python3 scripts/tp1_batch_runner.py --queue q.jsonl --out-dir ~/tp1-runs/x \\
        --model qwen3.8-max --concurrency 4 --max-concurrency 12
    touch ~/tp1-runs/x/STOP        # kill switch: no new dispatch, in-flight calls finish
"""

from __future__ import annotations

import argparse
import collections
import concurrent.futures as cf
import datetime as dt
import json
import os
import random
import re
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Callable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tp1_call import (  # noqa: E402  (sibling import: one door, one parser, one scrubber)
    TP1_CHAT_COMPLETIONS_URL,
    TP1_LIVE_SLUGS,
    _prompt_identifiers,
    build_body,
    extract_answer,
    no_stream_chat_completion,
    resolve_effort,
    resolve_tp1_key,
    scrub,
)

TOKEN_PLAN_HOST = "token-plan.ap-southeast-1.maas.aliyuncs.com"
DEFAULT_STOP_AT = "2026-10-11T23:30:00+08:00"
QUOTA_RE = re.compile(
    r"insufficient[_ ]quota|arrearage|overdue"
    r"|quota[^\"]{0,40}(exhaust|used up|insufficient|depleted)"
    r"|exceeded your (current )?quota"
    r"|credits?[^\"]{0,30}(exhaust|insufficient|depleted|used up)"
    r"|(plan|subscription)[^\"]{0,40}(expired|exhausted|inactive)",
    re.I,
)
RATE_RE = re.compile(r"throttl|rate.?limit|too many requests|requestlimit", re.I)


def assert_token_plan_endpoint(url: str = TP1_CHAT_COMPLETIONS_URL) -> None:
    host = urllib.parse.urlparse(url).hostname
    if host != TOKEN_PLAN_HOST:
        raise SystemExit(f"tp1_batch_runner: refusing non-Token-Plan endpoint host {host!r}")


def classify(status: Optional[int], body: str) -> str:
    """ok | quota | rate | transient | rejected. Quota wins over rate: when a body
    is ambiguous, stopping costs idle time, continuing could cost money."""
    if status == 200:
        return "ok"
    if status in (401, 402, 403) or QUOTA_RE.search(body or ""):
        return "quota"
    if status == 429 or RATE_RE.search(body or ""):
        return "rate"
    if status is None or status == 408 or status >= 500:
        return "transient"
    return "rejected"


def parse_json_answer(text: Optional[str]) -> Optional[object]:
    if not text:
        return None
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    body = fenced.group(1) if fenced else text
    start, end = body.find("{"), body.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(body[start : end + 1])
    except ValueError:
        return None


def tp1_call_once(model: str, prompt: str, effort: Optional[str], max_tokens: int,
                  timeout: float, token: str) -> dict:
    """Non-streaming on purpose: the streamed reassembly in tp1_call drops the
    `usage` object, and the heartbeat must count real tokens, not characters."""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = build_body(model, prompt, max_tokens, resolve_effort(model, effort))
    started = time.time()
    status, raw, tail = no_stream_chat_completion(TP1_CHAT_COMPLETIONS_URL, headers, body, timeout, [token])
    out: dict = {"status": status, "secs": round(time.time() - started, 1), "usage": {}}
    if status != 200:
        out["error"] = scrub(raw or tail or "", [token])[-300:]
        return out
    try:
        usage = json.loads(raw).get("usage") or {}
    except (ValueError, AttributeError):
        usage = {}
    pt, ct = int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)
    out["usage"] = {"prompt_tokens": pt, "completion_tokens": ct,
                    "total_tokens": int(usage.get("total_tokens") or pt + ct)}
    answer, warning, error = extract_answer(raw)
    if error:
        out["error"] = scrub(error, [token])[-300:]
    else:
        out["answer"] = scrub(answer or "", [token], keep=_prompt_identifiers(prompt))
        if warning:
            out["warning"] = warning
    return out


def load_queue(path: Path) -> list[dict]:
    jobs, seen = [], set()
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        job = json.loads(line)
        if not isinstance(job.get("id"), str) or not isinstance(job.get("prompt"), str):
            raise ValueError(f"{path}:{n}: a queue row needs string 'id' and 'prompt'")
        if job["id"] in seen:
            raise ValueError(f"{path}:{n}: duplicate id {job['id']!r}")
        seen.add(job["id"])
        jobs.append(job)
    return jobs


class Runner:
    def __init__(self, jobs: list[dict], out_dir: Path, call: Callable[[str, str], dict], *,
                 model: str, concurrency: int = 4, max_concurrency: int = 12,
                 stop_at: Optional[dt.datetime] = None, kill_file: Optional[Path] = None,
                 token_budget: int = 0, max_attempts: int = 2, max_rate_strikes: int = 6,
                 backoff: float = 15.0, retry_failed: bool = False) -> None:
        self.jobs, self.call, self.model = jobs, call, model
        self.out_dir = out_dir
        self.results = out_dir / "results.jsonl"
        self.heartbeat = out_dir / "heartbeat.json"
        self.kill_file = kill_file or out_dir / "STOP"
        self.stop_at = stop_at or dt.datetime.fromisoformat(DEFAULT_STOP_AT)
        self.limit, self.max_c = max(1, concurrency), max(1, max_concurrency, concurrency)
        self.token_budget, self.max_attempts = token_budget, max_attempts
        self.max_rate_strikes, self.backoff, self.retry_failed = max_rate_strikes, backoff, retry_failed
        self.pause_until, self.ok_streak, self.rate_strikes = 0.0, 0, 0
        self.started, self.last_beat, self.last_error = time.time(), 0.0, None
        self.stats = collections.Counter()

    def done_ids(self) -> set[str]:
        done: set[str] = set()
        if not self.results.exists():
            return done
        for line in self.results.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue  # a torn last line from a crash: that job simply runs again
            if row.get("status") == "ok" or not self.retry_failed:
                done.add(row.get("id"))
        return done

    def stop_reason(self) -> Optional[str]:
        if self.kill_file.exists():
            return "kill-file"
        if dt.datetime.now(dt.timezone.utc) >= self.stop_at:
            return "deadline"
        if self.token_budget and self.stats["total_tokens"] >= self.token_budget:
            return "token-budget"
        return None

    def run(self) -> int:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        done = self.done_ids()
        pending = collections.deque((j, 1) for j in self.jobs if j["id"] not in done)
        self.stats["skipped_done"] = len(self.jobs) - len(pending)
        reason: Optional[str] = None
        inflight: dict = {}
        with cf.ThreadPoolExecutor(max_workers=self.max_c) as ex:
            while (pending and reason is None) or inflight:
                reason = reason or self.stop_reason()
                if reason is None and pending and len(inflight) < self.limit and time.time() >= self.pause_until:
                    job, attempt = pending.popleft()
                    inflight[ex.submit(self.call, job.get("model") or self.model, job["prompt"])] = (job, attempt)
                    continue
                if not inflight:
                    time.sleep(min(1.0, max(0.05, self.pause_until - time.time())))
                    continue
                finished, _ = cf.wait(inflight, timeout=5, return_when=cf.FIRST_COMPLETED)
                for fut in finished:
                    job, attempt = inflight.pop(fut)
                    reason = self.settle(job, attempt, fut, pending) or reason
                self.beat("running" if reason is None else f"stopping:{reason}", force=bool(finished))
        self.beat(f"stopped:{reason or 'drained'}", force=True)
        return 0 if reason is None else 5 if reason == "quota" else 3

    def settle(self, job: dict, attempt: int, fut: cf.Future, pending: collections.deque) -> Optional[str]:
        try:
            res = fut.result()
        except Exception as e:  # a crashed call is a transient failure, never a dead runner
            res = {"status": None, "error": f"{type(e).__name__}: {e}", "usage": {}}
        for k, v in (res.get("usage") or {}).items():
            self.stats[k] += int(v or 0)
        kind = classify(res.get("status"), res.get("error", ""))
        if kind != "ok":
            self.last_error = f"{kind}: HTTP {res.get('status')}: {(res.get('error') or '')[-160:]}"
        if kind == "ok":
            self.rate_strikes, self.ok_streak = 0, self.ok_streak + 1
            if self.ok_streak >= 2 * self.limit and self.limit < self.max_c:
                self.limit, self.ok_streak = self.limit + 1, 0
            self.write(job, attempt, res, "ok" if res.get("answer") else "no_answer")
            return None
        if kind == "quota":
            return "quota"
        if kind == "rate":
            self.stats["rate_limited"] += 1
            self.ok_streak = 0
            if self.limit == 1:
                self.rate_strikes += 1
            self.limit = max(1, self.limit // 2)
            delay = min(600.0, self.backoff * 2 ** min(self.rate_strikes, 6)) * (1 + random.random() / 4)
            self.pause_until = time.time() + delay
            pending.appendleft((job, attempt))  # not answered, not an attempt
            return "quota" if self.rate_strikes >= self.max_rate_strikes else None
        if kind == "transient" and attempt < self.max_attempts:
            pending.append((job, attempt + 1))
            return None
        self.write(job, attempt, res, "failed" if kind == "transient" else "rejected")
        return None

    def write(self, job: dict, attempt: int, res: dict, status: str) -> None:
        self.stats[status] += 1
        answer = res.get("answer")
        row = {"id": job["id"], "lane": job.get("lane"), "model": job.get("model") or self.model,
               "status": status, "answer": answer, "parsed": parse_json_answer(answer),
               "usage": res.get("usage") or {}, "secs": res.get("secs"), "attempts": attempt,
               "error": res.get("error"), "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
        with open(self.results, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    def beat(self, state: str, force: bool = False) -> None:
        now = time.time()
        if not force and now - self.last_beat < 30:
            return
        self.last_beat = now
        hours = max(now - self.started, 1.0) / 3600
        hb = {"ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "pid": os.getpid(),
              "state": state, "queue": len(self.jobs), **self.stats, "concurrency": self.limit,
              "calls_per_hour": round(self.stats["ok"] / hours, 1),
              "tokens_per_hour": int(self.stats["total_tokens"] / hours),
              "stop_at": self.stop_at.isoformat(), "kill_file": str(self.kill_file), "last_error": self.last_error}
        tmp = self.heartbeat.with_suffix(".tmp")
        tmp.write_text(json.dumps(hb, indent=1) + "\n", encoding="utf-8")
        os.replace(tmp, self.heartbeat)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Resumable TP1 batch runner (see module docstring).")
    ap.add_argument("--queue", required=True, help="JSONL queue: one {id, prompt[, lane, model]} per line")
    ap.add_argument("--out-dir", required=True, help="results.jsonl + heartbeat.json land here (outside the repo)")
    ap.add_argument("--model", default="qwen3.8-max")
    ap.add_argument("--effort", default="medium", choices=["low", "medium", "high", "xhigh", "max"])
    ap.add_argument("--max-tokens", type=int, default=16000)
    ap.add_argument("--timeout", type=float, default=900.0, help="per-call wall clock, seconds")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--max-concurrency", type=int, default=12)
    ap.add_argument("--stop-at", default=DEFAULT_STOP_AT, help="ISO time with offset; no dispatch after it")
    ap.add_argument("--kill-file", default=None, help="default: <out-dir>/STOP")
    ap.add_argument("--token-budget", type=int, default=0, help="stop after this many total tokens (0 = none)")
    ap.add_argument("--retry-failed", action="store_true")
    args = ap.parse_args(argv)

    out_dir = Path(args.out_dir).expanduser().resolve()
    if out_dir.is_relative_to(Path(__file__).resolve().parent.parent):
        ap.error("--out-dir must live outside the repository")
    stop_at = dt.datetime.fromisoformat(args.stop_at)
    if stop_at.tzinfo is None:
        ap.error("--stop-at needs an explicit UTC offset")
    jobs = load_queue(Path(args.queue).expanduser())
    unknown = {j.get("model") or args.model for j in jobs} - TP1_LIVE_SLUGS
    if unknown:
        ap.error(f"not live TP1 slugs: {sorted(unknown)}")
    assert_token_plan_endpoint()
    token, source, note = resolve_tp1_key()
    if token is None:
        sys.stderr.write(f"tp1_batch_runner: credential unavailable: {note}\n")
        return 2
    sys.stderr.write(f"tp1_batch_runner: credential source: {source}; {len(jobs)} jobs\n")

    def call(model: str, prompt: str) -> dict:
        return tp1_call_once(model, prompt, args.effort, args.max_tokens, args.timeout, token)

    runner = Runner(jobs, out_dir, call, model=args.model, concurrency=args.concurrency,
                    max_concurrency=args.max_concurrency, stop_at=stop_at,
                    kill_file=Path(args.kill_file).expanduser() if args.kill_file else None,
                    token_budget=args.token_budget, retry_failed=args.retry_failed)
    return runner.run()


if __name__ == "__main__":
    sys.exit(main())
