"""One module per F5 tool, each exporting an ``args_model``, a
``result_model``, and a ``call`` coroutine — the shape ``tool_executor.py``
dispatches to. Only ``get_required_documents`` exists today (lane B9's one
proof-of-seam tool); the other nine tool names are registered in
``team_bot.registry`` but have no module here yet, which is why
``tool_executor.py`` returns ``ExecutorErrorCode.NOT_IMPLEMENTED`` for
them rather than raising or guessing at a call shape."""

from __future__ import annotations
