# Hari 4 — Playwright E2E Test Coverage

**Mission ref:** §5 testing infrastructure (`07_60_DAY_MISSION_BAHASA.md`)
**Estimasi waktu:** 2 jam
**Pre-req:** Day 3 PR merged, atau under review (jangan blocked)

## Tujuan

Tambah Playwright e2e test yang cover semua 4 funnel CTA dan WhatsApp
CTA contextual. Run test lokal, semua green.

## Konteks

Day 3 kamu fix 2 CTA + add 1 test. Day 4 expand: tambah test untuk
sisa CTA + WA CTA, jadi total minimal 5-6 tests yang assert tracking.

Day 30 KPI: 95% CTA homepage punya tracking. Test = assertion bahwa
tracking works.

## Pre-requisiti

- [ ] Day 3 selesai (PR D1 open atau merged)
- [ ] CWD di `~/Projects/nuzantara/`
- [ ] Branch sancho/* baru (`sancho/d4-e2e-coverage`)

## Langkah-langkah

### 1. Buat branch baru

```bash
cd ~/Projects/nuzantara
git checkout main
git pull origin main
git checkout -b sancho/d4-e2e-coverage
```

### 2. Audit existing test

```bash
code apps/mouth/e2e/funnel-ctas.spec.ts
```

List test yang sudah ada:

```bash
grep "test(" apps/mouth/e2e/funnel-ctas.spec.ts
```

Catat di `local/notes-day4.md`:

- Test 1: ...
- Test 2: ...
- Gap: ...

### 3. Identifikasi CTA yang belum di-test

Tanya tutor:

```
/agent zantara-onboarding di FunnelFeature.tsx ada berapa CTA total dan di e2e funnel-ctas.spec.ts berapa yang ditest? Kasih saya gap list.
```

Tutor cross-reference dan kasih gap list.

### 4. Tambah test untuk gap

Pattern (sama dengan Day 3 test):

```ts
test('FunnelFeature CTA Setup Company fires GA4 event', async ({ page }) => {
  await page.addInitScript(() => {
    (window as any).__ga4Events = [];
    (window as any).gtag = (...args: any[]) => {
      (window as any).__ga4Events.push(args);
    };
  });

  await page.goto('/');
  await page.click('[data-testid="funnel-setup-company"]');

  const events = await page.evaluate(() => (window as any).__ga4Events);
  expect(events).toContainEqual(['event', 'cta_setup_company', { source: 'homepage_funnel' }]);
});
```

Tambah variasi untuk:

- `cta_apply_visa`
- `cta_setup_company`
- `cta_tax_help`
- `cta_property_eligibility`
- `whatsapp_cta_homepage` (kalau ada di header/footer)

### 5. Refactor: extract helper

Kalau test mulai repetitif, extract helper:

```ts
// e2e/helpers/ga4.ts
import { Page, expect } from '@playwright/test';

export async function setupGa4Mock(page: Page) {
  await page.addInitScript(() => {
    (window as any).__ga4Events = [];
    (window as any).gtag = (...args: any[]) => {
      (window as any).__ga4Events.push(args);
    };
  });
}

export async function assertGa4Event(page: Page, event: string, props: any) {
  const events = await page.evaluate(() => (window as any).__ga4Events);
  expect(events).toContainEqual(['event', event, props]);
}
```

Lalu test jadi:

```ts
test('FunnelFeature CTA Setup Company fires GA4 event', async ({ page }) => {
  await setupGa4Mock(page);
  await page.goto('/');
  await page.click('[data-testid="funnel-setup-company"]');
  await assertGa4Event(page, 'cta_setup_company', { source: 'homepage_funnel' });
});
```

Tutor bantu refactor:

```
/agent zantara-onboarding tolong review struktur helper ini, apakah idiomatic Playwright? Ada cara yang lebih baik?
```

### 6. Run all e2e

```bash
cd apps/mouth
npm run test:e2e
```

Semua harus green. Output target:

```
Running 12 tests using 4 workers
  ✓ ... (semua test)
12 passed (45s)
```

Kalau red: tutor bantu debug.

### 7. Stage + commit

```bash
git status
git add apps/mouth/e2e/funnel-ctas.spec.ts apps/mouth/e2e/helpers/

git commit -m "$(cat <<'EOF'
test(e2e): expand funnel CTA tracking coverage to 5 CTAs (D4)

Day 3 added 1 test for Apply Visa CTA. This commit expands coverage to
all 4 funnel CTAs + WhatsApp CTA, refactoring duplicate setup into
e2e/helpers/ga4.ts (setupGa4Mock + assertGa4Event).

Total tests: 5 (Apply Visa, Setup Company, Tax Help, Property
Eligibility, WhatsApp). All green locally.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### 8. Push + PR

```bash
git push origin sancho/d4-e2e-coverage

gh pr create --title "test(e2e): expand funnel CTA tracking coverage to 5 CTAs (D4)" \
  --body "$(cat <<'EOF'
## Summary
- Expand test coverage dari 1 ke 5 CTA
- Extract helper ga4.ts untuk reduce repetition
- Cover Apply Visa, Setup Company, Tax Help, Property Eligibility, WhatsApp

## Test plan
- [x] `npm run test:e2e` lokal — 12 passed
- [x] Verify helper idiomatic dengan tutor review
- [ ] Antonello review

## Related
- Day 4 mission (§5 testing infrastructure)
- Day 30 KPI: 95% CTA tracking — sekarang tested
EOF
)"
```

## Verifikasi

- [ ] 5 test files ada di `e2e/funnel-ctas.spec.ts`
- [ ] Helper extracted di `e2e/helpers/ga4.ts`
- [ ] Local run green
- [ ] PR open

## Kalau ada error

| Masalah | Fix |
| --- | --- |
| Test flaky (kadang green kadang red) | Race condition. Tambah `await page.waitForLoadState('networkidle')` sebelum click. |
| Selector `[data-testid=...]` tidak match | Cek HTML render — `data-testid` tidak konsisten case. Lower-case kebab. |
| `npm run test:e2e` hang | Browser tidak install. Run `npx playwright install chromium`. |
| CI fail tapi lokal green | Tutor diagnose — biasanya env vars / fixture issue |

## Selesai?

PR open + green CI. WA Antonello, tunggu review.

Lanjut Day 5: `day5_article_inventory.md`.
