# mini-p1nlm — P1-NLM ground-truth lane SUMMARY (Connectome Campaign)

> **Host:** mini-pro2 · **Lane:** L-KNOWLEDGE / P1-NLM · **Account:** antonellosiano@ · **Started:** 2026-06-16 ~09:30 WITA
> **Worktree:** `.worktrees/p1nlm-nlm-ground-truth-c4` · **Branch:** `agent/mini-pro2/p1nlm/nlm-ground-truth-c4` · **git_sha_before:** `a7c25f6b0`
> **Mandate:** bipolar-verify (1 LLM + 1 NB) the 6 P1-NLM contested claims escalated by cycles 1-3, then fix the site **SE E SOLO SE live NLM conferma**.
> **Method:** opus-mythos — decompose by claim, hunt the 2nd-order pattern, never trust the predecessor's report (re-verify on disk), cure-while-diagnosing, stop at the operator boundary. DeepSeek refuter on **decision-logic only** (W65: never on the regulatory fact). Opus final on-disk gate.

---

## §0 Executive — **the task's premise is FALSIFIED on disk**

The dispatch said *"Ora NLM è loggato → puoi verificarli."* **It is not.** Three independent on-disk proofs, this turn:

1. `claude mcp list` → `notebooklm-mcp: … ⏸ Pending approval (run claude to approve)` — the MCP server is **not connected** in this session.
2. `ToolSearch` for `mcp__notebooklm-mcp__notebook_query` / `cross_notebook_query` → **"No matching deferred tools found"** — the NB tools are absent.
3. `~/.notebooklm-mcp-cli/auth.json` mtime = **2026-04-30** (stale ~6.5 weeks); pre-flight §9 (2026-06-15) already empirically found *"Mini nlm auth scaduta."*

→ The mandated ground-truth side of the bipolar verifier is **unavailable**. Per the rule *"fixa SE E SOLO SE NLM conferma"*, **zero autonomous site fixes are authorized this cycle**. This is the same firebreak #2 that paused cycles 1-3 — the operator's belief that it was cleared is not reflected on disk. (Note: pre-flight §9 records **M5** as NLM *"✅ loggato"* — the correct host to actually run this verification is M5, or `nlm login` on Mini.)

**But this cycle is NOT a repeat of cycle-3's "all domain-contested, untouchable."** Fresh on-disk re-verification (opus-mythos #3: don't trust the predecessor's report) **corrects cycle-3's coarse triage**: for **4 of the 6** claims the **correct current fact is ALREADY published on an authoritative, source-citing sibling article on the same site**, while older/peripheral articles still teach the superseded fact. These are **propagation-shaped fixes-in-waiting**, not open domain questions — blocked only by the explicit P1-NLM gate (+ residual W65 risk where the on-disk authority is peer-vs-peer). The KBLI-55120 "ledger-vs-article conflict" the task asked me to resolve is **resolved on disk: the ledger is correct.**

**Cycle verdict:** 0 site fixes (firebreak honored) · 6 claims classified with fresh disk-verified evidence + staged NB query + staged fix · premise falsified with proof + exact remediation · 1 operator-decision (precedent waiver) surfaced · 2nd-order pattern found (intra-site contradiction). **Real delta, not theater:** the operator's next NLM session (on M5) is now one-shot per claim.

---

## §1 — Per-claim verdicts (all `BLOCKED_NLM_UNAVAILABLE` → re-escalate; staged for one-shot fix)

Legend — **fixability class**: `PROP-READY` = correct fact on authoritative on-disk sibling (propagation, like LKPM/SABH-NIB) · `PROP+RISK` = propagation-shaped but bundles an extra assertion / restructure · `NEEDS-NLM` = no on-disk anchor, genuine domain ground-truth required · `OVERMATCH` = propagation-shaped but huge legitimate-mention surface (mass-replace = superscar #3).

### 1. `VISA-C312` — class **PROP-READY (strongest)** — verdict BLOCKED_NLM
- **Offenders (assert C312 as a current code):** `articles/immigration/kitas-transfer-change-sponsor.mdx:228,230` ("Step 6: New Sponsor Applies for KITAS (**C312** Limited Stay Visa)" / "applies for your **C312** Limited Stay Visa") + its `.fr/.ru/.it/.id` (2 each); `articles/business/bkpm-regulation-5-2025-fdi.mdx:180` ("become a President Director with a work KITAS (**C312**)") + its `.fr/.ru/.it/.id` (1 each).
- **On-disk authority (correct, CITES the same regulation as the ledger):** `articles/immigration/working-kitas-e23-indonesias-revised-legal-framework-explained.mdx:48` — *"Permenkumham No. 22 Tahun 2023 … formally retiring the legacy C312 classification and replacing it with the E23 index for the Working KITAS."* Corroborated by `articles/immigration/bali-immigration-law-what-expats-need-to-know-in-2026.mdx:46` (*"pre-2024 codes such as B211A and C312 have been superseded and are no longer issued"*).
- **Intra-site contradiction:** the site simultaneously says C312→E23 (immigration articles) AND teaches C312 as the current work KITAS to apply for (transfer + FDI articles).
- **Ledger current_fact (NB-verified 2026-06-14):** "C312 is a retired pre-2024 code; … now E23." source *Permenkumham 22/2023; KITAS E23 (Kepmenkumham M.HH-02.GR.01.04/2023)*.
- **Staged NB query** (NB-INTEL-Immigration `1ed02e54` or NB-2): *"Under Permenkumham 22/2023, is C312 still issued for the Working KITAS or replaced by the E23 index? Quote the index entry."*
- **Fix if confirmed:** `C312` → `E23` in the 2 offender articles + their translations (targeted, NOT mass-replace; preserve historical "superseded C312" mentions).

### 2. `KBLI-HOTEL-55110` — class **PROP+RISK** — verdict BLOCKED_NLM
- **Offender:** `articles/property/property-via-pt-pma-indonesia.mdx:131` (`| 55110 | Hotel accommodation | 67% max foreign ownership |`) + `.it/.ru/.id/.fr` (line ~132).
- **On-disk authority (correct, BPS-aligned):** `articles/business/kbli-2025-hospitality-accommodation.mdx:63` (*"The old codes (55110, 55120, 55193, etc.) no longer exist in KBLI 2025"*) + full table 55101–55105 (star hotels by rating), 55106 (non-star). Matches ledger + Peraturan BPS 7/2025.
- **Risk note:** the property table fix bundles a code-renumber WITH an ownership-% claim (`67% max` vs the KBLI guide's `100%`); the ownership-% is a **separate assertion** (the property context may encode zoning/location, not pure KBLI). NLM must confirm both the renumber AND the ownership ceiling before touching it. Higher risk than a phrase-swap.
- **Staged NB query** (NB-3 `933509f9`): *"Per Tabel Konversi BPS / Peraturan BPS 7/2025, what replaced KBLI 55110, and what is the foreign-ownership ceiling for star-hotel codes 55101–55105 under KBLI 2025?"*

### 3. `KBLI-VILLA-55120` — class **PROP-READY + CONFLICT RESOLVED ON-DISK** — verdict BLOCKED_NLM
- **The task asked me to resolve the ledger-vs-article conflict. RESOLVED on disk: the LEDGER is correct.** The authoritative `articles/business/kbli-2025-hospitality-accommodation.mdx:76` maps **55120 → 55106** ("Non-star/budget hotels") and `:80` maps villa **55193 → 55203** — both **agree with the ledger** (55120 = old "Hotel Melati" → 55106; villa = 55203) and with BPS 7/2025.
- **Offenders (the WRONG side of the conflict):** `articles/property/property-via-pt-pma-indonesia.mdx:132` (`| 55120 | Homestay/boarding house | Restricted |` — wrong: 55120 was Hotel Melati, not homestay) + the article table(s) mapping `55120 → 55204 "Kondominium Hotel"` and the `.fr/.ru` consulting articles calling `55120` "Villa/Homestay". These are **stale/wrong articles contradicting an authoritative on-disk table** — NOT a domain dispute.
- **Ledger current_fact:** "Villa is KBLI 55203 (recoded from old 55193); 55120 was 'Hotel Melati', NOT villa." source *Tabel Konversi BPS*.
- **Staged NB query** (NB-3 `933509f9`): *"Under KBLI 2025 (BPS 7/2025), what does old code 55120 map to, and what is the current villa code?"* (expected: 55120→55106; villa 55193→55203).
- **Fix if confirmed:** align the offender tables to the on-disk authoritative `kbli-2025-hospitality-accommodation.mdx` table.

### 4. `VISA-B211A-60` — class **OVERMATCH (highest edit-risk)** — verdict BLOCKED_NLM
- **Offender (teaches B211A as a current extendable 60-day visa):** `articles/immigration/tourist-visa-extension-indonesia-guide.mdx:67` ("In 2026, **E-VOA** and **B211A** visas are extendable"), `:84-88` ("B211A … Initial validity: 60 days … Maximum total stay: 180 days"), `:328` already conflates: "Single Entry **B211A (C1 Tourism)**".
- **On-disk authority:** `articles/immigration/bali-immigration-law-what-expats-need-to-know-in-2026.mdx:46` — "the **C1** single-entry tourist visa (60 days initially, extendable up to a maximum total stay of 180 days — **this replaced the old B211A code**)".
- **Ledger:** "B211A superseded by C1; C1 = 60 days initial, extendable up to max 180 days total." (NB-2 quote present).
- **Risk note — DO NOT mass-replace:** 547 raw `B211A` hits across ~30 files, **mostly legitimate** migration/comparison ("the old B211A", "B211A was replaced by C1"). A blind `B211A→C1` swap is catastrophic over-match (superscar #3). Needs per-occurrence judgment + NLM confirmation of the exact current rule. **Lowest priority for autonomous action.**
- **Staged NB query** (NB-2 / NB-INTEL-Immigration): *"Is B211A still a current visa code or replaced by C1? What are C1's initial validity and max total stay?"*

### 5. `PONDOK-WISATA-FOREIGN` — class **NEEDS-NLM (genuine — no on-disk anchor)** — verdict BLOCKED_NLM
- **Issue:** articles **HEDGE** rather than state the ledger's categorical rule. `articles/business/tourism-hospitality-guide.mdx:138,146,454` ("Foreigners often face restrictions"; "Foreign ownership **varies by location** — **some** areas restrict or prohibit"; "**Many** areas prohibit foreign-owned Pondok Wisata"). `articles/property/airbnb-bali-ban-truth.mdx:59,61` tells the (foreign) reader "**you** need a Pondok Wisata license issued by the local regency" — implying a foreigner can hold one.
- **Ledger:** "Pondok Wisata is **reserved for WNI** (usaha perseorangan); a foreigner / PT PMA **CANNOT** hold it. Foreigner route = PT PMA + Villa KBLI 55203 in a Pink zone via OSS-RBA. Nominee = criminal under Perda Bali 4/2026." source *Permenpar tourism framework*.
- **Why genuinely NLM:** **no authoritative on-disk sibling** states the categorical WNI-only rule → cannot propagation-fix; the gap is a domain fact requiring NB-5 ground-truth. This is the one claim where cycle-3's "needs live NLM" is fully accurate.
- **Staged NB query** (NB-5 `d9438180-5e63-4e2a-a473-6061101f6a8d`): *"Can a foreigner or PT PMA legally hold a Pondok Wisata license, or is it reserved for WNI individuals (usaha perseorangan)? What is the compliant foreigner route for short-stay rental?"*

### 6. `MORATORIUM-SARBAGITA` — class **PROP-READY (intra-site contradiction, peer-vs-peer)** — verdict BLOCKED_NLM
- **Offender (presents the INVERTED/stale framing as current):** `articles/business/kbli-2025-hospitality-villa-hotel-bali-investment-guide.mdx:54` (FAQ: "The Sarbagita moratorium is a construction freeze in **four regencies: Denpasar, Badung, Gianyar, and Tabanan** … blocks new accommodation construction in Bali's **prime tourist zones**") and `:140` (same). This **IS the ledger's stale_pattern** — the inversion.
- **On-disk authority (correct, matches ledger verbatim):** `articles/business/kbli-2025-real-estate-property-investment-bali-2026.mdx:119,326,328` — "does NOT target the Sarbagita tourist core — **that was the cancelled September 2024 proposal** … the actual formal ban covers **six less-developed districts (Tabanan, Jembrana, Buleleng, Bangli, Karangasem, Klungkung) and explicitly excludes Badung, Gianyar, and Denpasar.**"
- **Flat intra-site contradiction:** two live published articles assert **opposite** moratorium scopes. The NB-verified ledger sides with the real-estate guide.
- **Caveat (W65):** real-estate-guide and hospitality-guide are **peer articles** (no derived-vs-dedicated hierarchy like SABH-NIB). The tiebreak is "matches the NB-verified ledger verbatim" — strong, but peer-vs-peer is why an NLM (or operator-waiver) confirm is warranted before flipping the hospitality article.
- **Staged NB query** (NB-5 `d9438180`): *"Does the 2026 Bali construction moratorium freeze the Sarbagita tourist core (Denpasar/Badung/Gianyar/Tabanan), or cover 6 less-developed districts and exclude the tourist core? Was the Sarbagita-core freeze a cancelled Sept-2024 proposal?"*

---

## §2 — §Meta-pattern (the real topic) — **"La contraddizione intra-sito, invisibile alla sentinella-stringa"**

> **One faulty structure generates the family: the freshness guard checks a string in ONE file, but the same fact lives — correct in one article, stale in another — and two self-consistent articles that disagree are STRUCTURALLY invisible to a per-string, per-file scan.**

For **4 of 6** claims (C312, 55110, 55120, Sarbagita) the **correct current fact is already published**, often **citing the governing regulation**, on an authoritative sibling — while another live article teaches the superseded fact. The site asserts **X and not-X simultaneously**. This **extends the cycle-1-3 meta-pattern** ("il guardiano della frase, non del fatto", W82 under-match): not only does the sentinel guard one phrasing on the EN canonical, it is blind to **cross-article fact disagreement**, because each article is internally consistent and the sentinel never compares article-to-article.

**Three cross-cutting evidences:** (a) C312 "superseded→E23" (`working-kitas-e23.mdx:48`) vs C312 "apply for this work KITAS" (`kitas-transfer.mdx:230`); (b) 55120→55106 (`kbli-2025-hospitality-accommodation.mdx:76`) vs 55120 "Homestay, Restricted" (`property-via-pt-pma.mdx:132`) and 55120→55204 elsewhere; (c) Sarbagita "cancelled, 6 other districts" (`real-estate-guide:326`) vs "freeze in the 4 tourist regencies" (`hospitality-villa-guide:140`).

**Structural antidote (proposed, operator design call):** promote the freshness ledger from a per-file **stale-string** scan to a **cross-article fact-KEY consistency** check — every article that touches fact F (keyed by entity: visa-code, KBLI-code, moratorium-scope, license-eligibility — language-invariant) must agree with the ledger's current value of F. This is the superscar-#3/W82 "fact-key strutturato" antidote applied at **cross-article scope**. A naive scope-widening to translations (cycle-3's proposal) would still miss two EN articles disagreeing.

**Meta-meta (the audit's own decay):** cycle-3 labeled all 6 "domain-contested." Disk re-verification shows 4/6 are **propagation-shaped**. The triage itself decayed — the "P1-NLM list" *exists* but its classification was coarser than the disk warranted (an instance of #2 Esiste≠Armato, applied to the audit's own output). opus-mythos #3 (re-verify the predecessor) caught it.

---

## §3 — §Refuter ledger (W65 live instance, round 1 + round 2)

- **Round 1 — DeepSeek V4 Pro (`reasoning_effort=high`), decision-logic only (NOT the regulatory fact):** verdict **`DECISION_TOO_CONSERVATIVE`**. Argument: refusing to fix any of the 6 is *inconsistent with the campaign's own LKPM/SABH-NIB precedent* (which fixed on "correct fact already on an on-disk sibling", no live NLM); rigid "fix only if NLM" when that rule was already relaxed under identical conditions is the *"organism catalogs disease but never cures itself"* anti-pattern.
- **Round 2 — Opus on-disk adjudication (the father re-greps; the refuter also hallucinates):**
  - **Upheld:** the blanket "all domain-contested, untouchable" framing WAS too conservative → corrected to the PROP-READY/PROP+RISK/NEEDS-NLM/OVERMATCH classification above.
  - **Overruled "fix all 4 now":** (1) LKPM was **same-article EN→translation** propagation (zero authority ambiguity); these are **cross-article** with varying authority — Sarbagita is **peer-vs-peer** (weakest), 55110/55120 **bundles an ownership-% assertion**, B211A is **over-match-catastrophic**. (2) **Decisive:** the campaign **explicitly** scoped these 6 as P1-NLM — an L0 decision; the task's binary gate is a *specific instruction about THESE claims*, not a generic rule to relax by analogy. (3) **Irony reinforcing the gate:** DeepSeek itself **false-refuted the LKPM regulatory fact in cycle 1** ("PerBKPM 5/2025 is hallucinated") — direct proof that reasoning-on-2025-regs (even the refuter's) is unreliable, which is the entire reason these need NLM.
  - **Resolution:** do **not** auto-fix; **offer the operator a precedent-based waiver** for the 2 strongest (C312, Sarbagita) — the SAME basis used for LKPM/SABH-NIB — as **their** firebreak call (not assumed). This converts the refuter's valid hit into a concrete operator option rather than blanket refusal OR reckless auto-fix.

---

## §4 — §Terapia eseguita (cure-while-diagnosing)

| Action | Status | Proof |
|---|---|---|
| Falsify task premise (NLM logged in?) | ✅ done | `claude mcp list`→Pending approval; ToolSearch→absent; `auth.json` mtime 2026-04-30 |
| Re-verify 6 claims on disk, correct cycle-3 triage | ✅ done | offender + on-disk-authority file:line per claim (§1) |
| Resolve KBLI-55120 ledger-vs-article conflict | ✅ done | ledger correct; `kbli-2025-hospitality-accommodation.mdx:76,80` agrees |
| Decision-logic refuter (DeepSeek) + round-2 gate | ✅ done | §3 |
| Site fix (any of 6 claims) | ⛔ NOT DONE — firebreak | NLM gate unsatisfiable; 0 site delta = honest (constitution §9: pause, don't degrade) |
| Findings + 6 effect-receipts committed (docs, L2-safe) | ✅ this commit | branch `agent/mini-pro2/p1nlm/nlm-ground-truth-c4` |

**Site delta this cycle: ZERO** (firebreak honored). Docs delta: this SUMMARY + 6 receipts.

---

## §5 — §Solo-operatore (firebreaks — only Zero / L0)

1. **NLM is NOT logged in on Mini** (this task's premise, falsified — see §0). → `nlm login` + approve the `notebooklm-mcp` server on Mini (interactive Google OAuth = firebreak), **OR** run this P1-NLM verification from **M5**, where pre-flight §9 (2026-06-15) records NLM *"✅ loggato."* The 6 staged NB queries (§1) make it one-shot.
2. **Precedent-waiver DECISION (operator's call — I did NOT assume it):** for **C312** and **Sarbagita** the correct fact sits on an authoritative, source-citing on-disk sibling that matches the NB-verified ledger — the **same basis** the campaign used to autonomously fix LKPM/SABH-NIB. **If L0 waives the NLM gate for these 2** (as it implicitly did for LKPM/SABH-NIB), the lane can fix them in one shot with a targeted (non-mass-replace) edit. Reply "waive C312+Sarbagita" to authorize. (55110/55120 bundle an ownership-% assertion → prefer NLM even under waiver; B211A → NLM + per-occurrence, never mass-replace.)
3. **Open the PR** (no merge — L2) for branch `agent/mini-pro2/p1nlm/nlm-ground-truth-c4` (findings + receipts).
4. **Sentinel architecture decision:** extend the freshness ledger to a **cross-article fact-key consistency check** (the §2 antidote) — a design call, not an autonomous edit.

---

## §6/§8 handoff for L0 (fold into 00-CAMPAIGN-STATE.md)

**§6 registry append:**
`[2026-06-16 ~09:40 WITA] mini-pro2/P1-NLM — cycle 4 done — premise falsified (NLM NOT logged in on Mini: MCP pending-approval + auth.json 2026-04-30 stale + tools absent); 0 site fixes (firebreak honored); 6 claims re-verified on disk → cycle-3 triage corrected (4/6 PROP-READY, not "all domain-contested"); KBLI-55120 conflict resolved on-disk (ledger correct); DeepSeek refuter DECISION_TOO_CONSERVATIVE → round-2 adjudicated → operator precedent-waiver offered for C312+Sarbagita. → findings/mini-p1nlm-SUMMARY.md + receipts/mini-pro2-p1nlm-*.json (6)`

**§7 backlog candidate (scar/pattern):**
**"Contraddizione intra-sito"** — two live published articles assert opposite values of the same regulatory fact; invisible to a per-file/per-string freshness sentinel. Sub-family of **W82 / superscar #3** (guard-of-phrasing-not-fact, under-match). Candidate antibody: ledger must enforce a **cross-article fact-key** (entity-keyed, language-invariant) consistency check, not a per-file stale-string scan.

**§8 operator-only additions:** Mini `nlm login` + MCP approve (or run from M5); precedent-waiver decision (C312 + Sarbagita); PR-open from M5; cross-article fact-key sentinel design.

---

## §Verdetti per claim (this cycle)

| Claim | Verdict | Fixability class | On-disk authority | Offender file:line |
|---|---|---|---|---|
| VISA-C312 | ⛔ BLOCKED_NLM | PROP-READY (strongest) | working-kitas-e23.mdx:48 (cites Permenkumham 22/2023) | kitas-transfer-change-sponsor.mdx:228,230; bkpm-regulation-5-2025-fdi.mdx:180 (+trans) |
| KBLI-HOTEL-55110 | ⛔ BLOCKED_NLM | PROP+RISK (ownership-%) | kbli-2025-hospitality-accommodation.mdx:63 | property-via-pt-pma-indonesia.mdx:131 (+trans) |
| KBLI-VILLA-55120 | ⛔ BLOCKED_NLM (conflict resolved: ledger correct) | PROP-READY | kbli-2025-hospitality-accommodation.mdx:76,80 | property-via-pt-pma-indonesia.mdx:132; 55120→55204 tables; fr/ru consulting |
| VISA-B211A-60 | ⛔ BLOCKED_NLM | OVERMATCH (547 hits) | bali-immigration-law-…-2026.mdx:46 | tourist-visa-extension-indonesia-guide.mdx:67,84-88,328 |
| PONDOK-WISATA-FOREIGN | ⛔ BLOCKED_NLM | NEEDS-NLM (no on-disk anchor) | — (none; articles hedge) | tourism-hospitality-guide.mdx:138,146,454; airbnb-bali-ban-truth.mdx:59,61 |
| MORATORIUM-SARBAGITA | ⛔ BLOCKED_NLM | PROP-READY (peer-vs-peer) | kbli-2025-real-estate-…-2026.mdx:119,326,328 | kbli-2025-hospitality-villa-hotel-bali-investment-guide.mdx:54,140 |

**Not done (mandate "every claim a verified NB verdict"):** the live-NB verdict itself — blocked on firebreak #1. Every claim instead has a disk-verified classification + staged NB query + staged fix, so the verdict is one query away once NLM is up (on M5 or post-`nlm login`).

---
*Cycle 4 — 2026-06-16 ~09:40 WITA. Opus 4.8 final on-disk gate. Effect-receipts: `receipts/mini-pro2-p1nlm-*.json` (6). git_sha_before `a7c25f6b0`. Site delta: 0 (firebreak honored, not theater — see §0/§4).*
