# Layout family: timeline-pinboard

> Pinboard-style date markers with short captions. Used for chronologies and regulatory timelines.

## When to use

- When narrative spans multiple dates (regulatory timeline, project chronology, audit cycles).
- 1 time per carousel max (becomes visual cliché if reused).

## Parameters

```yaml
heading: string  # e.g. "REGULATORY PERIMETER 2024-2026"
events:  # 3-5 events
  - date: string  # e.g. "JUL 2024"
    label: string  # 4-10 words UPPERCASE
    accent: enum [yellow, red, white]
```

## HTML/CSS skeleton

```html
<!doctype html>
<html><head>
<link rel="stylesheet" href="../_base.css">
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@700;800&display=swap');
body {
  padding: 80px var(--spacing-edge-margin) 180px var(--spacing-edge-margin);
  display: flex; flex-direction: column;
}
.heading {
  font-weight: var(--font-weight-extrabold);
  font-size: 48px; line-height: var(--line-height-tight);
  letter-spacing: var(--letter-spacing-title);
  color: var(--color-text-white);
  text-transform: uppercase; margin-bottom: var(--spacing-edge-margin);
}
.timeline {
  display: flex; flex-direction: column; gap: 40px;
  position: relative;
}
.timeline::before {
  content: ''; position: absolute;
  left: 18px; top: 0; bottom: 0;
  width: 2px; background: rgba(255,255,255,0.2);
}
.event {
  display: flex; gap: 32px; align-items: flex-start;
}
.dot {
  width: 38px; height: 38px; border-radius: 50%;
  background: rgba(255,255,255,0.2); flex-shrink: 0;
  z-index: 1;
}
.event.accent-red .dot { background: var(--color-status-red); }
.event.accent-yellow .dot { background: var(--color-accent-yellow); }
.event.accent-white .dot { background: var(--color-text-white); }
.event-content { display: flex; flex-direction: column; gap: 8px; }
.date {
  font-weight: var(--font-weight-bold);
  font-size: 22px; letter-spacing: 0.04em;
  color: rgba(255,255,255,0.6); text-transform: uppercase;
}
.label {
  font-weight: var(--font-weight-extrabold);
  font-size: 30px; line-height: var(--line-height-snug);
  letter-spacing: var(--letter-spacing-title);
  color: var(--color-text-white); text-transform: uppercase;
}
.event.accent-yellow .label { color: var(--color-accent-yellow); }
.event.accent-red .label { color: var(--color-text-white); }
</style></head>
<body>
  <div class="heading" data-zone-type="text">{{heading}}</div>
  <div class="timeline" data-zone-type="text">
    {{#each events}}
    <div class="event accent-{{accent}}">
      <div class="dot"></div>
      <div class="event-content">
        <div class="date">{{date}}</div>
        <div class="label">{{label}}</div>
      </div>
    </div>
    {{/each}}
  </div>
  <div class="logo" data-zone-type="logo">3 ALI ZERO</div>
</body></html>
```

## Common failures

- More than 5 events → visual fatigue, dates blur
- Date format inconsistent ("JUL 2024" vs "2024-07-15") → pick one and stick to it
- Heading >10 words → eats vertical space, timeline gets cramped
