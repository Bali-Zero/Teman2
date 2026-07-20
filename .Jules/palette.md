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

## 2026-05-18 - [Loading States and Interaction Feedback in Portal]

**Learning:** Asynchronous actions in the client portal (like marking notifications as read) lacked visual feedback, leading to a "dead" feel during network latency. Providing immediate feedback via spinning icons and disabling buttons during mutations significantly improves the perceived responsiveness and prevents duplicate requests.
**Action:** Always expose and utilize mutation pending states from hooks to provide visual feedback and disable interactive elements during async operations.

## 2026-05-19 - [Fluid Inputs in Utility Widgets]

**Learning:** Small utility widgets that contain text inputs (like FeedbackWidget) often feel "heavy" when they use standard textareas with fixed heights and internal scrollbars. Utilizing the project's standard AutoResizeTextarea component ensures a fluid, consistent input experience across all interface layers. Additionally, secondary widgets must strictly adhere to semantic labeling (htmlFor/id) and ARIA dialog roles to ensure they are not overlooked by screen reader users.
**Action:** Consistently use AutoResizeTextarea for multi-line inputs in all UI layers. Always associate labels with inputs using semantic IDs and apply aria-labelledby to dialog containers.

## 2026-06-14 - [A11y for Disclosure Widgets and Semantic Action Lists]

**Learning:** Disclosure widgets (collapsible panels) require explicit programmatic relationships using `aria-controls` and `useId` to ensure screen readers can announce the expanded content. Additionally, refactoring groups of interactive elements (like quick actions or citation lists) from `div` to semantic `ul`/`li` containers provides a clearer document structure and navigation context for assistive technologies.
**Action:** Always use `useId` to link toggle buttons to their content via `aria-controls`. Prefer semantic list structures (`ul`/`li`) for collections of actions or items even when visual styling removes bullets/padding.

## 2026-06-15 - [Proper Nesting in Semantic Lists and Standard Iconography]

**Learning:** Refactoring generic containers to semantic lists must be done with care to avoid invalid HTML (e.g., nesting an `<li>` directly inside another `<li>`). Additionally, micro-UX improvements should adhere to established iconography patterns—such as using `ChevronRight` for collapsed and `ChevronDown` for expanded states—to maintain an intuitive visual language across the application.
**Action:** Double-check HTML structure for valid nesting when using `ul`/`li`. Follow project-standard icon orientations for collapsible components to ensure a predictable user experience.

## 2026-06-16 - [Safe Exit Animations for Streaming UI]

**Learning:** Exit animations in streaming interfaces (e.g., transitions from a 'thinking' state to a 'response' state) can feel abrupt if elements simply disappear. Wrapping conditional status indicators in `AnimatePresence` ensures a smooth visual handoff. However, avoid implementing live timers with `aria-live="polite"` as it creates excessive screen reader noise; prioritize silent visual progress for frequent updates.
**Action:** Always use `AnimatePresence` for smooth transitions between streaming states. Avoid frequent `aria-live` updates for rapidly changing values like timers.

## 2026-06-21 - [A11y for Live States and Semantic Interaction Groups]

**Learning:** Live UI states that lack visual labels (like a voice recording overlay) are "silent" to screen readers. Adding `role="status"` and `aria-live="polite"` ensures that assistive technology users are notified of state transitions (e.g., recording started) without being interrupted. Furthermore, adding `aria-label` to semantic lists of "Quick Actions" provides necessary context for group navigation, making the interface more discoverable.
**Action:** Always apply ARIA live regions to dynamic status overlays. Use descriptive `aria-label` on semantic list containers that serve as primary interaction points.

## 2026-07-12 - [Centralized Localization for Chat Overlays]

**Learning:** UI overlays that provide instructional feedback (e.g., voice recording status) must be localized to maintain a professional, accessible experience for multi-language users. Utilizing a shared `useChatLocale` hook ensures that ephemeral UI elements remain in sync with the user's selected language across the application.
**Action:** Always use `useChatLocale` for instructional text in chat-specific overlays and indicators.

## 2025-05-15 - [Stop Generation Pattern]

**Learning:** In AI chat interfaces, the primary action button (Send) should transition to a 'Stop' button during streaming to provide users with control and an intuitive way to interrupt long or irrelevant responses. This requires carefully managing the 'disabled' state to ensure the button remains interactive while the background process is active.
**Action:** Always implement a 'Stop Generation' toggle on the main input action button when dealing with streaming LLM responses. Use a clear visual cue like a 'Square' icon and ensure proper ARIA labels ('Stop generating') for accessibility.

## 2026-06-25 - [Stable A11y IDs and Dynamic Avatar Context]

**Learning:** Hardcoded IDs in reusable components can lead to duplicate IDs in the DOM, breaking accessibility associations. Using the `useId` hook ensures unique, stable IDs for linking triggers to menus via `aria-controls` and `aria-labelledby`. Additionally, providing dynamic, descriptive `alt` text for avatars (e.g., "Avatar for [Name]") instead of generic placeholders like "User avatar" provides better context for screen reader users when multiple users are present in an interface.
**Action:** Use `useId` for all ARIA-linked elements within components. Always pass user-specific context to avatar `alt` text to ensure unique and helpful descriptions.

## 2026-07-19 - [A11y and Keyboard Focus for Toast Notifications]

**Learning:** Toast notifications are critical status messages that can easily be missed by assistive technologies unless explicitly marked with `role="status"` and `aria-live="polite"`. Furthermore, close buttons within toast notifications are often skipped or unusable by keyboard navigation if they lack correct interactive attributes, such as `type="button"`, explicit focus indicators via `.focus-ring`, and informative hover/tooltip texts (`aria-label`, `title`).
**Action:** Always wrap custom toast elements with standard ARIA live/status roles and ensure any interactive elements (such as close/dismiss actions) are fully semantic buttons styled with `.focus-ring` and labeled with both `aria-label` and `title`.
