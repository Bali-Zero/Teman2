"""Run only in an isolated backend snapshot with synthetic database configuration."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone


def main() -> int:
    output = Path(sys.argv[1])
    output.mkdir(parents=True, exist_ok=True)
    router = Path("backend/app/routers/e33_cases.py")
    tests = Path("backend/tests/routers/test_e33_cases.py")
    original = router.read_bytes()
    source = original.decode()
    start = source.index("    if body.principal_case_id is not None:\n")
    end = source.index("    today = date.today()", start)
    receipts = []

    def run(name: str, args: list[str]) -> int:
        started = datetime.now(timezone.utc).isoformat()
        result = subprocess.run([sys.executable, *args], capture_output=True, text=True)
        log = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout + result.stderr)
        (output / f"{name}.log").write_text(log)
        summary = next(
            (line for line in reversed(log.splitlines()) if line.strip()), ""
        )
        receipts.append(
            {
                "name": name,
                "command": args,
                "started_at": started,
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "exit_code": result.returncode,
                "summary": summary,
            }
        )
        print(f"{name}: exit={result.returncode}; {summary}")
        return result.returncode

    pytest_args = ["-m", "pytest", str(tests)]
    try:
        router.write_text(source[:start] + source[end:])
        guilt = run("guilt-no-principal-guard", pytest_args)
    finally:
        router.write_bytes(original)
    assert router.read_bytes() == original, "Failed to restore exact router source"
    innocence = run("innocence-restored", pytest_args)
    lint = run("ruff", ["-m", "ruff", "check", str(router), str(tests)])
    record = {
        "receipts": receipts,
        "router_restored_exactly": True,
        "file_sha256": {
            str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in [router, tests]
        },
    }
    (output / "results.json").write_text(json.dumps(record, indent=2) + "\n")
    return 0 if guilt == 1 and innocence == 0 and lint == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
