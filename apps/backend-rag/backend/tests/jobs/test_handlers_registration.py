"""Handler wrappers register the expected jobs."""
from __future__ import annotations


def test_import_handlers_registers_expected_jobs():
    # Importing the package self-registers via register_job()
    from backend.jobs import handlers  # noqa: F401
    from backend.jobs.registry import get_registry

    reg = get_registry()
    names = {d.name for d in reg.all()}
    assert {"auto-practice-creator", "conversation-cleanup"}.issubset(names), (
        f"expected auto-practice-creator and conversation-cleanup in registry, got {names}"
    )


def test_auto_practice_creator_cron_and_tz():
    from backend.jobs import handlers  # noqa: F401
    from backend.jobs.registry import get_registry

    decl = get_registry().get("auto-practice-creator")
    assert decl.cron == "30 7 * * *"
    assert decl.timezone == "Asia/Makassar"


def test_conversation_cleanup_cron():
    from backend.jobs import handlers  # noqa: F401
    from backend.jobs.registry import get_registry

    decl = get_registry().get("conversation-cleanup")
    assert decl.cron == "15 4 * * *"
