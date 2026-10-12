from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("restore_drill_role_scanner", ROOT / "role_scanner.py")
scanner = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(scanner)


def test_scans_owner_grant_default_privileges_and_quoted_roles() -> None:
    dump = """
ALTER SCHEMA mata_garuda OWNER TO backend_rag_v2;
ALTER TABLE public.x OWNER TO "backend_rag_v2";
GRANT SELECT ON TABLE public.x TO nuzantara_readonly, "visa_ledger_owner";
ALTER DEFAULT PRIVILEGES FOR ROLE zantara_rag_user IN SCHEMA public
  GRANT SELECT ON TABLES TO nuzantara_readonly;
GRANT USAGE ON SCHEMA public TO PUBLIC;
ALTER DATABASE nuzantara OWNER TO postgres;
ALTER DATABASE nuzantara OWNER TO drill;
"""

    assert scanner.scan_roles(dump.splitlines(), exclude={"drill"}) == {
        "postgres",  # the drill superuser is "drill", so the dump's postgres owner must be created
        "backend_rag_v2",
        "nuzantara_readonly",
        "visa_ledger_owner",
        "zantara_rag_user",
    }


def test_quoted_role_with_hyphen_or_uppercase_is_created_quoted_not_rejected() -> None:
    roles = scanner.scan_roles(['ALTER SCHEMA public OWNER TO "Role-Name";\n'])

    assert roles == {"Role-Name"}
    assert scanner.generate_role_sql(roles) == 'CREATE ROLE "Role-Name" NOLOGIN;\n'


def test_generated_sql_is_sorted_quoted_and_nologin_and_cannot_be_broken_out_of() -> None:
    sql = scanner.generate_role_sql({"visa_ledger_owner", "backend_rag_v2"})

    assert sql == (
        'CREATE ROLE "backend_rag_v2" NOLOGIN;\n'
        'CREATE ROLE "visa_ledger_owner" NOLOGIN;\n'
    )
    hostile = scanner.generate_role_sql({'safe"; DROP ROLE drill; --'})
    assert hostile == 'CREATE ROLE "safe""; DROP ROLE drill; --" NOLOGIN;\n'
    with pytest.raises(scanner.UnsafeRoleName):
        scanner.generate_role_sql({"line\nbreak"})
    with pytest.raises(scanner.UnsafeRoleName):
        scanner.generate_role_sql({"x" * 64})


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        ("GRANT SELECT ON t TO role_a, role_b GRANTED BY grantor_role;", {"role_a", "role_b", "grantor_role"}),
        ("REVOKE UPDATE ON TABLE public.clients FROM reporting_ro;", {"reporting_ro"}),
        ("SET ROLE session_role;", {"session_role"}),
        ("CREATE POLICY p ON t\n  FOR SELECT\n  TO policy_role USING (true);", {"policy_role"}),
        ("ALTER ROLE configured_role SET work_mem = '64MB';", {"configured_role"}),
        ('GRANT SELECT ON TABLE public."reports to delete" TO app_ro;', {"app_ro"}),
        ("GRANT role_a TO role_b;", {"role_a", "role_b"}),
        ("ALTER DEFAULT PRIVILEGES FOR ROLE x IN SCHEMA public\n  GRANT SELECT ON TABLES TO y, z;", {"x", "y", "z"}),
        ("GRANT s ON t TO CURRENT_USER, PUBLIC, pg_read_all_data, SESSION_USER;", set()),
        ("ALTER TABLE a RENAME TO b;", set()),
        ("ALTER TABLE t OWNER TO postgres;", {"postgres"}),
        ('ALTER TABLE t OWNER TO "Drill";', {"Drill"}),  # quoted is exact: not the drill user
        ("ALTER DEFAULT PRIVILEGES FOR ROLE alpha, beta GRANT SELECT ON TABLES TO gamma;", {"alpha", "beta", "gamma"}),
        ("ALTER DEFAULT PRIVILEGES FOR ROLE a REVOKE ALL ON TABLES FROM b;", {"a", "b"}),
        ("/* outer /* nested */ GRANT s TO ghost; */ ALTER TABLE t OWNER TO real;", {"real"}),
        ('GRANT role_a TO "option";', {"role_a", "option"}),
        ("GRANT role_a, role_b TO role_c;", {"role_a", "role_b", "role_c"}),
        ("REVOKE role_a, role_b FROM role_c;", {"role_a", "role_b", "role_c"}),
    ],
)
def test_statement_forms_a_real_pg_dump_emits(sql: str, expected: set[str]) -> None:
    assert scanner.scan_roles(sql.splitlines(True), exclude={"drill"}) == expected


def test_literals_and_dollar_bodies_are_blanked_before_scanning() -> None:
    dump = (
        "CREATE FUNCTION f() RETURNS text LANGUAGE sql AS $x$\n"
        "COPY public.fake FROM stdin;\n"
        "GRANT s TO bogus;\n"
        "$x$;\n"
        "COMMENT ON TABLE c IS 'transfer owner to \"Budi Santoso\"\n"
        "GRANT s TO ghost';\n"
        "SELECT E'it\\'s owner to x';\n"
        "ALTER TABLE t OWNER TO real_owner;\n"
    )

    assert scanner.scan_roles(dump.splitlines(True)) == {"real_owner"}


def test_payload_keeps_on_error_stop_and_never_prints_restore_log() -> None:
    payload = (ROOT / "run_drill.sh").read_text(encoding="utf-8")

    assert payload.count("-v ON_ERROR_STOP=1") >= 2
    assert "tail -25" not in payload
    assert "cat \"$RESTORE_LOG\"" not in payload


def test_copy_data_rows_are_never_scanned_for_roles() -> None:
    dump = [
        "ALTER TABLE public.clients OWNER TO backend_rag_v2;\n",
        "COPY public.notes (id, body) FROM stdin;\n",
        "1\ttransfer owner to budi before closing\n",
        '2\tgrant select on x to "not a role"\n',
        "\\.\n",
        "GRANT SELECT ON public.clients TO nuzantara_readonly;\n",
    ]
    assert scanner.scan_roles(dump) == {"backend_rag_v2", "nuzantara_readonly"}


def test_rejection_message_does_not_echo_the_dump_token() -> None:
    with pytest.raises(scanner.UnsafeRoleName) as exc:
        scanner.scan_roles(['ALTER TABLE t OWNER TO "Client\x01Name";\n'])
    assert "Client" not in str(exc.value)


def test_wrapper_and_payload_have_no_silent_or_racy_exits() -> None:
    wrapper = (ROOT.parents[1] / "infra/launchagents/wrappers/mini-restore-drill.sh").read_text(encoding="utf-8")
    payload = (ROOT / "run_drill.sh").read_text(encoding="utf-8")

    assert 'mkdir "$LOCKDIR"' in wrapper and "PIDFILE" not in wrapper  # atomic lock, no recycled-PID skip
    assert 'skipped: previous run alive' not in wrapper  # a skip must never write an ok sidecar
    assert "FINISHED" in wrapper and 'trap on_exit EXIT' in wrapper  # no exit without a trace
    assert "trap 'exit 143' TERM" in payload  # a signal cannot read green
    assert "nuzantara-fly-[0-9]{8}-[0-9]{4}" in payload and "MAX_DUMP_AGE_HOURS" in payload  # stale dump != PASS
    assert "--memory" in payload and "docker rm -f" in payload


def test_verdict_needs_zero_exit_and_a_parsed_pass_and_a_sane_dump_date() -> None:
    payload = (ROOT / "run_drill.sh").read_text(encoding="utf-8")
    wrapper = (ROOT.parents[1] / "infra/launchagents/wrappers/mini-restore-drill.sh").read_text(encoding="utf-8")

    assert '"$aggregate" != "PASS"' in payload  # exit 0 with unreadable output is not green
    assert "head-object" in payload and "LastModified" in payload  # age from the store, not the local-time name
    assert 'kill -TERM "-$DRILL_PID"' in payload.split("cleanup()")[1].split("trap 'exit 143'")[0]  # signals stop the worker
    assert 'heartbeat "running"' not in wrapper  # sentinel-aggregate reads "running" as dead
    assert 'heartbeat "ok" "running' not in wrapper  # and "ok" at start would paint over the last verdict


def test_exit_paths_do_not_hide_an_incomplete_restore_or_an_unrecorded_green() -> None:
    payload = (ROOT / "run_drill.sh").read_text(encoding="utf-8")
    wrapper = (ROOT.parents[1] / "infra/launchagents/wrappers/mini-restore-drill.sh").read_text(encoding="utf-8")

    assert "-eq 141" not in payload  # SIGPIPE with psql rc=0 means an incomplete restore
    assert '[ -n "$DRILL_PID" ]; then' in payload and "kill -0 \"$DRILL_PID\"" not in payload.split("cleanup()")[1].split("trap 'exit 143'")[0]
    assert 'mv -f "$tmp"' in wrapper  # the sidecar is replaced atomically
    assert '! heartbeat "ok"' in wrapper  # a green that cannot be recorded is CANNOT-VERIFY


def _payload_text() -> str:
    return (ROOT / "run_drill.sh").read_text(encoding="utf-8")


def test_cleanup_and_watchdog_remove_only_containers_carrying_this_runs_label() -> None:
    text = _payload_text()
    cleanup = text[text.index("cleanup() {") : text.index("\n}\n", text.index("cleanup() {"))]
    watchdog = text[text.index('sleep "$TIMEOUT_SECONDS"') :]
    for block in (cleanup, watchdog):
        assert 'docker rm -f "$CONTAINER_NAME"' not in block
        assert "remove_own_containers" in block
    assert 'docker run --rm --detach --name "$CONTAINER_NAME" --label "$RUN_LABEL"' in text
    assert 'docker ps -aq --filter "label=$RUN_LABEL"' in text
    assert "container-id" not in text


def test_a_refused_run_creates_nothing_so_its_label_owns_nothing() -> None:
    text = _payload_text()
    refusal = text.index("return 75")
    reap = text.index('docker rm -f "$CONTAINER_NAME"')
    create = text.index("docker run --rm --detach")
    # the only name-based removal is the stale reap, after the age guard and before creation
    assert text.count('docker rm -f "$CONTAINER_NAME"') == 1
    assert refusal < reap < create


def _run_payload_until_listing(tmp_path: Path, extra_env: dict[str, str]) -> tuple[int, str, list[str]]:
    """Run the real payload with stub tools; the stub `aws` records its argv and refuses the listing."""
    import hashlib
    import os
    import subprocess

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    record = tmp_path / "aws.argv"
    stubs = {
        "aws": f'#!/bin/bash\nprintf "%s\\n" "$*" >> "{record}"\nexit 1\n',
        "colima": '#!/bin/bash\nprintf "Filesystem 1024-blocks Used Available Capacity Mounted\\n/dev/root 1 1 99999999 1%% /\\n"\n',
        "docker": '#!/bin/bash\ncase "$1 $2" in "image inspect") echo "$STUB_IMAGE_HASH" ;; esac\nexit 0\n',
        "psql": "#!/bin/bash\nexit 0\n",
    }
    for name, body in stubs.items():
        stub = bin_dir / name
        stub.write_text(body, encoding="utf-8")
        stub.chmod(0o755)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("RESTORE_DRILL_", "TIGRIS_", "AWS_"))}
    env.update(
        PATH=f"{bin_dir}:{env.get('PATH', '/usr/bin:/bin')}",
        AWS_ACCESS_KEY_ID="stub",
        AWS_SECRET_ACCESS_KEY="stub",
        STUB_IMAGE_HASH=hashlib.sha256((ROOT / "Dockerfile").read_bytes()).hexdigest(),
        RESTORE_DRILL_CONTAINER=f"pytest-drill-{os.getpid()}",
        # The watchdog's `sleep` outlives the run by design and would hold a pipe open: output goes to
        # a file, and a short cap bounds the orphan.
        RESTORE_DRILL_TIMEOUT_SECONDS="20",
        **extra_env,
    )
    out = tmp_path / "payload.out"
    with out.open("w", encoding="utf-8") as sink:
        proc = subprocess.run(
            ["/bin/bash", str(ROOT / "run_drill.sh")], env=env, stdout=sink, stderr=sink, timeout=60
        )
    calls = record.read_text(encoding="utf-8").splitlines() if record.exists() else []
    return proc.returncode, out.read_text(encoding="utf-8"), calls


def test_the_generic_secrets_env_bucket_cannot_redirect_the_drill(tmp_path: Path) -> None:
    # Mini's secrets env exports TIGRIS_BUCKET for the app's media bucket and the wrapper sources it with
    # `set -a`; a generic TIGRIS_ENDPOINT would leak the same way. The drill must still list the backups bucket.
    rc, stderr, calls = _run_payload_until_listing(
        tmp_path, {"TIGRIS_BUCKET": "media-bucket", "TIGRIS_ENDPOINT": "https://media.invalid"}
    )
    assert rc == 2 and "cannot list Tigris postgres backups" in stderr
    assert calls == ["--endpoint-url https://fly.storage.tigris.dev s3 ls s3://nuzantara-backups/postgres/"]


def test_the_drill_scoped_bucket_override_still_applies(tmp_path: Path) -> None:
    rc, _, calls = _run_payload_until_listing(
        tmp_path, {"TIGRIS_BUCKET": "media-bucket", "RESTORE_DRILL_TIGRIS_BUCKET": "drill-bucket"}
    )
    assert rc == 2
    assert calls == ["--endpoint-url https://fly.storage.tigris.dev s3 ls s3://drill-bucket/postgres/"]
