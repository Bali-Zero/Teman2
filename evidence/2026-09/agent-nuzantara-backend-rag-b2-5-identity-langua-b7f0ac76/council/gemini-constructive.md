Here is the constructive review from the second seat, focused on client experience, behavioral gaps, and production safety.

---

### A. The Scripted Presentation Texts (`_IDENTITY_REPLIES`)

#### 1. Accuracy of Domain Scope

The capability bullets in [`apps/backend-rag/backend/services/integrations/wa_identity.py:171-175`](file:///Users/nuzantara/nuzantara/.worktrees/backend-rag-b2-5-identity-language/apps/backend-rag/backend/services/integrations/wa_identity.py#L171-L175) accurately summarize Bali Zero’s core consultancy pillars:

1. Visas & stay permits (`KITAS`, `KITAP`, visit visas)
2. Corporate setup & licensing (`PT PMA`, `NIB`, `OSS`, `KBLI`)
3. Tax & compliance (`NPWP`, `SPT`, `LKPM`)
4. Property & land titles

#### 2. WhatsApp Length & Layout

At ~450–500 characters formatted across four short paragraphs with bullet points, the presentation comfortably fits within a single mobile screen viewport without requiring scrolling or feeling overwhelming.

#### 3. Human Introduction vs. Form Letter & Truth in Capabilities

The grounding statement ([`wa_identity.py:176-177`](file:///Users/nuzantara/nuzantara/.worktrees/backend-rag-b2-5-identity-language/apps/backend-rag/backend/services/integrations/wa_identity.py#L176-L177)) sets honest expectations about RAG retrieval (_"when I'm not sure, I say so instead of guessing"_ / _"quando non sono sicuro te lo dico, invece di tirare a indovinare"_). It does not overpromise unverified facts.

#### 4. Cross-Language Parity

- **Italian vs. English/Indonesian:** In [`wa_identity.py:196`](file:///Users/nuzantara/nuzantara/.worktrees/backend-rag-b2-5-identity-language/apps/backend-rag/backend/services/integrations/wa_identity.py#L196), the Italian text lists `visti turistici`, whereas English lists `visit visas` and Indonesian lists `visa kunjungan`. _Visa kunjungan_ (e.g. B211A) covers business and pre-investment visits, not just tourism.
- **Indonesian Naturalness:** The Indonesian version contains an unnatural literal calque from English at [`wa_identity.py:178-179`](file:///Users/nuzantara/nuzantara/.worktrees/backend-rag-b2-5-identity-language/apps/backend-rag/backend/services/integrations/wa_identity.py#L178-L179): `«saya mau bicara dengan manusia»` ("talk to a human"). In Indonesian business communication, speaking to a human is never phrased as "bicara dengan manusia" (which sounds like talking to a human vs. an alien/animal); natural phrasing is `bicara dengan tim / staf / konsultan`. Furthermore, `"orang Bali Zero"` is overly colloquial compared to `"tim Bali Zero"`.

#### Exact Lines to Change and Replacements

**In [`apps/backend-rag/backend/services/integrations/wa_identity.py:169-180`](file:///Users/nuzantara/nuzantara/.worktrees/backend-rag-b2-5-identity-language/apps/backend-rag/backend/services/integrations/wa_identity.py#L169-L180):**

```python
# CURRENT:
    "id": (
        "Saya Zantara, asisten digital Bali Zero.\n\n"
        "Saya bisa bantu soal:\n"
        "• Visa & izin tinggal (KITAS, KITAP, visa kunjungan)\n"
        "• Pendirian perusahaan & perizinan (PT PMA, NIB, OSS, KBLI)\n"
        "• Pajak & pelaporan (NPWP, SPT, LKPM)\n"
        "• Properti & sertifikat tanah\n\n"
        "Jawaban saya selalu berdasarkan sumber resmi; kalau saya tidak yakin, "
        "saya bilang terus terang dan tidak menebak.\n\n"
        "Mau bicara langsung dengan orang Bali Zero? Tulis saja "
        "«saya mau bicara dengan manusia» dan saya teruskan ke tim."
    ),

# REPLACEMENT:
    "id": (
        "Saya Zantara, asisten digital Bali Zero.\n\n"
        "Saya bisa bantu mengenai:\n"
        "• Visa & izin tinggal (KITAS, KITAP, visa kunjungan)\n"
        "• Pendirian perusahaan & perizinan (PT PMA, NIB, OSS, KBLI)\n"
        "• Pajak & pelaporan (NPWP, SPT, LKPM)\n"
        "• Properti & sertifikat tanah\n\n"
        "Jawaban saya selalu berdasarkan sumber resmi; jika saya belum yakin, "
        "saya akan sampaikan apa adanya dan tidak menebak.\n\n"
        "Ingin berbicara langsung dengan tim Bali Zero? Beritahu saya kapan saja, "
        "dan konsultan kami akan segera membantu Anda."
    ),
```

**In [`apps/backend-rag/backend/services/integrations/wa_identity.py:196`](file:///Users/nuzantara/nuzantara/.worktrees/backend-rag-b2-5-identity-language/apps/backend-rag/backend/services/integrations/wa_identity.py#L196):**

```python
# CURRENT:
        "• Visti e permessi di soggiorno (KITAS, KITAP, visti turistici)\n"

# REPLACEMENT:
        "• Visti e permessi di soggiorno (KITAS, KITAP, visti d'ingresso e soggiorno)\n"
```

---

### B. The Invitation / Human Handoff Promise

#### The Problem

In [`apps/backend-rag/backend/services/integrations/wa_identity.py:178-204`](file:///Users/nuzantara/nuzantara/.worktrees/backend-rag-b2-5-identity-language/apps/backend-rag/backend/services/integrations/wa_identity.py#L178-L204), the presentation explicitly instructs the client:

- Line 178-179: `Tulis saja «saya mau bicara dengan manusia» dan saya teruskan ke tim.`
- Line 190-191: `Just write “I want to talk to a human” and I'll pass you to the team.`
- Line 202-203: `Scrivi «voglio parlare con un operatore» e ti passo al team.`

If a client follows these instructions and writes that exact phrase:

1. [`match_identity_question`](file:///Users/nuzantara/nuzantara/.worktrees/backend-rag-b2-5-identity-language/apps/backend-rag/backend/services/integrations/wa_identity.py#L232) returns `None` (not an identity phrase).
2. [`match_greeting`](file:///Users/nuzantara/nuzantara/.worktrees/backend-rag-b2-5-identity-language/apps/backend-rag/backend/services/integrations/wa_greeting.py#L269) returns `None`.
3. The message is dispatched to the RAG retrieval pipeline in [`wa_codex_leg.py:729`](file:///Users/nuzantara/nuzantara/.worktrees/backend-rag-b2-5-identity-language/apps/backend-rag/backend/services/integrations/wa_codex_leg.py#L729).
4. Retrieval finds no grounding context in Qdrant for "talk to a human", causing the evidence gate to either **abstain** or fail through retries to the terminal apology.
5. **No handoff occurs and no human is notified.** The bot explicitly gave the user a command prompt that immediately breaks upon execution.

#### Severity

**High UX friction on first contact.** Guiding a user to input a magic phrase that fails immediately shatters user trust.

#### Cheapest Honest Replacement Sentences

Replace the prescriptive keyword trigger with an informative invitation:

- **English ([`wa_identity.py:190-191`](file:///Users/nuzantara/nuzantara/.worktrees/backend-rag-b2-5-identity-language/apps/backend-rag/backend/services/integrations/wa_identity.py#L190-L191)):**
  `"Prefer to speak directly with our team? Just let me know anytime, and a Bali Zero consultant will take over."`
- **Italian ([`wa_identity.py:202-203`](file:///Users/nuzantara/nuzantara/.worktrees/backend-rag-b2-5-identity-language/apps/backend-rag/backend/services/integrations/wa_identity.py#L202-L203)):**
  `"Preferisci parlare direttamente con il team di Bali Zero? Fammelo sapere in qualsiasi momento e un nostro consulente prenderà in carico la conversazione."`
- **Indonesian ([`wa_identity.py:178-179`](file:///Users/nuzantara/nuzantara/.worktrees/backend-rag-b2-5-identity-language/apps/backend-rag/backend/services/integrations/wa_identity.py#L178-L179)):**
  `"Ingin berbicara langsung dengan tim Bali Zero? Beritahu saya kapan saja, dan konsultan kami akan segera membantu Anda."`

---

### C. The New Database Query (`_recent_inbound_texts`)

In [`apps/backend-rag/backend/services/integrations/wa_outbox_worker.py:340-360`](file:///Users/nuzantara/nuzantara/.worktrees/backend-rag-b2-5-identity-language/apps/backend-rag/backend/services/integrations/wa_outbox_worker.py#L340-L360):

```sql
SELECT body FROM meta_inbox_messages
WHERE thread_id = $1 AND direction = 'inbound'
  AND body IS NOT NULL AND body != ''
ORDER BY created_at DESC
OFFSET 1 LIMIT $2
```

1. **Is it bounded?**
   **Yes.** Line 341 defines `limit: int = 5` and line 355 passes `OFFSET 1 LIMIT $2`. It scans at most 5 rows using the index `meta_inbox_messages_thread_created_idx` (`(thread_id, created_at DESC)` created in migration 206).
2. **Lock/Claim Window Location:**
   **Outside transaction locks.** It runs within [`_maybe_send_apology`](file:///Users/nuzantara/nuzantara/.worktrees/backend-rag-b2-5-identity-language/apps/backend-rag/backend/services/integrations/wa_outbox_worker.py#L451) (called at lines 1224 and 1458), after generation or delivery has already failed permanently. It executes a read-only `SELECT` without holding table locks.
3. **Failure Isolation:**
   **Safely isolated.** The entire body of `_maybe_send_apology` is wrapped in `try: ... except Exception:` ([`wa_outbox_worker.py:523-625`](file:///Users/nuzantara/nuzantara/.worktrees/backend-rag-b2-5-identity-language/apps/backend-rag/backend/services/integrations/wa_outbox_worker.py#L523-L625)). If the query fails (e.g. database disconnect), the error is logged and swallowed, preventing worker crashes. The outbox failure state is already durably committed. _(Note: an exception during this query will skip sending the apology message, but the system remains resilient.)_
4. **Execution Path:**
   **Only executed on `'auto'` detection.** Line 578 (`if detected_language == "auto":`) ensures that normal message flows and terminal failures with identifiable languages (`en`, `it`, `id`) never execute this query.
5. **Ship Together or Split Out?**
   **Ship in the same PR.** Both changes share the same objective: preventing non-English clients from receiving fallback English text. The query logic is compact (< 25 LOC), defensive, and covered by unit tests in [`test_wa_outbox_worker_manners.py:279-322`](file:///Users/nuzantara/nuzantara/.worktrees/backend-rag-b2-5-identity-language/apps/backend-rag/backend/tests/unit/services/test_wa_outbox_worker_manners.py#L279-L322).

---

### D. Missing Behavioral Edge Cases

1. **Repeated Identity Questions in Same Thread:**
   [`match_identity_question`](file:///Users/nuzantara/nuzantara/.worktrees/backend-rag-b2-5-identity-language/apps/backend-rag/backend/services/integrations/wa_identity.py#L232) is completely stateless. If a client asks _"chi sei"_ and later asks _"ma chi sei tu esattamente?"_, the bot will send the exact same 500-character introductory block verbatim without acknowledging the prior presentation.
2. **Compound Queries with Non-Domain Terms:**
   If a client asks an identity question coupled with an unvetted general inquiry under 120 characters (e.g., _"who are you and can you help me move next month?"_), `move` and `month` are not in [`_DOMAIN_VETO_TOKENS`](file:///Users/nuzantara/nuzantara/.worktrees/backend-rag-b2-5-identity-language/apps/backend-rag/backend/services/integrations/wa_identity.py#L131-L154). The bot will match `"who are you"`, send the canned presentation, and swallow the client's practical question.
3. **Colleague / CRM Visibility:**
   When [`wa_codex_leg.py:723`](file:///Users/nuzantara/nuzantara/.worktrees/backend-rag-b2-5-identity-language/apps/backend-rag/backend/services/integrations/wa_codex_leg.py#L723) returns `CodexLegResult(text=identity.text, served_by="scripted_identity")`, the text is durably persisted to `meta_inbox_messages.body` ([`wa_outbox_worker.py:1267`](file:///Users/nuzantara/nuzantara/.worktrees/backend-rag-b2-5-identity-language/apps/backend-rag/backend/services/integrations/wa_outbox_worker.py#L1267)). Staff viewing the thread in the inbox will see the outbound message. However, `wa_outbox.generation_route` remains `NULL` (declared gap at [`wa_codex_leg.py:692-697`](file:///Users/nuzantara/nuzantara/.worktrees/backend-rag-b2-5-identity-language/apps/backend-rag/backend/services/integrations/wa_codex_leg.py#L692-L697)), so SQL reports filtering by generation route will not count these turns.
4. **Russian & Ukrainian Language Parity:**
   [`wa_greeting.py:227-245`](file:///Users/nuzantara/nuzantara/.worktrees/backend-rag-b2-5-identity-language/apps/backend-rag/backend/services/integrations/wa_greeting.py#L227-L245) provides dedicated greetings for `ru` and `uk`. In contrast, `wa_identity.py` only scripts `id`, `en`, and `it`. A Russian or Ukrainian user asking _"кто ты"_ will fall through to retrieval and receive an abstain refusal.

---

### Verdict

**FIX-FIRST**

**Single Most Valuable Change:** Remove the unbacked magic phrase promise (`"Just write 'I want to talk to a human' and I'll pass you to the team"` / `«saya mau bicara dengan manusia»`) from `_IDENTITY_REPLIES` so clients are not directed into a broken command loop before handoff intent detection is implemented.
