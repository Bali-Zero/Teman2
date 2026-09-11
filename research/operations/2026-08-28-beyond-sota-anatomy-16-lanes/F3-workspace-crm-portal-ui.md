---
date: 2026-08-28
domain: operations
part: F3 workspace-crm-portal-ui
scope: Internal tools + back-office UX — kita (team workspace), my (client portal), prime (owner surface), admin/wa dashboards, team inbox, review queues, HR surfaces, RBAC UI
sources:
  - https://linear.app/method
  - https://blog.superhuman.com/how-to-build-a-remarkable-command-palette/
  - https://www.intercom.com/blog/announcing-intercoms-next-gen-inbox/
  - https://www.intercom.com/blog/betting-on-the-future-of-frontend-at-intercom/
  - https://attio.com/blog/introducing-attio-objects
  - https://attio.com/blog/ai-and-the-next-generation-of-CRM
  - https://www.clio.com/blog/legal-matter-management/
  - https://www.nngroup.com/articles/complex-application-design/
  - https://docs.github.com/en/subscriptions-and-notifications/how-tos/viewing-and-triaging-notifications/managing-notifications-from-your-inbox
  - https://retool.com/blog/state-of-internal-tools-2023
  - https://retool.com/use-cases/admin-panels
  - https://workos.com/blog/the-developers-guide-to-audit-logs-siem
  - https://www.enterpriseready.io/features/audit-log/
status: DONE
adversarial_review: kimi-k3
---

> ## ⚠️ Read this before acting on anything below
>
> **These findings are pinned to `11a3c89a2e` (2026-08-28). `origin/main` was 123 commits ahead
> when this file was published on 2026-08-30.** A verdict in here is a **LEAD, not a fact**: it
> was true of a tree that no longer exists. Re-measure before you build on it.
>
> **Defects presented below as current that were already CURED before publication** — each fix
> verified as a descendant of the pin with `git merge-base --is-ancestor 11a3c89a2e <sha>`:
>
> | Presented as a live defect | Actually cured by | Verified |
> |---|---|---|
> | R9 harness time-bomb dated 2026-09-02 (X1) | #5190 | ancestor check |
> | Phantom DeepSeek voter (B8) | #5211 / #5207 (`cc82ed62e4`, `0cccbbc925`) | ancestor check |
> | Auth split-brain across the portals (F3, F4) | #5181 (`d6556a75bf`) | ancestor check |
> | Magic-link `result_id` ownership — which F2 calls "replay-safe" (F2) | #5298 (`3861567e52`) | ancestor check |
> | Meta webhook signature unenforced in prod (B3) | fail-closed by default since 2026-08-26; `WHATSAPP_APP_SECRET` deployed | live probe: unsigned `POST /webhook/whatsapp` → **401 `Invalid signature`** (2026-08-30) |
>
> **Counts that were re-measured and found WRONG** (they were not corrected in the text, so that
> the reports stay the artefact the panel actually produced rather than a quietly-improved one):
> `X3:31` reads 10 directories + 6 symlinks, measured 11 + 5. `X3:45` reads 162 `@mcp.tool`,
> measured 153. Other counts flagged by the review but NOT settled either way are listed in this
> PR's evidence pack under `dissent`, marked PLAUSIBLE — treat every number in these files as
> unverified unless you have just re-run it.
>
> **Known internal contradiction, left standing:** `B4` states that OCR of identity documents
> never leaves the machine, and then, two paragraphs later, that OCR'd passport/NPWP/akta text is
> shipped to Gemini by CRM-Guardian. The second statement is the accurate one. It is ledgered.
>
> **Two things were withheld from this publication rather than edited quietly:** the panel's own
> mandate file (self-labelled `IN-PROGRESS` / `internal`), and the location of a live DNS-write
> credential named in `B5`. Both omissions are declared here because a silently-sanitised audit is
> worth less than an audit that says what it removed.
>
> The reports' own thesis is that a written artefact gets presumed to be in force. This header
> exists because that thesis applies, first, to the reports themselves.


# F3 — Workspace / CRM / Portal UI

## Anatomy (as measured)

**Scale.** The `(workspace)` route group (kita.balizero.com) holds 44 pages across 206 non-test TSX files, 59,716 lines. The `portal` tree (my.balizero.com) holds 29 pages across 79 files, 14,404 lines, backed by 67 portal components. One Next.js app (`apps/mouth`) serves three domains via host-based routing in `apps/mouth/src/proxy.ts` (portal domain gate at `proxy.ts:260-279`, prime domain match at `proxy.ts:242`).

**Auth split-brain (verified).** Real authentication is the httpOnly SSO cookie `nz_access_token` (`proxy.ts:78`), which client JS cannot read. Yet `isAuthenticated()` at `apps/mouth/src/lib/api/client.ts:211-215` returns `getToken() !== null`, and `getToken()` (`client.ts:137-156`) reads **localStorage** `auth_token` via `safeStorage`. 13 non-test files reference `isAuthenticated` as a gate — including `app/(workspace)/settings/roles/page.tsx:214`, `settings/users/page.tsx:49`, `settings/security/page.tsx:91`, `admin/page.tsx:108`, `admin/team-activity/page.tsx:215`, `admin/cell/page.tsx:12`, `admin/system/page.tsx:61`, `app/agents/page.tsx:94`. This confirms the known live defect: page-level gates judge a localStorage artifact while the session truth is a cookie; the two can diverge in either direction. The workspace layout itself does the honest version — a server-verified profile fetch that redirects to `https://kita.balizero.com/login` on 401 (`app/(workspace)/layout.tsx:198-276`) — so the localStorage gates are a *second, weaker* auth model living alongside the real one.

**One table, one column.** Backend confirms the second known context: staff and client logins share `team_members` (`apps/backend-rag/backend/app/routers/auth.py:346-354`), branch on `role == "client"` at `auth.py:439` and `auth.py:513`, and the code's own comment (`auth.py:243-246`) states the email guard cannot distinguish — "only the role can."

**Genuinely sophisticated surfaces (measured, not marketing):**
- **Document review queue** — `app/(workspace)/review/page.tsx` (1,465 lines): per-member server-enforced queues, 15-minute claim leases, original-document preview streamed over the SSO cookie, inline field correction, explicit dry-run surfacing so "nobody is misled" (header comment, lines 1-25). This is real case-management engineering.
- **INTAKE compliance gate** — `app/(workspace)/GateScreen.tsx`: a mandatory pre-workspace wall (Late → Documents → Deadlines) rendered *instead of* the workspace when `GET /api/intake/gate/status` reports blocked; fail-open on probe outage (`layout.tsx:176-195`); leaves exactly one route (`/review`) reachable while blocked (GateScreen header, lines 10-25). Forcing obligations before tool access is a pattern the benchmarked sector does not have.
- **Admin impersonation** — `components/portal/SuperuserImpersonationBar.tsx` + `AdminImpersonationContext` imported in the portal layout (`app/portal/(authenticated)/layout.tsx:16`): support-mode client-view, a feature usually found only in mature SaaS.
- **Command palette** — `components/workspace/KitaCommandPalette.tsx`: Cmd+K (`:24`), mounted workspace-wide (`layout.tsx:513`). But it holds only ~9 static actions — navigation plus two case-creation deep links — with role-gating for owner inbox (`:42`) and accounting (`:52`). No record search, no in-context actions, no recents.
- **Role-shaped dashboards** — `components/dashboard/role-widgets/`: five per-role widgets (Zero/Tax/Marketing/Accounting/Team) plus an 888-line dashboard page; full i18n (`I18nProvider`, `src/i18n/locales`).
- **HR suite** — 10 routes, 4,588 lines (payroll slips, leave requests, bonuses, owner weekly cashout).
- **CRM depth** — clients list 1,406 lines, client detail 1,042, `ClientKanban`, `TaxCompanyPilotWorkspace` (8 files, 2,623 lines in `components/crm`), partners module with an orphan-recovery route (`partners/orphaned/page.tsx`), LKPM appears twice (team side + portal side), second-home vertical.
- **Client portal** — process stepper (`ProcessStepper.tsx`), `PracticeBaton`, vault (43-line page delegating to a 6-component vault tree), billing, visa (600 lines), taxes, family. `portal/messages/page.tsx` is a 10-line re-export of `portal/chat` — both URLs deliberately serve one implementation.

**The omnichannel inbox is real code but an unreachable room.** `app/(workspace)/omnichannel/page.tsx` (244 lines) is a proper 3-pane inbox — `ThreadList` / `ThreadView` / `CRMPanel` (729 component lines) with per-channel WhatsApp/Telegram/Instagram list+viewer pairs (518/491/499 lines). Grep over `app/`, `components/`, `types/` finds **zero inbound links** to `/omnichannel`; it is absent from the sidebar navigation registry (`types/navigation.ts:40-81`). Last touched 2026-07-26. Meanwhile `/whatsapp` (189-line page reusing the WhatsApp pair) *is* linked — from one dashboard widget (`components/dashboard/WhatsAppPreview.tsx:80`). The unified inbox exists; the org navigates to the single-channel view.

**Inbox fragmentation count: five.** (1) `/omnichannel` (orphaned), (2) `/whatsapp` (widget-linked), (3) `/inbox` — owner-only `InboxTimeline`, gated by a hardcoded email comparison in client JS (`layout.tsx:222-229`, backend 403 as SSOT per its comment), (4) `apps/wa-dashboard-m1` — a local read-only 3-column viewer on local Postgres (README, DB note verified 2026-08-06), (5) `apps/wa-meta-inbox` (server.cjs + viewer.html). Five inbox implementations, no single one canonical.

**Dead and experimental route-trees (all with zero inbound links from app or components — measured):**

| Route | Size | Last touch | Verdict |
|---|---|---|---|
| `/edge` | 18-line static stub | 2026-02-17 | dead diagnostic page |
| `/exclusive` | 78-line video player | 2026-07-29 | one-off pitch artifact |
| `/lab/voice-concierge` | 29 lines | 2026-06-23 | experiment shell |
| `/agents` | 266-line agent-status console | 2026-03-27 | abandoned ops console |
| `/dream` | **2,180-line single file** | 2026-08-28 | live experiment, anonymous-by-design (`dream/page.tsx:999-1014`) |
| `/v2` | design-system preview, noindex, 8 pages | 2026-07-31 | design lab (17 commits) |
| `/prime` | 13-line page → `PrimeNexusLayout` (20 files, 2,359 lines) | 2026-07-08 | geospatial hub, reached only via external URL from the palette (`KitaCommandPalette.tsx:79`) |

`/dream` deserves its own flag: a 2,180-line client component ("Dream Thinking Room" — article composer with autosave to `/api/dream/state`) deliberately reachable anonymously, unlinked, still receiving commits (11 total, last 2026-08-28). It is the largest single page file in the app and it is invisible to navigation.

**Four admin surfaces.** (1) `apps/mouth` `(workspace)/admin/*` — 4 pages (system, cell, team-activity 900 lines). (2) `apps/admin-dashboard` — 67 files, Fly config `app = 'nuzantara-admin'` (`fly.toml:1`), pages for qdrant/postgres/rag/war-room/knowledge-graph/legal; **its deploy target is dead — `nuzantara-admin.fly.dev` does not resolve in DNS (curl: "Could not resolve host", measured 2026-08-28)** — yet the app received a commit 2026-08-20. (3) `apps/admin-dashboard-local` — explicitly "NOT deployed anywhere — localhost:3100" (README), `LOCAL_ONLY=1` refusal, HMAC bearer held only in React memory, actively maintained (2026-08-26): this one is honest about its nature and has real ops content (garuda-voa, cockpit, cost-dashboard, observatory). (4) `wa-dashboard-m1` (2026-08-06). An operator wanting "admin" must know which of four doors to open, and one of the four is a Fly app whose DNS no longer exists.

## Honest state vs. SOTA

**What is genuinely good.** The review queue + INTAKE gate pair is the strongest back-office UX in the system and would survive comparison with commercial case-management tools: server-enforced work queues, leases against double-work, dry-run transparency, and a compliance wall that converts "nagging" into "gating." Portal impersonation, role widgets, i18n, and the process stepper are mature-SaaS features a solo operator rarely ships. The one-codebase/three-domains proxy is sound engineering.

**What is theater.** The unified omnichannel inbox — the centerpiece claim of an "ops workspace" — is unreachable by any click path; the org lives in a single-channel WhatsApp view plus two local viewers. `admin-dashboard` is maintained toward a DNS-dead deploy target: commits with no consumer, the repo-wide "Esiste ≠ Armato" disease (superscar #2) expressed in UI form. Six orphan route-trees ship in the production bundle of a business-critical domain; `/dream` ships 2,180 anonymous-reachable lines on the same app that serves the CRM.

**What is broken by design.** The 13 localStorage `isAuthenticated()` gates are not just a defect list — they are a second auth model that contradicts the cookie model, and every new page must choose between them (several admin pages chose wrong). The palette is keyboard-*present*, not keyboard-*first*: no entity search, no per-view actions, so daily CRM work remains mouse-bound. Notifications exist as a page (566 lines) and a bell, but there is no triage model — no done/saved states, no per-source muting.

**Net assessment.** Feature breadth is far beyond what a solo operator should plausibly own — CRM + HR + payroll + LKPM + partners + second-home + intel + review + portal ≈ 74k lines of surface. Depth is uneven: two or three surfaces are near-SOTA; the connective tissue (navigation, auth consistency, one-inbox, dead-code hygiene) is where it loses against every benchmarked product below.

## Deep research: the world's best

**1. Linear — quality bar and keyboard-first ops.** The [Linear Method](https://linear.app/method) is the sector's reference for internal-tool feel: three principles (speed, clarity, execution) enforced by a local-first sync engine and a command menu where *every* action has a keyboard shortcut. The engineering pattern that matters is not the shortcut list but the architecture underneath it: optimistic local state means no interaction waits on the network, which is what makes keyboard velocity real rather than cosmetic. Nuzantara's workspace is request-response throughout (every page fetches on mount, e.g. `omnichannel/page.tsx:43-58`).

**2. Superhuman — the command palette as the product.** Superhuman's engineering write-up ([How to build a remarkable command palette](https://blog.superhuman.com/how-to-build-a-remarkable-command-palette/)) gives a concrete recipe: put **every possible action** in the palette (features "that could never warrant a button"); fuzzy matching with typo tolerance (their open-sourced `command-score`, 0-1 scoring); a synonym/alias system ("Mark Done (Archive)"); relevance = default score × context multiplier × usage frequency; and the palette *teaches* shortcuts by displaying them beside each action. Their internal latency target is 50-60ms per interaction (public claim 100ms). Against this recipe, `KitaCommandPalette.tsx`'s 9 static navigation actions is a v0.1.

**3. Intercom — the omnichannel inbox rebuild.** Intercom threw away its most-used product and rebuilt it ([next-generation Inbox](https://www.intercom.com/blog/announcing-intercoms-next-gen-inbox/)) around three ideas transferable to kita: (a) claimed 10x faster, "no spinners, every action immediate"; (b) **Cmd+K inside the inbox** — keyboard control of every inbox action from one place; (c) a **Table Layout** for managers — a dense, customizable bird's-eye grid over the same conversation data, acknowledging that the 3-pane view serves responders while supervisors need density. Their [frontend-platform post](https://www.intercom.com/blog/betting-on-the-future-of-frontend-at-intercom/) adds the org-level lesson: consolidating on one stack (React, sub-1s rebuilds) is what made 10+ teams productive on one inbox — the opposite of five parallel inbox implementations.

**4. Front-class shared-inbox patterns.** Across the shared-inbox category (Front, Zoho TeamInbox, et al. — survey: [dragapp.com](https://www.dragapp.com/blog/multi-channel-shared-inbox/)), the invariant feature set is: one queue across channels; explicit **ownership** (every conversation has exactly one assignee); rules-based routing (sender/keyword/channel → assignee/tag); internal comments on the conversation itself; and **collision detection** — showing that a teammate is viewing/replying to the same thread. Nuzantara has ownership server-side in the review queue (leases) but nowhere in its messaging surfaces.

**5. Attio — the CRM data-model as UX.** [Attio Objects](https://attio.com/blog/introducing-attio-objects) makes the case that CRM UX quality is downstream of the data model: typed objects/records/attributes with semantic meaning (not strings), custom objects shaped to the business, and — their explicit argument in [A new vision for CRM](https://attio.com/blog/ai-and-the-next-generation-of-CRM) — a structured model is what lets an LLM operate the CRM reliably. This is directly relevant to a company whose second user is an agent fleet: the fleet can only be as good as the objects it manipulates.

**6. Clio — matter-centricity in legal ops.** Clio's organizing principle ([legal matter management](https://www.clio.com/blog/legal-matter-management/)) is that **every artifact hangs off the matter**: contacts, documents, calendar events, notes, time entries, bills — one spine per case, plus Matter Stages (kanban across the case lifecycle) and automation on stage transitions (generate document / assign task when a matter advances). Nuzantara's nearest concept is the practice + `ProcessStepper`, but artifacts are scattered: messages live in channel views, documents in the vault/review, deadlines in the gate — not unified under the practice.

**7. GitHub — notification triage as a model.** GitHub's inbox ([managing notifications](https://docs.github.com/en/subscriptions-and-notifications/how-tos/viewing-and-triaging-notifications/managing-notifications-from-your-inbox)) is the reference triage grammar: **Done** (out of inbox, queryable `is:done`), **Saved** (kept indefinitely, `is:saved`), unread/all, custom filters, grouping by source, and bulk triage. It is a small, complete state machine — precisely what a 566-line notifications page with read/unread lacks.

**8. Retool — internal-tool economics and admin-panel hygiene.** Retool's [State of Internal Tools](https://retool.com/blog/state-of-internal-tools-2023) measures that engineers spend ~33% of their time building/maintaining internal tools — the argument for consolidating surfaces instead of multiplying them. Their [admin-panel guidance](https://retool.com/use-cases/admin-panels) sets the baseline: per-user/per-group permissions on view/edit/trigger, centralized audit logs, and write operations deliberately constrained.

**9. NN/g — complex-application guidelines.** The [8 guidelines](https://www.nngroup.com/articles/complex-application-design/) most applicable here: staged disclosure ("reduce clutter without reducing capability"), flexible pathways (skip/loop within workflows), track actions and thought processes (notes attached to work items), and salience by *removal* ("removing nonessential elements can be equally or more effective"). Their research on dashboards ties abandonment to cognitive load, not aesthetics.

**10. WorkOS / EnterpriseReady — audit-log UX.** The [developer's guide to audit logs](https://workos.com/blog/the-developers-guide-to-audit-logs-siem) and [EnterpriseReady](https://www.enterpriseready.io/features/audit-log/) define the enterprise pattern: an immutable, time-synced, admin-accessible stream with actor-action-target schema, covering auth events, privilege use, and admin config changes. Nuzantara has fragments (review audits server-side, team-activity page) but no unified stream a client or auditor could read.

## Gap table

| Dimension | SOTA benchmark | Nuzantara measured state | Gap |
|---|---|---|---|
| Keyboard-first command surface | Superhuman/Linear: every action, fuzzy search, taught shortcuts | 9 static nav actions (`KitaCommandPalette.tsx:40-107`) | Large |
| Unified team inbox | Intercom/Front: one canonical inbox, ownership, collision detection | 5 implementations; the unified one has 0 inbound links | Large (structural, not code) |
| Inbox manager view | Intercom Table Layout (density for supervisors) | none | Medium |
| Matter-centricity | Clio: every artifact on the matter spine | practice + stepper, artifacts scattered across 4 surfaces | Medium |
| CRM object model as UX | Attio: typed objects, AI-operable | fixed tables; agent fleet reads ad-hoc endpoints | Medium |
| Notification triage | GitHub: Done/Saved/filters/grouping/bulk | read/unread only (566-line page) | Medium |
| Auth consistency | one server-verified session truth | cookie truth + 13 localStorage gates | Large (severity, small fix) |
| Dead-surface hygiene | Retool: consolidate (33% eng time at stake) | 6 orphan route-trees; DNS-dead admin app still committed to | Large |
| Audit trail | WorkOS: immutable actor-action-target stream, admin-readable | fragments (review audit, team-activity) | Medium |
| Latency model | Linear local-first, Superhuman 50-100ms | fetch-on-mount everywhere | Large (accepted: cost/benefit poor for 1 team) |
| Impersonation, role dashboards, i18n, review leases, compliance gate | rare even in SOTA products | present and real | **Ahead** on gate/leases; at par elsewhere |

## Recommendations — reach SOTA

- **P0 — Kill the second auth model.** Replace all 13 `api.isAuthenticated()` page gates with the layout's server-verified pattern (or nothing, where the layout already guards). *Acceptance (falsifiable):* `grep -rn "api.isAuthenticated()" src/app src/components --include="*.tsx" | grep -v test` returns 0 rows; a browser with the cookie but empty localStorage reaches all 13 pages; a browser with a forged localStorage token and no cookie reaches none. One session, no backend change.
- **P0 — One inbox ruling, then wiring.** Decide the canonical team inbox (candidate: `/omnichannel`, it already has the CRM panel), add it to `types/navigation.ts`, fold `/whatsapp` into a channel filter of it, and mark wa-dashboard-m1/wa-meta-inbox as local diagnostic viewers in their READMEs. *Acceptance:* exactly one inbox route appears in the sidebar registry; `/whatsapp` 308-redirects to `/omnichannel?channel=whatsapp`; orphan-inbox count 5 → 1 canonical + 2 declared-diagnostic.
- **P0 — Dead-route quarantine.** Delete `/edge`, `/exclusive`, `/lab`; archive `/agents` unless its backend endpoints still answer; put `/dream` behind auth or move it off the CRM-serving app. *Acceptance:* a route-liveness check (every `page.tsx` has ≥1 inbound link, a sitemap entry, or an explicit `experiment` marker) passes in CI; anonymous fetch of `/dream` returns a redirect, not 2,180 lines of app.
- **P1 — Disposition of `admin-dashboard`.** Either redeploy (make `nuzantara-admin.fly.dev` resolve) or archive the app directory and port its 2-3 live pages (qdrant/postgres browsers) into `admin-dashboard-local`. *Acceptance:* `dig nuzantara-admin.fly.dev` resolves AND login answers, OR `apps/admin-dashboard` is renamed `.archived-*` and receives no further commits (CI check on path).
- **P1 — Command palette v2 (Superhuman recipe).** Add entity search (clients/practices via the existing `QuickSearch` API), per-page contextual actions, alias matching, and shortcut hints. *Acceptance:* from any workspace page, Cmd+K + typing 3 chars of a client name reaches that client's page in one round-trip; palette action count ≥30; a typo test ("lnik"-class) still ranks the intended action first.
- **P1 — GitHub-grammar notifications.** Add Done/Saved states, source grouping, and bulk triage to `/notifications`. *Acceptance:* the three states are server-persisted; `is:done`-equivalent filter exists; median unread count for the team drops and stays below a set threshold for 30 days.
- **P2 — Practice as the matter spine (Clio pattern).** On `clients/[id]` and `process/[id]`, aggregate every linked artifact: documents (review/vault), conversations, invoices, deadlines, LKPM filings. *Acceptance:* practice detail renders ≥5 linked artifact types from live endpoints, each deep-linking back.
- **P2 — NN/g density pass + Intercom table view.** Progressive-disclosure audit of the 888-line dashboard (≤7 competing above-fold elements) and a dense table mode over the inbox for supervision. *Acceptance:* above-fold element count measured before/after; table mode ships behind a toggle.
- **P2 — List-view keyboarding.** J/K navigation + Enter to open + single-key approve/reject in the review queue and clients list. *Acceptance:* a full review-queue item can be processed with zero pointer events (scriptable Playwright proof).

## Recommendations — beyond SOTA

- **The palette becomes an agent command line.** No benchmarked product lets Cmd+K *dispatch work*. With the fleet already operating, palette entries like "draft LKPM reminder for <client>" or "summarize this thread" should enqueue an agent task and post the result into the activity feed. *Acceptance:* ≥3 agent-dispatch actions live; each produces an auditable task record with actor=`agent`, approved by a human before any outbound send. (P1 — this is the highest-leverage differentiator and reuses existing fleet plumbing.)
- **Draft-first inbox (promote "Zantara risolve").** wa-dashboard-m1's shadow view (signals read, diagnosis, next-best-action, draft + human gate — its README's own description) is a beyond-SOTA inbox pattern the commercial tools are only now shipping as "AI copilot." Promote it into the canonical kita inbox as a right-hand pane: every inbound thread arrives with a proposed draft and a one-key approve/edit/discard. *Acceptance:* ≥50% of threads answered via approved drafts within a month; zero unapproved auto-sends (hard gate).
- **Obligations-as-gates, extended to clients.** The INTAKE GateScreen is already a pattern nobody in the sector has. Extend it to the portal: a client with missing documents or an approaching deadline sees their own gate (soft, informative) before their dashboard. *Acceptance:* portal gate renders from the same `/api/intake/gate`-class probe; measured reduction in team chase-messages for documents.
- **Collision presence everywhere.** Generalize the review queue's lease concept into lightweight presence ("Ari is viewing this client") on client and practice detail — Front-class collision detection, but backed by leases that already exist server-side. *Acceptance:* two sessions on the same record see each other within 5s; double-edit incidents traceable to zero.
- **One audit stream (WorkOS-shape) with client-visible slices.** Fuse review audits, impersonation events, agent actions, and admin changes into one immutable actor-action-target stream; expose the client's own slice in the portal ("what Bali Zero did on your case this week"). Legal-ops competitors do not show clients their audit trail — for a trust-selling agency this is a product feature, not plumbing. *Acceptance:* impersonated and agent actions appear in the stream with distinct actor types; portal renders the client slice read-only.

## §Meta-pattern

The lane's disease is the program-wide one: **the artifact built is treated as the thing in force.** The omnichannel inbox was written, so the workspace "has" a unified inbox — but nothing links to it. `admin-dashboard` is maintained, so there "is" an admin panel — but its DNS is gone. `isAuthenticated()` exists, so pages "are" gated — but it reads a localStorage token the real session doesn't use. Five inboxes each answer "do we have an inbox?" and none answers "which one is *the* inbox?" The corrective is connective, not creative: every surface needs a consumer proof (a nav link, a resolving DNS name, a cookie-verified session) before it counts as existing — the UI equivalent of PROVE-LIVE.

## §Solo-operatore

Decisions only Zero can take:

1. **Which inbox is canonical** (business call — it fixes the team's daily workflow and the WA-bot handoff point). Everything in "one inbox ruling" waits on this.
2. **`admin-dashboard`: redeploy or archive.** Redeploying is a small Fly spend and an auth-hardening obligation (it fronts Postgres/Qdrant); archiving is free. Status quo — committing to a dead target — is the only wrong option.
3. **`/dream`'s fate.** It is anonymous-reachable by explicit design on the CRM-serving app and it autosaves to a backend endpoint. If it is Zero's personal thinking tool, ruling needed: gate it, or accept the exposure knowingly.
4. **Portal ambition vs. client volume.** The portal has 29 pages for a client base whose actual login usage is unmeasured here. Before investing further (e.g. client-visible audit), decide whether the portal is a product bet or a service accessory — that ruling sizes P1/P2 above.
5. **Keyboard-first investment.** Worth it only if the team actually lives in kita daily; a week of simple usage telemetry (page views per route per role) should precede the palette-v2 spend.
6. **Risk acceptance on the localStorage gates** until the P0 fix lands: the pages behind them include roles/users/security settings.

## Sources

1. Linear Method — https://linear.app/method
2. Superhuman, "How to build a remarkable command palette" — https://blog.superhuman.com/how-to-build-a-remarkable-command-palette/
3. Intercom, "Announcing Intercom's next-generation Inbox" — https://www.intercom.com/blog/announcing-intercoms-next-gen-inbox/
4. Intercom, "Betting on the future of frontend" — https://www.intercom.com/blog/betting-on-the-future-of-frontend-at-intercom/
5. Attio, "Introducing Attio Objects" — https://attio.com/blog/introducing-attio-objects
6. Attio, "A new vision for CRM" — https://attio.com/blog/ai-and-the-next-generation-of-CRM
7. Clio, "Legal matter management" — https://www.clio.com/blog/legal-matter-management/
8. Nielsen Norman Group, "8 Design Guidelines for Complex Applications" — https://www.nngroup.com/articles/complex-application-design/
9. GitHub Docs, "Managing notifications from your inbox" — https://docs.github.com/en/subscriptions-and-notifications/how-tos/viewing-and-triaging-notifications/managing-notifications-from-your-inbox
10. Retool, "State of Internal Tools" — https://retool.com/blog/state-of-internal-tools-2023
11. Retool, "Admin panel software" — https://retool.com/use-cases/admin-panels
12. WorkOS, "The developer's guide to audit logs / SIEM" — https://workos.com/blog/the-developers-guide-to-audit-logs-siem
13. EnterpriseReady, "Audit log" — https://www.enterpriseready.io/features/audit-log/
14. Multi-channel shared-inbox pattern survey — https://www.dragapp.com/blog/multi-channel-shared-inbox/

## Adversarial review

**Reviewer: `kimi-k3` (Moonshot K3) and `codex` (OpenAI gpt-5.6-sol at xhigh effort), 2026-08-30 — cross-family, generator ≠ grader.** Neither seat wrote any part of this panel. Both read all 18 files of the set in full and were asked the *publication* question rather than a proof-reading one: what in this diff creates real incremental risk beyond what the repository already discloses, whether "it is already public elsewhere" is a sound argument or a rationalisation, whether the sequencing is wrong, and what is simply FALSE. Every concrete file claim either seat made was then re-derived independently with `grep`/`git` before being recorded, and objections that measurement falsified are kept as RETRACTED rather than quietly dropped. The full journal and the complete objection list, with per-objection status, are in this PR's evidence pack (`council-journal.jsonl` and the pack's `dissent` block).

**Limits of this review, stated so it is not read as more than it was.** It happened at PUBLICATION time, not at authoring time: no seat re-derived this lane's technical findings against the codebase, so it is not a correctness review of the analysis. Nine numeric objections across the set were recorded PLAUSIBLE because the fact-checking pass ran out of time, not because they were investigated and cleared — an open list, not an all-clear.

**Finding for this file:** The auth split-brain this lane maps was already cured on `origin/main` by #5181 before publication (verified by ancestry). The page and gate counts it gives were disputed and are unsettled — treat them as unverified.
