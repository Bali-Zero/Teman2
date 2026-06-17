from datetime import datetime, timezone

from scripts.wa_corpus.reconcile import (
    Action,
    DesiredState,
    RecordedState,
    archived_title,
    decide_action,
)

T0 = datetime(2026, 6, 1, tzinfo=timezone.utc)
T1 = datetime(2026, 6, 4, tzinfo=timezone.utc)


def _rec(title, msg_at):
    return RecordedState(file_id="f", source_id="s", last_title=title, last_msg_at=msg_at)


# --- CREATE ---------------------------------------------------------------

def test_new_loadable_is_create():
    d = DesiredState(loadable=True, title="WA · +62123", latest_msg_at=T0)
    assert decide_action(d, None).action is Action.CREATE


def test_new_not_loadable_is_skip():
    d = DesiredState(loadable=False, title="WA · +62123", latest_msg_at=T0)
    assert decide_action(d, None).action is Action.SKIP


# --- RENAME: the headline case (prospect -> client) -----------------------

def test_prospect_becomes_client_renames_to_name_plus_number():
    # last pass: only the phone (was a prospect / not in CRM yet)
    recorded = _rec("WA · +33600000000", T0)
    # this pass: now in CRM -> title is name + number
    desired = DesiredState(loadable=True, title="WA · Alexandre · +33600000000", latest_msg_at=T0)
    dec = decide_action(desired, recorded)
    assert dec.action is Action.RENAME
    assert dec.new_title == "WA · Alexandre · +33600000000"
    assert "+33600000000" in dec.new_title  # phone preserved


def test_crm_name_updated_renames():
    recorded = _rec("WA · Alex · +33600000000", T0)
    desired = DesiredState(loadable=True, title="WA · Alexandre Dupont · +33600000000", latest_msg_at=T0)
    assert decide_action(desired, recorded).action is Action.RENAME


# --- UPDATE ---------------------------------------------------------------

def test_new_messages_triggers_update():
    recorded = _rec("WA · +62123", T0)
    desired = DesiredState(loadable=True, title="WA · +62123", latest_msg_at=T1)  # newer
    assert decide_action(desired, recorded).action is Action.UPDATE


def test_same_title_same_msgs_is_skip():
    recorded = _rec("WA · +62123", T1)
    desired = DesiredState(loadable=True, title="WA · +62123", latest_msg_at=T1)
    assert decide_action(desired, recorded).action is Action.SKIP


# --- ARCHIVE (rename, keep the Doc) ---------------------------------------

def test_became_not_loadable_archives_by_rename():
    recorded = _rec("WA · Alexandre · +33600000000", T0)
    desired = DesiredState(loadable=False, title="WA · +33600000000", latest_msg_at=T0)
    dec = decide_action(desired, recorded)
    assert dec.action is Action.ARCHIVE
    assert dec.new_title == "ARCHIVED · WA · Alexandre · +33600000000"


def test_already_archived_is_skip():
    recorded = _rec("ARCHIVED · WA · +62123", T0)
    desired = DesiredState(loadable=False, title="WA · +62123", latest_msg_at=T0)
    assert decide_action(desired, recorded).action is Action.SKIP


def test_archived_title_idempotent():
    once = archived_title("WA · +62123")
    assert archived_title(once) == once  # never double-prefixes


# --- precedence: rename wins over update when both would fire -------------

def test_rename_takes_precedence_over_update():
    # both title changed AND new messages -> rename first (update happens next pass)
    recorded = _rec("WA · +33600000000", T0)
    desired = DesiredState(loadable=True, title="WA · Alexandre · +33600000000", latest_msg_at=T1)
    assert decide_action(desired, recorded).action is Action.RENAME
