# Hari 1 — Setup Check

**Tanggal:** Hari pertama kamu di kantor (yang ditentukan Antonello)
**Mission ref:** §10 setup teknis (`07_60_DAY_MISSION_BAHASA.md`)
**Estimasi waktu:** 30 menit

## Tujuan

Pastikan semua tools terpasang di MacBook kamu dan kamu bisa "ngobrol"
dengan Zantara Onboarding untuk pertama kali.

## Konteks

Antonello sudah pre-setup beberapa hal:

- Akun GitHub `subhi@balizero.com` collaborator di `balizero/nuzantara`
- NotebookLM share NB-1, NB-2, NB-9, NB-OPS ke email kamu
- MAX plan Claude Code dengan slot kamu
- Tailscale tailnet `balizero` (kamu sudah join via laptop kamu sebelumnya)

Sekarang kamu install client-side: Claude Code CLI, nlm CLI, dan join
tailnet di MacBook baru.

## Pre-requisiti

- [ ] MacBook Pro 16GB sudah on
- [ ] Login macOS dengan akun kamu
- [ ] Internet kantor Kuta connected
- [ ] WhatsApp video call dengan Antonello ready (untuk supervisi)

## Langkah-langkah

### 1. Buka Terminal (atau iTerm)

`Cmd+Space` → ketik "Terminal" → Enter.

### 2. Run install script

Antonello kasih kamu link gist. Copy-paste command ini:

```bash
bash <(curl -sL <gist-url-yang-dikirim-Antonello>)
```

Script akan:

- Install Xcode CLI tools (jika belum)
- Install Homebrew (jika belum)
- Install Node.js 20, GitHub CLI, Tailscale, VSCode
- Install Claude Code CLI
- Install nlm CLI
- Login Tailscale (akan buka browser, login pakai subhi@balizero.com)
- Initial rsync ke `~/zantara-onboarding/` dari Pro Antonello via Tailscale
- Clone repo `balizero/nuzantara` ke `~/Projects/nuzantara/`
- Setup OAuth Claude (akan buka browser)
- Setup OAuth NLM (akan buka browser)
- Setup LaunchAgent rsync pull harian 06:00 WITA

Total ~15 menit. Bisa minum kopi.

### 3. Verifikasi install

```bash
claude --version
nlm --version
gh --version
git --version
node --version
```

Semua harus jalan tanpa "command not found".

### 4. Verifikasi rsync awal

```bash
ls -la ~/zantara-onboarding/
```

Harus ada minimum:

- `.claude/` (config + memory-mirror + hooks)
- `docs/onboarding/` (8 file md)
- `exercises/` (6 file md)
- `CLAUDE.md`, `README.md`

Kalau directory kosong: rsync awal gagal — ping Antonello.

### 5. Buka VSCode

```bash
cd ~/zantara-onboarding
code .
```

VSCode terbuka. Tekan `Ctrl+\`` untuk buka integrated terminal.

### 6. Test tutor pertama kali

Di terminal VSCode (CWD harus `~/zantara-onboarding`):

```bash
claude
```

Setelah masuk Claude session:

```
/agent zantara-onboarding halo, perkenalkan diri kamu dan jelaskan apa yang akan kamu bantu saya selama 90 hari ke depan
```

## Verifikasi

Tutor harus jawab:

- ✅ Dalam **Bahasa Indonesia** (BUKAN Inggris atau Italia)
- ✅ Memperkenalkan diri sebagai "Zantara Onboarding"
- ✅ Menjelaskan scope kamu (Growth Systems Owner)
- ✅ Menyebut perimeter VERDE/GIALLO/ROSSO
- ✅ Menyebut workflow `sancho/*` branch

## Kalau ada error

| Error                                 | Fix                                                                                              |
| ------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `claude: command not found`           | Re-source `~/.zshrc`, atau `npm install -g @anthropic-ai/claude-code` ulang                      |
| OAuth login Claude fail               | Cek koneksi internet, retry. Login pakai email Pro kamu di browser yang kebuka. Kalau persisten, ping Antonello |
| `/agent zantara-onboarding not found` | CWD kamu salah. `cd ~/zantara-onboarding` dulu                                                   |
| Tutor jawab dalam bahasa Inggris      | Sub-agent prompt salah load. Restart Claude session, retry                                       |
| `nlm login` fail                      | Google MFA — coba `nlm login --clear` lalu login lagi                                            |
| Rsync awal kosong                     | Tailscale belum connect, atau ACL salah — ping Antonello                                         |

## Selesai?

Kalau verifikasi 5/5 ✅:

1. Screenshot tutor reply
2. Kirim screenshot ke Antonello via WhatsApp
3. Lanjut ke `exercises/day2_codebase_tour.md` besok

Kalau ada blocker yang nggak ke-fix di tabel di atas:

- Stop di sini, ping Antonello dengan screenshot error
- Jangan teruskan ke Day 2 sebelum Day 1 selesai
