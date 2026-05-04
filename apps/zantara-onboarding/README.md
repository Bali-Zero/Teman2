# Subhi Workspace — Bali Zero

Halo Subhi! Ini direktori pribadi kamu untuk onboarding 90 hari di Bali
Zero sebagai **Growth Systems Owner**.

## Struktur

- `.claude/` — config Claude Code + tutor sub-agent
- `docs/onboarding/` — dokumentasi bahasa Indonesia
- `exercises/` — exercise harian Day 1-7 (Day 8+ dihasilkan tutor on-demand)

## Mulai dari sini

1. Buka `docs/onboarding/00_SELAMAT_DATANG.md`
2. Lalu `exercises/day1_setup_check.md`

## Tutor

```
claude
/agent zantara-onboarding halo
```

Tutor selalu jawab dalam Bahasa Indonesia.

## Repo lavoro

Lavoro reale ada di `~/Projects/nuzantara/` (clone repo `balizero/nuzantara`).
Branch kamu: `sancho/<task-slug>` saja.

## Distribusi

Direktori ini bukan repo git Subhi sendiri — di-update dari Pro Antonello
via rsync over Tailscale tiap pagi 04:00 WITA. Kamu cukup pakai (read),
tutor sub-agent yang akan baca konteks dari `.claude/memory-mirror/`.

Kalau kamu mau catatan pribadi (notes, draft, sketsa), simpan di
`local/` — folder itu di-exclude dari rsync supaya tidak ketimpa.

## Kontak

- Antonello (boss): WhatsApp 1-1
- Asya (platform): backend pair
- Daily standup: 09:00 WITA, kantor Kuta
