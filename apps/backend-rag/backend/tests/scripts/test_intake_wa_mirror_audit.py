"""Pure tests for scripts/intake_wa_mirror_audit.py.

The live audit runs on the Pro against nuzantara_dev. These tests keep the
load-bearing SQL contract stable without touching the WA mirror DB:
technical source filter, direct CRM buckets, group safety, and read-only output.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

# test file: apps/backend-rag/backend/tests/scripts/<this>
# parents: [0]=scripts [1]=tests [2]=backend [3]=backend-rag [4]=apps [5]=repo root
_REPO_ROOT = Path(__file__).resolve().parents[5]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "intake_wa_mirror_audit.py"


def _load():
    spec = importlib.util.spec_from_file_location("iwa_under_test", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_media_types_default_and_custom() -> None:
    audit = _load()
    assert audit._media_types(None) == ("document", "image")
    assert audit._media_types("document") == ("document",)
    assert audit._media_types(" document, image , audio ") == ("document", "image", "audio")
    assert audit._media_types("  ") == ("document", "image")


def test_parser_is_read_only_by_shape() -> None:
    audit = _load()
    args = audit.build_parser().parse_args(["--pretty", "--check-disk"])
    assert args.pretty is True
    assert args.check_disk is True
    assert not hasattr(args, "apply")


def test_sql_constants_are_read_only() -> None:
    audit = _load()
    sql_values = [
        value
        for name, value in vars(audit).items()
        if name.endswith("_SQL") and isinstance(value, str)
    ]
    assert sql_values
    joined = "\n".join(sql_values).lower()
    for forbidden in (" insert ", " update ", " delete ", " alter ", " drop ", " truncate "):
        assert forbidden not in joined


def test_source_funnel_sql_matches_initial_filter() -> None:
    audit = _load()
    sql = audit.SOURCE_FUNNEL_SQL
    assert "direction = 'inbound'" in sql
    assert "media_stored_path IS NOT NULL" in sql
    assert "media_type = ANY($1::text[])" in sql
    assert "baileys_message_id IS NOT NULL" in sql
    assert "chat_type = 'group' OR group_jid IS NOT NULL" in sql


def test_direct_crm_match_sql_excludes_groups_and_buckets_phone_matches() -> None:
    audit = _load()
    sql = audit.DIRECT_CRM_MATCH_SQL
    assert "NOT (w.chat_type = 'group' OR w.group_jid IS NOT NULL)" in sql
    assert "phone_normalized" in sql
    assert "phone" in sql
    assert "whatsapp" in sql
    assert "'missing_phone'" in sql
    assert "'prospect_no_client'" in sql
    assert "'lead_one_client'" in sql
    assert "'ambiguous_multi_client'" in sql
    assert "team_phone_rows" in sql


def test_group_safety_sql_targets_group_wa_mirror_rows() -> None:
    audit = _load()
    sql = audit.GROUP_SAFETY_SQL
    assert "q.source = 'whatsapp'" in sql
    assert "q.source_ref LIKE 'wa-mirror:%'" in sql
    assert "w.chat_type = 'group' OR w.group_jid IS NOT NULL" in sql
    assert "unsafe_sender_phone_rows" in sql
    assert "unsafe_client_id_hint_rows" in sql


def test_routing_proposal_sql_uses_latest_proposal_per_queue() -> None:
    audit = _load()
    sql = audit.ROUTING_PROPOSAL_SQL
    assert "SELECT DISTINCT ON (queue_id)" in sql
    assert "ORDER BY queue_id, created_at DESC, id DESC" in sql
    assert "entity_resolution->>'decision'" in sql
    assert "'NO_PROPOSAL'" in sql
