## 2025-05-15 - [Accessibility for Custom Interactive Elements]
**Learning:** Adding keyboard handlers (`onKeyDown`) to non-semantic elements like `div` is insufficient for accessibility if the element is not focusable (`tabIndex={0}`) and lacks visible focus indicators. Interactive elements that only appear on hover must also be made visible on focus for keyboard users.
**Action:** Always ensure `tabIndex={0}`, `role="button"`, and visible focus states (`focus-visible:ring`, `focus:opacity-100`) are implemented together for custom interactive components.

## 2025-05-15 - [Menu Trigger Accessibility]
**Learning:** Popover and menu triggers often miss `aria-haspopup` and `aria-expanded` attributes, which are critical for screen reader users to understand that a button controls a dynamic region.
**Action:** Include `aria-haspopup="true"` and bind `aria-expanded` to the open state on all toggle buttons that control menus or popovers.
