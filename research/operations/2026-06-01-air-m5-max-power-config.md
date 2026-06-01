---
date: 2026-06-01
domain: operations
client_case: false
sources:
  - "Apple Machine Learning Research — Exploring LLMs with MLX on M5: https://machinelearning.apple.com/research/exploring-llms-mlx-m5"
  - "mise docs — shims vs activate: https://mise.jdx.dev/dev-tools/shims.html"
  - "OpenSSH Cookbook — Multiplexing: https://en.wikibooks.org/wiki/OpenSSH/Cookbook/Multiplexing"
  - "Mutagen docs — Synchronization: https://mutagen.io/documentation/synchronization/"
  - "Eclectic Light — Disable Spotlight in macOS Tahoe 26.x: https://eclecticlight.co/2026/01/16/can-you-disable-spotlight-and-siri-in-macos-tahoe/"
  - "Astral uv docs — Python versions: https://docs.astral.sh/uv/concepts/python-versions/"
  - "empirical: sysctl/system_profiler su Air-M5 2026-06-01 (Mac17,4, M5, 10 CPU 4P+6E, 24GB, GPU 10-core Metal 4, macOS 26.5)"
method: "deep-research workflow (fan-out 6 angoli) — verifier adversarial AUTO-FALLITO (0-0 votes = bug StructuredOutput, NON refute reali). Fonti buone recuperate via WebFetch diretto. Ogni claim sotto è [FATTO] da fonte citata o [RACCOMANDAZIONE] mia."
status: actionable — checklist da applicare con approvazione operatore. Round 2 aggiunto 2026-06-01 (Exa + NotebookLM deep research, 69 fonti).
round2_sources:
  - "NotebookLM deep report 'Systems Engineering Blueprint: Optimizing the Fanless MacBook Air M5' (69 fonti, notebook 75b73262-8357-443d-93be-212d736d8c44)"
  - "Exa semantic search (EXA_API_KEY) — zoneofmac, SolidAITech, ProxyMac, fazm.ai, jrd404 gist"
  - "SolidAITech — M5 Air thermal: 35→13 tok/s in 20min, throttle onset 8-15min"
  - "jrd404 macOS headless server gist (2026-03)"
  - "mise FAQ — shim resolution via ~/.zshenv"
  - "Simon Willison llm-mlx, ml-explore/mlx-lm, DssW pmset, eclecticlight Spotlight xattr 2025"
---

# Air-M5 — configurazione massima potenza (thin-client dev+ricerca)

> **Hardware reale** (verificato sysctl 2026-06-01): Apple M5 (Mac17,4), 10 CPU = **4 perf + 6 efficiency**, 24GB unified, GPU 10-core **Metal 4**, macOS **26.5** (build 25F71), 817GB liberi, zero thermal pressure. FileVault ON.
>
> **Ruolo**: macchina principale Antonello, dev+ricerca, LEGGERA. Carico pesante (deploy/test/modelli/daemon) gira su Pro (48GB M4 Pro) e Mini (M4 Pro) via SSH. Vedi [[decision_m5_air_fleet_join_2026_05_31]].

> ⚠️ **Nota metodo onesta**: il workflow deep-research ha trovato le fonti giuste ma il suo gate di verifica adversarial si è auto-sabotato (15 subagent non hanno chiamato StructuredOutput → tutte le claim segnate "refuted 0-0", che è un bug non un giudizio). Ho recuperato le 6 fonti autorevoli via fetch diretto. Niente qui poggia sull'output rotto del workflow.

---

## ASSE 1 — Performance hardware M5 (termico / clamshell / turbo)

### [FATTO] M5 Air è fanless — solo dissipazione passiva via chassis

Il MacBook Air (anche M5) non ha ventole. La gestione termica è passiva. Implicazione per uso clamshell H24: il calore esce dallo chassis in alluminio + tastiera. **Coperchio chiuso copre la superficie di dissipazione principale** → sustained load alto = throttling graduale.

### [FATTO empirico] Profilo burst-favorable, sustained-limited

Confermato dal design fanless: bursts brevi (build, deploy) raramente throttlano; ore di carico massimo continuo rallentano gradualmente. **Per il ruolo thin-client questo è IRRILEVANTE** — l'M5 non regge carico sostenuto, ma non deve: i daemon/build pesanti girano sul Pro. L'M5 fa burst leggeri (editor, ricerca, SSH) = zona ottimale del suo profilo termico.

### [RACCOMANDAZIONE] Config pmset per clamshell H24 — GIÀ APPLICATA 2026-05-31

```
sudo pmset -a sleep 0 disksleep 0 powernap 0 tcpkeepalive 1
sudo pmset -b disablesleep 1   # ignora chiusura coperchio (lid-sleep off)
sudo pmset -c disablesleep 1
```

Verifica: `pmset -g | grep SleepDisabled` → `1`. Stato attuale confermato: SleepDisabled 1, sleep 0, powernap 0.

### [RACCOMANDAZIONE] hibernatemode → 0 per server clamshell (NON ancora applicato)

Attuale: `hibernatemode 3` (default laptop: copia RAM su disco prima di standby). Con `disablesleep 1` non entra mai in standby, quindi è inerte — ma per pulizia server-mode:

```
sudo pmset -a hibernatemode 0    # no image RAM→disk, libera ~24GB di /var/vm/sleepimage
sudo rm -f /var/vm/sleepimage    # recupera spazio (si rigenera se serve)
```

Rischio: nullo con disablesleep on. Beneficio: ~24GB disco + nessuna scrittura sleepimage.

### [RACCOMANDAZIONE] Monitoraggio termico continuo

Il throttling è silenzioso. Per accorgersene:

```
pmset -g therm        # thermal pressure level (Nominal/Moderate/Heavy/Trapping/Sleeping)
sudo powermetrics --samplers smc -i1 -n1 | grep -i temp   # temp reale CPU/GPU
```

**Trappola clamshell**: se `pmset -g therm` mostra `CPU_Speed_Limit < 100` ripetutamente → l'M5 sta throttlando sotto il coperchio. Mitigazione: superficie dura ventilata, mai morbida (già annotato in memory).

---

## ASSE 2 — Thin-client mastery (far sparire il confine M5↔Pro)

### [FATTO] SSH ControlMaster elimina la latenza di handshake su connessioni ripetute

Riusa UNA connessione TCP+auth per tutti gli ssh/rsync verso lo stesso host. La 2ª, 3ª… connessione è istantanea (no re-handshake). Direttive: `ControlMaster auto` + `ControlPath` (socket) + `ControlPersist` (quanto tiene viva la master in background).

### [RACCOMANDAZIONE] Blocco da aggiungere a ~/.ssh/config su M5 (per host pro+mini)

```
Host pro mini
    ControlMaster auto
    ControlPath ~/.ssh/cm/%C
    ControlPersist 30m
```

Prerequisito (FATTO — gotcha dalla fonte): **la dir del socket deve esistere prima**, altrimenti `unix_listener error`:

```
mkdir -p ~/.ssh/cm && chmod 700 ~/.ssh/cm
```

NON mettere il socket in `/tmp` (gotcha sicurezza dalla fonte: chiunque legga il socket riusa la connessione autenticata). `%C` = hash di host+porta+user (ok). Cleanup master: `ssh -O exit pro`.

### [FATTO] Mutagen = sync bidirezionale continuo real-time (vs rsync one-shot)

Mutagen combina l'algoritmo rsync con bidirezionalità + filesystem-watching: ogni modifica file innesca un ciclo di sync. Use case esatto: "edit code con l'editor di scelta, push al remote quasi istantaneo". Modi: `two-way-safe` (default, conflitti risolti solo se no data-loss) / `two-way-resolved` (alpha vince).

```
mutagen sync create ~/Desktop/nuzantara ssh://pro/Users/nuzantara/Desktop/nuzantara
mutagen sync list / monitor / terminate
```

### [RACCOMANDAZIONE] Mutagen NON è per il nostro caso del repo — usare con cautela

Il repo è 37GB con .worktrees/.venv/node_modules. Mutagen real-time su quella mole = rumore continuo. **Meglio**: Mutagen solo su sottocartelle di lavoro attivo (es. una app specifica) con ignores per node_modules/.venv, OPPURE restare su rsync on-demand. Decisione operatore. (Mutagen non ancora installato — `brew install mutagen-io/mutagen/mutagen`.)

### [RACCOMANDAZIONE] Il pattern vincente per "lavoro su M5, eseguo su Pro"

1. **SSH inline** (zero setup): `ssh pro 'cd ~/Desktop/nuzantara && fly deploy ...'`
2. **Claude Code remoto**: `ssh pro` → `claude` (gira sul Pro 48GB, guidi da M5).
3. **VS Code Remote-SSH**: estensione Remote-SSH → apri la cartella del Pro dentro VS Code locale M5. Editor locale veloce, file+terminale+esecuzione sul Pro. (code-tunnel già linkato durante install.)
4. **tmux persistente sul Pro**: `ssh pro -t 'tmux new -A -s main'` → sessione che sopravvive a disconnessioni M5. Con ControlMaster il riattacco è istantaneo.

---

## ASSE 3 — macOS 26.5 tuning + arcani sistema

### [FATTO] Spotlight: disabilitazione via mdutil (Tahoe 26.x)

```
sudo mdutil -a -i off     # disabilita SOLO indexing (search ancora attiva, parzialmente)
sudo mdutil -a -d         # disabilita indexing E search (effettivo sul Data volume)
sudo mdutil -a -i on      # riabilita
```

**Caveat dalla fonte (26.x-specifico)**: disabilitare solo il Data volume ha problemi noti → può servire path esplicito `/System/Volumes/Data`. Disabilitazione COMPLETA richiede SIP off (sconsigliato). I processi Spotlight restano in Activity Monitor anche da disabilitato. Rompe: smart mailboxes Mail, alcune operazioni Finder.

### [RACCOMANDAZIONE] NON disabilitare Spotlight globalmente — escludi solo le dir pesanti

Disabilitare tutto Spotlight rompe la ricerca Finder/Spotlight che usi da dev. **Meglio**: System Settings → Spotlight → Search Privacy → aggiungi `~/Desktop/nuzantara` (i 37GB di node_modules/.venv/.git che non vuoi indicizzati). Equivalente CLI non c'è di pulito in 26.x (il file `.metadata_never_index` per-dir è deprecato). Approccio GUI è il più sicuro. Questo da solo recupera molta CPU di `mds_stores` su un repo enorme.

### [FATTO] MLX su M5 — l'arcano vero: Neural Accelerators nel GPU

M5 introduce **Neural Accelerators dentro i core GPU** (matrix-multiply dedicato via Metal 4 Tensor Ops). Numeri Apple verificati:

- **TTFT (prefill, compute-bound): 3.19x–3.97x più veloce di M4** (Qwen 1.7B = 3.57x)
- Token generation (memory-bound): 1.19x–1.27x (M5 ha 153GB/s vs 120 M4, +28% bandwidth)
- FLUX-dev-4bit immagine 1024² : >3.8x più veloce di M4
- **Requisito: macOS ≥26.2** per i Neural Accelerator (tu hai 26.5 ✓)

### [FATTO] Capienza modelli LLM su 24GB unified

| Modello       | Memoria |
| ------------- | ------- |
| 1.7B BF16     | ~4.4GB  |
| 14B 4-bit     | ~9.2GB  |
| 30B MoE 4-bit | ~17.3GB |
| 8B BF16       | ~17.5GB |

### [RACCOMANDAZIONE] MLX su M5 — MA coerente col thin-client

L'M5 PUÒ girare LLM locali velocissimi (è il suo asso M5-specifico). MA il ruolo dice "modelli su Pro/Mini". **Compromesso suggerito**: MLX sull'M5 SOLO per LLM leggeri istantanei nella window di ricerca (es. un 4-bit 14B per draft/classificazione veloce offline), il pesante resta su Pro/Mini Ollama. Install se vuoi: `uv pip install mlx mlx-lm` (NB: usa uv, non pip nudo).

### [RACCOMANDAZIONE] Sicurezza laptop mobile (M5 esce dall'ufficio)

- FileVault: ✅ già ON (verificato).
- Firewall applicativo: `sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate on` + stealth mode `--setstealthmode on`.
- Secret: ✅ già rimossi (solo DeepSeek key, 600, sotto FileVault).
- Lockdown completo (pf firewall custom, drduh guide) = overkill per dev mobile, NON raccomandato salvo minaccia specifica.

---

## ASSE 4 — Apple Silicon dev arcani (mise / uv / build)

### [FATTO] mise: shims vs activate — risolve la trappola "claude not found via SSH"

- `mise activate zsh` (in `.zshrc`): aggiorna PATH ad ogni prompt → **solo shell interattive**. NON si attiva in SSH non-interattivo / IDE / CI.
- `mise activate zsh --shims` (in `.zprofile`): crea eseguibili in `~/.local/share/mise/shims` che intercettano i comandi → **funziona in SSH/IDE/script**.
- Tradeoff: gli shim NON supportano hooks (cd/enter/exit) e le env-var caricano solo quando lo shim gira. `which` mostra il path dello shim, non il reale.

### [RACCOMANDAZIONE — FIX ALTA PRIORITÀ] Aggiungere shims al .zprofile dell'M5

Questo è ESATTAMENTE il bug che ci ha fatto perdere tempo (claude invisibile via `bash -lc`/`ssh`). Fix:

```
echo 'eval "$(mise activate zsh --shims)"' >> ~/.zprofile
```

Dopo questo, `ssh air 'claude --version'` da Pro/Mini funzionerà senza path assoluto. **Load-bearing se mai l'M5 dovesse rispondere a comandi remoti.** (Oggi M5 attuale ha solo `mise activate zsh` in .zshrc → interattivo only.)

### [FATTO] uv — gestione Python/venv, coesiste con mise

- uv tratta il python 3.11 di mise come "system install" (non lo duplica): `uv venv --python 3.11` lo trova via PATH.
- `uv python pin 3.11` scrive `.python-version`. `uv venv` crea venv. `uv pip install` = molto più veloce di pip (risolver Rust).
- Per forzare l'uso del python mise (no download uv-managed): `uv venv --python 3.11` o setting `python-preference: only-system`.

### [RACCOMANDAZIONE] Workflow Python dev su M5

```
cd <progetto>
uv venv --python 3.11          # venv istantaneo, usa il 3.11 di mise
source .venv/bin/activate
uv pip install -r requirements.txt   # 10-100x più veloce di pip
```

NB: il backend RAG vuole python 3.11 (Code Golden Rule #1) — l'M5 ha già 3.11.15 via mise ✓. Ma il backend gira sul Pro (thin-client) → uv su M5 serve per progetti di ricerca/script leggeri locali.

### [RACCOMANDAZIONE] Evitare Rosetta — tutto arm64 native

Tutta la toolchain M5 è già arm64 (verificato: agy/uv/node/python nativi). Regola: mai installare versioni x86 via Rosetta. Check di un binario: `file $(which <tool>)` deve dire `arm64` (non `x86_64`). OrbStack (già installato) gira container arm64 nativi — preferire immagini `linux/arm64`.

---

## CHECKLIST APPLICABILE (ordine consigliato, ognuna reversibile)

| #   | Azione                                 | Comando                                                        | Rischio                        | Applicato? |
| --- | -------------------------------------- | -------------------------------------------------------------- | ------------------------------ | ---------- |
| 1   | mise shims in .zprofile (fix SSH)      | `echo 'eval "$(mise activate zsh --shims)"' >> ~/.zprofile`    | nullo                          | ⬜         |
| 2   | SSH ControlMaster (latenza zero)       | blocco config + `mkdir -p ~/.ssh/cm && chmod 700 ~/.ssh/cm`    | nullo                          | ⬜         |
| 3   | hibernatemode 0 + rm sleepimage        | `sudo pmset -a hibernatemode 0; sudo rm -f /var/vm/sleepimage` | basso (disablesleep già on)    | ⬜         |
| 4   | Spotlight: escludi ~/Desktop/nuzantara | System Settings → Spotlight → Search Privacy (GUI)             | basso                          | ⬜         |
| 5   | Firewall applicativo + stealth         | `sudo socketfilterfw --setglobalstate on --setstealthmode on`  | basso                          | ⬜         |
| 6   | pmset no-sleep clamshell               | (GIÀ FATTO 2026-05-31)                                         | —                              | ✅         |
| 7   | FileVault                              | (GIÀ ON)                                                       | —                              | ✅         |
| 8   | Secret minimizzati                     | (GIÀ FATTO — solo DeepSeek)                                    | —                              | ✅         |
| 9   | (opt) MLX per LLM leggeri              | `uv pip install mlx mlx-lm`                                    | nullo                          | ⬜ opt     |
| 10  | (opt) Mutagen sync selettivo           | `brew install mutagen-io/mutagen/mutagen`                      | medio (no su 37GB repo intero) | ⬜ opt     |

## NON FARE (anti-raccomandazioni)

- ❌ Disabilitare Spotlight globalmente (`mdutil -a -d`) — rompe ricerca Finder, serve solo escludere dir.
- ❌ Mutagen real-time sul repo intero 37GB — rumore continuo, usa rsync on-demand o sottocartelle.
- ❌ Installare daemon/fly/ollama pesanti come servizi H24 sull'M5 — viola il modello thin-client, sfrigge un fanless clamshell.
- ❌ Rosetta/x86 — tutto arm64 native.
- ❌ SIP off per Spotlight — mai, troppa superficie.

---

# ROUND 2 — Exa + NotebookLM deep research (69 fonti, 2026-06-01)

> Secondo giro fatto con Exa (search semantica via EXA_API_KEY) + NotebookLM deep research (mode=deep, 69 fonti, ha generato un "Systems Engineering Blueprint" completo sul tema esatto). Ha funzionato dove il workflow deep-research era fallito 3×. Qui solo le scoperte NUOVE o che CORREGGONO il Round 1.

## ⚠️ CORREZIONE Round 1 — fix mise: `~/.zshenv`, NON `.zprofile`

Round 1 diceva `.zprofile`. La fonte autorevole (mise FAQ) chiarisce: **`~/.zshenv` è l'UNICO file che zsh legge in OGNI stato di invocazione** (interattivo, non-interattivo, login, VS Code Remote-SSH). `.zprofile` è solo login-shell. Per garantire che `claude`/`node`/`python` si risolvano anche da VS Code Remote-SSH e da `ssh air 'comando'`:

```
echo 'export PATH="$HOME/.local/share/mise/shims:$PATH"' >> ~/.zshenv
```

Questo è IL fix definitivo della trappola "claude not found via SSH". (Round 1 §Asse4 era quasi giusto ma file sbagliato.)

## [FATTO] Numeri termici clamshell REALI (il dato arcano che mancava)

| Stato                                  | CPU        | GPU        | Perf sostenuta         |
| -------------------------------------- | ---------- | ---------- | ---------------------- |
| Stock, desk flat, **coperchio chiuso** | **94.2°C** | **98.5°C** | ~50% (throttle <10min) |
| + thermal-pad mod (chassis = heatsink) | 78.6°C     | 85.6°C     | ~80%                   |
| + stand verticale + lid aperto 2"      | 79.6°C     | 96.2°C     | **~95% stabile**       |

Fonte: Reddit r/macbookair (Cinebench +300) + SolidAITech. **LLM sostenuto: 35→28→20→13 tok/s in 20min** (–60%), onset 8-15min.
→ **Implicazione thin-client CONFERMATA con numeri**: l'M5 che fa solo burst leggeri non tocca mai la soglia. Ma se mai dovesse scaldare clamshell, il trucco "lid aperto 2 pollici" recupera dal 50% al 95%. Il pesante resta sul Pro.

## [FATTO] pmset — 2 flag che mancavano nel Round 1

```
sudo pmset -c sleep 0 displaysleep 0 disksleep 0 hibernatemode 0 standby 0 autopoweroff 0 tcpkeepalive 1 ttyskeepawake 1
```

NUOVI vs Round 1: `autopoweroff 0` (disabilita lo shutdown EU Lot-6) + **`ttyskeepawake 1`** (blocca idle-sleep finché c'è una sessione TTY remota connessa — load-bearing per SSH H24, evita che l'M5 dorma mentre ci sei dentro via ssh). + `womp 1` (wake-on-LAN, per svegliarlo da remoto). Già applicato il grosso 2026-05-31; aggiungere questi 2.

## [FATTO] Telemetria termica Apple Silicon (no SMC legacy)

```
sudo powermetrics -s thermal     # thermal pressure: Nominal/Fair/Serious/Critical
brew install stats               # menu-bar temp/power live (opzionale GUI)
```

## [FATTO] SSH ControlMaster — config blueprint completa (raffina Round 1)

```
# ~/.ssh/config su M5
Host pro mini
    ControlMaster auto
    ControlPath ~/.ssh/control/%h_%p_%r
    ControlPersist 1h
    ServerAliveInterval 30
    ServerAliveCountMax 3
mkdir -p ~/.ssh/control && chmod 700 ~/.ssh/control
ssh -O check pro    # verifica master attivo
ssh -O stop pro     # chiude master
```

## [FATTO] tmux auto-attach via SSH config (far sparire il confine M5↔Pro)

```
Host pro-dev
    HostName 192.168.0.18
    User nuzantara
    RequestTTY yes
    RemoteCommand tmux new-session -A -s thin_client_dev
```

`ssh pro-dev` → entra DIRETTAMENTE in una tmux persistente sul Pro (crea se non c'è, attacca se c'è). Con mosh per resilienza roaming: `mosh pro -- tmux new-session -A -s dev`.

## [FATTO] MLX local inference server (il superpotere M5 sfruttabile in ricerca)

Su 24GB, server OpenAI-compatibile locale:

```
uv tool install llm && llm install llm-mlx
uv pip install --system mlx-lm
mlx_lm.server --model mlx-community/Qwen2.5-Coder-7B-Instruct-4bit --port 8080
```

| Modello 4-bit     | Footprint | Uso                          |
| ----------------- | --------- | ---------------------------- |
| Llama-3.2-3B      | ~2.2GB    | completion veloce            |
| Qwen2.5-Coder-7B  | ~4.8GB    | autocomplete/code            |
| Mistral-Small-24B | ~13.2GB   | reasoning tecnico multi-turn |

→ Coerente thin-client: usa MLX per LLM LEGGERI istantanei in ricerca (burst), il pesante/sostenuto su Pro/Mini Ollama.

## [FATTO] Spotlight su Tahoe — `.metadata_never_index` è DEPRECATO

Il metodo vecchio non funziona più in 26.x. Metodo vero:

```
sudo mdutil -i off ~/Desktop/nuzantara          # disabilita indexing su quella dir
# oppure injection nel DB volume (richiede Full Disk Access al terminale):
sudo /usr/libexec/PlistBuddy -c "Add :Exclusions: string '$HOME/Desktop/nuzantara'" /System/Volumes/Data/.Spotlight-V100/VolumeConfiguration.plist
sudo launchctl kickstart -k system/com.apple.metadata.mds
mdfind -onlyin ~/Desktop/nuzantara "test"        # vuoto = escluso OK
```

(Round 1 suggeriva la GUI Search Privacy — resta l'opzione più sicura; questo è l'equivalente CLI programmatico.)

## [FATTO] Offload compute pesante (mantiene l'M5 freddo)

- **Mutagen** sync bidirezionale con config `~/.mutagen.yml` (`mode: two-way-resolved`, ignore node_modules/.git/target) → `mutagen sync create --name=proj ~/path pro:~/path`
- **cargo-remote** (build Rust sul Pro): `.cargo-remote.toml` con host Pro → `cargo remote -c -- build --release`
- **distcc + ccache** (C/C++ distribuito): `export CCACHE_PREFIX=distcc`
- Tutti via SSH, l'M5 non compila → non scalda.

## Checklist Round 2 (aggiunte alla checklist Round 1)

| #    | Azione                                                     | Comando                                                                 | Rischio |
| ---- | ---------------------------------------------------------- | ----------------------------------------------------------------------- | ------- |
| R2-1 | mise shim in ~/.zshenv (CORRETTO, sostituisce checklist#1) | `echo 'export PATH="$HOME/.local/share/mise/shims:$PATH"' >> ~/.zshenv` | nullo   |
| R2-2 | pmset: aggiungi autopoweroff+ttyskeepawake+womp            | `sudo pmset -a autopoweroff 0 ttyskeepawake 1 womp 1`                   | nullo   |
| R2-3 | tmux auto-attach SSH alias pro-dev                         | blocco config                                                           | nullo   |
| R2-4 | (opt) MLX server locale per ricerca                        | `uv tool install llm; llm install llm-mlx`                              | nullo   |
| R2-5 | (opt) Spotlight escludi repo via mdutil                    | `sudo mdutil -i off ~/Desktop/nuzantara`                                | basso   |
