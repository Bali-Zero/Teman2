## 2026-04-25 - [Semantic Lists and Sibling Interactive Elements]
**Learning:** Using generic `div` wrappers with `onClick` for lists of interactive items makes them inaccessible to keyboard and screen reader users. Refactoring to semantic `<ul>`, `<li>`, and `<button>` elements provides immediate a11y benefits. Additionally, nesting interactive elements (like a delete button inside a clickable container) is invalid HTML and requires fragile event propagation logic; refactoring them to sibling buttons within a list item is a cleaner, more robust pattern.
**Action:** Always use `<ul>` and `<li>` for collections of items. Ensure interactive items are semantic `<button>` or `<a>` tags. Use sibling structures instead of nesting for multiple actions on a single item.

## 2026-04-25 - [Keyboard Visibility for Actions]
**Learning:** Actions that only appear on hover (e.g., a "Delete" button) are inaccessible to keyboard-only users unless they are also triggered by focus.
**Action:** Use Tailwind's `group-focus-within:opacity-100` (or similar focus-based classes) alongside `group-hover:opacity-100` to ensure secondary actions become visible when a user tabs through a list.

## 2026-04-25 - [Immediate Visual Feedback for Attachments]
**Learning:** Providing immediate visual feedback for file attachments (like image previews) in a chat interface significantly improves the user's sense of control and reduces errors. Users can verify they attached the correct file before sending.
**Action:** Always include animated previews for file attachments in input components, and provide an easy, accessible way to remove them (visible on hover/focus).
