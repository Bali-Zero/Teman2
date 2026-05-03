# air-a1 — auth surface hardening — checkpoint FINAL

**Session:** Air A1 (pro-checkup-6-prompts, 2026-04-18)
**Worktree:** `.worktrees/auth-surface-hardening`
**Branch:** `security/auth-surface-hardening` ← `origin/main`
**Model:** Opus 4.7, xhigh effort
**Status:** DONE — 4/4 subtask chiusi, tutti i test verdi, PR pronta.

---

## Audit findings coperti

| ID     | Severity | Findings                                                                                  | Esito                                                  |
| ------ | -------- | ----------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| CRIT-1 | Critical | `apps/admin-dashboard` espone `/api/{postgres,qdrant,kg,legal,rag,calendar}/*` senza auth | ✅ Fixed con middleware Edge runtime                   |
| HIGH-5 | High     | `apps/web` senza middleware + `setToken` mai chiamato                                     | ✅ Escalated a Zero (ambiguità product/security)       |
| HIGH-6 | High     | Portal service si fida ciecamente di `client_id`                                          | ✅ Defense-in-depth decorator `@require_client_access` |
| HIGH-7 | High     | 86+ admin email hardcoded, 3 set `ADMIN_EMAILS` divergenti                                | ✅ Centralizzati in `settings.admin_emails_set`        |

---

## Commits

```
8213bcc01 feat(config): centralize admin emails + notification recipients (HIGH-7)
4f882d622 feat(portal): defensive RBAC at service layer (HIGH-6)
4efaa0ffe docs(security): escalate apps/web SSO policy to Zero (HIGH-5)
6b676cc03 feat(admin-dashboard): middleware auth gate (CRIT-1)
```

---

## Subtask 1 — CRIT-1 admin-dashboard middleware (6b676cc03)

**Problema rilevato:** Tutti i 5 satelliti esistenti (drive, mail, calendar, knowledge, mouth) fanno
`if (pathname.startsWith('/api')) return NextResponse.next();` — inadeguato per admin-dashboard
che espone direttamente PG + Qdrant.

**File toccati:**

- `apps/admin-dashboard/lib/auth/verify-admin.ts` (nuovo)
- `apps/admin-dashboard/middleware.ts` (nuovo)
- `apps/admin-dashboard/package.json` (+ `jose`, `vitest`, script test)
- `apps/admin-dashboard/vitest.config.ts` (nuovo)
- `apps/admin-dashboard/tests/verify-admin.test.ts` (14 casi)
- `apps/admin-dashboard/tests/middleware.test.ts` (10 casi)

**Differenze dal pattern standard (volontarie):**

1. NON salta `/api/*` — protegge anche gli endpoint DB
2. Decodifica JWT via `jose/HS256` usando `JWT_SECRET_KEY` (vs sola presenza cookie)
3. Richiede `role ∈ {admin, super_admin, owner}`
4. Supporta allowlist `ADMIN_EMAILS` env-var come difesa in profondità
5. Risposte: `/api/*` → 401/403 JSON (no redirect loop); HTML → redirect a `kita.balizero.com/login`
6. Logged-in non-admin su pagina HTML → 403 plain text (mai bounce a login)

**Test:** 24/24 vitest passati. Typecheck OK sui nuovi file (errori TS pre-esistenti non miei).

---

## Subtask 2 — HIGH-5 escalation apps/web (4efaa0ffe)

**Decisione:** NON toccare `apps/web/`. L'audit descriveva uno stato più semplice del reale:

- `apps/web` non ha middleware.ts
- `GraphClient.setToken()` mai chiamato → nessun Bearer iniettato
- Backend `hybrid_auth` NON lista `/api/query` in `public_endpoints` → risponde 401 senza JWT

Tre risposte product-level possibili (gate come satellite / lasciare pubblico con UI error / aprire
anonymous tier con rate limit). È una decisione Zero, non implementativa.

**File toccati:**

- `shared/escalations_air.jsonl` (append 1 entry `type=zero_decision, priority=HIGH`, audit_id=2026-04-18-HIGH-5)

---

## Subtask 3 — HIGH-6 portal RBAC defensivo (4f882d622)

**Approccio:** Gate primario resta il router (`get_current_client`). Il service layer riapplica
il controllo come difesa in profondità. Se un futuro router regredisce, il service nega.

**Nuovi elementi:**

- `backend/core/exceptions.py`: `PortalAccessDenied` (ForbiddenError), `PortalAuthRequired` (UnauthorizedError indiretta via `_rbac.py`)
- `backend/services/portal/_rbac.py` (nuovo): `ClientContext` TypedDict, `@require_client_access` decorator
- `backend/tests/services/portal/test_rbac_defensive.py` (nuovo, 10 test)

**Decorator applicato a (14 metodi):**

- `PortalDashboardMixin`: get_dashboard, get_visa_status, get_companies, get_company_detail, set_primary_company, get_tax_overview, get_timeline
- `PortalDocumentsMixin`: get_documents, upload_document
- `PortalBillingMixin`: get_billing, get_invoice_pdf_url, update_profile
- `PortalMessagingMixin`: get_messages, send_message, mark_message_read, get_preferences, update_preferences

**Router updates (16 call sites):**

- `routers/portal.py`: 14 siti → `current_user=client`
- `routers/portal_billing.py`: 2 siti
- `routers/crm_portal_integration.py`: team-side endpoint costruisce `ClientContext` con `impersonating=True` via helper `_team_impersonation_ctx()` DOPO `verify_client_access`

**Guardia impersonation (key insight):** Anche con `impersonating=True`, il decorator rifiuta se
`current_user['client_id'] != target_client_id`. Questo impedisce a un superuser che ha passato
`?as_client=A` past the router di piovotare a `client_id=B` nella stessa request.

**Test aggiornati (legacy):** 7 file portal-related aggiornati per passare `current_user=` kwarg.
Un assert in `tests/routers/test_portal.py` riscritto per introspettare `call.args/call.kwargs`
invece di `assert_awaited_once_with` (la signature è cambiata).

**Test run:** 236 passed, 1 skipped (portal + exceptions scope)

---

## Subtask 4 — HIGH-7 admin emails → config (8213bcc01)

**Scoperta:** 86 occorrenze hardcoded di `zero@/asya@/antonellosiano@` nel backend (escluse tests +
migrations). 3 set `ADMIN_EMAILS = {...}` duplicati e **divergenti**: `guardian.py` usava
`antonellosiano@gmail.com`, `workspace_*.py` usavano `@balizero.com`.

**Centralizzazione in `backend/app/core/config.py`:**

- `settings.admin_emails` (ADMIN_EMAILS env var, CSV)
- `settings.admin_emails_set` property (lower-cased, frozen, fallback storico per dev)
- `settings.notification_cc_emails` + `notification_cc_emails_list` property
- `settings.hr_notification_email` (default `asya@`)
- `settings.admin_notification_email` (default `zero@`)

**Migrazione RBAC consumers:**
| File | Prima | Dopo |
| --- | --- | --- |
| `routers/workspace_analytics.py` | `ADMIN_EMAILS = {...}` | `settings.admin_emails_set` |
| `routers/workspace_inbox.py` | `ADMIN_EMAILS = {...}` | idem |
| `routers/guardian.py` | `ADMIN_EMAILS = {...}` (con gmail drift) | idem |
| `routers/crm_interactions.py` | `["zero@", "admin@zantara.io"]` inline | `is_crm_admin({"email": user_email})` |
| `routers/portal.py` | `SUPERUSER_EMAILS = frozenset({"zero@"})` | `_superuser_emails()` → settings |
| `deps/auth.py` | `_SUPERUSER_EMAILS = frozenset({"zero@"})` | idem |
| `routers/team_drive.py` | `from crm_utils import SUPER_ADMIN_EMAILS` | `settings.admin_emails_set` |
| `utils/crm_utils.py` | 3 set hardcoded | `_crm_admin_emails()`, `_practices_full_view_emails()` — union di settings + extras domain-specific |
| `utils/hr_utils.py` | `HR_ADMIN_EMAILS = {...}` | `HR_EXTRA_ADMIN_EMAILS = frozenset({"ruslana@"})` + `_hr_admin_emails()` union |
| `deps/crm_access.py` | `CLIENTS_FULL_VIEW_EMAILS = PRACTICES_FULL_VIEW_EMAILS` | `_clients_full_view_emails()` |

**Migrazione notification recipient:**
| File | Prima | Dopo |
| --- | --- | --- |
| `routers/crm_practices.py` | `to="asya@balizero.com"` | `to=settings.hr_notification_email` |
| `services/crm/stale_practice_notifier.py` | `ADMIN_EMAIL = "zero@"` | `settings.admin_notification_email` |
| `services/crm/welcome/welcome_email_service.py` | `"bcc": "zero@"` | `settings.admin_notification_email` |
| `services/crm/welcome/welcome_practice_service.py` | `"bcc": "zero@"` | idem |

**Test aggiunti:** `backend/tests/services/test_admin_emails_config.py` (16 casi) — parsing env var,
normalisation case/whitespace, dedup, fallback, frozenset immutability, consumer behaviour (override
in `is_crm_admin`, Ruslana sopravvive a un override di ADMIN_EMAILS in HR).

**Test aggiornati:** `TestNotifyHRBonus` in `test_crm_practices.py` patcha `settings.hr_notification_email`
per pinnare il contratto senza dipendere dall'env var.

**Finale:** `grep -rn "ADMIN_EMAILS\s*=\s*{" apps/backend-rag/backend/ = 0` — zero set hardcoded
nel production RBAC path.

---

## Rischi residui / non coperti

1. **Email literal residui (66/86):** Sono in docstring, commenti, log, dev scripts, data seeds,
   federation host map (`federation.py` roles), e alcuni workflow-specific (`hr_leave_routing.py`,
   `deps/owner.py`, `work_session_service.py`, `practice_status_listener.py` BCC/CC). Nessuno di
   questi influenza decisioni RBAC. Lasciati intatti per ridurre il blast radius della PR.

2. **`ruslana@balizero.com` in HR/practices:** Rimane come `HR_EXTRA_ADMIN_EMAILS` costante nel
   modulo. Domain-specific, OK. Se Ruslana cambia ruolo, toccare `hr_utils.py`.

3. **Settings è singleton module-level:** Il test `test_is_crm_admin_honours_override` fa monkey-patch
   via assegnazione diretta. In produzione un cambio `ADMIN_EMAILS` richiede restart del processo
   (comportamento atteso per pydantic-settings + BaseSettings).

4. **apps/web/** — in attesa di decisione Zero. PR NON include modifiche a quell'app.

5. **Cicatrix aggiornabili:** Dopo il merge varrebbe la pena aggiungere a `.claude/rules/cicatrix-scars.md`
   un'entry "RBAC allowlist centralization" per prevenire la prossima drift.

---

## Verifica finale (criteria dal prompt)

- [x] `pytest backend/tests/services/portal/test_rbac_defensive.py -v` → 10 passed
- [x] `pytest backend/tests/services/test_admin_emails_config.py -v` → 16 passed
- [x] Admin-dashboard vitest (24 casi) → passed
- [x] `grep -rn "ADMIN_EMAILS\s*=\s*{" apps/backend-rag/backend/ --include="*.py"` → 0
- [x] Import chain `from backend.app.dependencies import get_current_user` → OK
- [x] No merge a `main` — PR per review umana
- [x] Ruff check sui file toccati → tutti i miei file green
- [x] Pre-commit hook (formatting, import chain, off-limits) → passed su ogni commit
- [x] OFF-LIMITS files non toccati (`zantara_core.py`, `fly.toml`, `alembic/env.py`, `.env*`)

---

## Handoff

**Per Zero:**

- Rispondere all'escalation in `shared/escalations_air.jsonl` (audit_id=2026-04-18-HIGH-5) scegliendo
  A/B/C per `apps/web` SSO policy. In attesa di decisione la PR resta indipendente.
- In produzione: settare `ADMIN_EMAILS`, `NOTIFICATION_CC_EMAILS`, `HR_NOTIFICATION_EMAIL`,
  `ADMIN_NOTIFICATION_EMAIL` come Fly.io secrets prima del deploy (fallback storico garantisce
  che anche senza env var il comportamento resti invariato).

**Per un'eventuale sessione di follow-up:**

- Estendere il decorator `@require_client_access` al `portal_profile_service.py` e
  `portal_visa_service.py` / `tax_service.py` (non coperti in questa PR perché hanno una superficie
  diversa — solo letture, già filtrate dal router).
- Aggiornare cicatrix-scars.md con il pattern defensive-at-service-layer.

---

_Session end: 2026-04-18_
_Claude Opus 4.7 (1M ctx), xhigh effort_
