# Layout family: source-citation

> Penultimate slide (slide N-1) for regulatory / visa / tax / property carousels. Dedicates an entire slide to the verbatim primary-source citation. Credibility infrastructure. Inspired by SOTA pattern #11 (ProPublica, The Markup, AP). Added 2026-05-12 from `_external-bench-2026-05.md` adoption.

## When to use

- **MUST** be present as slide N-1 (before statement-bomb/elegant-close) for these domains:
  - `regulatory`
  - `visa`
  - `tax`
  - `property`
- **MAY** be omitted only for `cultural-photo` carouseli where no primary regulation is cited (rare).
- Soft fail at constitution Article 14.3 if missing for required domains.

## Parameters

```yaml
title: string  # "SUMBER" (ID default) or "SOURCES" (EN) — single word, UPPERCASE
citations: array  # 1-5 items, each with:
  - body: string         # regulation citation verbatim (e.g. "KEP-71/PJ/2026")
    issuer: string       # ministry / agency (e.g. "DJP — Direktorat Jenderal Pajak")
    date: string         # decree date (e.g. "30 April 2026")
    url: string          # primary source URL (DJP / OSS / JDIH / Permenkumham PDF)
    note: string         # optional 5-15 word clarification
primary_source_url: string  # the one URL to encode as QR if also using qr-closing pattern (typically citations[0].url)
```

## HTML/CSS skeleton

```html
<!doctype html>
<html><head>
<link rel="stylesheet" href="../_base.css">
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@700;800&family=IBM+Plex+Mono:wght@400;500&display=swap');
body {
  background: var(--color-bg-antracite);
  padding: var(--spacing-edge-margin);
  display: flex; flex-direction: column;
}
.source-title {
  font-family: var(--font-family-primary);
  font-weight: var(--font-weight-extrabold);
  font-size: 48px;
  letter-spacing: 0.04em;
  color: var(--color-accent-yellow);
  text-transform: uppercase;
  margin-bottom: 8px;
}
.source-title::after {
  content: "";
  display: block;
  width: 80px;
  height: 4px;
  background-color: var(--color-status-red);
  margin-top: 12px;
}
.citations-list {
  list-style: none;
  margin-top: 48px;
  display: flex; flex-direction: column;
  gap: 32px;
  max-width: 920px;
}
.citation-item {
  font-family: var(--font-family-mono);
  color: var(--color-text-white);
}
.citation-code {
  font-size: 26px;
  font-weight: 500;
  letter-spacing: 0.02em;
  margin-bottom: 6px;
}
.citation-issuer {
  font-family: var(--font-family-primary);
  font-size: 18px;
  font-weight: var(--font-weight-bold);
  color: var(--color-text-muted);
  letter-spacing: 0.04em;
  margin-bottom: 4px;
}
.citation-date {
  font-family: var(--font-family-mono);
  font-size: 15px;
  color: var(--color-text-muted);
  margin-bottom: 6px;
}
.citation-url {
  font-family: var(--font-family-mono);
  font-size: 14px;
  color: var(--color-accent-yellow);
  word-break: break-all;
  max-width: 100%;
}
.citation-note {
  font-family: var(--font-family-primary);
  font-size: 16px;
  font-style: italic;
  color: var(--color-text-muted);
  margin-top: 4px;
}
.verbatim-stamp {
  position: absolute;
  bottom: 200px;
  right: var(--spacing-edge-margin);
  font-family: var(--font-family-mono);
  font-size: 12px;
  color: var(--color-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.1em;
}
.verbatim-stamp::before {
  content: "✓ ";
  color: var(--color-status-red);
}
</style></head>
<body>
  <div class="source-title" data-zone-type="text">{{title}}</div>
  <ul class="citations-list" data-zone-type="text">
    {{#each citations}}
    <li class="citation-item">
      <div class="citation-code">{{body}}</div>
      <div class="citation-issuer">{{issuer}}</div>
      <div class="citation-date">{{date}}</div>
      <div class="citation-url">{{url}}</div>
      {{#if note}}<div class="citation-note">{{note}}</div>{{/if}}
    </li>
    {{/each}}
  </ul>
  <div class="verbatim-stamp" data-zone-type="text">Verbatim · Primary source</div>
  <div class="logo" data-zone-type="logo">3 ALI ZERO</div>
</body></html>
```

## Examples

### Example 1 — KEP-71/PJ/2026 (tax)
- title: `SUMBER`
- citations:
  - body: `KEP-71/PJ/2026`
    issuer: `DJP — Direktorat Jenderal Pajak`
    date: `30 April 2026`
    url: `https://www.pajak.go.id/...`
    note: `Surat keputusan resmi, dapat diunduh sebagai PDF`

### Example 2 — Permenkumham 22/2023 + Permenimipas 5/2025 (visa)
- title: `SOURCES`
- citations (2 items):
  - body: `Permenkumham 22/2023`
    issuer: `Kemenkumham — Ministry of Law & Human Rights`
    date: `Effective 1 January 2024`
    url: `https://jdih.kemenkumham.go.id/...`
    note: `KITAS visa classifications C1-C28`
  - body: `Permenimipas 5/2025`
    issuer: `Kemenimipas — Ministry of Immigration`
    date: `1 March 2025`
    url: `https://jdih.imigrasi.go.id/...`
    note: `Golden Visa amendments to Permenkumham 22/2023`

## Common failures

- Paraphrased citation ("recent tax decree" instead of `KEP-71/PJ/2026`) → constitution Article 6.4 hard fail
- Missing date → soft fail, decree without date can't be verified
- URL not from primary issuer (e.g. links to a blog summary instead of JDIH/DJP) → hard fail, defeats purpose of credibility-infra
- Citations array empty → hard fail, layout has no content
- >5 citations → split into 2 source-citation slides if needed (rare)
- citation-url cut off (overflow) → use shortened anchor-text alternative or break URL across lines

## Render-time check (Playwright assertion)

```js
// 1. Every citation must have body + issuer + date + url
const citations = await page.evaluate(() =>
  Array.from(document.querySelectorAll('.citation-item')).map(li => ({
    body: li.querySelector('.citation-code')?.textContent.trim(),
    issuer: li.querySelector('.citation-issuer')?.textContent.trim(),
    date: li.querySelector('.citation-date')?.textContent.trim(),
    url: li.querySelector('.citation-url')?.textContent.trim(),
  }))
);
for (const c of citations) {
  if (!c.body || !c.issuer || !c.date || !c.url) {
    throw new Error('source-citation slide missing required field on citation');
  }
}

// 2. URL must look like a primary source domain
const trustedHosts = [
  'pajak.go.id', 'jdih.kemenkumham.go.id', 'jdih.imigrasi.go.id',
  'oss.go.id', 'bps.go.id', 'bi.go.id', 'kemenkeu.go.id',
  'simbg.pu.go.id', 'kpu.go.id'
];
for (const c of citations) {
  const isTrustred = trustedHosts.some(h => c.url.includes(h));
  if (!isTrustred) {
    console.warn(`source-citation URL ${c.url} not from known primary host — Antonello review`);
  }
}
```

## Companion: QR code (when also using elegant-close as slide N)

If the carousel ends with `source-citation` (slide N-1) + `elegant-close` (slide N), the elegant-close MAY include a `.qr-closing` element encoding `primary_source_url` (typically `citations[0].url`). This closes the loop: reader screenshots the QR, opens primary source. Patterns #11 + #25 combined.

If the carousel skips elegant-close and ends with `source-citation` as the literal last slide, embed the QR directly on the source-citation slide (right column) — same `.qr-closing` CSS class.
