• **Verdict: REWORK**

1. **Critical —** The checker runs after arbitrary tests in the same writable checkout. A test can rewrite `scripts/wa_attention_presence.py`, edit suite sources before AST collection, or overwrite `junit.xml` from `atexit`/a terminal hook. Snapshot the AST expectations and use an integrity-protected checker/report.

2. **Critical —** Unknown decorators can replace a body while preserving identity: a `@wraps`-style wrapper can turn `def test_guard(): assert False` into a passing callable named `test_guard`. Class decorators can similarly replace an entire class. Only fixture decorators are analyzed.

3. **Critical —** Rebinding misses non-`Name` targets and reflection: `TestC.test_guard = lambda self: None`, `globals()["test_guard"] = lambda: None`, or `setattr(module, "test_guard", ...)` replaces the defined test while junit retains the expected identity.

4. **Critical —** Hook blocking is bypassable. Allowed `pytest_configure` can `pluginmanager.register()` an object implementing `pytest_pyfunc_call`; conftest `from helper import *` can import that hook under its own name. `pytest_runtest_logreport` may also rewrite a skipped report before junit consumes it.

5. **High —** Fixture trust is spoofable: after `import pytest`, rebinding `pytest` to a fake object still makes `@pytest.fixture` pass `is_fixture`; likewise an accepted bare `fixture` import can later be rebound.

6. **Medium false-RED —** Every conditional import is rejected, including `if TYPE_CHECKING: import typing`; any innocent `x.obj = value` is rejected; `specname=` is rejected on unrelated decorators; module constants such as `test_data` fail. Valid `import pytest as pt; @pt.fixture` also becomes “missing.”
