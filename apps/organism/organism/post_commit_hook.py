"""Git post-commit hook — emit `new_module` event for each app/* directory.

Wired into .husky/post-commit. Walks `apps/` and emits `new_module` for any
sub-directory without an `.adopted_marker` file. AdoptModule actuator then
does its own gating (maturity, branch check, opt-out) — this emitter is
cheap and fire-and-forget.
"""
import asyncio
import logging
from pathlib import Path

from organism.emit import emit_event
from organism.schemas import Severity


log = logging.getLogger(__name__)


async def main() -> int:
    apps_dir = Path("apps")
    if not apps_dir.exists():
        log.info("post_commit_hook: apps/ not found, skipping")
        return 0

    count = 0
    for mod in apps_dir.iterdir():
        if not mod.is_dir():
            continue
        if mod.name.startswith(".") or mod.name.startswith("_"):
            continue
        if (mod / ".adopted_marker").exists():
            continue
        try:
            await emit_event(
                severity=Severity.INFO,
                source="git.post_commit",
                kind="new_module",
                payload={
                    "module_path": str(mod),
                    "module_name": mod.name,
                },
            )
            count += 1
        except Exception:
            log.exception("post_commit_hook: failed to emit for %s", mod.name)
    return count


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        # Hook must never block a commit — always exit 0
        pass
