# Layout family: dark-status-list

> Plain dark background + structured list with status colors. Used for "FACTS (SOURCED) VS OUR TAKE" frames, status-list slides ("MARINA WORKS : STOPPED"), and timeline-style summaries.

## When to use

- Slide 2 typically (frame slide) styled as "FACTS (SOURCED) VS OUR TAKE".
- Status enumeration ("X : STOPPED", "Y : SUSPENDED", "Z : OPERATIONAL").
- 1-2 times per carousel max.

## Parameters

```yaml
heading: string # e.g. "FACTS (SOURCED) VS OUR TAKE"
items: # 3-6 items
  - label: string
    value: string
    status: enum [neutral, critical, positive] # neutral=white, critical=white value + red left-bar, positive=yellow
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
        padding: 80px var(--spacing-edge-margin) 180px
          var(--spacing-edge-margin);
        display: flex;
        flex-direction: column;
      }
      .heading {
        font-weight: var(--font-weight-extrabold);
        font-size: 56px;
        line-height: var(--line-height-tight);
        letter-spacing: var(--letter-spacing-title);
        color: var(--color-text-white);
        text-transform: uppercase;
        margin-bottom: var(--spacing-edge-margin);
      }
      .items {
        display: flex;
        flex-direction: column;
        gap: 32px;
      }
      .item {
        display: flex;
        flex-direction: column;
        gap: 8px;
        border-left: 4px solid rgba(255, 255, 255, 0.2);
        padding-left: 20px;
      }
      .label {
        font-weight: var(--font-weight-bold);
        font-size: 24px;
        letter-spacing: 0.04em;
        color: rgba(255, 255, 255, 0.6);
        text-transform: uppercase;
      }
      .value {
        font-weight: var(--font-weight-extrabold);
        font-size: 40px;
        line-height: 1.15;
        letter-spacing: var(--letter-spacing-title);
        text-transform: uppercase;
      }
      .status-neutral .value {
        color: var(--color-text-white);
      }
      .status-critical .value {
        color: var(--color-text-white);
      } /* WCAG fix 2026-07-14: red text on antracite = 1.87:1 (fail) — the red ALARM lives on the border line, per Art 14.4 */
      .status-critical .item {
        border-left-color: var(--color-status-red);
      }
      .status-positive .value {
        color: var(--color-accent-yellow);
      }
      .status-positive .item {
        border-left-color: var(--color-accent-yellow);
      }
    </style>
  </head>
  <body>
    <div class="heading" data-zone-type="text">{{heading}}</div>
    <div class="items" data-zone-type="text">
      {{#each items}}
      <div class="item status-{{status}}">
        <div class="label">{{label}}</div>
        <div class="value">{{value}}</div>
      </div>
      {{/each}}
    </div>
    <div class="logo" data-zone-type="logo">3 ALI ZERO</div>
  </body>
</html>
```

## Example data

```yaml
heading: "MARINA TUKA TIBUBENENG"
items:
  - label: "PBG STATUS"
    value: "MISSING"
    status: critical
  - label: "KKPR"
    value: "NOT FILED"
    status: critical
  - label: "OPENING DATE"
    value: "MARCH 2026"
    status: neutral
  - label: "OUR TAKE"
    value: "STOPPED"
    status: critical
```

## Common failures

- More than 6 items → visual fatigue
- Status enum outside [neutral, critical, positive] → undefined color, palette fail
- Heading >12 words → too dense
- All items same status → defeats the contrast purpose
