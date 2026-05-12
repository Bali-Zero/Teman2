# Bali Zero red-team cortex — CLIENT QUOTE PDF / EMAIL scope

Apply ONLY these rules when reviewing an A4 quote PDF (HTML source) or a Brevo email template.

## Constitution articles in scope

- **Article 6.4 — Citations verbatim**: regulation quoted exactly.
- **Article 6.5 — Bilingual lexicon untranslated**: KITAS, PT PMA, etc. — never translated.
- **Article 8 — Acronym verification**: every reg code must be verifiable; for client deliverables ALL regs must have JDIH primary verification, not just disclaimers.

## Quote/email-specific hard rules

- **From line**: ALWAYS `from=zantara@balizero.com / name=Zantara`. Never `notifications@`, `subhi@`, `no-reply@`.
- **Numerical figures**: every IDR amount must be derivable from PricingTool (`apps/backend-rag/.../pricing.py`) OR explicitly marked as "estimate pending PricingTool lookup". No plucked-from-air numbers.
- **Deadline arithmetic**: every date in deliverable must show holiday-shift derivation OR cite the source (SKB 3 Menteri 2026 #verified).
- **Client name spelling**: must match CRM record exactly (case + accents).

## Forbidden marketing clichés (apply here too)

Same closed list as research:

- "in today's evolving landscape"
- "delve into"
- "tapestry of regulations"
- "ecosystem"
- "navigate the complex"
- "unlock the potential"

## Severity for quotes/emails

- **CRITICAL**: wrong client name, wrong from-line, hallucinated regulation, IDR figure not from PricingTool, missed legal deadline that would expose client to penalty.
- **HIGH**: regulation cited as "verbatim" without JDIH verification, numerical claim without source, tax/visa interpretation contradicted by primary regulation.
- **MEDIUM**: vague phrasing where concrete commitment is expected, missing checklist item, scope ambiguity.
- **LOW**: typo in non-name field, minor formatting.

## Bali Zero canonicals (NEVER flag)

- "3 ALI ZERO" logo wordmark
- Untranslated Indonesian terms (Article 6.5 lexicon)
- "konsultan pajak" untranslated
