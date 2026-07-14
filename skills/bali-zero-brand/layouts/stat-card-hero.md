# Layout family: stat-card-hero

> Text-only comparison slide: a big "A vs B" headline stat, followed by a
> horizontal bar-comparison chart (grey vs yellow) that makes the delta
> between two (or three) values legible at a glance, then a closing
> takeaway line. Used for "same metric, two periods" reveals — e.g. H1
> revenue year-over-year — where the number alone doesn't convey the size
> of the gap as well as a bar does.

## When to use

- A slide whose core content is a numeric comparison between 2-3 rows
  (periods, categories) AND the storyboarder supplied a `chart` object.
- Do NOT auto-route here (see composer.py `map_slide_to_family`) — this
  family needs a `chart.rows` array with parseable numeric `value` strings,
  which the generic non-hero routing does not guarantee. Pin explicitly via
  `layout_family: "stat-card-hero"` in slides.json.

## Parameters

```yaml
heading: string # big stat line, e.g. "IDR / 2.815T VS 2.645T"
subheading: string # kicker above the heading, yellow
body: string # closing takeaway line below the chart
chart:
  type: "bar-comparison"
  rows: # 2-3 rows
    - label: string # e.g. "H1 2025"
      value: string # display string, e.g. "IDR 2.645T"
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
        padding: 100px var(--spacing-edge-margin) 180px
          var(--spacing-edge-margin);
        display: flex;
        flex-direction: column;
        /* 2026-07-14: center the stack vertically — heading+chart+body filled
           ~50% of the canvas top-anchored (top-heavy void, critic soft flag). */
        justify-content: center;
      }
      .top-rule {
        width: 90px;
        height: 8px;
        background: var(--color-accent-yellow);
        margin-bottom: 36px;
      }
      .subheading {
        font-weight: var(--font-weight-bold);
        font-size: var(--font-size-subheadline);
        line-height: var(--line-height-snug);
        letter-spacing: var(--letter-spacing-title);
        color: var(--color-accent-yellow);
        text-transform: uppercase;
        margin-bottom: 16px;
      }
      .heading {
        font-weight: var(--font-weight-extrabold);
        font-size: 64px;
        line-height: var(--line-height-tight);
        letter-spacing: var(--letter-spacing-title);
        color: var(--color-accent-yellow);
        text-transform: uppercase;
        text-wrap: balance;
        margin-bottom: 48px;
      }
      .heading .lead {
        color: var(--color-text-white);
      }
      .chart {
        display: flex;
        flex-direction: column;
        gap: 28px;
        margin-bottom: 40px;
      }
      .chart-row .row-head {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        margin-bottom: 10px;
      }
      .chart-row .row-label {
        font-weight: var(--font-weight-bold);
        font-size: 22px;
        letter-spacing: 0.04em;
        color: rgba(255, 255, 255, 0.6);
        text-transform: uppercase;
      }
      .chart-row .row-value {
        font-weight: var(--font-weight-extrabold);
        font-size: 28px;
        letter-spacing: var(--letter-spacing-title);
        color: var(--color-text-white);
      }
      .chart-row.is-max .row-value {
        color: var(--color-accent-yellow);
      }
      .chart-row .bar-track {
        width: 100%;
        height: 32px;
        background: rgba(255, 255, 255, 0.06);
      }
      .chart-row .bar-fill {
        height: 100%;
        background: rgba(255, 255, 255, 0.45);
      }
      .chart-row.is-max .bar-fill {
        background: var(--color-accent-yellow);
      }
      .baseline-rule {
        height: 2px;
        background: rgba(255, 255, 255, 0.14);
        margin-bottom: 28px;
      }
      .body {
        font-weight: var(--font-weight-bold);
        font-size: 32px;
        line-height: 1.4;
        letter-spacing: var(--letter-spacing-body);
        color: var(--color-text-white);
        text-transform: none;
      }
      .body .emphasis {
        color: var(--color-accent-yellow);
      }
    </style>
  </head>
  <body>
    <div class="top-rule" data-zone-type="text"></div>
    <div class="subheading" data-zone-type="text">{{subheading}}</div>
    <div class="heading" data-zone-type="text">{{heading}}</div>
    <div class="chart" data-zone-type="text">
      {{#each chart_rows}}
      <div class="chart-row{{#if is_max}} is-max{{/if}}">
        <div class="row-head">
          <div class="row-label">{{label}}</div>
          <div class="row-value">{{value}}</div>
        </div>
        <div class="bar-track">
          <div class="bar-fill" style="width:{{bar_pct}}%"></div>
        </div>
      </div>
      {{/each}}
    </div>
    <div class="baseline-rule"></div>
    <div class="body" data-zone-type="text">{{body}}</div>
    <div class="logo" data-zone-type="logo">3 ALI ZERO</div>
  </body>
</html>
```

## Example data (H1 revenue YoY)

```json
{
  "subheading": "H1 REVENUE, YEAR OVER YEAR · +6.42%",
  "heading": "IDR / 2.815T VS 2.645T",
  "chart": {
    "type": "bar-comparison",
    "rows": [
      { "label": "H1 2025", "value": "IDR 2.645T" },
      { "label": "H1 2026", "value": "IDR 2.815T" }
    ]
  },
  "body": "SAME METRIC, SAME SOURCE, SIX MONTHS EACH. VISA VOLUME FELL 6.77% — YET REVENUE ROSE 6.42%."
}
```

## Common failures

- `chart.rows` missing/empty → composer drops the `{{#each}}` block entirely,
  slide renders with an empty gap between heading and body. Always verify
  `chart.rows` has ≥2 parseable numeric `value` strings before pinning this
  family.
- More than 3 rows → bars get visually thin, comparison reads as clutter.
- Values in mixed units (e.g. one row "IDR 2.6T", another "38%") → the
  proportional bar width is meaningless across units. One chart = one unit.
