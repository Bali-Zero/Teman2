# WSL2 Bootstrap Message — Subhi (Windows Acer bridge before MacBook)

**Tujuan:** Installer WSL2 Ubuntu di Windows Acer Subhi, supaya bisa run
Claude Code CLI sebelum MacBook datang (Kamis 2026-05-06).

**Untuk:** Antonello copy-paste ke WhatsApp Subhi (sera prima).

**Estimasi waktu untuk Subhi:** 15-20 menit (mostly download/reboot wait).

---

## WhatsApp message — copy-paste

```
Halo Subhi 👋

Sebelum MacBook baru kamu datang (Kamis), saya mau kasih kamu akses
ke sistem kita SEKARANG biar kamu bisa mulai eksplorasi.

Ada 2 langkah, total ~20 menit. Lakukan SAAT KAMU BEBAS hari ini
atau besok pagi.

═══════════════════════════════════════
LANGKAH 1: Install WSL2 (Linux di Windows)
═══════════════════════════════════════

WSL2 adalah cara resmi Windows untuk run Linux tools (termasuk
Claude Code CLI). Tanpa ini, sistem kita tidak jalan di Windows.

1. Buka PowerShell sebagai Administrator:
   - Tekan Windows key
   - Ketik "PowerShell"
   - Klik kanan "Windows PowerShell" → "Run as administrator"
   - Klik "Yes" di dialog

2. Di PowerShell, copy-paste command ini, lalu Enter:

   wsl --install -d Ubuntu

3. Tunggu download (5-10 menit, ~700 MB)

4. Setelah selesai, RESTART Windows

5. Setelah reboot, Ubuntu akan auto-buka dan minta:
   - Username: ketik "subhi" (huruf kecil)
   - Password: pilih password (akan kamu pakai untuk sudo nanti)

6. Saat selesai, kamu akan lihat prompt:
   subhi@LAPTOP-XXX:~$

   Itu artinya WSL Ubuntu siap. Tutup window-nya untuk sekarang.

═══════════════════════════════════════
LANGKAH 2: Beri tahu saya
═══════════════════════════════════════

Kirim WhatsApp ke saya:
"WSL ready"

Saya akan kirim installer next yang setup Claude Code + tutor untuk
kamu. ~15 menit lagi setelah itu, kamu sudah bisa chat dengan
"Zantara Onboarding" — AI tutor yang tahu segalanya tentang sistem
Bali Zero.

═══════════════════════════════════════

Pertanyaan? Tanya saya. Ini langkah satu kali — Mac baru hari Kamis
nanti akan ada install yang berbeda (lebih sederhana karena macOS).

— Antonello
```

---

## Antonello-side checklist (mentre Subhi installa WSL)

- [ ] Crea gist GitHub con `subhi-tutor-install-wsl.sh`:
  ```bash
  cd ~/Desktop/nuzantara
  gh gist create scripts/subhi/subhi-tutor-install-wsl.sh \
    --public \
    --desc "Subhi WSL2 Ubuntu installer (Bali Zero bridge, $(date +%Y-%m-%d))"
  ```
- [ ] Copia il raw URL del gist:
  ```bash
  GIST_ID=<id-from-create>
  gh api gists/$GIST_ID --jq '.files | to_entries[0].value.raw_url'
  ```
- [ ] Verifica WSL mirrored networking attivo (richiede Win11 22H2+):
  Subhi può controllare con: `cat /etc/wsl.conf` (dentro Ubuntu) — se
  manca `networkingMode=mirrored`, va aggiunto. Vedi sotto.

## Possibile fix Tailscale WSL → Pro (se ping fallisce)

Se durante install l'ping a `100.64.165.11` (Pro tailnet IP) fallisce:

**Opzione A: Mirrored networking (preferito, Win11 22H2+)**

```bash
# Subhi run in Ubuntu WSL:
sudo nano /etc/wsl.conf
```

Aggiungi:
```ini
[network]
networkingMode=mirrored
```

Salva (Ctrl+O, Enter, Ctrl+X).

```powershell
# Subhi run in PowerShell (admin):
wsl --shutdown
wsl
```

Riprova ping.

**Opzione B: Install Tailscale dentro WSL (fallback)**

Solo se opzione A non funziona. Subhi run in Ubuntu:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

Login pakai subhi@balizero.com (URL stampato a console).

⚠️ Cautela: doppio account Tailscale (Windows + WSL) può creare conflitti.
Solo se A non lavora.

---

## Quando MacBook arriva (Kamis 2026-05-06)

Subhi:

1. Smette di usare WSL (Windows Acer va in archivio o handoff).
2. Setup MacBook seguendo `subhi-tutor-day1.md` runbook (variant macOS).
3. Tempo: ~30 min (più veloce di WSL perché Tailscale è nativo, brew
   più veloce di apt, etc.).
4. Memory mirror, scaffold, sub-agent prompt **identici** — solo
   reinstall locally.

---

## Note operative

- **PAT GitHub**: stesso PAT scoped a `balizero/nuzantara` (sancho/* write,
  contents read, metadata read) lavora sia su WSL sia su macOS. Riusa lo
  stesso PAT giovedì.
- **Claude Pro account**: Subhi usa il SUO Pro plan (sua email, sua sottoscrizione,
  indipendente dal MAX di Antonello). Il login è per-device — su WSL fa OAuth la
  prima volta, su MacBook giovedì rifà login con la stessa email Pro. Non c'è uno
  "slot Antonello" da claim.
- **NLM share**: NB-1, NB-2, NB-9, NB-OPS sono shared a `subhi@balizero.com`
  email — invariato tra WSL e macOS.
- **Tailscale**: tailnet membership è per-device. Quando MacBook joins,
  diventa un secondo device sotto stesso account. Old WSL device può
  essere rimosso da Tailscale admin se non più usato.
