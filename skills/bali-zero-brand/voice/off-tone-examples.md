# Off-tone examples — voice that failed, with diagnosis

> 3 examples of failed Bali Zero copy + diagnosis. Used by wr2-critic to recognize off-tone patterns.

---

## Failure 1 — engagement-bait opener

### What was written
```
ARE YOU THINKING OF MOVING TO BALI?
HERE ARE 5 THINGS YOU NEED TO KNOW BEFORE YOU GO.
```

### Why it fails
- Question opener = engagement-bait pattern (forbidden-phrases §D).
- "5 things you need to know" = listicle template, not editorial.
- "Before you go" assumes audience hasn't moved yet — Bali Zero audience is mostly already-in-Bali expats fixing mistakes, not pre-arrival researchers.
- No regulatory citation. No concrete number. No sentence-bomb. Could be from any of 100 competitor accounts.

### How to fix
Rewrite as: "MOST PEOPLE MOVING TO BALI PICK THE WRONG VISA IN THE FIRST MONTH. SIGN A LEASE THAT DOES NOT HOLD UP UNDER PP 18/2021. FIND OUT ONLY AT TAX TIME. WE SPEND OUR DAYS FIXING THAT." (See on-tone Ex 9.)

---

## Failure 2 — corporate-legalese disclaimer

### What was written
```
PLEASE NOTE THAT THIS POST IS FOR INFORMATIONAL PURPOSES ONLY
AND DOES NOT CONSTITUTE LEGAL ADVICE.
ALWAYS CONSULT A LICENSED PROFESSIONAL BEFORE MAKING DECISIONS.
TERMS AND CONDITIONS APPLY.
```

### Why it fails
- Bali Zero IS the konsultan pajak + PPJK + immigration consultancy. Telling readers to "consult a licensed professional" undermines the brand.
- "Please note" = empty politeness phrase, not editorial.
- Disclaimers signal that the brand is afraid of liability. Bali Zero's authority comes from being the lawyers, not from disclaiming itself.

### How to fix
Delete the slide. If a legal-protection clause is genuinely needed (rare, for tax-strategy carousels), use a single line in IBM Plex Mono 11px in the source-citation footer of the closing slide: "Sources: KEP-71/PJ/2026, NB-4 catalog. For case-specific guidance contact zantara@balizero.com." No "this is not legal advice" — that phrase is banned.

---

## Failure 3 — vague feel-good close

### What was written
```
WHATEVER YOUR DREAM, BALI HAS A PATH.
LET'S BUILD IT TOGETHER.
START YOUR JOURNEY TODAY.
LINK IN BIO ➡️
```

### Why it fails
- "Whatever your dream" = boilerplate marketing.
- "Bali has a path" = empty metaphor.
- "Let's build it together" / "start your journey" = forbidden phrases (§B, §C of forbidden-phrases.md).
- Emoji ➡️ in a slide = forbidden (§H).
- "Link in bio" on a slide = forbidden in slide context (§B).
- Fails the closing-slide rule: must be statement-bomb single-line bold centered, NO CTA hard-sell.

### How to fix
Replace with a register-rituale closing: "EVERY QUARTER, THE PERIMETER TIGHTENS." or register-militante: "PERMITS ARE PERMISSIONS. THEY CAN BE RESCINDED." (See on-tone Ex 1, 2.)

---

## Pattern recognition for wr2-critic

When scoring a slide, mark off-tone if 2+ of these fire:
- Question mark in title or first sentence (D-pattern engagement-bait)
- "Let's" / "We're here to" / "We're excited to" opener
- Emoji anywhere
- Disclaimer language ("please note", "always consult", "subject to change")
- Vague quantifier ("a lot of", "many", "several") without concrete number
- CTA hard-sell in closing ("book now", "DM us", "link in bio")
- Empty metaphor ("landscape", "tapestry", "realm", "journey", "ecosystem" in marketing sense)
- Numbered listicle structure ("5 things you need to know")
- Title in sentence case
- Body length outside 25-90 words (cover slide exempt)

3+ markers = hard fail. 2 markers = soft fail (route to human review).


---

*Reflexion 2026-W19*: ## Rejected: marina-tuka-tibubeneng-shutdown (2026-05-08)

**Reason:** factually-wrong

**Note:** Tibubeneng enforcement/shutdown narratives carry high factual-error risk. Before storyboarding, require explicit NB-INTEL or NB-0 citation for the specific enforcement action claimed. Do not infer shutdown scope from secondary reporting.
