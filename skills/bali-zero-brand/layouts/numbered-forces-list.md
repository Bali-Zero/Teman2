# Layout family: numbered-forces-list

> A giant numeral (matching the count named in the headline, e.g. "3
> FORCES...") sits left of a two-line headline, followed by a stack of
> yellow-label / white-caption items separated by a thin yellow rule. Used
> for "N things driving X" enumerations where the count itself is the hook.
> Distinct from `dark-status-list`: that family renders label=small-muted /
> value=large (status enumeration); this one renders label=large-yellow /
> value=small-white (numbered driver list) — inverting the hierarchy would
> break every existing dark-status-list carousel, hence the separate family.

## When to use

- Headline names a count ("3 FORCES BEHIND THE RISE", "4 REASONS WHY...").
- 2-4 items, each a short driver/force/reason + one-line elaboration.
- Pin explicitly via `layout_family: "numbered-forces-list"` — never
  auto-routed (needs the leading numeral parsed out of the headline AND a
  structured `items` array, neither of which the generic non-hero routing
  guarantees).

## Parameters

```yaml
heading:
  string # "N FORCES BEHIND THE RISE" — leading integer is extracted
  # into the giant numeral graphic; the remainder is the
  # two-line headline text next to it.
items: # 2-4 items
  - label: string # short driver name, rendered large + yellow
    value: string # one-line elaboration, rendered small + white
```

## HTML/CSS skeleton

```html
<!doctype html>
<html>
  <head>
    <link rel="stylesheet" href="../_base.css" />
    <style>
      @import url("https://fonts.googleapis.com/css2?family=Montserrat:wght@700;800&display=swap");
      body {
        padding: 110px var(--spacing-edge-margin) 180px
          var(--spacing-edge-margin);
        display: flex;
        flex-direction: column;
        /* 2026-07-14: center the block vertically — with 3 forces the content
           filled ~45% of the canvas top-anchored (top-heavy void, critic soft
           flag on every render). Padding still reserves logo/indicator zones. */
        justify-content: center;
      }
      .numeral-row {
        display: flex;
        align-items: center;
        gap: 20px;
        margin-bottom: var(--spacing-edge-margin);
      }
      .numeral {
        font-weight: var(--font-weight-extrabold);
        font-size: 160px;
        line-height: 1;
        color: var(--color-accent-yellow);
      }
      .heading {
        font-weight: var(--font-weight-extrabold);
        font-size: 52px;
        line-height: var(--line-height-tight);
        letter-spacing: var(--letter-spacing-title);
        color: var(--color-accent-yellow);
        text-transform: uppercase;
        white-space: pre-line;
      }
      .items {
        display: flex;
        flex-direction: column;
        gap: 28px;
      }
      .item {
        border-left: 4px solid var(--color-accent-yellow);
        padding-left: 20px;
      }
      .item .label {
        font-weight: var(--font-weight-extrabold);
        font-size: 32px;
        line-height: 1.15;
        letter-spacing: var(--letter-spacing-title);
        color: var(--color-accent-yellow);
        text-transform: uppercase;
        margin-bottom: 6px;
      }
      .item .value {
        font-weight: var(--font-weight-bold);
        font-size: 24px;
        line-height: 1.3;
        letter-spacing: var(--letter-spacing-body);
        color: var(--color-text-white);
        text-transform: uppercase;
      }
    </style>
  </head>
  <body>
    <div class="numeral-row" data-zone-type="text">
      <div class="numeral">{{numeral}}</div>
      <div class="heading">{{heading}}</div>
    </div>
    <div class="items" data-zone-type="text">
      {{#each items}}
      <div class="item">
        <div class="label">{{label}}</div>
        <div class="value">{{value}}</div>
      </div>
      {{/each}}
    </div>
    <div class="logo" data-zone-type="logo">3 ALI ZERO</div>
  </body>
</html>
```

## Example data (visa revenue drivers)

```json
{
  "heading": "3 FORCES BEHIND THE RISE",
  "items": [
    {
      "label": "SECOND HOME VISA",
      "value": "E33 — THE PRODUCT DRIVING INVESTOR UPTAKE."
    },
    {
      "label": "REMOTE WORKER VISA",
      "value": "E33G — CAPTURES DIGITAL-NOMAD DEMAND."
    },
    {
      "label": "DIGITAL TRANSFORMATION",
      "value": "DIRECTOR GENERAL MARANTOKO CITES IT ALONGSIDE SELECTIVE POLICY."
    }
  ]
}
```

## Common failures

- Headline has no leading integer → composer falls back to no numeral
  graphic (empty `{{numeral}}`), heading still renders full-width. Verify
  the headline is authored "N ..." before pinning this family.
- More than 4 items → numeral+heading proportions get crowded out, items
  stack too tall for the canvas.
- `value` longer than ~12 words → wraps to 3 lines, breaks the item's
  visual rhythm against its siblings.
