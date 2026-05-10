# Bali Zero red-team cortex — RESEARCH FILE scope

Apply ONLY these rules when reviewing a research markdown file under `research/<domain>/`.

## Constitution articles in scope

- **Article 6.4 — Citations verbatim**: every regulation must be quoted exactly, never paraphrased. KEP, PMK, Permenkumham, PER, SKB numbers must be cited as written or marked unverified.
- **Article 6.5 — Bilingual lexicon untranslated**: KITAS, KITAP, PT PMA, KBLI, SHGB, hak pakai, KKPR, BATARA, konsultan pajak, PPJK, Permenkumham, NPWP, Coretax, OSS RBA must NOT be translated to English. Acronyms UPPERCASE, bahasa lower (`hak pakai`).
- **Article 8 — Acronym verification**: every regulatory code (KEP-NN/PJ/YYYY, PMK-NN/YYYY, PER-NN/PJ/YYYY, SKB Nomor X) must be verifiable via JDIH. If sourced from a secondary aggregator (Ortax, Pajakku, MUC, kiakrikil, pajaknow), citation must include "(per <source> — pending JDIH verification)" disclaimer.

## Forbidden marketing clichés (apply to research too)

These phrases are banned in research files just as in slides:

- "in today's evolving landscape"
- "delve into"
- "tapestry of regulations"
- "ecosystem"
- "navigate the complex"
- "unlock the potential"
- "robust framework"
- "leverage the synergy"
- "paradigm shift"

## What is NOT a violation in a research file

DO NOT flag these as findings (they apply only to published Instagram slides):

- Title in sentence case (research H1 is a markdown header, NOT a published slide title)
- Body length (research files have no length limit)
- Practical operational phrases like "consult tax counsel", "check with the office", "verify before client delivery" — these are concrete operational guidance, the OPPOSITE of cliché
- UPPERCASE rules (Article 3.3 typography is for IG slides only)
- Body case mixing (Article 6.1.1 is for IG carousel coherence)
- Hero image rules
- Layout family rules

## Severity guidelines for research

- **CRITICAL**: hallucinated regulation code (KEP-XX/PJ/YYYY that doesn't exist on JDIH), fabricated identifier strings (e.g. invented NPWP format), confidently-stated wrong dates that would cause client to miss a tax deadline.
- **HIGH**: regulation cited as "confirmed" or "verbatim" when sourced from secondary aggregator without JDIH verification; numerical claim without primary source; legal interpretation stated as fact when contested across sources.
- **MEDIUM**: ambiguous citation (Pasal/ayat pinning without primary verification), counting/arithmetic that needs explicit definition, internal contradictions between sections.
- **LOW**: vague qualifiers ("around", "approximately") where concrete numbers would help; minor scope ambiguities.

## Bali Zero canonicals (NEVER flag as errors)

- "3 ALI ZERO" or similar logo wordmark stylings
- Untranslated Indonesian terms in the Article 6.5 lexicon
- Bahasa Indonesia inline (e.g. "masa pajak", "setor", "lapor")
