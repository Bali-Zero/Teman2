# CLAUDE.md — Subhi Workspace

**User:** Subhi Darajat
**Peran:** Growth Systems Owner — Akuisisi Organik & Konversi
**Probation:** 2026-04-30 → 2026-07-29 (90 hari)
**Track:** Operator → Builder → Rekan
**Repo lavoro:** `balizero/nuzantara` (branch `sancho/*`)
**Repo onboarding:** `~/zantara-onboarding/` (kamu di sini, distribusi rsync dari Pro)

## Model — JANGAN PAKAI OPUS

**Default model: `claude-sonnet-4-6`** (Sonnet, sudah set di settings.json).

**JANGAN pakai Opus** (`claude-opus-*`) tanpa izin eksplisit Antonello.
Opus ~5x lebih mahal. Kamu pakai akun Claude Pro kamu sendiri — kuota
terbatas, jangan habiskan dengan Opus untuk task harian. Sonnet 4.6
cukup untuk semua exercise + onboarding.

Kalau kamu accidentally trigger Opus (via `/model opus` atau
`claude --model opus`), STOP dan kembali ke Sonnet:

```
/model sonnet
```

## Bahasa

**Selalu jawab dalam Bahasa Indonesia kepada Subhi.** Code, commit, branch
name, PR title tetap dalam Bahasa Inggris (konvensi codebase).

Antonello (boss, owner Bali Zero) parla italiano — tapi ketika kamu
berinteraksi DI SINI, dengan Subhi, selalu bahasa.

## Tutor

Untuk setiap pertanyaan tentang sistem Bali Zero, perimeter Subhi,
NotebookLM authority, atau 60-day mission, panggil:

```
/agent zantara-onboarding "<pertanyaan>"
```

Sub-agent ini punya akses ke memory mirror harian dari sistem Bali Zero,
4 NotebookLM (NB-1, NB-2, NB-9, NB-OPS), dan GitHub MCP scoped sancho/*.

## Memory mirror

`.claude/memory-mirror/` di-update setiap pagi 04:00 WITA dari Pro Antonello
via rsync di tailnet Tailscale (tidak via GitHub). Baca file ini ketika
butuh konteks tentang:

- Project aktif (NLM strategy, Sprint W1, audit zero-crash)
- Konvensi codebase, repo paths
- Lessons learned, scar incidents (cicatrix)
- NB authority

`.claude/memory-mirror-subhi/` di-update otomatis tiap sesi (Stop hook):
ringkasan topik yang kamu obrolkan dengan tutor, supaya esok hari dia
ingat percakapan kemarin.

## RBAC singkat

Lihat `docs/onboarding/02_RBAC_BAHASA.md` lengkap. Ringkasan:

- ✅ **VERDE**: `apps/mouth/**`, GA4/GSC, distribution
- ⚠️ **GIALLO**: backend endpoint baru → pair Asya/Antonello
- 🚫 **ROSSO**: RAG core, Qdrant, secrets, fly.toml, organism/genome

Tutor akan tolak request yang masuk ROSSO. Hooks `.claude/hooks/subhi-bash-guard.sh`
juga enforce di Bash level (fly, gcloud, sudo, dll).

## Workflow git

1. Branch baru: `git checkout -b sancho/<task-slug>`
2. Edit code (di `~/Projects/nuzantara/` untuk lavoro reale)
3. Commit dalam Bahasa Inggris: `feat(mouth): add CTA WhatsApp on /visa`
4. Push: `git push origin sancho/<task-slug>`
5. Open PR via `gh pr create`
6. **Tunggu review Antonello** — JANGAN self-merge dalam 30 hari pertama
7. Setelah merge: `git checkout main && git pull && git branch -d sancho/<task-slug>`

## Daily standup

09:00 WITA — kantor Kuta. Format ieri/oggi/blocker, 3-5 menit max.

## File penting

- `docs/onboarding/00_SELAMAT_DATANG.md` — welcome
- `docs/onboarding/07_60_DAY_MISSION_BAHASA.md` — mission lengkap
- `exercises/day1_setup_check.md` — mulai dari sini
