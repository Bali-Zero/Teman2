# Bali Zero — Mac & Mobile Setup (Onboarding Dipendente)

Cartella di asset distribuibili per il setup dei dispositivi aziendali dei nuovi dipendenti.

## File chiave (eseguibili)

| File | Scopo | Audience |
|---|---|---|
| **`setup-balizero.sh`** | Setup unificato Mac: profilo + Tailscale + daemon + Handbook immutable | Antonello esegue dal profilo `balizero` del Mac dipendente |
| **`setup-mobile.md`** | Procedura step-by-step smartphone (SIM + WA Business + wa-mirror QR) | Antonello segue manualmente |

## Asset sottostanti

| File | Scopo |
|---|---|
| `profile-monitor` | Binary Swift compilato (daemon NSWorkspace, 64 KB) |
| `profile-monitor.swift` | Sorgente Swift (per ricompilare se necessario) |
| `com.balizero.profile-monitor.plist.template` | LaunchAgent plist con placeholder `__INSTALL_DIR__` / `__HOME__` / `__EMPLOYEE__` |
| `handbook-asset/employee-handbook-v1-ID.pdf` | Employee Handbook 10 pagine Bahasa Indonesia |

## Workflow setup per ogni nuovo dipendente

### Prerequisiti

- [ ] Dipendente ha firmato PKWTT (lunedì 19 maggio 2026, vedi `~/Desktop/PKWTT-Contratti-2026-05-19/`)
- [ ] SIM Telkomsel allocata (vedi `~/nuzantara/research/hr/sim-registry.md`)
- [ ] Dipendente porta Mac personale (per setup profilo `balizero`)
- [ ] Pro acceso, profile-monitor wrapper attivo, Tailscale online
- [ ] Antonello connesso a Tailscale e in grado di invitare device tailnet

### Procedura A — Mobile (manuale, ~15-20 min)

Apri `setup-mobile.md` e segui i 6 step. Risultato:
- SIM Telkomsel inserita
- WhatsApp Business installato + registrato
- Profilo Business configurato (nome + foto + business hours)
- QR wa-mirror scansionato → numero linked al DB Pro
- Test end-to-end completato

### Procedura B — Mac (automatica, ~5 min)

```bash
# Sul Mac dipendente, dopo aver creato profilo macOS `balizero`:
# 1. Logout dal profilo personale del dipendente
# 2. Login al profilo balizero
# 3. Install Tailscale (https://tailscale.com/download/mac) + join tailnet balizero
# 4. Copia questa cartella sul Mac (AirDrop dal Pro, scp, o git clone)
# 5. Esegui:

cd ~/Downloads/mac-client    # (o ovunque hai copiato la cartella)
bash setup-balizero.sh <nome_dipendente>
```

Es: `bash setup-balizero.sh surya`

Lo script esegue in sequenza:
1. Verifica profilo macOS = `balizero` (refuse altrimenti)
2. Verifica Tailscale + ping a Pro wrapper :9099
3. Installa daemon `profile-monitor` come LaunchAgent (KeepAlive)
4. Installa Employee Handbook PDF sul Desktop con flag `chflags uchg` (immutable)
5. Stampa summary + test end-to-end

## Trasferimento cartella al Mac dipendente

3 opzioni in ordine di preferenza:

**Opzione 1 — AirDrop** (più veloce):
1. Sul Pro: Finder → seleziona cartella `mac-client/`
2. Click destro → Share → AirDrop → seleziona Mac dipendente

**Opzione 2 — Git clone** (richiede Git installato sul Mac dipendente):
```bash
cd ~/Downloads
git clone https://github.com/Balizero1987/Teman2.git temp-repo
cp -r temp-repo/scripts/profile-monitor/mac-client .
rm -rf temp-repo
```

**Opzione 3 — USB / SCP** (offline):
```bash
# Sul Pro:
scp -r ~/nuzantara/scripts/profile-monitor/mac-client/ balizero@mac-dipendente.local:~/Downloads/
```

## Disinstallazione (offboarding)

Eseguire SOLO da Antonello quando un dipendente lascia Bali Zero:

```bash
# 1. Stop daemon
launchctl bootout gui/$(id -u)/com.balizero.profile-monitor

# 2. Rimuovi LaunchAgent + binary
rm ~/Library/LaunchAgents/com.balizero.profile-monitor.plist
rm -rf ~/Library/Application\ Support/BaliZero

# 3. Rimuovi Handbook immutable
chflags nouchg ~/Desktop/employee-handbook-v1-ID.pdf
rm ~/Desktop/employee-handbook-v1-ID.pdf

# 4. Disconnetti Tailscale (Tailscale app → Logout)

# 5. (Opzionale) elimina profilo balizero macOS
#    System Settings → Users & Groups → balizero → "−" → Delete Home Folder
```

Per smartphone, vedi sezione "Disinstallazione futura" in `setup-mobile.md`.

## Verifiche post-setup

Sul Pro, verifica che il dipendente sia effettivamente integrato nel sistema:

```bash
# 1. Tailscale device list
tailscale status | grep -i <nome_mac_dipendente>

# 2. Profile-monitor wrapper log
tail -20 ~/logs/profile-monitor-wrapper.log

# 3. wa-mirror DB (numero linked)
psql "$(grep DATABASE_URL_LOCAL ~/.nuzantara-secrets.env | cut -d= -f2-)" \
  -c "SELECT counterpart_phone, MAX(created_at) FROM whatsapp_message_context GROUP BY counterpart_phone;"

# 4. Test alert: chiedi al dipendente di fare logout dal profilo balizero
#    → Antonello deve ricevere alert Telegram entro 10 secondi
```

## Troubleshooting

Vedi `setup-mobile.md` per smartphone. Per Mac:

| Problema | Soluzione |
|---|---|
| `setup-balizero.sh` errore "Profilo non balizero" | Sei loggato sul profilo sbagliato. Logout e relogin al profilo `balizero`. |
| Wrapper Pro non raggiungibile | (a) Tailscale non connesso sul Mac. (b) Pro spento. (c) Wrapper crashato — su Pro: `launchctl kickstart -k gui/$(id -u)/com.balizero.profile-monitor-wrapper` |
| Daemon non avvia (LastExitStatus != 0) | Controlla `~/Library/Logs/balizero-profile-monitor.error.log` |
| Handbook ancora eliminabile dopo install | Antonello esegue `chflags uchg ~/Desktop/employee-handbook-v1-ID.pdf` manualmente |

## Aggiornamenti futuri

Quando aggiorni `setup-balizero.sh` o `employee-handbook-v1-ID.pdf`:

1. Modifica sorgente in `~/nuzantara/research/hr/handbook/` (per Handbook) o direttamente qui (per scripts)
2. Se Handbook: rigenera PDF con `python3 ~/.claude/skills/bali-zero-brand/surfaces/internal-print-a4/_render.py --html ... --pdf ...`
3. Copia il PDF aggiornato in `handbook-asset/`
4. Commit + push su `origin/main`
5. Su ogni Mac dipendente: ricarica setup → `bash setup-balizero.sh <nome>` (lo script rimuove flag immutable per consentire update, poi riapplica)
