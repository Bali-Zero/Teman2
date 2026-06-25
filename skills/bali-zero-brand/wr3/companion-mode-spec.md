---
name: companion-mode-spec
description: Voice register, hook patterns, and example translations for the wr3-design-architect `companion_from_carousel` mode. Read this when WR3 is dispatched on the `wr2_episode_published` channel.
mode: companion_from_carousel
sub_modes: [story_15s, reel_60s, comment_interactive]
version: 1.0.0
status: active
---

# Companion Mode Spec — WR3 Brand Cortex

> Loaded by `wr3-design-architect` whenever the dispatch arrives via the
> `wr2_episode_published` channel. This file is the **voice + structure
> authority** for WR2→WR3 companion content. Mode mechanics
> (durations, costs, critic lane masks) live in
> `docs/wr3/contracts/modes/companion-mode.yaml` — this file owns the
> editorial register.

## Core principle

Companion content is the **echo** of the carousel, not its rerun. The carousel already did the heavy lifting (full citation, slide-by-slide build, fact-check). The companion's job is to make the reader want to swipe back to the carousel — or comment, or DM. Never recap the carousel verbatim.

> Carosello = la spiegazione.
> Companion = il gancio che riporta alla spiegazione.

## Sub-mode 1 — `story_15s` (default)

### Voice register: **ironico**

Single rhetorical question + visual proof + soft CTA. Never lecture. Never read out a number Zantara has not earned. The 15s window is too short for context — assume the viewer has not seen the carousel yet.

### Structure (15s = 3 beats × 5s)

| Beat | Seconds | Element | Brand cortex anchor |
|---|---|---|---|
| Hook | 0-5s | One question. Ironic, with a number. | `voice/registers/ironico.md` |
| Proof | 5-10s | One visual fact, vertical-animated number, no voiceover at peak | `tokens.json` (palette + typography) |
| CTA | 10-15s | "Carosello completo nel link in bio" / "Swipe-up al carosello" | `voice/cta-soft.md` |

### Examples (concrete carousels)

#### KEP-71 SPT (carosello tax 2026-05)
- **Hook (5s)**: *"Sai cosa è il KEP-71?"* (close-up Zantara, eyebrow raised)
- **Proof (5s)**: "21 giorni" + "IDR 18 milioni" animati in verticale, palette `accent-yellow`
- **CTA (5s)**: *"Carosello completo nel link in bio."* (small Zantara wave)

#### KITAS investor 2026 (carosello visa)
- **Hook**: *"Investor KITAS senza PMA? Spoiler: no."*
- **Proof**: "PMA min IDR 10 mld" verticale, citazione `BKPM PerKBPM 4/2024` slide-anchor
- **CTA**: *"Sai perché? Carosello in bio."*

### Critic gate (Lane 1 + Lane 3 only)

- Lane 1 (Identity ArcFace ≥ 0.6): Zantara must be recognizable in the hook close-up — fail = re-render the hook clip only, never the proof clip.
- Lane 3 (Brand voice): scan VO + on-screen text against `voice/taboo.md`. Forbidden in companion mode: "guida completa", "tutto quello che devi sapere", "ecco i 5 step" (carousel-style cliches that signal not-companion).

## Sub-mode 2 — `reel_60s` (opt-in `--expand`)

### Voice register: **analitico**

Reel is a **first-class WR3 episode** that happens to share claim_ids with the carousel. Full investigative-journalistic voice — same register as a standalone WR3 episode. The carousel is the source, but the Reel is autonomous.

### Structure (60s = standard WR3 8-clip arc)

Same 8-clip pacing as a regular `wr3-script-editor` output:

1. Cold open (8s) — hook with the strongest claim from the carousel
2. Stakes (8s) — what happens if reader ignores
3. Context (8s) — legal/regulatory anchor
4. Pivot (8s) — the contrarian/insightful angle
5. Proof 1 (8s) — first concrete number with claim_id
6. Proof 2 (8s) — second concrete number with claim_id
7. Synthesis (8s) — the "what to do" line
8. CTA (4s, trimmed) — "Carosello con tutti i 10 punti nel link in bio"

### Critic gate (full 4-lane)

Reel is first-class — full critic pass identical to a standalone WR3 episode. No shortcuts.

### Example arc (KEP-71 SPT, expanded)

1. *"Marta ha pagato IDR 18 milioni a marzo. Il suo errore costa 2 mesi di affitto."*
2. *"L'80% degli expat che vediamo non sa che esiste un'opzione legale per evitarlo."*
3. *"La regola è dentro un decreto del 2018. KEP-71. Nessuno lo cita."*
4. *"Eppure cambia tutto: 21 giorni, non 30. E la sanzione non si applica."*
5. *"IDR 18 milioni evitabili."*
6. *"21 giorni dalla data dell'errore."*
7. *"Devi solo sapere che il KEP-71 esiste. E che si applica al tuo caso."*
8. *"Carosello completo con i 10 step nel link in bio."*

## Sub-mode 3 — `comment_interactive` (opt-in `--engage`)

### Voice register: **pedagogico-ironico** (mixed)

Generates two text-only artifacts for community engagement:

1. **IG comment (≤220 chars)**: Zantara's pinned comment on the carousel itself
2. **DM reply template (3 variants)**: response template for the 3 most likely DM categories ("Mi serve aiuto", "Quanto costa?", "Sono in questa situazione")

No video. No voiceover. Output is structured JSON for manual review by Antonello before publishing.

### Structure

```json
{
  "ig_comment": {
    "text": "<≤220 char Zantara reply>",
    "tone": "pedagogico-ironico",
    "claim_ids_referenced": ["..."]
  },
  "dm_templates": [
    {
      "category": "need_help",
      "trigger_keywords": ["aiuto", "help", "perso", "lost"],
      "response": "<Zantara voice reply, ≤500 chars>",
      "next_step_cta": "Vuoi che ti mandi il link al servizio specifico?"
    },
    {
      "category": "pricing",
      "trigger_keywords": ["quanto", "prezzo", "cost", "costa", "fee"],
      "response": "<Zantara voice reply with PricingTool anchor>",
      "next_step_cta": "Vuoi che ti mandi un preventivo personalizzato?"
    },
    {
      "category": "personal_case",
      "trigger_keywords": ["io sono", "il mio caso", "my case", "situation"],
      "response": "<Zantara voice empathetic reply>",
      "next_step_cta": "Prenoti una call gratuita 15 min?"
    }
  ]
}
```

### Voice rules for comment_interactive

- **IG comment**: open with a question (never a statement). Mirror one specific number from the carousel. End without CTA (the carousel link is already in bio — don't ask twice).
- **DM templates**: never use "Ciao!" or "Hi!" — start with the user's apparent emotion ("Capisco la frustrazione...", "Sembra urgente...", "Ottima domanda..."). End with ONE concrete next step.

### Examples (concrete)

#### KEP-71 carousel IG comment
*"Quanti di voi hanno già pagato la sanzione senza sapere del KEP-71? (Curiosità onesta — non giudicante.)"*

#### Visa investor carousel IG comment
*"Domanda da expat: avete mai trovato un agente che vi ha detto NO a un Investor KITAS senza PMA? Se sì, fategli un regalo."*

### Manual review checkpoint (Law 5)

`comment_interactive` outputs are **ALWAYS** manually reviewed by Antonello before publish. The critic Lane 3 gate flags forbidden phrases but does NOT autopublish — there is no "autopublish_comment" code path by design.

## Forbidden across all 3 sub-modes (Lane 3 regex)

- "guida definitiva" / "ultimate guide"
- "tutto quello che devi sapere" / "everything you need to know"
- "ecco i N passi" / "here are the N steps"
- "non perderti" / "don't miss"
- "swipe up adesso!" (exclamation point + adesso/now)
- emoji a inizio frase (only mid-sentence accent emojis allowed per brand constitution)

## Identity tokens

All visual sub-modes (`story_15s` + `reel_60s`) use the standard Zantara anchor A007. ArcFace cosine threshold inherited from `wr3-clip-renderer` contract (≥ 0.6, not relaxed for companion mode — face recognizability matters MORE on Story format where the viewer has 5s to recognize her).
