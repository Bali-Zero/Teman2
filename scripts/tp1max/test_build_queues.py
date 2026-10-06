"""Tests for the TP1MAX queue builders: what may leave the machine for an external provider."""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_code_queue as bcq  # noqa: E402
import build_verify_queue as bvq  # noqa: E402

BODY = "def handler(event):\n    return event.get('value', 0) + 1\n" * 12
# Assembled at runtime so no scanner reads a credential- or PII-shaped literal in this file.
GUILT = {
    "secret": [
        "xkeysib-" + "A1b2" * 6, "12345678:" + "Ab3_" * 8 + "XYZ",
        "FlyV1 " + "Ab3_" * 6, "fo1_" + "Ab3_" * 6,
        *[prefix + "A1b2" * 8 for prefix in ("ghp_", "gho_", "ghs_", "ghr_", "github_pat_")],
        *[prefix + "A1b2" * 5 for prefix in ("sk_live_", "sk_test_", "rk_live_")],
        "GOCSPX-" + "A1b2" * 5, "ya29." + "A1b2" * 6,
        "AKIA" + "QWERTYUIOPASDFGH", "xoxb-" + "A1b2" * 5,
        *[name + '=\"' + "A1b2" * 3 + '\"' for name in ("password", "passwd", "secret", "api_key")],
        "-----BEGIN " + "PRIVATE KEY-----\n" + "A1b2" * 8 + "\n-----END PRIVATE KEY-----",
        'api_key="' + "a1b2" * 8 + '"', "fm2_" + "A1b2" * 6,
        "aws_secret_access_key = '" + "wJalrXUtnFMq7/K7MDEN" + "G/bPxRfiCYHq2Lz9Wk3P'",  # compound names, dict keys
        'DB_PASSWORD = "' + "Pz8kQ2wL5mR9" + '"', "client_secret: '" + "q8Lm2Zr7Vb4N" + "'",
        '{"password": "' + "hunter2" * 2 + '"}', "export DB_PASSWORD=" + "S3cr3tPass99",
        "postgres://app:" + "S3cr3tPass" + "@db.host-fiktif.co/x",
        'K = "-----BEGIN ' + 'PRIVATE KEY-----\\n' + "MIIEvQIBADANBgkq" * 2 + '"',  # "\n"-escaped JSON body
        'DB_PASSWORD = "' + "lowercasepassword" + '"', "DB_PASSWORD=" + "SuperSecret",  # council: letters-only literals
        "xkeysib-" + "A1b2" * 4 + "sample" + "A1b2" * 3,  # a family is never excused by a placeholder-ish word
        'DB_PASSWORD = "' + "postgres" + '"', 'API_KEY = "' + "correct horse battery staple 9" + '"',
        *[prefix + "A1b2" * 9 for prefix in ("whsec_", "ghu_", "glpat-", "npm_")], "ASIA" + "Q7W3E9R1T5Y2U8I4",
        "eyJ" + "hbGciOi1" + "." + "eyJ" + "zdWIiOi1" + "." + "c2lnbmF0dXJl",
        "eyJ" + "hbGciOiJIUzI1NiJ9" + "." + "e30" + "." + "c2lnbmF0dXJl" * 3, 'DB_PASSWORD = "' + "hunter2" + '"',
        "postgres://app:" + "q7" + "@db/x", 'DB_PASSWORD = "' + "correct-horse-battery-staple" + '"',
        'DB_PASSWORD = "' + "!StrongPass92" + '"', 'API_KEY = "' + "X9K2" + "QWERTY7Z" * 2 + '"',
        'x = "{\\"password\\": \\"' + "hunter2hunter2" + '\\"}"',  # an all-caps token; escaped JSON in a string
        'DB_PASSWORD = """' + "InventedPass92" + '"""',
        'DB_PASSWORD = "' + "Sup3r" + chr(92) + '"' + "Secret99" + '"',  # an escaped quote inside the value
        "postgres://app:" + "ab_cd_ef" + "@db/x", 'DB_PASSWORD = "' + "$" + "Ab3dE6Fg9" + '"',  # final review F3, F4
        "-----begin " + "rsa private key-----",  # a lower-case PEM header (Ollama review O6)
        # gate #7971 B1: shell/HTTP credential contexts, a PEM body by name, three families, base64-wrapped
        "machine api.klien-fiktif.co login bot pass" + "word " + "S3cr3tPass99",
        "curl -u admin:" + "Hunter2" + "Hunter2" + " https://api.klien-fiktif.co/v1",
        "mysqldump --pass" + "word " + "S3cr3tPass99" + " --host db",
        'curl -H "Authori' + 'zation: Basic ' + base64.b64encode(b"admin:" + b"S3cr3tPass99").decode() + '" x',
        'curl -H "Authori' + 'zation: Bearer ' + "Qz8" + "Ab3d" * 10 + '" x',
        'BLOB = "' + base64.b64encode(("xkeysib-" + "9f3c" * 16).encode()).decode() + '"',
        'PRIVATE_KEY = "' + "MIIEvQIBADANBgkq" + "Ab3d" * 10 + '"', '{"private_' + 'key": "' + "MIIEvQIBADANBgkq" + "Ab3d" * 10 + '"}',
        "https://discord.com/api/web" + "hooks/" + "123456789012345678/" + "Ab3d" * 17, "hf_" + "Ab3d" * 9,
        "DefaultEndpointsProtocol=https;AccountName=x;Account" + "Key=" + "Ab3d" * 22 + "==",
        # Kimi K3 on the cure: newline after =, a real-length JWT and RSA body, a long base64 tail, an
        # escaped assignment, --user=, an all-caps header token
        'api_key =\n    "' + "Qz8" + "Ab3d" * 4 + 'Q"', "jwt = " + "eyJhbGciOiJIUzI1NiJ9." + "QQ" * 300 + "." + "ss" * 20,
        'PRIVATE_KEY = "' + "MIIEvQIBADANBgkq" + "Ab3d" * 80 + '"',
        'B = "' + base64.b64encode(b"x" * 3100 + b" pass" + b"word = Sup3rSecret99 " + b"y" * 200).decode() + '"',
        "api%5Fkey%3D%22" + "Sup3rSecret99Ab3d" + "%22", "curl --user=admin:" + "Sup3rSecret99" + " https://x.co",
        'curl -H "Authori' + 'zation: Bearer ' + "QZ7XK9TM4WNP8V2JDAB3D" + '_E7F9" x',
        # Kimi K3, third pass: a quoted value over 4096 chars, a quoted -u credential with spaces, a binary head
        'PRIVATE_KEY = "' + "Ab3d" * 1200 + '"', 'curl -u "admin:Sup3r ' + 'Secret 99" https://x.co',
        'B = "' + base64.b64encode(b"\x00\xff" + b"pass" + b"word = Sup3rSecret99").decode() + '"',
    ],
    "phone": ["(0812) 3456-7890", "+62 (812) 3456–7890", "0812  3456  7890",
              "0812/3456/7890", "0812—3456—7890", "(021) 555-0123", "+62 21 555 0123",
              "+44 (20) 7946-0958", "62 (0)812 3456 7890", "0812\u00a03456\u00a07890", "0812\u20103456\u20107890",
              "WA_6281" + "234567890 = 1", "12 0812 3456 7890", "0812 3456 7890 / 0813 1111 2222", "0812-3456-7890 2026",
              "(0361) 754321", "+1 415 555 0123", "+ (44) 20 7946 0958", "0 812 3456 7890", "\uff10\uff18\uff11\uff12 3456 7890", "+7 912 345-67-89", "0039 333 1234567",
              "https://wa.me/%2B44%2020%20" + "7946%200958", "send?phone=%2B62%20812%20" + "3456%207890",
              'p = "\\u002B44 20 ' + '7946 0958"', "phone6281" + "234567890 = 1",  # +CC only after unescaping
              'WA = "' + base64.b64encode(b"+62 812-" + b"3456-7890").decode() + '"'],  # a phone inside base64
    "email": ["info" + "@" + "pt-klien-fiktif.co.id", "user" + "@" + "klien-fiktif.com",
              "nama.fiktif" + "@" + "balizero.com", "budi.zantara" + "@" + "balizero.com", "nama!info" + "@" + "balizero.com", "nama'info" + "@" + "balizero.com", "nama" + "@" + "xn--fiktif-9ya.xn--p1ai",
              "to=budi.santoso%40" + "balizero.com", "devi" + "@" + "balizero.com"],  # %40; a role word is a prefix, not the role
}
INNOCENT = "\n".join(("version=3.12.7", "sha=0123456789abcdef" * 3, "uuid=550e8400-e29b-41d4-a716-446655440000",
                       "ip=192.168.1.1 port=5432 timestamp=2026-10-06T12:34:56Z", "id=0812345678901234",
                       "colour=#12ab34", "blob=VGhpcyBp" + "cyBhIHRl" + "c3QgYmFz" + "ZTY0IHBh" + "eWxvYWQ=", "docs: xkeysib-, ghp_, GOCSPX-",
                       "token=" + "ghp_" + "x" * 36, "api_key=EXAMPLE_API_KEY", "password=<token>",
                       "login(username=username, password=password)", "client(api_key=settings.API_KEY)",
                       "TOKEN_ENV = 'CLAUDE_CODE_OAUTH_TOKEN'", "DB = 'postgres://app:${PG_PASSWORD}@db/x'",
                       'headers = {"X-API-Key": API_KEY}', "max_tokens = 4096", "pass" + "word = 'changeme-1234'", "price = 'Rp 62.500.000'",
                       "d = ['2026-10-06..2026-10-07', 0.0812345678, '+0700']",
                       'class TokenUsage:\n    """Count tokens per model and per day."""', "stamp=$(date -u +%Y%m%d%H%M%S)",
                       'curl -H "Authori' + 'zation: Bearer YOUR_JWT_TOKEN" x', "docker run -u 1000:1000 img",
                       'curl -u "deploy:$(cat ~/.pw)" x'))


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
    files = {"scripts/clean.py": BODY + INNOCENT, "scripts/tiny.py": "x = 1\n", "scripts/empty.py": b"",
             "scripts/nul.py": BODY.encode() + b"\0\x01", "scripts/latin1.py": BODY.encode() + b"\xff\xfe",
             "scripts/limit_minus.py": "a" * (bcq.MAX_BYTES - 1), "scripts/limit.py": "a" * bcq.MAX_BYTES,
             "scripts/huge.py": "a" * (bcq.MAX_BYTES + 1),
             "scripts/gone.py": BODY, "scripts/now_a_dir.py": BODY, "scripts/fifo.py": BODY,
             "scripts/tests/test_never_read.py": BODY + GUILT["secret"][0], "scripts/wa_0812" + "34567890.py": BODY}
    for reason, values in GUILT.items():
        files.update({f"scripts/guilt_{reason[0]}_{i}.py": BODY + value for i, value in enumerate(values)})
    files.update({"scripts/unicodé.py": BODY, "scripts/new\nline.py": BODY, "scripts/control\x01.py": BODY})
    repo = git_repo(tmp_path / "repo", files)
    (repo / "scripts/link.py").symlink_to(outside)
    subprocess.run(["git", "-C", str(repo), "add", "scripts/link.py"], check=True)
    (tmp_path / "elsewhere").mkdir()
    (tmp_path / "elsewhere" / "inner.py").write_text(BODY)
    (repo / "scripts/realdir").mkdir()
    (repo / "scripts/realdir/inner.py").write_text(BODY)
    subprocess.run(["git", "-C", str(repo), "add", "scripts/realdir/inner.py"], check=True)
    (repo / "scripts/realdir/inner.py").unlink()
    (repo / "scripts/realdir").rmdir()
    (repo / "scripts/realdir").symlink_to(tmp_path / "elsewhere")  # tracked file now read THROUGH a linked dir
    (repo / "scripts/gone.py").unlink()  # tracked but missing: stat() raises
    (repo / "scripts/now_a_dir.py").unlink()
    (repo / "scripts/now_a_dir.py").mkdir()  # a directory where a tracked file was
    (repo / "scripts/fifo.py").unlink()
    os.mkfifo(repo / "scripts/fifo.py")  # reading a FIFO would block the build forever

    out = tmp_path / "queue.jsonl"
    assert bcq.main([str(repo), str(out)]) == 0
    assert bcq.MAX_BYTES == 512 * 1024

    ids = [json.loads(line)["id"] for line in out.read_text().splitlines()]
    assert ids == ["code:scripts/clean.py", "code:scripts/limit.py", "code:scripts/limit_minus.py"]
    assert json.loads(capsys.readouterr().out)["skipped"] == {
        "binary": 2, "email": len(GUILT["email"]), "empty": 1, "excluded_path": 1, "oversized": 1,
        "phone": len(GUILT["phone"]) + 1, "secret": len(GUILT["secret"]), "short": 1,
        "not_regular": 2, "symlink": 2, "unreadable": 1, "unsafe_path": 3}
    sent = out.read_text()
    assert all(value not in sent for values in GUILT.values() for value in values)


def test_each_leak_shape_is_refused_by_the_screen_on_its_own(tmp_path):
    for reason, values in GUILT.items():
        for i, value in enumerate(values):
            path = tmp_path / f"{reason}_{i}.py"
            path.write_text(BODY + value)
            assert bcq.screen(path) == (None, reason), value
    path = tmp_path / "ok.py"
    text = BODY + INNOCENT + '\nCONTACT = "info@balizero.com admin@zantara.io dev@nuzantara.com qa@example.com x@app.test a@docs.example.org info+qa@mail.balizero.com"\n'
    path.write_text(text)
    assert bcq.screen(path) == (text, "ok")


def test_the_screen_stays_linear_on_adversarial_text():
    import time

    def cost(n: int) -> float:
        start = time.process_time()  # CPU, not wall: a loaded runner must not flap
        for unit in ("eyJ", "eyJAb3dAb3dAb3dAb3dAb3dAb3dAb3dAb3d", "a", "12 ", "QUJD", 'token=\\"', "api_key = '" + "A" * 4000 + "\n"):
            bcq.classify(unit * (n // len(unit)))
        for gap in ("token =", "token = (", "token :"):  # Kimi K3: three adjacent [ \t]* after "=" were cubic
            bcq.classify(gap + " " * (n // 64) + "\n")
        return time.process_time() - start

    small, big = cost(16384), cost(65536)
    assert big < 8 * small + 0.5  # x4 input: linear ~x4; the unbounded JWT alternative was ~x16 (64 KiB took 10 s)


def test_screen_exception_is_counted_fail_closed(tmp_path, monkeypatch):
    repo = git_repo(tmp_path / "repo", {"scripts/clean.py": BODY})
    monkeypatch.setattr(bcq, "screen", lambda *args: (_ for _ in ()).throw(RuntimeError("boom")))
    jobs, skipped = bcq.build(repo)
    assert jobs == [] and skipped == {"screen_error": 1}


def test_verify_queue_takes_only_answered_rows_that_report_defects(tmp_path):
    stage_a = tmp_path / "a.jsonl"
    stage_a.write_text(json.dumps({"id": "code:x.py", "prompt": "audit\n-----\n    1| x = 1\n-----"}) + "\n")
    results = tmp_path / "r.jsonl"
    rows = [{"id": "code:x.py", "model": "m1", "status": "ok", "parsed": {"defects": [{"line": 1, "defect": "d"}]}},
            {"id": "code:x.py", "model": "m2", "status": "failed", "parsed": {"defects": [{"line": 1}]}},
            {"id": "code:x.py", "model": "m3", "status": "ok", "parsed": {"defects": []}},
            {"id": "code:x.py", "model": "m4", "status": "ok",
             "parsed": {"defects": [{"line": 1, "evidence": 'DB_PASSWORD = "' + "InventedPass92" + '"'}]}}]
    results.write_text("".join(json.dumps(r) + "\n" for r in rows) + '{"id": "torn')
    out = tmp_path / "v.jsonl"
    assert bvq.main([str(stage_a), str(out), str(results), str(tmp_path / "missing.jsonl")]) == 0
    jobs = [json.loads(line) for line in out.read_text().splitlines()]
    assert [j["id"] for j in jobs] == ["verify:m1:code:x.py"]
    assert "    1| x = 1" in jobs[0]["prompt"]
