---
date: 2026-09-04
domain: operations
client_case: none — internal context-diet study, phase 2 (sessione M5, mandato Zero)
adversarial_review: codex
sources: 13 primary pages fetched by a Sonnet research seat (Anthropic engineering ×2, code.claude.com docs ×10, Manus) + disk-state measurement of this M5 session (numbers reproduced in §1); community MCP-bloat figures are marked as such; Codex GPT-5 red-team on the draft (§9, verdict "block" → every finding dispositioned)
---

# Dieta del contesto, fase 2 — dove stanno davvero i 102k e quali leve sono provate

> Mandato Zero, 2026-09-04 sera: «non sono convinto che 95/97,5k siano ottimali; studia le
> best practice mondiali, enterprise e grandi dev, e rendi il tutto coerente col nostro sistema».
> Innesco: `/context` su sessione M5 fresca dopo la fase 1 = **101,9k/500k**.
> Continua `2026-09-04-context-engineering-sota.md` (R1-R7): lì i principi, qui il pannello
> decomposto voce per voce, le leve che Claude Code espone e — dopo il red-team — quali sono
> documentate, quali inferite, quali già smentite dal disco.

## 0. Executive summary

- Il pannello vero è **101,9k**, non 93-97k. La differenza sta in tre errori dell'handoff che il
  disco smentisce: MCP mai staccato (16,4k), superscar mai dimagrito (nessuna PR esiste), e un
  rapporto byte→token assunto a 3,3 quando quello misurato sui file iniettati è **2,04**.
- La leva più grande non è un altro taglio di prosa: è il **loadout**. `ENABLE_TOOL_SEARCH=auto:5`
  carica per intero ogni server MCP sotto il 5% della finestra, ed è il nostro caso (3,3%). La doc
  documenta il default "differito" e `auto`/`false`; che `true` differisca sempre è un'**inferenza
  da misurare per prima**, per ciascuna classe di server (locale, connector claude.ai, Chrome).
- Tre risparmi hanno meccanismo documentato (Chrome off, `enabledPlugins`, `Agent(name)` deny):
  **−5,7k certi**. Due sono inferenze con probe da fare (tool search, deny dei built-in): **−15…−19k**.
  Sette sono strutturali: **−7k**. Tre sono decisioni di Zero: **−9,5k**. Traiettoria onesta:
  102k → 96k (certo) → ~81k (se il tool search si comporta come inferito) → ~74k (strutturale)
  → ~60k (con le decisioni). Ogni leva si misura da sola: una modifica, una sessione fresca, un
  `/context` annotato. Le somme di stime hanno già sbagliato una volta.

## 1. Il pannello decomposto (disk-state, sessione M5 2026-09-04, Fable 5.1, finestra 500k)

| Voce | `/context` | Cosa contiene davvero | Governabile? |
|---|---|---|---|
| System prompt | 7,0k | harness + sezioni browser (istruzioni Chrome + regole di navigazione) presenti perché Chrome è attaccato; stima 1-2k | in parte |
| System tools | 41,8k | built-in: Artifact (~5k), Agent, Bash, Workflow, DesignSync, RemoteTrigger, Monitor, ScheduleWakeup, Cron×3, ReportFindings, SendFeedback, EndConversation… | ipotesi via deny (§2.3, §5) |
| MCP tools | 16,4k | Chrome 22 tool 9.893 · Drive 11 tool 4.838 (connector claude.ai) · nuzantara-knowledge 9 tool 1.684 = 16.415 | sì |
| Custom agents | 4,3k | WR3 13 agent ~1,07k · WR2 8 ~0,90k · business/cron 13 ~0,98k · repo 12 ~1,08k · plugin 3 ~0,24k | sì |
| Memory files | 20,7k | 42.185B caricati: MEMORY.md 16.302 (166 emoji; 101 link con slug 60-90 char ≈7KB) · superscar 12.484 · CLAUDE.md repo 9.752 (checkout M5; `origin/main` 10.571) · globale 3.647 | sì |
| Skills | 8,2k | built-in ~2,6k · plugin ~2,0k (document-skills 1,0k, superpowers 0,9k) · 29 corner in `~/.claude/commands` ~1,3k · skill user 7 ~1,1k · skill+command repo 22 ~1,3k | sì |
| Messages | 3,6k | hook SessionStart (proprioception, organismo, escalations ≈1,5k) + blocco `using-superpowers` del plugin (≈1,1k) + prompt | sì |

Le righe arrotondate sommano 102,0k contro 101,9k del pannello: arrotondamento, non voce mancante.

**Rapporto byte→token.** 42.185B sempre iniettati per 20.700 token = **2,04 B/token**. Le tre
rules con `paths:` (frontend 803, infrastructure 695, python 1.135, blocklist 758 = 3.391B) sono
caricate solo a file corrispondente secondo la doc; se il pannello le contasse comunque il rapporto
sarebbe 2,20. Italiano, emoji, tabelle e slug con underscore tokenizzano male: ogni budget in byte
si converte con **token = byte / 2,04** (non ×; non /3,3). Il "residuo ~19k mai decomposto"
dell'handoff non esiste: sono i quattro file sopra, al rapporto giusto.

**Correzioni all'handoff (verificate sul disco, non sul rapporto):**

1. `.mcp.json` dichiara ancora `nuzantara-knowledge`; nessun `.bak-diet` esiste; il file è untracked
   dal commit 83638caf39, quindi "svuotato" non poteva stare in una PR. Lo stesso server è nel local
   scope di `~/.claude.json` e in `enabledMcpjsonServers` del settings globale: tre strati.
2. Drive è connesso (11 tool): connector claude.ai dell'account, non una voce locale.
3. Superscar: nessuna PR aperta né fusa oltre #4482; `origin/main` porta 12.484B.
4. PR #5634 fusa alle 06:55Z; il checkout M5 è 3 commit indietro (atteso, non è drift).
5. `ENABLE_TOOL_SEARCH=auto:5` nel settings globale + `enableToolSearch=true`: i 16,4k di MCP sono il
   3,3% della finestra, sotto soglia, quindi caricati per intero — la sessione infatti non ha
   `ToolSearch` per gli MCP.
6. `skillOverrides` contiene tre chiavi che non corrispondono a nessuna skill (`superpowers:brainstorm`,
   `execute-plan`, `write-plan`: i nomi reali sono `brainstorming`, `executing-plans`, `writing-plans`)
   e due `user-invocable-only` (`receiving-code-review`, `writing-skills`) le cui skill compaiono
   comunque nel pannello. Cinque righe, zero effetto misurabile (famiglia #2, esiste ≠ armato).
7. `com.balizero.wr2.queue-pull` è **caricato e attivo** su M5 (`active count = 1`) nonostante la
   decisione «WR2 solo a comando, 33 launchd spenti» (Zero 1/9). Consumer potenziale degli agent WR2.

## 2. Cosa fanno i migliori (fonti fetchate; le community-only sono marcate)

**2.1 Anthropic, principio.** «The smallest possible set of high-signal tokens that maximize the
likelihood of some desired outcome»; progressive disclosure e just-in-time retrieval con
identificatori leggeri; sui tool: se un ingegnere non sa dire quale tool va usato, nemmeno l'agente
(anthropic.com/engineering/effective-context-engineering-for-ai-agents).

**2.2 Anthropic, tool search.** Cinque server MCP = 58 tool ≈ 55K token; con deferimento «an 85%
reduction in token usage»; accuratezza MCP-eval di Opus 4 da 49% a 74% (advanced-tool-use). Claude
Code: schemi MCP «deferred by default», `ENABLE_TOOL_SEARCH=auto` li carica in anticipo se sotto il
10% del contesto, `false` carica tutto (code.claude.com/docs/en/context-window). Il nostro `auto:5`
è la variante a soglia 5%. **Non documentato qui**: la semantica esatta di `true`, e se i connector
claude.ai e Chrome seguono lo stesso deferimento dei server locali. Sono i probe P1-P3 di §5.

**2.3 Claude Code, doc ufficiale (memory, permissions, mcp, chrome, sub-agents, skills, plugins).**
CLAUDE.md «target under 200 lines»; rules senza `paths:` «loaded unconditionally»; `permissions.deny`
con nome nudo «removes the tool from Claude's context entirely, so Claude never sees it», la regola
scopata lo lascia — **la doc parla del tool list, non dice se un tool già differito pesa ancora nel
pannello**; Chrome: «enabling Chrome by default in the CLI increases context usage since browser
tools are always loaded… use `--chrome` only when needed»; sub-agent: tutte le description di
`~/.claude/agents` e `.claude/agents` entrano al boot, avviso oltre 15.000 token, scoping via
`permissions.deny: ["Agent(name)"]`; skill: al boot entra solo la description (cap 1.536 caratteri),
budget di listing 1% della finestra; plugin: `enabledPlugins` è rispettata a livello di progetto.

**2.4 Prompt caching in Claude Code** (code.claude.com/docs/en/prompt-caching). Tre strati:
system prompt (tool, output style) → contesto di progetto (CLAUDE.md, auto-memory, rules senza
path) → conversazione. «A change to the system prompt invalidates everything»; gli MCP differiti si
attaccano e staccano senza invalidare; un CLAUDE.md editato a sessione viva non si applica fino al
riavvio. Corollario misurato qui: l'ultima sessione M5 ha letto **90,0M token da cache** contro
0,44M di output (≈200:1). Ogni 1k tolto dal prefisso si risparmia 1k per turno, per tutta la sessione.

**2.5 Manus** (manus.im/blog/…Lessons-from-Building-Manus). KV-cache hit rate come metrica
numero uno; «a single-token difference can invalidate the cache from that token onward»; niente
timestamp volatili nel prefisso; «mask, don't remove» per i tool; file system come contesto
esternalizzato; input:output ≈ 100:1; cached $0,30 vs uncached $3 per MTok.

**2.6 Enterprise** (code.claude.com/docs/en/managed-settings). Il meccanismo di flotta è
`managed-settings.json`: `allowedMcpServers`/`deniedMcpServers`, `strictPluginOnlyCustomization`,
`claudeMd` fleet-wide. È il nostro problema HOME-fork su tre macchine, risolto da un SSOT.

**2.7 Cursor** [search-only]. Quattro tipi di rule (Always · Auto Attached per glob · Agent
Requested · Manual): «mostly Auto Attached and Agent Requested, with a small handful of Always».
È il nostro `paths:`; la superscar è la "handful of Always" e va tenuta piccola per questo.

**2.8 Community** [search-only, cifre terze]. Playwright MCP ≈ 13,6-15,2k token; GitHub MCP ≈ 42k;
sessioni che «burn 50,000-67,000 tokens before the user types a first prompt». Cura convergente: 2.2.

## 3. Diagnosi

Nuzantara ha già i meccanismi giusti (budget armati da CI, indici + corpi lazy, `paths:`,
`skillOverrides`, `claudeMdExcludes`, `enabledMcpjsonServers`, `enabledPlugins`). Il gap è di
**taratura e di verifica**: la fase 1 ha lavorato sulla prosa (giusto, R1-R5), ha lasciato il loadout
sui default (R6 "da studiare") e ha chiuso su rapporti invece che su misure — quattro correzioni su
sette in §1 sono "il rapporto dice, il disco no" (famiglia #6, linea W65→W113), due sono "esiste ma
non è armato" (famiglia #2).

| Voce | Leva | Stato della prova | Coerenza con l'organismo |
|---|---|---|---|
| MCP 16,4k | `ENABLE_TOOL_SEARCH=true` | inferita (P1-P3) | i server restano attaccati e costano poco finché non usati: niente da staccare, niente GUI |
| System prompt browser | `claudeInChromeDefaultEnabled=false` + `--chrome` | documentata | raccomandazione letterale della doc |
| System tools 41,8k | `permissions.deny` nomi nudi | inferita (P4) | stesso file dei 23 deny esistenti; reversibile |
| Skills plugin 1,0k | `enabledPlugins: false` su document-skills | documentata | on quando si producono docx/pptx/xlsx |
| Skills corner 1,3k | spostare i 29 corner fuori da `~/.claude/commands` dietro UNA skill `team` con `args` | meccanica (il listing conta i file) | i corner li invoca Zero con `/nome`: un solo ingresso, 29 corpi |
| Agents 2,0k | `permissions.deny: Agent(name)` per 13 WR3 + 8 WR2 su M5 | documentata; **prima** censimento consumer (§1.7) | WR2 «solo a comando»: agent caricati in ogni sessione per una room ferma è teatro |
| Memory files 20,7k | budget CI esistenti + riscrittura al rapporto 2,04 | meccanica | superscar 8KB già mandato; niente rename di slug (rompe i `[[link]]`) |
| Hook output 1,5k | cap in byte nei tre script SessionStart, «muto se verde» | meccanica | antidoto #2: si stampa l'esito, non il teatro |

## 4. Piano in tre livelli (delta = stima da confermare con §5; "certo" = meccanismo documentato)

**Livello A — configurazione, reversibile in una riga.**

| # | Azione | Delta | Stato |
|---|---|---|---|
| A1 | `ENABLE_TOOL_SEARCH`: `auto:5` → `true` | MCP 16,4k → ≤1k (−15,4k) | inferito → P1-P3 |
| A2 | `claudeInChromeDefaultEnabled: false`; `claude --chrome` quando serve | system prompt −1…2k | certo |
| A3 | `permissions.deny` nomi nudi, SOLO tool senza consumer censito: `DesignSync RemoteTrigger EndConversation ReportFindings SendFeedback ListMcpResourcesTool ReadMcpResourceTool ReadMcpResourceDirTool` | −3…5k | inferito → P4 |
| A4 | `enabledPlugins: document-skills=false`; 29 corner → skill unica `team`; correggere/eliminare le 5 righe inerti di `skillOverrides` | −2,2k | certo |
| A5 | `permissions.deny: Agent(<13 wr3 + 8 wr2>)` su M5, dopo aver risolto §1.7 | −2,0k | certo, condizionato |
| A6 | `nuzantara-knowledge`: resta attaccato se A1 regge; altrimenti togliere nei 3 strati | 0 / −1,7k | — |

Esclusi dal deny per consumer noto: `Workflow` (dottrina `docs/rules/operations.md` §6,
`verify-template.js`; skill `workflow`, `modus`), `CronCreate/CronDelete/CronList`,
`ScheduleWakeup`, `PushNotification` (skill `/loop`, `/schedule`) → livello C.
Somma: **−5,7k certi** (A2+A4+A5) · **−21k** se P1-P3 reggono · **−25k** se anche P4.

**Livello B — strutturale (PR nel repo + HOME-fork via `diet_home_apply.sh`).**

- B1 superscar 12.484B → ≤8.192B, cap del test a 8192 (mandato esistente, mai eseguito): −2k.
- B2 MEMORY.md 16.302B → ≤11KB: zero emoji, un claim per riga, **nessun rename** di file: −2,5k.
- B3 CLAUDE.md repo 10.571B → ≤7,5KB: la tabella macchine duplica il globale; il Builder Contract
  (3,5KB, identico in 4 porte) si stringe in una PR sola che tocca tutte e quattro: −1,4k.
- B4 Hook SessionStart: cap 1,5KB ciascuno, stampa solo rosso/cambiato: −1k.
- B5 WR2+WR3 → plugin locale `plugins/wr-rooms/` (agent + skill), `enabledPlugins` per macchina;
  sostituisce A5 e serve anche Pro/Mini. Precondizione: mappa dei consumer (plist, script, cron) che
  spawnano quegli agent per nome, perché un plugin disabilitato non serve un cron.
- B6 Anti-regressione: `scripts/context_budget_audit.py` — byte per categoria, **token = byte / 2,04**
  (rapporto ricalibrato a ogni prove-live), cap in CI sul modello di `test_superscar_budget.py`; e
  un ledger di prove-live con il numero VERO di `/context` per ogni leva.

Somma: **−6,9k**.

**Livello C — decisioni di Zero.** Artifact nel deny (−5k; è stato usato: `loggedAuthoredArtifactPaths`);
superpowers (−2k tra hook e skill: scelta di workflow dichiarata); Cron/Schedule/Push nel deny
(−2,5k: rinuncia a `/loop` e `/schedule` su M5); Drive connector (GUI claude.ai; con A1 pesa poco).

## 5. Metrica falsificabile e protocollo prove-live

**Probe da fare per primi, uno per sessione fresca:**

- P1 `ENABLE_TOOL_SEARCH=true` con solo `nuzantara-knowledge` attaccato → MCP nel pannello?
- P2 idem con Drive (connector claude.ai) → segue il deferimento?
- P3 idem con Chrome → segue il deferimento? e le sezioni browser del system prompt?
- P4 `permissions.deny` su un tool già "deferred" (es. `DesignSync`) → system tools cala?
- P5 `skillOverrides: off` su una built-in (`keybindings-help`) e su una plugin (nome corretto) → il pannello cala?

**Gate per livello** (totale `/context` di sessione fresca in `~/nuzantara`):

| Dopo | Certo | Base (P1-P3 sì) | Stretch (P4 sì) |
|---|---|---|---|
| A | ≤97k | ≤82k | ≤78k |
| A+B | ≤90k | ≤75k | ≤71k |
| A+B+C | ≤81k | ≤66k | ≤62k |

Per voce dopo A (base): MCP ≤1k · agents ≤2,5k · skills ≤6k · memory 20,7k (A non la tocca).
Dopo B: memory ≤14k · agents ≤1,5k (plugin) · skills ≤5,5k.

**Regola**: una leva, una sessione, una riga di ledger (`voce · prima · dopo · delta · setting/commit`).
La doc conferma che un CLAUDE.md editato a sessione viva non si applica: misurare senza riavvio è
misurare il vecchio.

## 6. Flotta

Le stesse chiavi valgono su Pro e Mini, dove il globale è ancora pre-dieta (HOME-fork, 3 copie).
La forma enterprise (§2.6) è un SSOT: un file `infra/claude-settings/` nel repo applicato da
`diet_home_apply.sh` v2 (o `managed-settings.json` in `/Library/Application Support/ClaudeCode/`,
che richiede sudo: gesto operatore). Su Pro niente pull sul main checkout (134 file uncommitted).
Pro e Mini hanno cron WR3 vivi: lì B5 va abilitato, non negato.

## 7. Limiti

Le stime per voce vengono dal pannello di UNA sessione e dai byte su disco; 2,04 vale per questo
corpus. `ENABLE_TOOL_SEARCH=true`, il deny sui tool differiti e `skillOverrides` sulle built-in sono
inferenze: il piano parte dai probe, non dai delta. Il binario 2.1.260 è compresso, nessuna lettura
del sorgente. Il Workflow `verify-template.js` prescritto dalla dottrina per research/audit non è
stato eseguito: il tool richiede l'opt-in esplicito dell'utente nella sessione; al suo posto il
red-team Codex di §9 su contesto fresco, che è lo stesso pattern generator≠grader.

## 8. Fonti

Fetchate: anthropic.com/engineering/effective-context-engineering-for-ai-agents ·
anthropic.com/engineering/advanced-tool-use · code.claude.com/docs/en/{memory, mcp, sub-agents,
context-window, skills, managed-settings, chrome, prompt-caching, permissions, plugins} ·
manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus.
Search-only: sintesi terze del post di Boris Cherny; Cursor rules (redirect); misure community MCP.
Interne: `2026-09-04-context-engineering-sota.md` (+3 lane); misure di questa sessione (§1).

## Adversarial review

Seat: Codex GPT-5 (`codex exec --sandbox read-only`, contesto fresco, prompt red-team "default a
difettoso"), sulla bozza precedente a questa versione. Verdetto: **block**, 10 finding. Disposizione:

| # | Sev | Finding (sintesi) | Esito |
|---|---|---|---|
| 1 | blocker | `byte × 2,1` dimensionalmente invertito | **fixed**: `token = byte / 2,04` (§1, B6) |
| 2 | blocker | gate per voce irraggiungibili con le leve elencate (memory ≤12k dopo A, ≤9k dopo B) | **fixed**: gate ricalcolati dai delta (§5) |
| 3 | major | tabella somma 102,0k; 43,0KB vs 42.176B; rules non quantificate | **fixed**: byte esatti, CLAUDE.md caricato = 9.752B, rules 3.391B, nota arrotondamento |
| 4 | major | −30k da 101,9k non dà ≤70k | **fixed**: certo/base/stretch, target sul caso conservativo |
| 5 | major | semantica di `true` e dei connector non documentata | **fixed**: declassata a inferenza, probe P1-P3 |
| 6 | major | executive summary tratta il deny come fatto | **fixed**: ipotesi + P4 |
| 7 | major | `skillOverrides` sui corner/built-in non supportato dalla doc | **fixed + verificato**: 5 righe già inerti sul disco (§1.6); corner → skill unica; built-in → P5 |
| 8 | blocker | `adversarial_review: none`; `Workflow` nel deny contro `operations.md` §6 | **fixed**: review eseguita; Workflow escluso dal deny; verify-template dichiarato non eseguito e perché (§7) |
| 9 | major | deny Cron/Push/Schedule e Agent(wr*) senza mappa consumer | **fixed**: Cron/Push/Schedule → livello C; censimento: `wr2.queue-pull` attivo su M5 (§1.7) |
| 10 | major | rename degli slug rompe `[[link]]`/MOS | **accepted**: nessun rename (B2 rivista, −2,5k invece di −3,5k) |
