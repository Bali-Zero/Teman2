"""Event handlers package.

Historical note: `handlers.py` (519 lines with register_handlers,
_is_duplicate, _recent_events, the `insert_outbox_event` re-export and
the internal coroutines) coexisted with this package for several weeks
after `compliance_handlers.py` was added. Python always resolves the
package over the sibling module, so `from backend.services.events import
handlers` quietly returned this empty __init__ and every downstream
`handlers.register_handlers` / `handlers.insert_outbox_event` reference
fell back into silent `try/except ImportError` branches (including
`app_factory._background_init`, which meant the EventBus subscribers
were never wired up in production).

Moved the old `handlers.py` into this package as `_core.py` and
re-export its public surface from here, so every historical import path
keeps working without touching consumers:

    from backend.services.events.handlers import register_handlers
    from backend.services.events.handlers import insert_outbox_event
    from backend.services.events.handlers import _is_duplicate  # tests
"""
from ._core import (  # noqa: F401
    _CHAIN_CONTEXT_MAX,
    _DEDUP_WINDOW_S,
    _chain_context,
    _check_client_expiry_on_completion,
    _create_drive_folder,
    _is_duplicate,
    _log_interaction,
    _recent_events,
    _run_predictive_scan_for_client,
    _send_admin_telegram,
    _store_context,
    get_chain_context,
    insert_outbox_event,
    register_handlers,
)
