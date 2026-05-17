# Agent Library — Patterns (hand-written 2026-05-17)

<!-- DO NOT auto-regenerate — this file is curated by hand. -->
<!-- Companion to 01-inventory.md (auto-gen) and 03-lessons.md (hand-written). -->

9 recurring patterns extracted from the 16 Claude subagents + 35 agentic
crons + cicatrix-scars. Each entry: when to use, anti-pattern, concrete
example with `file:line`, trade-off, correlated scar.

## Index

| #   | Pattern                                     | Category          |
| --- | ------------------------------------------- | ----------------- |
| 1   | Cascade fallback multi-LLM                  | resilience        |
| 2   | Bipolar verifier (LLM + NB)                 | ground-truth      |
| 3   | 3-LLM panel review parallelo                | quality-gate      |
| 4   | Devils-advocate red-team pre-publish        | quality-gate      |
| 5   | Imagegen no-silent-reuse (sha256)           | integrity         |
| 6   | Voyager skill library + Reflexion synthesis | learning          |
| 7   | Wave-orchestrator parallel agents           | orchestration     |
| 8   | Verify-not-trust durante orchestration      | orchestration     |
| 9   | Local-pre-filter (qwen2.5vl) → cloud        | cost-optimization |

---

## Pattern 1: Cascade fallback multi-LLM

**Quando usarlo**: cron job autonomo che deve completare nonostante quota-exhaust del Tier-1 LLM (Claude OAuth MAX rolling 5h). Pattern di base per ogni agentic cron a Pro.

**Anti-pattern**: single-LLM hard dependency in cron path — quota cap blocca cascata downstream con failure silenzioso ("ALL TIERS FAILED — manual investigation needed").

**Esempio concreto**: `~/scripts/regulatory-watcher-run.sh:33` (4 tier in cascata)

```bash
if [ $EXIT -eq 0 ] && ! grep -qE "out of extra usage|usage limit|quota exceeded|rate.limit" "$TMPOUT"; then
    SUCCESS=1
    USED_LLM="claude-sonnet-4-6"
fi
```

Lo wrapper greppa stdout per pattern di quota-exhaust dopo ogni tier (Claude → Gemini 3.1 Pro → Codex GPT-5.5 → Ollama qwen3.5:9b) e fall-through al tier successivo. Tier 4 (Ollama) è always-on, $0, lower quality acceptable. Vedi anche `~/.claude/CLAUDE.md` §"Multi-LLM cascade for autonomous agents".

**Trade-off**: wrapper complexity (~20 LOC per tier + regex su stdout) vs zero-stall garantito anche durante wave parallelizzazione concurrente (cicatrix Wave 2 Pro 2026-04-29: 3 agent paralleli hit Codex+Gemini+NLM exhaust simultaneamente, solo DeepSeek/Ollama consegnò). Empirical signal di "quota wave-level": ≥2 cloud LLM falliscono in 5min.

**Scar correlato**: `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/lessons.md:286` (Wave 2 Pro 2026-04-29 — brainstorm capacity exhaustion pattern wave-level).

---

## Pattern 2: Bipolar verifier (LLM main + NotebookLM ground-truth)

**Quando usarlo**: domain-critical query (regulatory, KBLI, visa, tax, property) dove single-LLM hallucination su normativa Indonesia = costo catastrofico per cliente Bali Zero. Use quando il dominio ha NB-INTEL specifico curato.

**Anti-pattern**: 4-LLM council su ogni query (overhead + latency 30s+); single-LLM trust senza ground-truth (Claude su regolamenti Indonesia produce false positive frequenti, cf. CLAUDE.md "Federation Orchestrator" trigger "KBLI, visa, normativa → Gemini search"); querying NB sbagliato per il dominio.

**Esempio concreto**: `~/.claude/agents/wr2-brief-interpreter.md:41-44`

```yaml
- `visa` → NB-1 (Bali Zero legal/immigration)
- `tax` → NB-4 (Bali Zero tax)
- `property` → NB-5 (Bali Zero property)
- `regulatory` → NB-1 + cross-check against NB-INTEL family
```

Il brief-interpreter routea domanda → NB dominio-specifico, estrae citation verbatim (`PP 18/2021`, `KEP-71/PJ/2026`) + concrete numbers, e li impone come "load-bearing contract" ai downstream agent (storyboarder, layout-composer).

**Trade-off**: NB query 3-8s extra vs single-LLM <1s. Costo accettabile su critical-path (legal/tax/visa client output); non usare su low-stakes Q&A interno. NB sources count vincolata: 60 notebook attivi, 2970 sources (cf. memory `reference_notebooklm_arsenal_full.md`).

**Scar correlato**: preventivo, nessuno (rule documentata CLAUDE.md §"External LLM arsenal" + §"Federation Orchestrator" da prima di incidenti).

---

## Pattern 3: 3-LLM panel review parallelo (pre-approval)

**Quando usarlo**: prima di chiedere user approval su spec/design non triviale (≥3 file diversi, feature critical-path, qualsiasi cosa che mergia a main). Hard rule introdotta 2026-05-13.

**Anti-pattern**: review sequenziale (slow + biases later LLM by earlier output); single-reviewer (mono-bias provider-correlato); skipping perché "il design sembra ovvio" — l'ovvio è dove i killer flaw si nascondono.

**Esempio concreto**: `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/feedback_always_review_spec_with_4_llm.md`

```
2026-05-13 case — WR2 orchestrator FileTokenStorage v1 design, I (Claude)
drafted a shared-cache approach [...] All 3 sibling LLMs independently
identified the SAME killer flaw I had missed: tokens OAuth are bound to
client_id at registration time.
```

Fan-out parallelo (background bash): Gemini 3.1 Pro free OAuth + GPT-5.5 codex `--full-auto` + DeepSeek V4 Pro API ($0.01). Sintesi convergence/divergence: 3/3 converge → CRITICAL revise; 2/3 → SIGNIFICANT flag; 1/3 → flag but trust majority. NB-1 4° panelista quando UUID known.

**Trade-off**: $0.01/section + ~2min wall vs ship-broken-design 2-3h debug + rollback. Skip esplicito su user override "skip panel" o "I trust your judgment".

**Scar correlato**: preventivo (rule proattiva 2026-05-13 — FileTokenStorage v1 sarebbe stato shipped broken senza il panel).

---

## Pattern 4: Devils-advocate red-team pre-publish

**Quando usarlo**: dossier finiti, research capture, quote client, alto-stakes output prima di consegnare/pubblicare. Mandatory gate per deep-researcher, client-case-quote-generator, wr2-strategos.

**Anti-pattern**: usarlo su iterazione N>3 (loop infinito di refinement editorial — caught empirically PPh21 Q3 2026 file: P1 BLOCK → P3 NEEDS_FIX risolto critical+high, P4-P7 medium-only nitpicks); usarlo come revisor di stile (è breaker logico, non editor); skip cap perché "verdict says PASS" feels natural.

**Esempio concreto**: `~/.claude/agents/devils-advocate.md:3`

```
System prompt: "find the legal flaw, the tax miscalculation, the missing
regulation, the hallucinated KBLI code, the contradiction between sentence A
and sentence B."
```

DeepSeek V4 Pro reasoning chain è empiricamente migliore di Claude/Gemini su "show me where this argument breaks" per contradiction numerici/legali. $0.01/query.

**Trade-off**: 1 LLM call DeepSeek ($0.01-0.05) per fixare un'allucinazione legal-grade che costerebbe ore di debug client-side. Cap 3 iter hard: se P3 verdict ha 0 critical + 0 high, treat as functional PASS, log medium/low in frontmatter, NON loop further. Loop 7-pass cost 30min + $0.30 vs 3-pass 12min + $0.15 con same outcome (cf. memory `lessons_devils_advocate_loop_pattern.md`).

**Scar correlato**: `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/lessons_devils_advocate_loop_pattern.md` (cap 3 iter, empirical PPh21 2026-05-10).

---

## Pattern 5: Imagegen no-silent-reuse (sha256 anchor check)

**Quando usarlo**: pipeline carosello/template che riusa asset hero da run precedenti. Mandatory per ogni WR2 carousel run.

**Anti-pattern**: trust dell'`image_source` field nel `slides.json` senza verifica sha256 sul file effettivo. Sprint S11 docet: 12 caroselli con stesso "paper on dark desk" hero template silently reused — disastro reputazionale visivo.

**Esempio concreto**: `~/.claude/agents/wr2-design-architect.md:77` (Contract C)

```
Silent reuse of placeholders from a prior carousel directory (e.g.,
`cp ../test-1/placeholder-*.jpg .`) is forbidden. Each reuse decision must
be logged in `slides.json` as `image_source: "anchor:<file>"` or
`image_source: "imagegen:<codex_session>"`.
```

Verifica via `_audit-checklist.sh` mode `MODE=hero-sha`: compute anchor sha + every hero sha, asserts per slide_spec.image_source declaration (cf. line 41).

**Trade-off**: 1 Read + sha256 hash per hero (~50ms × N slide) vs disastro reputazionale 12-caroselli-identici. Costo accettabile sempre — il check è cheap, il fail è expensive.

**Scar correlato**: S11 hero monotone-template trap (preventivo dopo S11, documentato in agent description di `wr2-image-prompt-author`: "Avoids the monotone-template trap from S11 (12 carouseli all 'paper documents on dark desk')").

---

## Pattern 6: Voyager skill library + Reflexion weekly synthesis

**Quando usarlo**: orchestrator agent (wr2-design-architect) che deve evolversi nel tempo accumulando lezioni operative. Voyager = skill accumulate dopo episodi success; Reflexion = weekly sintesi delle failure/override per aggiornare prompt e curriculum.

**Anti-pattern**: skill library senza pruning (drift week-su-week 5-10%); Reflexion daily invece di weekly (rumore vs segnale); curriculum statico (niente exploration su topic-type sotto-rappresentati).

**Esempio concreto**: `~/.claude/agents/wr2-design-architect.md:376-380`

```
- Weekly cron (com.balizero.wr2.reflexion.weekly.plist, Sunday 02:30 WITA)
  runs Reflexion synthesis [...] read last 7 days of episodes +
  designer-override diffs (final published vs your draft), generate ≤10
  verbal lessons.
- Voyager curriculum: weekly inspect last 30 carousels. If a topic-type is
  underrepresented (e.g., "0 tax carousels in last 14 days"), generate 1
  exploratory variant for next production cycle and tag exploration:true.
```

**Trade-off**: rumore drift week-su-week vs zero-evoluzione. Cap esplicito: weekly synthesis (NOT daily), max ≤10 lessons/settimana, exploration mandatory su underrepresented topic. Pattern academico Voyager (Wang et al. 2023) + Reflexion (Shinn et al. 2023) adattati per dominio editoriale.

**Scar correlato**: preventivo, nessuno (pattern academico adattato).

---

## Pattern 7: Wave-orchestrator parallel agents on independent tasks

**Quando usarlo**: ≥2 task indipendenti senza shared state né dipendenze sequenziali. Singolo orchestrator dispatcha N agent paralleli (cf. `superpowers:dispatching-parallel-agents`).

**Anti-pattern**: >4 sessioni parallele se ≥1 tocca prod esterna (LLM provider capacity exhaustion wave-level); brainstorm cap >3 scambi (gonfiamento scope, FASE 2 wave 2026-05-07 docet); scope esterno-irreversibile in wave parallela (prod deploy concorrente).

**Esempio concreto**: `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/lessons_wave_pacing_design_rigor.md`

```
wave 6-sessioni 2026-05-07: 5 chiuse fast, FASE 2 gonfiata. 3 cause
evitabili: brainstorm no-cap, design review missing, scope esterno-
irreversibile in wave parallela. Cap brainstorm 3 scambi, design review
Codex sandbox, smoke runtime deps al design time, max 4 sessioni parallele
se 1 tocca prod esterna.
```

**Trade-off**: wall-clock ~N× faster vs coordination overhead + capacity-exhaustion risk wave-level. Sweet spot 2-4 agent. Pattern multi-agent topology Kim 2025: star (orchestrator + N workers) per task indipendenti, chain per pipeline sequenziale, broadcast per fan-out.

**Scar correlato**: `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/lessons.md:286` (Wave 2 Pro 2026-04-29 — brainstorm capacity exhaustion wave-level: Codex+Gemini+NLM simultanei).

---

## Pattern 8: Verify-not-trust durante orchestration

**Quando usarlo**: orchestrator che dispatcha sub-agent paralleli. Quando un agent ha 20-30min di silenzio sostanziale, investiga disk state (gh pr list, git log, /tmp/\*) SENZA inviare wake-up message (evita context disruption del sub-agent in tool calls lunghe).

**Anti-pattern**: ping ogni 10min (overhead + context disruption); trust dello status "in progress" sopra 30min senza verify; assumere completion da idle notification (è normal lifecycle, NON completion signal); citare output tool ricordato dal context buffer senza re-eseguire in this turn (hard rule "Errare è umano, allucinare è diabolico").

**Esempio concreto**: `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/lessons_hallucinating_tool_output_is_diabolical.md`

```
5 regole operative:
1. Mai citare l'output di un tool senza averlo eseguito in questo turn.
   Il context buffer NON è autoritativo.
2. Verifica con un secondo tool call indipendente prima di citare risultati
   critici.
3. Dopo Write, ri-verifica con `ls -la` SUBITO (Write può tornare success
   ma file rimosso da sibling process, visto live 2026-05-13).
4. Quando ho dubbio "ho letto questo o me lo sto inventando?" — fare il
   tool call adesso.
5. Quando operatore chiede "è finito?" / "non è vero?" — è quasi sempre
   segnale di mio skipped verification; trattare come trigger di
   re-verification disk-state, NON come richiesta di conferma.
```

Caso live 2026-04-29: agent-X aveva 30+min silence post-merge. Investigation su disco (`gh pr list`, `git log`, `/tmp/kakuro-SX-brainstorms/`) ha scoperto PR #342 già merged da 50min, 3 commit pushati, synthesis completo — wake-up message sarebbe stato context-disruptive.

**Trade-off**: extra tool call cost (1-3 Bash/Read) vs catastrophic decision su world-state fittizio. Hard rule: sempre verify. Soglia pratica 20-30min silence → disk-state investigate senza ping.

**Scar correlato**: `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/lessons.md:286` (Wave 2 Pro 2026-04-29) + `lessons_hallucinating_tool_output_is_diabolical.md` (2026-05-13).

---

## Pattern 9: Local-pre-filter (Ollama qwen2.5vl) → cloud LLM

**Quando usarlo**: ingestion batch (screenshot IG, OCR documenti, large corpus) dove 70-90% del materiale è triage-out. Local vision/text model classifica low-cost → solo materiale rilevante sale a cloud LLM per analisi quality-grade.

**Anti-pattern**: tutto-cloud (cost waste su material triage-out, Sonnet quota burn); local-only su task qualitative (qwen2.5vl 7B Q4 non riesce su brand-grade synthesis o legal-grade reasoning); skipping pre-filter quando triage-rate è basso (<50% — overhead non amortizza).

**Esempio concreto**: `~/.claude/agents/competitor-monitor.md:58-67`

```
### Step 3 — Instagram pre-filter via local qwen2.5vl:7b

Pre-filter via local Ollama vision model (qwen2.5vl:7b, already pinned warm):

ollama run qwen2.5vl:7b "Look at this Instagram post screenshot. Classify:
is this (a) educational/informational content, (b) promotional/CTA,
(c) lifestyle/aesthetic, (d) news/regulatory, (e) other? Respond with one
letter and one sentence rationale."
```

Solo screenshot classified (a) o (d) salgono a Sonnet per detailed analysis. Cost guardrail al §147: "Sonnet 4.6 OAuth + qwen2.5vl local (free). Total ~$0/run on Anthropic."

**Trade-off**: local 30-120s/batch + $0 vs cloud 5-10s + N × $0.01. Sweet spot quando batch ≥10 item e triage-rate ≥70%. Graceful degradation: qwen2.5vl unavailable → skip pre-filter, send all to Sonnet (line 160).

**Scar correlato**: preventivo, nessuno (cost-discipline rule introdotta proattivamente).
