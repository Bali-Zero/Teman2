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

## 2026-04-28 - [Consistent Focus Indicators with focus-ring Utility]
**Learning:** In highly customized dark UIs, default browser focus outlines are often invisible or clash with the aesthetic. Providing a dedicated `.focus-ring` utility class using `focus-visible` ensures that keyboard users have clear, brand-consistent navigation cues without affecting mouse users.
**Action:** Apply `.focus-ring` to all interactive elements that do not have a robust built-in focus state.

## 2026-04-30 - [Shared Locale Hook for Chat Micro-frontend]
**Learning:** In applications where certain routes (like `/chat`) are architecturally isolated from the main `I18nProvider`, duplicating locale-detection logic across components leads to inconsistencies and maintenance overhead. Consolidating this into a shared `useChatLocale` hook that synchronizes with `localStorage` ensures a unified language experience across all chat-specific components.
**Action:** Use a shared `useChatLocale` hook for any components in the chat interface that require multi-language support (Tool Indicators, Badges, Panels).

## 2026-05-18 - [Stateful Indicators and Localized Panels]
**Learning:** Collapsible panels and toggle buttons should provide clear visual feedback for their state. Using a rotating chevron icon synchronized with the 'aria-expanded' attribute ensures both visual and assistive technology users understand the component's state. Additionally, hardcoded strings in a multi-language app should always be refactored to use the shared localization hooks.
**Action:** Always include a rotating chevron for toggles. Synchronize 'aria-expanded' with the UI state. Use 'useChatLocale' for all UI text in the chat interface.
