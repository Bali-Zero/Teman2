## 2026-04-23 - Accessibility for Sidebar Items
**Learning:** Custom interactive elements (e.g. `div` with `role="button"`) must have keyboard handlers for Enter and Space to be accessible. Elements hidden on hover should also be shown on focus using `group-focus-within`.
**Action:** Always add `onKeyDown` and focus-visible states to custom buttons. Use `group-focus-within:opacity-100` for hover-only actions.

## 2026-04-23 - CI-Safe Python Import Tests
**Learning:** Subprocess-based import tests in Python need absolute `PYTHONPATH` to be reliable in CI. Performance thresholds for cold imports must be generous (e.g. 100ms) to accommodate slower runner hardware.
**Action:** Use `os.path.abspath` for setting up test environments and increase timing thresholds in CI.
