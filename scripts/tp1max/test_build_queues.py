"""Tests for the TP1MAX queue builders: what may leave the machine for an external provider."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_code_queue as bcq  # noqa: E402
import build_verify_queue as bvq  # noqa: E402

BODY = "def handler(event):\n    return event.get('value', 0) + 1\n" * 12
# Assembled at runtime so no scanner reads a credential- or PII-shaped literal in this file.
LEAKS = {
    "scripts/aws_key.py": 'KEY = "' + "AKIA" + "QWERTYUIOPASDFGH" + '"\n',
    "scripts/pem.py": 'PEM = "' + "-----BEGIN " + "RSA PRIVATE KEY-----" + '"\n',
    "scripts/phone.sh": 'WA="' + "+62 812 " + "3456 7890" + '"\n',
    "scripts/phone_dash.sh": 'WA="' + "+62-812-" + "3456-7890" + '"\n',
    "scripts/phone_bare.py": 'WA = "' + "0812" + "34567890" + '"\n',
    "scripts/mail.ts": 'const owner = "' + "someone.private" + "@" + "gmail.com" + '";\n',
}


def git_repo(root: Path, files: dict) -> Path:
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content if isinstance(content, bytes) else content.encode())
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    return root


def test_only_clean_text_is_queued_and_every_other_file_is_skipped_and_counted(tmp_path, capsys):
    outside = tmp_path / "outside.py"
    outside.write_text(BODY)
    files = {"scripts/clean.py": BODY, "scripts/tiny.py": "x = 1\n",
             "scripts/nul.py": BODY.encode() + b"\0\x01", "scripts/latin1.py": BODY.encode() + b"\xff\xfe",
             "scripts/huge.py": "x = 1\n" * (bcq.MAX_BYTES // 6 + 10),
             "scripts/gone.py": BODY, "scripts/now_a_dir.py": BODY,
             "scripts/tests/test_never_read.py": BODY + LEAKS["scripts/aws_key.py"]}
    files.update({rel: BODY + leak for rel, leak in LEAKS.items()})
    repo = git_repo(tmp_path / "repo", files)
    (repo / "scripts/link.py").symlink_to(outside)
    subprocess.run(["git", "-C", str(repo), "add", "scripts/link.py"], check=True)
    (repo / "scripts/gone.py").unlink()  # tracked but missing: stat() raises
    (repo / "scripts/now_a_dir.py").unlink()
    (repo / "scripts/now_a_dir.py").mkdir()  # read_bytes() raises

    out = tmp_path / "queue.jsonl"
    assert bcq.main([str(repo), str(out)]) == 0

    assert [json.loads(line)["id"] for line in out.read_text().splitlines()] == ["code:scripts/clean.py"]
    assert json.loads(capsys.readouterr().out)["skipped"] == {
        "binary": 2, "oversized": 1, "secret_pii": 6, "short": 1, "symlink": 1, "unreadable": 2}
    sent = out.read_text()
    for leak in LEAKS.values():
        assert leak.split('"')[1] not in sent


def test_each_leak_shape_is_refused_by_the_screen_on_its_own(tmp_path):
    for rel, leak in LEAKS.items():
        path = tmp_path / Path(rel).name
        path.write_text(BODY + leak)
        assert bcq.screen(path) == (None, "secret_pii"), rel
    path = tmp_path / "ok.py"
    path.write_text(BODY + 'CONTACT = "zantara@balizero.com"\n')
    assert bcq.screen(path) == (BODY + 'CONTACT = "zantara@balizero.com"\n', "ok")


def test_verify_queue_takes_only_answered_rows_that_report_defects(tmp_path):
    stage_a = tmp_path / "a.jsonl"
    stage_a.write_text(json.dumps({"id": "code:x.py", "prompt": "audit\n-----\n    1| x = 1\n-----"}) + "\n")
    results = tmp_path / "r.jsonl"
    rows = [{"id": "code:x.py", "model": "m1", "status": "ok", "parsed": {"defects": [{"line": 1, "defect": "d"}]}},
            {"id": "code:x.py", "model": "m2", "status": "failed", "parsed": {"defects": [{"line": 1}]}},
            {"id": "code:x.py", "model": "m3", "status": "ok", "parsed": {"defects": []}}]
    results.write_text("".join(json.dumps(r) + "\n" for r in rows) + '{"id": "torn')
    out = tmp_path / "v.jsonl"
    assert bvq.main([str(stage_a), str(out), str(results), str(tmp_path / "missing.jsonl")]) == 0
    jobs = [json.loads(line) for line in out.read_text().splitlines()]
    assert [j["id"] for j in jobs] == ["verify:m1:code:x.py"]
    assert "    1| x = 1" in jobs[0]["prompt"]
