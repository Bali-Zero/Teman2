# Runbook — Subhi Tutor Day 1 Live Setup

**Durata stimata:** 90 minuti
**Audience:** Antonello, supervisione Subhi via WhatsApp video call
**Pre-requisito:** T1-T6 complete (memory mirror live su Pro, scaffold
seedato in `apps/zantara-onboarding/`, install script gist-hosted, dry-run
su Mac Mini OK).
**Modello distribuzione:** option B — single repo (`balizero/nuzantara`),
scaffold locale `~/zantara-onboarding/` su Subhi Mac, **rsync push from Pro**
via Tailscale (Subhi-side niente cron pull, solo Tailscale SSH server).

---

## Bridge WSL — Subhi parte SUBITO sul Windows Acer (2026-05-04)

Il MacBook Pro arriva giovedì 2026-05-06. Per non far aspettare 2 giorni,
Subhi parte oggi/domani su Windows tramite WSL2 (Linux dentro Windows).
Setup è separato dal Day 1 macOS:

**Flow WSL bridge:**

1. **Sera prima** (oggi): mandi via WhatsApp il messaggio bahasa
   step-by-step per installare WSL2 (vedi `docs/runbooks/subhi-wsl-bootstrap-bahasa.md`
   o copia dal messaggio originale).
2. Subhi installa WSL2 da solo (~15 min: `wsl --install -d Ubuntu` da
   PowerShell admin + reboot + setup user).
3. Subhi ti scrive "WSL ready" via WA.
4. Mandi gist URL del **install script WSL variant**
   (`scripts/subhi/subhi-tutor-install-wsl.sh`, NON quello macOS).
5. Subhi runs `bash <(curl -sL <gist-wsl-raw-url>)` dentro Ubuntu WSL.
6. ~25 min, ottiene tutor funzionante in WSL.

**Differenze WSL vs macOS:**

| Aspetto | WSL2 Ubuntu | macOS (giovedì) |
|---|---|---|
| Path home | `/home/subhi/` | `/Users/subhi/` |
| Package manager | `apt` | `brew` |
| Tailscale | Windows-host (mirrored networking) | nativo |
| VSCode | Windows + Remote-WSL extension | nativo |
| Browser flows | URL passati a Edge/Chrome Windows | Safari/Chrome Mac |

**Giovedì 2026-05-06 (MacBook Day 1):**

- Subhi smette di usare WSL.
- Riapri questo runbook **dalla sezione "Pre-Day-1"** sotto e procedi
  normalmente con `subhi-tutor-install.sh` (variant macOS).
- Memory mirror, scaffold, hooks **non cambiano** — solo l'OS dove girano.

---

## Convenzioni

- `<gist-url>` = URL del gist GitHub creato da Antonello con
  `gh gist create scripts/subhi/subhi-tutor-install.sh --public`. Salva
  l'URL raw (`https://gist.githubusercontent.com/...raw/...`) in nota
  WhatsApp prima del Day 1.
- `<subhi-tailscale-host>` = hostname Tailscale del MacBook di Subhi
  (es. `subhi-mac` o `subhi-macbook-pro`). Verificalo con
  `tailscale status | grep subhi`.
- Comandi `tailscale ssh subhi@<subhi-tailscale-host>` partono **da Pro**
  (mai dal Mac di Subhi).
- Tutti i path su Subhi Mac usano `~` = `/Users/subhi/`.

---

## Pre-Day-1 (sera prima, ~15 min)

Esegui questi passi la sera prima del Day 1, comodo seduto al Pro. Nessuno
di questi richiede Subhi online.

- [ ] **1. Verifica gist URL ancora valido**
  ```bash
  curl -sL '<gist-url>' | head -20
  ```
  Deve mostrare lo shebang `#!/usr/bin/env bash` e i primi commenti dello
  script. Se ricevi 404 o pagina HTML di GitHub: ricrea il gist con
  `gh gist create scripts/subhi/subhi-tutor-install.sh --public` e copia
  l'URL raw aggiornato.

- [ ] **2. Verifica NB share accettati da Subhi**
  ```bash
  nlm notebook_share_status --notebook NB-2 | grep subhi
  ```
  Deve restituire `subhi@balizero.com ACCEPTED`. Ripeti per `NB-1`, `NB-9`,
  `NB-OPS`. Se manca anche solo uno: rimanda l'invito da NotebookLM web UI
  e chiedi a Subhi di accettare l'email entro la sera.

- [ ] **3. Verifica MAX plan #2 ha slot libero per Subhi**
  - Apri https://console.anthropic.com/settings/billing nel browser
  - Vai su "Subscriptions" → identifica MAX plan #2 (quello dedicato a Subhi)
  - Verifica `seat usage`: deve essere `< limit` (slot libero)
  - Se piano pieno: liberare uno slot OPPURE fallback Path B (Subhi paga il
    proprio MAX dal suo Google personale — vedi tabella failure escalation
    sotto)

- [ ] **4. Verifica Tailscale ACL — asimmetria Pro↔Subhi**
  ```bash
  # Test 1: Subhi NON deve raggiungere Pro (devo dare 403/timeout)
  tailscale debug acl-test --user subhi@balizero.com --dst nuzantara
  # Output atteso: "denied" o solo "rsync drop zone allowed"

  # Test 2: Antonello DEVE raggiungere Subhi Mac (per push rsync)
  tailscale ssh subhi@<subhi-tailscale-host> 'echo OK'
  # Output atteso: OK
  ```
  Se test 1 mostra che Subhi può fare `tailscale ssh nuzantara` (Pro):
  STOP — apri Tailscale admin UI, restringi ACL prima del Day 1.
  L'asimmetria è fondamentale: Antonello → Subhi sì, Subhi → Pro no.

- [ ] **5. Genera GitHub fine-grained PAT scoped a `balizero/nuzantara`**
  - https://github.com/settings/personal-access-tokens/new
  - Resource owner: `balizero`
  - Repository access: solo `balizero/nuzantara` (NON tutti i repo)
  - Permissions:
    - Contents: **Read and write** (Subhi può push su `sancho/*`)
    - Metadata: **Read** (mandatory)
    - Pull requests: **Read and write**
  - Expiration: 90 giorni
  - Salva il token come `SUBHI_GITHUB_PAT=<token>` in
    `~/.nuzantara-secrets.env` (mai in plain file Git-tracked!)
  - Verifica:
    ```bash
    grep SUBHI_GITHUB_PAT ~/.nuzantara-secrets.env
    ```

- [ ] **6. Verifica Pro Remote Login OFF** (defense-in-depth)
  ```bash
  sudo systemsetup -getremotelogin
  # Output atteso: "Remote Login: Off"
  ```
  Se `On`: spegnere via `sudo systemsetup -setremotelogin off`.
  Tailscale SSH usa il proprio canale, non Remote Login macOS — meno
  superficie esposta.

- [ ] **7. Manda WhatsApp evening message a Subhi**

  Template bahasa pronto per copia-incolla:
  ```
  Halo Subhi 🌅
  Besok jam 09:30 di kantor Kuta. Bawa MacBook charged.
  Setup tutor 30 menit, kita install bareng via WA video call.
  Saya kirim installer link via WA jam 09:35 sebelum mulai.
  Sampai jumpa.
  ```

---

## T+0 (09:30 WITA) — arrivo Subhi

- [ ] Subhi arriva kantor Kuta, MacBook acceso, Wi-Fi connesso
- [ ] Antonello: WhatsApp video call, audio + screen share da Subhi (lui
      mostra a te il suo schermo, non il contrario)
- [ ] Antonello: chiedi a Subhi di aprire Terminal (Spotlight → "Terminal")
- [ ] Subhi: posiziona la finestra Terminal in modo che tu la veda nello
      screen share (full screen meglio)

---

## T+5 to T+30 — Install (25 min)

- [ ] **Antonello: manda WA message con il comando installer**
  ```
  Subhi, copy-paste questo comando in Terminal e premi Enter:

  bash <(curl -sL '<gist-url>')
  ```
  ⚠️ Manda l'URL gist raw (non la pagina UI gist).

- [ ] **Subhi: copy-paste, Enter, lo script parte**

- [ ] **Antonello: monitora screen share, aspetta 8 prompt sequenziali**

### Lista degli 8 prompt che lo script chiede a Subhi

**Prompt 1 — Xcode CLI tools install** (~5 min)
- Compare GUI dialog macOS "The xcode-select command requires the command line developer tools".
- Cosa watch: Subhi clicca **Install** (NON "Get Xcode" — quello è la versione full ~12GB).
- Successo: dialog si chiude, install ~5 min, script attende. Se script esce: re-run `bash <(curl -sL '<gist-url>')` quando dialog completato.

**Prompt 2 — Homebrew password**
- Terminal chiede `Password:` (è la password macOS di Subhi).
- Cosa watch: Subhi digita **alla cieca** (Terminal non mostra caratteri — questo è normale).
- Successo: `==> Installation successful!` + tempo install ~3 min.

**Prompt 3 — Tailscale browser login**
- Si apre browser su `https://login.tailscale.com/...`
- Cosa watch: Subhi seleziona **Google** → login con `subhi@balizero.com` (NON il suo Google personale!).
- Successo: pagina "Success! You can close this window." + Terminal mostra `Logged in as subhi@balizero.com`.
- ⚠️ Se Subhi sbaglia account: `tailscale logout && tailscale up` e riprova.

**Prompt 4 — SSH key prompt** (passphrase generation)
- Terminal: `Enter file in which to save the key (/Users/subhi/.ssh/id_ed25519):`
- Cosa watch: Subhi preme **Enter** (default OK), poi Enter di nuovo per passphrase vuota (ok per dev macchina personale).
- Successo: `Your identification has been saved in /Users/subhi/.ssh/id_ed25519`.

**Prompt 5 — GitHub `gh auth login`**
- Si apre browser su `https://github.com/login/device`
- Terminal mostra un codice tipo `WXYZ-1234`.
- Cosa watch: Subhi inserisce il codice nel browser, login GitHub con account corretto (probabilmente personale, NON `subhi@balizero.com` — il GitHub account di Subhi è quello che deve essere collaboratore di `balizero/nuzantara`).
- Successo: Terminal mostra `✓ Authentication complete` + `✓ Logged in as <subhi-github-username>`.

**Prompt 6 — Tailscale SSH server enable** (sudo)
- Terminal: `sudo tailscale up --ssh` (richiede password macOS Subhi).
- Cosa watch: Subhi digita password macOS (alla cieca).
- Successo: `Tailscale SSH server enabled`.
- Verifica live da Pro (in tmux split):
  ```bash
  tailscale ssh subhi@<subhi-tailscale-host> 'whoami'
  # Output atteso: subhi
  ```

**Prompt 7 — PAT GitHub paste** ⚠️ STEP CRITICO SECRECY
- Terminal chiede: `Paste GitHub Personal Access Token:`
- Cosa watch: **STOP screen share temporaneamente** (chiedi a Subhi di mettere in pausa lo screen share — "metti pausa video un attimo").
- Antonello manda PAT a Subhi via WhatsApp **messaggio separato** (NON tramite screen share, NON tramite voice call). Copia da `~/.nuzantara-secrets.env`:
  ```bash
  grep SUBHI_GITHUB_PAT ~/.nuzantara-secrets.env | cut -d= -f2
  ```
- Subhi paste in Terminal, Enter.
- Subhi riavvia screen share.
- Successo: script continua oltre — se PAT errato, gh API call dopo fallisce con `Bad credentials`.
- ⚠️⚠️⚠️ **MAI MAI MAI** mandare PAT via screen share visibile, voice call recordata, o screenshot. Anche se la call è 1:1, lascia traccia in WA cloud backup.

**Prompt 8 — Claude OAuth + nlm login** (browser flows ~3 min combined)
- 8a) Browser su `https://claude.ai/oauth?...` → Subhi login con `subhi@balizero.com` → "Authorize Claude Code".
- 8b) Browser su `https://accounts.google.com/...` (per nlm) → Subhi login con `subhi@balizero.com` → accetta scope NotebookLM.
- Cosa watch: entrambi gli account devono essere `subhi@balizero.com` (NON Google personale).
- Successo: Terminal mostra `✓ Claude OAuth saved` + `✓ NLM login complete`.

### Fine install

- [ ] Script termina con riga `✅ Subhi tutor install complete. Run 'cd ~/zantara-onboarding && code .'`
- [ ] **Antonello: verifica primo rsync push da Pro avvenuto**
  ```bash
  # Da Pro
  ls -la ~/Desktop/subhi_TUTOR_KIT/staging/.claude/memory-mirror/ | head -5
  # Subhi-side check via tailscale ssh
  tailscale ssh subhi@<subhi-tailscale-host> 'ls -la ~/zantara-onboarding/.claude/memory-mirror/ | head -5'
  ```
  Devono mostrare gli stessi file `.md` recenti.

---

## T+30 to T+45 — First tutor test (15 min)

- [ ] **Subhi: apre VSCode**
  ```bash
  cd ~/zantara-onboarding
  code .
  ```

- [ ] **Subhi: apre integrated terminal in VSCode** (Ctrl+` → backtick)

- [ ] **Subhi: lancia `claude`**
  ```bash
  claude
  ```
  Si apre la session interattiva.

- [ ] **Subhi digita comando di test:**
  ```
  /agent zantara-onboarding halo, perkenalkan diri kamu
  ```

- [ ] **Antonello: verifica risposta tutor su 4 punti**

  | # | Cosa verificare | Successo |
  |---|---|---|
  | 1 | Lingua | Bahasa Indonesia (NON inglese, NON italiano). Saluto inizia con "Halo" o "Selamat" |
  | 2 | Self-intro | Si presenta come "Zantara Onboarding" (o "Zantara" casual) |
  | 3 | Mention ruolo | Cita "Growth Systems Owner" o equivalent + perimetro VERDE (`apps/mouth/**`, GA4, GSC) |
  | 4 | Mention workflow | Menziona `sancho/*` branch o "branch sancho" come pattern lavoro |

  Se **tutti e 4 OK**: Subhi screenshot risposta, manda a te via WA. Tu salvi
  in `~/.claude/projects/-Users-nuzantara/memory/discovery_subhi_day1_first_tutor_response.md`.

### Recovery — tutor risponde lingua sbagliata

**Sintomo:** tutor risponde in inglese ("Hello, I am the Zantara Onboarding agent...") invece di bahasa.

**Cause comuni:**
1. Sub-agent prompt failed to load (file mancante o syntax error)
2. Subhi non ha invocato `/agent zantara-onboarding` ma ha chattato con Claude default
3. `name:` field nel sub-agent file non matcha il command

**Recovery sequence:**
- [ ] Subhi: digita `exit` per chiudere claude session
- [ ] Subhi: verifica file presente
  ```bash
  ls -la ~/zantara-onboarding/.claude/agents/zantara-onboarding.md
  head -10 ~/zantara-onboarding/.claude/agents/zantara-onboarding.md
  ```
  Prima riga deve essere `name: zantara-onboarding`.
- [ ] Subhi: rilancia `claude` e ri-prova `/agent zantara-onboarding halo`
- [ ] Se ancora inglese: Antonello edita prompt da Pro, push commit, attiva
      manual rsync push immediato:
  ```bash
  # Da Pro
  cd ~/Desktop/nuzantara
  # edit apps/zantara-onboarding/.claude/agents/zantara-onboarding.md
  git add apps/zantara-onboarding/.claude/agents/zantara-onboarding.md
  git commit -m "fix(subhi): tutor language enforcement bahasa-only"
  git push origin feat/zantara-onboarding-subhi
  bash ~/Desktop/nuzantara/scripts/subhi/subhi-rsync-push.sh
  ```
  Subhi rilancia claude, ri-prova.

### Recovery — `/agent` non riconosciuto

- [ ] Subhi: `claude --version`
- [ ] Se `< 2.0`: aggiorna
  ```bash
  npm install -g @anthropic-ai/claude-code@latest
  ```

---

## T+45 to T+75 — Reading + first exercise (30 min)

- [ ] **Subhi legge** `docs/onboarding/00_SELAMAT_DATANG.md` (~10 min, è il
      welcome bahasa con visione 60 giorni e mappa tutor).
- [ ] **Subhi legge** `exercises/day1_setup_check.md` (~5 min). Questo
      esercizio dice "verifica che setup è OK, fai screenshot tutor reply".
      Day 1 è **già completo** se siamo arrivati qui.
- [ ] **Subhi marca Day 1 complete:** screenshot della tutor reply iniziale
      + screenshot di `git status` su `~/Projects/nuzantara` pulito, manda
      entrambi via WA ad Antonello.
- [ ] Antonello salva entrambi screenshot in
      `~/Desktop/subhi_session_logs/day1/`.

---

## T+75 to T+90 — Daily standup briefing (15 min)

- [ ] **Subhi legge** `docs/onboarding/02_RBAC_BAHASA.md` (5 min) — VERDE /
      GIALLO / ROSSO perimeter.
- [ ] **Subhi legge** `docs/onboarding/06_SANCHO_BRANCH_WORKFLOW.md` (5 min)
      — branch naming `sancho/d1-...`, PR pattern, review da Antonello.
- [ ] **Q&A live:** Antonello risponde a qualsiasi domanda di Subhi su VA
      call. Tipiche:
  - "Saya boleh edit `apps/backend-rag/`?" → No, ROSSO. Pair con Asya o me.
  - "Branch saya harus mulai dengan apa?" → Sempre `sancho/<slug>`.
  - "Kalau saya tidak yakin warna apa file ini?" → Tanya saya / lihat `.claude/agents/zantara-onboarding.md`.
- [ ] Antonello chiude la call: *"Mantap. Day 2 besok pagi 09:00 — daily
      standup di kantor. Selamat bekerja."*

---

## Post-Day-1 (Antonello, sera del Day 1)

- [ ] **Read Subhi session log via Tailscale rsync (pull)**
  ```bash
  # Da Pro — pull session log da Subhi Mac (NON ssh interattivo, solo rsync)
  rsync -avz --no-perms \
    "subhi@<subhi-tailscale-host>:~/zantara-onboarding/.claude/session-log.jsonl" \
    "~/Desktop/subhi_session_logs/day1/session-log-$(date +%Y%m%d).jsonl"

  # Inspect
  jq -r '.transcript // empty' ~/Desktop/subhi_session_logs/day1/session-log-*.jsonl | head -100
  ```
  ⚠️ Modello option B = Antonello-side push/pull. **Non** SSH interattivo
  per leggere log; usa rsync diretto.

- [ ] **Check primo PR (improbabile Day 1, ma possibile)**
  ```bash
  gh pr list --repo balizero/nuzantara --author <subhi-github-username>
  ```
  Se c'è un PR: leggilo, NON mergiare ancora — Day 2 prima conversazione
  review live.

- [ ] **Salva memory MOS**
  ```bash
  ~/.claude/scripts/mem save fact "Subhi Day 1 setup OK $(date +%Y-%m-%d), tutor risponde bahasa, RBAC enforced via sub-agent prompt, install gist + rsync option B funzionante" 7
  ~/.claude/scripts/mem save discovery "Day 1 install option B end-to-end ~30 min effective install + 60 min reading/standup, totale 90 min stimato corretto" 7
  ```

- [ ] **Schedule Day 2 reminder** (cron, calendar, o WhatsApp manual)

- [ ] **Manda WA message Day 2 readiness**

  Template bahasa pronto per copia-incolla:
  ```
  Subhi, Day 1 selesai 🎉. Besok Day 2: codebase tour.
  Buka exercises/day2_codebase_tour.md setelah daily standup.
  Kalau ada pertanyaan, ping saya. Saya proud — kamu setup
  90 hari di 90 menit. Antonello
  ```

---

## Failure escalation

| Failure point | Sintomo | Recovery |
|---|---|---|
| Install script crash mid-step | Terminal exit non-zero, errore stderr | Re-run `bash <(curl -sL '<gist-url>')` — script idempotente, riprende dal primo step incompleto. Se stesso crash 3 volte: screenshot stderr, debug post-call. |
| OAuth Claude fail (slot saturo) | Browser mostra "subscription seat limit reached" | Antonello libera 1 slot in MAX plan #2. Se non possibile entro 1h: fallback Path B → Subhi paga il proprio MAX dal suo Google personale (ref `subhi-rbac-permissions.md` "PROPRIO Claude Code MAX subscription"). |
| Tailscale login wrong account | Subhi ha loggato Google personale invece di `subhi@balizero.com` | `tailscale logout && tailscale up` retry. Antonello revoca sessione Tailscale precedente da admin UI. |
| Tutor risponde lingua sbagliata (inglese/italiano) | `/agent zantara-onboarding halo` → reply in EN/IT | Antonello edita prompt su Pro → `git push` → manual `subhi-rsync-push.sh` → Subhi rilancia `claude`. Vedi sezione "Recovery — tutor risponde lingua sbagliata". |
| `/agent` non riconosciuto | Claude version `< 2.0` | `npm install -g @anthropic-ai/claude-code@latest` |
| Subhi non riesce a runnare comandi | Permission denied / command not found | Verifica Tailscale ACL: se Subhi accidentalmente ha accesso a Pro (`tailscale ssh nuzantara` da suo Mac funziona), revoca **immediatamente** in Tailscale admin UI. ACL deve essere asimmetrica. |
| Rsync push fallisce | `rsync: connection refused` da Pro | Verifica Subhi ha eseguito `sudo tailscale up --ssh` (Prompt 6). Verifica `tailscale status` su Pro mostra Subhi online. Se ancora rotto: fallback Path B (tarball + AirDrop, ref design §6 addendum B). |
| PAT GitHub leaked (scenario worst-case) | Antonello ha mandato PAT via screen share | **STOP**, revoca PAT immediato (https://github.com/settings/personal-access-tokens), genera nuovo PAT, re-distribuisci a Subhi via WA messaggio separato. Aggiorna in `~/.nuzantara-secrets.env`. |
| Anything taking >2x estimated time | Step >10 min stimato di blocco | Stop, screenshot stato Terminal, defer fix async. Riprendi setup dopo aver risolto offline. Non bruciare tutta la mattinata in debug live. |

---

## Quick reference card (stampabile, single page)

**Antonello stamp questo blocco e tienilo accanto durante la call:**

```
PRE-DAY-1 SERA PRIMA:
☐ curl gist URL                        ☐ TS ACL test asimmetria
☐ nlm share status NB-1/2/9/OPS        ☐ Pro Remote Login OFF
☐ MAX plan #2 slot libero              ☐ PAT generato in secrets.env
☐ WA evening message bahasa →

T+0 09:30: Subhi MacBook on, video call, screen share

T+5..T+30 INSTALL (8 prompt):
1. Xcode Install dialog                 5. gh auth login (browser)
2. Brew password (alla cieca)           6. sudo tailscale up --ssh
3. TS login subhi@balizero.com          7. PAT paste ⚠️ STOP screen share!
4. SSH key Enter                        8. Claude OAuth + nlm login

T+30..T+45 TUTOR TEST:
/agent zantara-onboarding halo
Verify: bahasa ✓ "Zantara Onboarding" ✓ Growth Systems VERDE ✓ sancho/* ✓

T+45..T+75 READING:
00_SELAMAT_DATANG → screenshot WA
exercises/day1_setup_check → screenshot WA

T+75..T+90 STANDUP:
02_RBAC_BAHASA + 06_SANCHO_BRANCH → Q&A → close

POST-DAY-1 SERA:
☐ rsync session-log.jsonl da Subhi     ☐ mem save fact + discovery
☐ check gh pr list                     ☐ WA Day 2 message bahasa →
```

---

**Fine runbook.** Per Day 2-7 vedi `docs/runbooks/subhi-tutor-day2-7.md`
(da scrivere dopo Day 1 retro).
