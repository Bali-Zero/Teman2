## 2026-02-05 - Improving Keyboard Accessibility for Interactive Elements

**Learning:** Interactive elements that rely on hover for visibility (like delete buttons in lists) or custom role="button" implementations without native event handling are inaccessible to keyboard-only users. Specifically in this app, many utility buttons are hidden by default and only shown on hover.

**Action:**
1. Use `group-focus-within:opacity-100` on buttons that are normally `opacity-0` but inside a `group` container, ensuring they appear when the user tabs into the container.
2. Always pair `role="button"` and `tabIndex={0}` with an `onKeyDown` handler for `Enter` and `Space`.
3. Implement `aria-haspopup` and `aria-expanded` on all menu triggers to support screen readers.
4. Use `aria-current="true"` for indicating the active item in navigation or conversation lists.
