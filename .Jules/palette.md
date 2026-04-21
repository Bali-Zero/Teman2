## 2026-03-29 - [Accessibility & Keyboard Navigation in Sidebar]
**Learning:** Icon-only buttons with conditional visibility (hover-only) create an accessibility trap for keyboard users. Using `group-focus-within` and `focus-visible` ensures they appear when the parent item is focused via keyboard.
**Action:** Always pair `hover:opacity-100` with focus-related visibility classes for secondary actions like 'Delete' buttons within list items.

**Learning:** Custom interactive elements like `div role="button"` need explicit `onKeyDown` handlers for both 'Enter' and 'Space' to meet ARIA standards.
**Action:** Implement a reusable `handleKeyDown` or ensure these events are always handled for custom buttons.
