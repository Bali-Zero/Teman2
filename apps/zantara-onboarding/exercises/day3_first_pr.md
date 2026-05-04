# Hari 3 — PR Pertama (D1 Mission Fix)

**Mission ref:** §3 D1 fix tracking GA4 (`07_60_DAY_MISSION_BAHASA.md`)
**Estimasi waktu:** 2-3 jam
**Pre-req:** Day 1 + Day 2 selesai, kamu sudah identify 2 CTA missing onClick

## Tujuan

PR pertama kamu di Bali Zero. Fix tracking GA4 di FunnelFeature.tsx,
add Playwright e2e test, push ke `sancho/d1-funnel-tracking-fix`,
buka PR, tunggu review Antonello.

## Konteks

Day 2 kamu identify gap. Hari ini implement fix + test.

Goal mission: hari 30, 95% CTA homepage punya tracking aktif.

## Pre-requisiti

- [ ] Day 2 selesai, catatan ada di `local/notes-day2.md`
- [ ] Kamu tahu line numbers 2 CTA missing onClick
- [ ] CWD di `~/Projects/nuzantara/`
- [ ] Branch saat ini = `main` (cek `git branch --show-current`)

## Langkah-langkah

### 1. Sync main + buat branch

```bash
cd ~/Projects/nuzantara
git checkout main
git pull origin main
git checkout -b sancho/d1-funnel-tracking-fix
```

Verifikasi:

```bash
git branch --show-current
# Output: sancho/d1-funnel-tracking-fix
```

### 2. Edit FunnelFeature.tsx

Buka file:

```bash
code apps/mouth/src/app/v2/_components/FunnelFeature.tsx
```

Di line yang Day 2 kamu identify, tambah onClick handler. Pattern
referensi (lihat CTA yang SUDAH punya onClick di file yang sama):

```tsx
<Button
  onClick={() => trackFunnelEvent('cta_apply_visa', { source: 'homepage_funnel' })}
  href="/visa"
>
  Apply Visa
</Button>
```

Pastikan import `trackFunnelEvent` di top of file (kalau belum ada):

```tsx
import { trackFunnelEvent } from '@/lib/analytics';
```

Tutor bantu kalau bingung:

```
/agent zantara-onboarding di FunnelFeature.tsx line XXX saya tambah onClick={() => trackFunnelEvent(...)} tapi import sudah ada di line YYY. Apa pattern eventName yang konsisten dengan CTA lain di file ini?
```

### 3. Verifikasi local — manual click

Run dev server:

```bash
cd apps/mouth
npm install   # kalau belum
npm run dev
```

Browser buka `http://localhost:3000`. Buka DevTools console:

```js
window.gtag = (...args) => console.log('GA4 event:', args);
```

Klik CTA yang kamu tambah onClick-nya. Console harus log `GA4 event:
['event', 'cta_apply_visa', {source: 'homepage_funnel'}]`.

Kalau tidak log apa-apa: onClick tidak terikat. Cek typo / missing
import.

### 4. Add Playwright e2e test

Buka:

```bash
code apps/mouth/e2e/funnel-ctas.spec.ts
```

Tambah test pattern:

```ts
test('FunnelFeature CTA Apply Visa fires GA4 event', async ({ page }) => {
  // Mock gtag
  await page.addInitScript(() => {
    (window as any).__ga4Events = [];
    (window as any).gtag = (...args: any[]) => {
      (window as any).__ga4Events.push(args);
    };
  });

  await page.goto('/');
  await page.click('[data-testid="funnel-apply-visa"]');  // sesuaikan selector

  const events = await page.evaluate(() => (window as any).__ga4Events);
  expect(events).toContainEqual(['event', 'cta_apply_visa', { source: 'homepage_funnel' }]);
});
```

Sesuaikan selector. Kalau CTA tidak ada `data-testid`, tambah:

```tsx
<Button data-testid="funnel-apply-visa" onClick={...}>
```

### 5. Run test e2e

```bash
cd apps/mouth
npm run test:e2e -- funnel-ctas
```

Output mestinya:

```
Running 5 tests using 1 worker
  ✓ FunnelFeature CTA Apply Visa fires GA4 event (2.5s)
  ✓ FunnelFeature CTA Setup Company fires GA4 event (2.3s)
  ...
5 passed (12s)
```

Kalau red: debug. Tutor bantu:

```
/agent zantara-onboarding test funnel-ctas fail dengan error: [paste error]. Saya stuck.
```

### 6. Stage + commit

```bash
git status
# Should show:
#   modified: apps/mouth/src/app/v2/_components/FunnelFeature.tsx
#   modified: apps/mouth/e2e/funnel-ctas.spec.ts

git add apps/mouth/src/app/v2/_components/FunnelFeature.tsx
git add apps/mouth/e2e/funnel-ctas.spec.ts

git commit -m "$(cat <<'EOF'
feat(mouth): add CTA tracking on FunnelFeature.tsx (D1)

Two CTAs ("Apply Visa" line XXX, "Setup Company" line YYY) were missing
onClick handlers, causing GA4 events to never fire. This caused 90 days
of website traffic with effectively zero attribution.

Adds onClick handler that calls trackFunnelEvent from lib/analytics.ts.
Also adds Playwright e2e test in funnel-ctas.spec.ts to prevent
regression.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### 7. Push branch

```bash
git push origin sancho/d1-funnel-tracking-fix
```

Output ada line:

```
remote: Create a pull request for 'sancho/d1-funnel-tracking-fix'
```

### 8. Open PR

```bash
gh pr create --title "feat(mouth): add CTA tracking on FunnelFeature.tsx (D1)" \
  --body "$(cat <<'EOF'
## Summary
- Fix tracking GA4 di FunnelFeature.tsx (2 CTA missing onClick)
- Add Playwright e2e test untuk prevent regression

## Test plan
- [x] Run `npm run test:e2e -- funnel-ctas` lokal — green (5 passed)
- [x] Manual klik CTA, verify GA4 event di DevTools console
- [ ] Antonello review

## Related
- Day 1 mission step #3 (lihat docs/onboarding/07_60_DAY_MISSION_BAHASA.md)
- Day 30 KPI: 95% CTA homepage punya tracking
EOF
)"
```

Output: PR URL. Salin URL.

## Verifikasi

- [ ] PR open di github.com/balizero/nuzantara/pulls
- [ ] Title pakai pattern `feat(mouth): ...`
- [ ] Branch = `sancho/d1-funnel-tracking-fix`
- [ ] Body include test plan checklist
- [ ] CI jalan (kalau ada — Actions tab)

## Kalau ada error

| Masalah | Fix |
| --- | --- |
| Push ditolak (permission denied) | Cek branch — harus `sancho/*` |
| `gh pr create` fail (auth) | `gh auth login` ulang, pilih web flow |
| CI fail (lint/type) | Tutor bantu fix, push lagi |
| Antonello request changes | Address comment, push lagi (tidak perlu force) |

## Selesai?

Ketika PR open + CI green:

1. Screenshot PR page
2. WA ke Antonello: "PR D1 ready for review: <URL>"
3. Tunggu review (target <24h)
4. Kalau ada comments, address + push update
5. Jangan self-merge — tunggu Antonello

Setelah merge:

```bash
git checkout main
git pull origin main
git branch -d sancho/d1-funnel-tracking-fix
```

Lanjut Day 4: `day4_playwright_test.md` (extend test coverage).
