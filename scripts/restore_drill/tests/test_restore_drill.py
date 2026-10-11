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
        "backend_rag_v2",
        "nuzantara_readonly",
        "visa_ledger_owner",
        "zantara_rag_user",
    }


def test_hostile_quoted_role_is_rejected() -> None:
    dump = ['ALTER SCHEMA public OWNER TO "bad-role";']

    with pytest.raises(scanner.UnsafeRoleName):
        scanner.scan_roles(dump)


def test_generated_sql_is_sorted_quoted_and_nologin() -> None:
    sql = scanner.generate_role_sql({"visa_ledger_owner", "backend_rag_v2"})

    assert sql == (
        'CREATE ROLE "backend_rag_v2" NOLOGIN;\n'
        'CREATE ROLE "visa_ledger_owner" NOLOGIN;\n'
    )
    with pytest.raises(scanner.UnsafeRoleName):
        scanner.generate_role_sql({'safe"; DROP ROLE drill; --'})


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
        scanner.scan_roles(['ALTER TABLE t OWNER TO "Client Name";\n'])
    assert "Client" not in str(exc.value)
