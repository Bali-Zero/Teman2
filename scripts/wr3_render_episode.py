#!/usr/bin/env python3
"""WR3 clip-renderer driver — Step 5/6.
Adapts our shot-pack schema (shot_id/prompt_positive) to the FlowKit client,
submits Veo 3.1 Fast Tier_ONE jobs, handles the 503 extension-drop health gate
explicitly (does NOT burn retries on 503), and emits a render report.
"""

from __future__ import annotations
import asyncio
import errno
import fcntl
import json
import os
import re
import sys
import urllib.error
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wr3_flowkit_client as fk  # noqa: E402
from wr3_spend_authority import zero_spend_enabled  # noqa: E402

EP = Path(sys.argv[1])
ENDPOINT = os.environ.get("WR3_FLOWKIT_ENDPOINT", "http://127.0.0.1:8100")
RUN_LOCK_NAME = ".render-episode.lock"
FLOWKIT_ALLOWED_HOSTS = frozenset({"127.0.0.1", "::1"})
FLOWKIT_ALLOWED_PORT = 8100


class EpisodeRunGuardError(RuntimeError):
    """A real episode run cannot safely start or resume automatically."""


def _validate_endpoint(endpoint: str) -> None:
    try:
        parsed = urlsplit(endpoint)
        port = parsed.port
    except ValueError as exc:
        raise EpisodeRunGuardError("invalid FlowKit endpoint") from exc
    if (
        parsed.scheme != "http"
        or parsed.hostname not in FLOWKIT_ALLOWED_HOSTS
        or port != FLOWKIT_ALLOWED_PORT
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise EpisodeRunGuardError(
            "FlowKit endpoint must be exactly loopback port 8100 with no URL extras"
        )


@contextmanager
def _exclusive_episode_lock() -> Iterator[None]:
    """Hold one persistent inode lock across the complete driver run."""

    EP.mkdir(parents=True, exist_ok=True)
    handle = (EP / RUN_LOCK_NAME).open("a+b")
    acquired = False
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN}:
                raise EpisodeRunGuardError(
                    f"episode render already in progress: {EP}"
                ) from exc
            raise
        yield
    finally:
        if acquired:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def _real_run_blockers() -> list[Path]:
    blockers = [
        path
        for path in (EP / "render-report.json", EP / "_flowkit_context.json")
        if path.exists()
    ]
    clips_dir = EP / "clips"
    if clips_dir.is_dir():
        blockers.extend(sorted(clips_dir.glob("*.mp4")))
    return blockers


def _shot_index(shot_id: str) -> int:
    """`s001` -> 1. Rejects anything else loudly.

    `str.lstrip` strips a CHARACTER SET, not a prefix: `"shot-2".lstrip("s")`
    is `"hot-2"`, so a non-conforming id used to reach `int()` and raise
    ValueError from outside any handler.
    """
    if not re.fullmatch(r"s\d+", shot_id):
        raise ValueError(f"expected s<digits>, got {shot_id!r}")
    return int(shot_id[1:])


def _write_report(report: dict) -> None:
    path = EP / "render-report.json"
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    directory_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _health() -> dict:
    import urllib.request

    with urllib.request.urlopen(ENDPOINT + "/health", timeout=10) as r:
        return json.loads(r.read().decode())


async def _main_locked() -> int:
    shot_pack = json.loads((EP / "shot-pack.json").read_text())
    shots = shot_pack["shots"]

    # Zero-spend mode short-circuits BOTH network preflights. Without this the
    # placeholder path is unreachable from the production entry point: _health()
    # and setup_episode_context() each dial the gateway and abort long before
    # submit_clip() ever reads WR3_ZERO_SPEND. That was finding F11 of P03 —
    # the zero-spend mode existed in the library and could not be run from the
    # command anyone actually types.
    zero_spend = zero_spend_enabled()
    ctx = None
    if zero_spend:
        print(
            "[render] WR3_ZERO_SPEND set — health gate and episode context skipped; "
            "every clip is a local placeholder, 0 credits",
            file=sys.stderr,
        )
    else:
        _validate_endpoint(ENDPOINT)
        blockers = _real_run_blockers()
        if blockers:
            print(
                json.dumps(
                    {
                        "status": "HALT",
                        "reason": "existing_real_run_state",
                        "automatic_resubmit_forbidden": True,
                        "blockers": [str(path) for path in blockers],
                    }
                )
            )
            return 6
        # Pre-flight health gate (commit 4c98e00 returns 503 if extension dropped)
        h = _health()
        if not h.get("extension_connected"):
            print(
                json.dumps(
                    {"status": "HALT", "reason": "extension_not_connected", "health": h}
                )
            )
            return 2
        print(f"[render] health OK: {h}", file=sys.stderr)

        ctx = await fk.setup_episode_context(name=EP.name, endpoint=ENDPOINT)
        (EP / "_flowkit_context.json").write_text(json.dumps(ctx.to_dict(), indent=2))
        print(
            f"[render] episode context project={ctx.project_id} video={ctx.video_id}",
            file=sys.stderr,
        )

    # `mode` is load-bearing for whoever reads this report later: a placeholder
    # run and a real run otherwise emit the same shape, and total_cost_cr is 0
    # in both whenever a real run fails before its first charge.
    report = {
        "rendered": [],
        "failed": [],
        "extension_drop": False,
        "total_cost_cr": 0,
        "mode": "placeholder" if zero_spend else "real",
        "status": "incomplete",
        "recovery_required": False,
    }
    # Stamp the report on disk BEFORE the first clip. Without this a run that
    # dies mid-flight leaves the PREVIOUS run's render-report.json in place —
    # so fresh placeholder clips can sit next to a stale `"mode": "real"` report
    # carrying genuine veo_job_ids, and the label describes the wrong run.
    # `status` stays "incomplete" until the loop finishes normally, so a
    # truncated run is legible as truncated instead of silently absent.
    _write_report(report)

    for shot in shots:
        # Building the request is INSIDE a handler: a malformed shot entry must
        # be a recorded failure, not an uncaught exception. Both statements here
        # used to sit outside every try — `int("shot-2".lstrip("s"))` raises
        # (lstrip strips a character SET, not a prefix) and a missing
        # `prompt_positive` raises KeyError — killing the process mid-loop
        # before any report was written.
        try:
            idx = _shot_index(shot["shot_id"])
            req = fk.ClipRequest(
                shot_index=idx,
                positive_prompt=shot["prompt_positive"],
                negative_prompt=shot.get("prompt_negative", ""),
                identity_tokens=tuple(shot.get("identity_tokens") or []),
                duration_s=int(round(shot.get("duration_s", 8))),
                resolution=shot_pack.get("resolution", "720x1280"),
                aspect=shot_pack.get("aspect_ratio", "9:16"),
                image_prompt=shot["prompt_positive"],
            )
        except (KeyError, TypeError, ValueError) as e:
            report["failed"].append(
                {"shot_id": shot.get("shot_id"), "reason": f"malformed shot entry: {e}"}
            )
            print(f"[render] skipping malformed shot: {e}", file=sys.stderr)
            continue
        last_err = None
        for attempt in range(3):  # 1 + 2 retries
            try:
                clip = await fk.submit_clip(
                    req, episode_dir=EP, episode_context=ctx, endpoint=ENDPOINT
                )
                report["rendered"].append(
                    {
                        "shot_id": shot["shot_id"],
                        "mp4": str(clip.mp4_path),
                        "cost_cr": clip.cost_credits,
                        "veo_job_id": clip.veo_job_id,
                        "duration_ms": clip.duration_ms,
                    }
                )
                report["total_cost_cr"] += clip.cost_credits
                print(
                    f"[render] {shot['shot_id']} OK ({clip.duration_ms}ms)",
                    file=sys.stderr,
                )
                break
            except urllib.error.HTTPError as e:
                if e.code == 503:
                    # health gate — extension dropped. Do NOT burn retries.
                    report["extension_drop"] = True
                    report["failed"].append(
                        {"shot_id": shot["shot_id"], "reason": "503_extension_dropped"}
                    )
                    print(
                        json.dumps(
                            {
                                "status": "HALT",
                                "reason": "extension_dropped_503",
                                "shot": shot["shot_id"],
                                "report": report,
                            }
                        )
                    )
                    _write_report(report)
                    return 3
                last_err = f"HTTP {e.code}"
            except fk.FlowkitNoResubmitError as e:
                # The charging boundary has been crossed, or may have been.
                # Every subclass is therefore a hard boundary for both the
                # per-shot retry loop and the remaining episode. Retrieval
                # errors carry an exact recoverable workflow/media tuple;
                # ambiguous generation errors instead carry the exact Flow
                # project/scene that requires inspection.
                if isinstance(e, fk.FlowkitRetrievalError):
                    reason = "paid_generation_retrieval_failed"
                    failure_reason = "retrieval_failed_after_generation"
                    recovery = {
                        "workflow_id": e.workflow_id,
                        "media_id": e.media_id,
                        "destination": str(e.destination),
                    }
                elif isinstance(e, fk.FlowkitGenerationAmbiguousError):
                    reason = "generation_state_ambiguous"
                    failure_reason = "generation_state_ambiguous"
                    recovery = {
                        "project_id": e.project_id,
                        "scene_id": e.scene_id,
                    }
                else:
                    reason = "no_resubmit_boundary"
                    failure_reason = "no_resubmit_boundary"
                    recovery = {"error_type": type(e).__name__}
                report["failed"].append(
                    {
                        "shot_id": shot["shot_id"],
                        "reason": failure_reason,
                        "recovery_required": True,
                        "automatic_resubmit_forbidden": True,
                        **recovery,
                        "error": str(getattr(e, "cause", e)),
                    }
                )
                report["status"] = "HALT"
                report["recovery_required"] = True
                report["automatic_resubmit_forbidden"] = True
                report["recovery"] = recovery
                _write_report(report)
                print(
                    json.dumps(
                        {
                            "status": "HALT",
                            "reason": reason,
                            "shot": shot["shot_id"],
                            "recovery_required": True,
                            "automatic_resubmit_forbidden": True,
                            **recovery,
                        }
                    )
                )
                return 5
            except fk.FlowkitQuotaError as e:
                report["failed"].append(
                    {"shot_id": shot["shot_id"], "reason": f"quota:{e}"}
                )
                print(
                    json.dumps(
                        {"status": "HALT", "reason": "quota_exceeded", "report": report}
                    )
                )
                _write_report(report)
                return 4
            except (fk.FlowkitError, fk.FlowkitTimeoutError, Exception) as e:
                last_err = str(e)
                print(
                    f"[render] {shot['shot_id']} attempt {attempt + 1} failed: {last_err}",
                    file=sys.stderr,
                )
        else:
            report["failed"].append(
                {
                    "shot_id": shot["shot_id"],
                    "reason": last_err,
                    "needs_broll_curator": True,
                }
            )

    report["status"] = "OK" if not report["failed"] else "PARTIAL"
    _write_report(report)
    status = report["status"]
    print(
        json.dumps(
            {
                "status": status,
                "rendered": len(report["rendered"]),
                "failed": len(report["failed"]),
                "total_cost_cr": report["total_cost_cr"],
                "mode": report["mode"],
            }
        )
    )
    return 0 if not report["failed"] else 1


async def main() -> int:
    try:
        with _exclusive_episode_lock():
            return await _main_locked()
    except EpisodeRunGuardError as exc:
        print(
            json.dumps(
                {
                    "status": "HALT",
                    "reason": "episode_run_guard",
                    "automatic_resubmit_forbidden": True,
                    "error": str(exc),
                }
            )
        )
        return 6


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
