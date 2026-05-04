# Workflow Branch sancho/* — Git untuk Subhi

Konvensi `sancho/*` adalah cara Subhi push code ke `balizero/nuzantara`
selama probation. Branch protection di `main` aktif → Subhi tidak bisa
push langsung. Pakai branch `sancho/*` → buka PR → review Antonello →
merge.

## Naming convention

Pattern: `sancho/<deliverable>-<short-desc>`

Format:

- `sancho/d1-funnel-tracking-fix` — Day 1 fix tracking GA4
- `sancho/d2-codebase-tour` — Day 2 codebase tour notes
- `sancho/article-money-pages-12` — Money pages task
- `sancho/visa-ux-improvements` — UX visa page improvements
- `sancho/ga4-utm-taxonomy` — UTM taxonomy update

Aturan:

- Lowercase
- Kata dipisah dengan dash `-`
- Max ~50 karakter (biar gampang baca)
- Awali dengan `d<N>` kalau task harian (Day 1, Day 2, ...)
- Atau slug deskriptif untuk task non-harian

Hook `subhi-bash-guard.sh` blok push ke `main` atau branch yang bukan
`sancho/*`.

## Workflow lengkap — step by step

### 1. Sync dengan main

```bash
cd ~/Projects/nuzantara
git checkout main
git pull origin main
```

Selalu start dari main yang up-to-date. Kalau ada pull conflict, ping
Antonello — biasanya berarti ada force push (rare) atau rebase yang
salah.

### 2. Buat branch baru

```bash
git checkout -b sancho/d1-funnel-tracking-fix
```

Branch dibuat lokal + automatically switched. Verifikasi:

```bash
git branch --show-current
# Output: sancho/d1-funnel-tracking-fix
```

### 3. Edit code

Buka file di VSCode / editor pilihan. Edit sesuai task.

Tips:

- Edit hanya scope VERDE (lihat `03_TASK_ROUTING_BAHASA.md`)
- Run linter / formatter sebelum commit
- Cek dulu file lain yang serupa (pattern matching) sebelum bikin
  pattern baru

### 4. Stage + commit

```bash
git status   # cek file yang berubah
git diff     # cek diff
git add apps/mouth/src/app/v2/_components/FunnelFeature.tsx
git commit -m "feat(mouth): add CTA tracking on FunnelFeature.tsx (D1)"
```

#### Commit message convention

Format: `<type>(<scope>): <subject>`

Type:

- `feat` — feature baru
- `fix` — bug fix
- `chore` — maintenance, dependency update
- `refactor` — restructure tanpa change behavior
- `docs` — dokumentasi only
- `test` — test only
- `style` — formatting / whitespace

Scope (untuk Subhi mostly):

- `mouth` — frontend
- `analytics` — analytics.ts only
- `e2e` — Playwright tests
- `docs` — onboarding docs

Subject:

- Kalimat imperatif (add, fix, update, refactor, NOT added/fixing)
- Lowercase pertama (kecuali nama file/component)
- No period di akhir
- Max ~70 karakter

Contoh good:

```
feat(mouth): add WhatsApp CTA on /visa page
fix(mouth): prevent double-click on FunnelFeature CTA
refactor(analytics): extract trackOutboundLink to lib/seo
docs(onboarding): clarify VERDE scope examples
```

Contoh bad:

```
✗ "Updated stuff."  → terlalu vague, no scope
✗ "feat: ADD CTA"   → uppercase, no scope
✗ "fixing bug"      → ing form
✗ "commit"          → meaningless
```

### 5. Multi-line commit (kalau perlu)

Kalau commit complex, body di paragraf kedua:

```bash
git commit -m "$(cat <<'EOF'
feat(mouth): add CTA tracking on FunnelFeature.tsx (D1)

Two CTAs ("Apply Visa" line 365, "Setup Company" line 393) were missing
onClick handlers, causing GA4 events to never fire. This was verified
with Search Console + GA4 cross-check showing 0 events for those CTAs
in last 90 days while page views were 2.3k.

Adds onClick handler that calls trackFunnelEvent from lib/analytics.ts.
Also adds Playwright e2e test in funnel-ctas.spec.ts to prevent
regression.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

#### Co-Authored-By

Kalau Claude sub-agent membantu (tutor, atau Claude di main repo
berkontribusi sketsa code), wajib include:

```
Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

di akhir commit body. Convention Bali Zero — credit yang kerja, bahkan
kalau itu AI.

### 6. Push branch

```bash
git push origin sancho/d1-funnel-tracking-fix
```

Output mestinya:

```
remote: Resolving deltas: 100% (5/5), done.
remote: Create a pull request for 'sancho/d1-funnel-tracking-fix' on GitHub by visiting:
remote:      https://github.com/balizero/nuzantara/pull/new/sancho/d1-funnel-tracking-fix
To github.com:balizero/nuzantara.git
 * [new branch]      sancho/d1-funnel-tracking-fix -> sancho/d1-funnel-tracking-fix
```

Kalau output ada error "permission denied" / "branch protection":

- Kemungkinan kamu lupa di branch `sancho/*` (cek dengan `git branch --show-current`)
- Atau coba push ke `main` (hook block ini)

### 7. Open PR

Cara paling cepat:

```bash
gh pr create --title "feat(mouth): add CTA tracking on FunnelFeature.tsx (D1)" \
  --body "$(cat <<'EOF'
## Summary
- Fix tracking GA4 di FunnelFeature.tsx (2 CTA missing onClick)
- Add Playwright e2e test untuk prevent regression

## Test plan
- [x] Run `npm run test:e2e` lokal — green
- [x] Manual klik CTA, verify GA4 event di console (window.gtag log)
- [ ] Antonello review

## Related
- Day 1 mission step #3 (lihat docs/onboarding/07_60_DAY_MISSION_BAHASA.md)
EOF
)"
```

Atau pakai UI GitHub:

1. Browse ke URL yang `git push` kasih
2. Klik "Create pull request"
3. Fill title + body sesuai template di atas

#### PR template

```markdown
## Summary
- [Bullet poin singkat: apa yang berubah]
- [Kenapa berubah]

## Test plan
- [ ] [Checklist test yang sudah jalan / akan jalan]
- [ ] Antonello review

## Related
- [Link ke issue / mission / context]
```

### 8. Tunggu review

**Tidak boleh self-merge dalam 30 hari pertama.**

Antonello (atau Asya kalau backend) akan review, kasih comment, request
changes kalau perlu. Kamu fix → push lagi → re-review → akhirnya merge.

Reasonable wait time:

- < 24 jam untuk review pertama (kalau urgent, ping WA)
- 1-3 hari untuk back-and-forth
- 1 minggu max sebelum kamu nudge

### 9. Setelah merge

Pull main, hapus branch lokal:

```bash
git checkout main
git pull origin main
git branch -d sancho/d1-funnel-tracking-fix
```

Branch remote di-auto-delete oleh GitHub setting (atau Antonello manual).

## Hal yang JANGAN dilakukan

### ❌ Push ke main langsung

```bash
# Hook akan blok ini
git push origin main
```

### ❌ Force push

```bash
# Risiko hapus history orang lain
git push --force-with-lease  # JANGAN, kecuali Antonello explicit OK
git push --force             # NEVER
```

### ❌ `--no-verify`

```bash
# Skip pre-commit hooks → bypass quality check
git commit --no-verify -m "..."  # JANGAN
```

Pre-commit hooks ada untuk format / lint / test. Kalau hook gagal,
**fix masalahnya**, jangan bypass.

### ❌ `--amend` di commit yang sudah pushed

```bash
# Modifikasi history yang sudah remote → break orang lain
git commit --amend  # JANGAN kalau commit udah di-push
```

OK kalau commit baru di lokal (belum push). NOT OK kalau sudah remote.

### ❌ Merge sendiri PR di 30 hari pertama

GitHub UI ada button "Merge pull request" — JANGAN klik untuk PR kamu
sendiri di 30 hari pertama. Tunggu Antonello.

### ❌ Branch lain selain `sancho/*`

```bash
git checkout -b feature/awesome  # JANGAN — bukan pattern Subhi
git checkout -b fix/visa-bug     # JANGAN — bukan pattern Subhi
git checkout -b sancho/quick     # OK
```

## Cheat sheet

```bash
# Workflow standard untuk task baru
git checkout main && git pull
git checkout -b sancho/<task-slug>
# ... edit code ...
git add <files>
git commit -m "feat(scope): subject"
git push origin sancho/<task-slug>
gh pr create --title "..." --body "..."
# ... wait review, fix if needed ...
# ... after merge:
git checkout main && git pull
git branch -d sancho/<task-slug>
```

## Kalau bingung

Tanya tutor:

```
/agent zantara-onboarding saya sudah commit di branch salah, gimana fix?
```

Tutor akan pandu cara `git stash`, `git cherry-pick`, atau apapun yang
diperlukan.
