## 2026-04-25 - [Semantic Lists and Sibling Interactive Elements]
**Learning:** Using generic `div` wrappers with `onClick` for lists of interactive items makes them inaccessible to keyboard and screen reader users. Refactoring to semantic `<ul>`, `<li>`, and `<button>` elements provides immediate a11y benefits. Additionally, nesting interactive elements (like a delete button inside a clickable container) is invalid HTML and requires fragile event propagation logic; refactoring them to sibling buttons within a list item is a cleaner, more robust pattern.
**Action:** Always use `<ul>` and `<li>` for collections of items. Ensure interactive items are semantic `<button>` or `<a>` tags. Use sibling structures instead of nesting for multiple actions on a single item.

## 2026-04-25 - [Keyboard Visibility for Actions]
**Learning:** Actions that only appear on hover (e.g., a "Delete" button) are inaccessible to keyboard-only users unless they are also triggered by focus.
**Action:** Use Tailwind's `group-focus-within:opacity-100` (or similar focus-based classes) alongside `group-hover:opacity-100` to ensure secondary actions become visible when a user tabs through a list.

## 2026-04-25 - [Interactive Menu Dismissal Patterns]
**Learning:** For interactive popover menus (like attachment or user menus), users expect to dismiss them using the 'Escape' key or by clicking outside. Implementing this requires a `useEffect` hook combined with a `useRef` on the menu container to detect click targets and event listener cleanup.
**Action:** Always implement 'Escape' and click-outside dismissal for ephemeral UI menus. Use a local `useEffect` to manage these global event listeners.

## 2026-04-26 - [Descriptive Action Labels and Explicit Button Types]
**Learning:** Generic action labels like "Delete" in lists are ambiguous for screen reader users. Including the item's title in the `aria-label` (e.g., "Delete conversation: [Title]") provides crucial context. Additionally, omitting `type="button"` on non-submit buttons can lead to accidental form submissions and inconsistent browser behavior.
**Action:** Always include identifying information in `aria-label` for repetitive actions in lists. Consistently apply `type="button"` to all interactive elements that are not meant to submit a form.
