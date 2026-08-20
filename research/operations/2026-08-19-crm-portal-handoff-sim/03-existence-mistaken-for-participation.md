---
date: 2026-08-19
domain: compliance
client_case: none
sources:
  - apps/backend-rag/backend/app/routers/team_members.py (disabled router, patched anyway)
  - apps/backend-rag/backend/app/setup/router_manifest.py + router_registration.py
  - apps/backend-rag/backend/app/routers/team.py (the live roster endpoint)
  - apps/backend-rag/backend/app/deps/auth.py + crm_portal_integration.py + portal_invite.py + agentic_rag.py + debug.py
  - apps/backend-rag/backend/app/routers/auth.py (two-layer auto clock-in)
  - apps/backend-rag/backend/app/routers/portal.py (get_current_client, per-request re-check)
  - apps/mouth/src/lib/api/client.ts + contexts/AdminImpersonationContext.tsx
  - .github/workflows/immune-enforcement.yml (merge_group path filter)
  - .github/workflows/tests.yml (Import chain gate, and where the test secrets are actually scoped)
  - .husky/pre-commit (Gate 2, the same check standing in a different CWD)
  - apps/backend-rag/backend/app/utils/__init__.py + core/config.py (the tollbooth and the import-time Settings)
  - infra/home-fork/declared-pairs.json
adversarial_review: codex
---

# Existence mistaken for participation

The mandate was to alternate operator and client across the two surfaces and root-cause each
snag. The snags were found and are recorded in files `00`–`02`. This file records what the
second half of the run found, which is a different and more general disease than the seam
between the two personas — and which bit the investigation itself, three times.

## The meta-pattern

**Something is present, and its presence is mistaken for its participation.**

Every finding below has the same shape. An artifact exists, is visible, reads as done, and is
inert. Nothing reports the gap, because nothing is *broken* — the check that would notice is
the one nobody runs, and the artifact's existence is what everyone checks instead.

| The artifact | Exists | Participates |
|---|---|---|
| The roster fix in `team_members.py` | yes | no — that router is never registered |
| The alert-corpus test added by the probe PR | yes | no — no workflow referenced it |
| The probe script itself, since 20 July | yes | no — undeclared, so no lint could see it |
| A declared-pairs entry, if dropped in a merge | no | — and nothing would say so |
| The build lane dispatched for the roster cure | yes | no — it died with 385 uncommitted lines |
| Auto-merge arming on a PR that hit CONFLICTING | no | — GitHub cleared it silently |
| The `login-healthcheck` probe for ten days | yes | no — 0 successes in 5941 log lines |
| The pre-commit import-chain gate | yes | no — it fails on every backend commit for a reason unrelated to the code |

The repo already names a version of this for daemons: green is not working. The finding here
is that the same disease governs **code, tests, registry entries, agent lanes and merge
arming** — anything whose participation is a separate fact from its existence, and whose
non-participation produces no error.

## The findings

### 1. A cure was merged and does not run

`team_members.py::list_team_members` was patched to exclude service accounts from the CRM
assignment roster. `router_manifest.py` lists that router under disabled routers ("duplicates
team.py /members endpoint") and `router_registration.py` has its import and its `include_router`
commented out — four sites, one pair per process group. The endpoint actually serving
`GET /api/team/members` is `team.py::get_team_members`, which applies no role filter at all.

The general form is worth more than the fix: **before curing a router, verify it is registered.**
A guard added to unreachable code is indistinguishable, at review time, from a guard that works.

### 2. "Not a client" used as a proxy for "is staff"

Five live consumers grant team authority to anything whose role is not the literal string
`client`: the shared `require_team_member` dependency (behind E33 case creation and CRM
intelligence, some of it mutating), `require_team_auth` in the portal integration (eight
endpoints, including messaging real clients), the portal invitation endpoints (which mint
tokens and send live email), the A/B experiment controls, and a conditionally-registered debug
route that is independently safe because it carries its own admin check.

Today a monitoring probe cannot exploit this, for an accidental reason: it holds `role='client'`,
so login refuses it and it has no token at all. **The outage is the protection.** Granting it a
non-client role — the whole point of the arming work — would create a continuously refreshed
machine credential that passes as staff across that surface. This is why the production role
change is held behind the code fix and not the other way round.

### 3. Two of the investigation's own premises were refuted

Recorded because a report that only lists confirmed suspicions is a report that stopped looking.

**Revocation does reach live sessions.** The hypothesis was that `portal_access` is checked only
at sign-in, so a revoked client would keep full access until token expiry. False:
`get_current_client` re-queries `portal_access`, `linked_client_id` and `active` from Postgres on
every request, across 35 path operations in 10 routers. Exposure is bounded by request latency,
not by the one-hour token. A real gap remains, but it is a product gap, not a hole: **no admin
endpoint exists to revoke portal access at all** — the only writes set it true, and turning it
off is a direct-database operation.

**The shared-cookie handover is safe by design, not by luck.** Both hosts share one
`.balizero.com` cookie, so a second login does overwrite it. It does not matter: the token is
also held in `localStorage`, which is per-origin, and the proxy prefers the Authorization header
and actively strips the cookie when the header is present — with a comment saying it exists to
prevent exactly this stale-session leak. The one path that still consults the cookie is a
genuinely new tab with no storage on that origin, and it degrades to a clean redirect to the
right login, with no loop and no broken render.

One asymmetry is traced but unproven: login carries a manual cookie-reconstruction workaround
for a dropped `Set-Cookie` on the hosting platform, and logout does not, though both mutate the
same domain-scoped cookie. Server-side JTI revocation covers the practical risk *if* the
revocation flag is enabled. Not verified; recorded as open.

### 4. A correction that overstated itself

A peer reported that the role change would start clocking the probe in every five minutes,
corrupting attendance data. Measured, it is two layers: the caller's gate still tests
`role != "client"` and does spawn the task, but the callee's **first statement** applies the
cured predicate and returns before any write. The probe gets no attendance row. The real cost is
roughly 288 pointless spawns a day.

The defect is real and the consequence was not. This is the sharper hazard: **a correction is
read with more trust than the thing it corrects**, so an overstated correction propagates
further than the original error. The fix ships described as what it is — removal of a stale
caller-side test that duplicates, less correctly, the guard the callee already applies.

### 5. Every merge-queue entry pays a network call that PR CI never makes

The immune-enforcement workflow derives its path filter from `github.event.pull_request.base.sha`
and `.head.sha`. On a `merge_group` event those fields do not exist, both read empty, and the
sentinel falls into its "no PR context — full battery" branch, written for a different case. So
every queue entry runs the complete battery including a live `apt-get`, for any PR, regardless of
what it changed. With a degraded package mirror this became a low-rate failure source visible
only in the queue: five unrelated PRs failed on merge-group refs in one window, interleaved with
dozens of successes.

The antidote worked and should not be "fixed": the install wrapper failed in about 120 seconds
**naming its own cause in the log**, which is why the diagnosis was possible at all. What is open
is a design decision — give `merge_group` its own base and head, or keep the full battery in the
queue as a deliberate safety margin. Recorded as a decision, not a defect.

### 6. One property, three checks, three environments — and only one of them tells the truth

The cure for finding 2 added a single import to `app/deps/auth.py`, and turned the most-imported
module in the backend into one that cannot be imported without production secrets. The first
reading — "my change broke a check" — is the one that stops the investigation. It is wrong in the
direction that matters: **the trap was already armed on `main` before my change, so my change did
not create it — and `git log --follow` now dates it.** The eager import entered this file on
**2026-02-07** (`deb4e6eaa`), survived a ruff sweep on 2026-05-19 (`f0ef81354`) untouched, and was
cured on **2026-08-19** by `3ff7b6fa6` (#4363) — the narrow cure this file recommends. So it stood
eager for roughly six and a half months. This paragraph has now been corrected twice in one day and
both corrections are worth keeping visible: the first draft asserted "had been the whole time" with
only a single `origin/main` snapshot behind it, which did not support it; the second draft
over-corrected, saying such a history "was not done" — as though it could not be. It could, it took
one command, and it confirms the original claim. **A retreat to "unprovable" is itself a claim, and
it was the wrong one.**
Measured against `origin/main` as it stood at investigation time, not a checkout:
`utils/__init__.py:17` carried the eager import, and **178 files** import a leaf of that package, so
each of them executed the tollbooth. **Read that in the past tense: as of `3ff7b6fa6` the line is
gone** — the heavy re-export now sits behind `TYPE_CHECKING` — so a reader checking the file today
will not find what this sentence describes. It is left standing, pinned, because the finding is
about the six months in which it was true.
(How many of those would require secrets anyway for unrelated reasons is not measured — but the
import-chain gate proves at least one did not.) What my change did was walk `dependencies.py`,
the one module the gate actually watches, into a room everyone else was already standing in.

The mechanism is not the import. It is the package. Importing *any* leaf under
`backend/app/utils/` first executes that package's `__init__.py`, which eagerly re-exports
`internal_api_auth` → `api_key_auth` → `core.config`, and `core/config.py` instantiates
`settings = Settings()` at module scope. Measured with a stripped environment: all five
submodules **and** the bare package exit 1; the same leaf imported from outside the package
exits 0 and prints its frozenset. **On a normal first import, a package `__init__` is a tollbooth
the submodule pays** — the scope matters and an earlier draft stated it as a universal law: an
already-initialised package sits in `sys.modules` and is not re-executed, and unusual loaders or
execution modes can change this. Under ordinary import of a cold package, which is what CI and the
pre-commit hook both do, it holds —
so the docstring that leaf carried, *"this module imports nothing, so it cannot participate in an
import cycle"*, states a property a module cannot have on its own. Its package decides. That is
the same defect as the migration-236 comment in file `02`: a comment promising a guarantee the
code does not deliver, of the kind someone reads while deciding whether they are safe.

The reason it survived review is the second layer. `Settings` declares
`env_file=".env"`, resolved **relative to the process CWD**, and `apps/backend-rag/.env` exists on
a developer machine. The same property is therefore asserted in three places that do not agree:

| Where | CWD | Secrets in env | Verdict on the same code |
|---|---|---|---|
| CI `Import chain gate` (`tests.yml:540`) | `apps/backend-rag` | no — the `env:` blocks carrying `JWT_SECRET_KEY` belong to *later* steps | red |
| `pre-commit` Gate 2 (`.husky/pre-commit:414`) | repo root | no | red, on every backend commit |
| a developer running it by hand | `apps/backend-rag` | supplied by the `.env` on disk | green |

"It passes locally" measured the presence of a dotfile, not the property.

An independent session hit the same symptom the same day at the hook layer and proposed two
cures: export the published dummy test values inside the hook, or `cd apps/backend-rag` before the
check. **Both blind the gate**, in opposite directions. Injecting the values makes the hook more
permissive than CI — the gate that fires first becomes blinder than the gate that fires last,
which is the worst arrangement available. Changing the CWD makes it pass *because a dotfile exists
on that machine*, which is precisely the mask described above. Neither is wrong about the symptom;
both would have made today's genuine defect permanently invisible at commit time.

Curing the tollbooth instead — the package must not require production secrets to import — makes
all three honest at once and requires no change to the hook. That is not a prediction: the hook's
own command, run verbatim from the repo root with a stripped environment, answers `IMPORT OK` on
the cured branch and still fails on `main`. The general form: **when a check starts failing, ask
whether the environment it stands in is the one that answers the question.** A check moved into a
friendlier environment stops being a check.

And the reason a gate watching one entry point could sit on top of a 178-file trap for months is
the same disease this file is named after. The gate exists, runs, and is green — on the single
import path that happened not to cross the tollbooth. Its coverage was never a property anyone
measured; it was inferred from the fact that it was passing.

**The correction this finding needed, and did not get until it was asked for.** Everything above
frames `backend/app/utils/` as *the* tollbooth. It is one of forty-five. A stripped-environment
probe of all 173 non-empty `__init__.py` files under `backend/` classifies **53 as tollbooths**,
of which **45 are independent entry points** and 8 are cascades that curing a parent already fixes.
There is exactly **one** `Settings()` instantiation at module scope — `app/core/config.py:1240`,
pulled unconditionally by `app/core/__init__.py:6` — and **all 45 chains terminate at those two
lines**. `backend.app.core` is not arguably the root; it is the only root, and its own blast radius
(238 files) is larger than `utils`'s.

*(Precisely: three `Settings()` expressions exist under `apps/backend-rag/`, but the other two —
`tests/services/test_admin_emails_config.py:62` and `scripts/health_check.py:235` — sit inside
function bodies and fire only when called. Only the module-scope one executes merely because
something imported a package, which is the whole mechanism here. An earlier draft said "exactly one
in the codebase", which is literally false and needed the narrower word.)*

Union across all entries: **1,293 of 3,055 files under
`backend/` (42%)** cannot be imported without production secrets. The cure in flight moves 179 of
them, leaving 1,114 — a **14% reduction in affected files, and no change at all to the failure
mode**: any of the remaining forty-four carriers produces the identical symptom the day something
imports through it. That distinction is the whole point, and an earlier draft of this paragraph got
it wrong by writing that the cure "does not reduce the risk" — it does reduce the count, measurably,
and saying otherwise contradicted the arithmetic two sentences above it. What it does not do is
close the class, which is the exact shape of the wrapper scar this repo already carries.

*(Method, so the counts are checkable rather than assertable: the 53/45 split comes from importing
each of the 173 non-empty `__init__.py` under `backend/` in a subprocess with a stripped environment
and recording exit status; "independent" means the package still fails when every ancestor package
is excluded, "cascade" means curing a parent already fixes it. "All 45 chains terminate at those two
lines" is a claim about the shared configuration point every failing chain passes through — it is
not a claim that each chain fails for no other reason as well.)*

**And the counter-argument — which an external reviewer showed I had overstated.** An
eagerly-instantiated settings singleton is a deliberate fail-fast: a missing secret crashes the
process at import, not at the first request that needs it. Deferring it trades that away. An earlier
draft of this paragraph then jumped straight from there to "so 'fix all 45' is the wrong
conclusion", and the Codex review named that a false dichotomy — correctly. **Fail-fast at process
start and utility packages that import settings are not the same property**, and keeping the first
does not require keeping the second: a deliberate `Settings()` construction in the app's startup
path preserves the crash-early guarantee exactly, while unrelated packages stop dragging it in as a
side effect of an import. That third road is narrower than a 45-file sweep and gives up nothing, and
by omitting it I made the broad cure look riskier than my own analysis supports.

So the honest disposition is: **ship the narrow cure, and route the root as an architectural
decision with the numbers attached** — but route it as a real decision between *three* options, not
as a choice between "leave it" and "sweep 45 files". What must not happen is the fourth option,
which is to ship the narrow cure and let the measurement stand as if the class were closed.

## Where the investigation was wrong about itself

Three measurement failures, all mine, all the same disease one level up.

- **A probe that died and was read as an answer.** `ls -d .worktrees/*a* .worktrees/*b*` under zsh
  aborts the entire command when *either* glob fails to match. The second pattern failed, the
  first — which matched — was never printed, and "no matches found" was read as proof that a lane
  had produced nothing. It had produced 385 lines. Work was re-dispatched that already existed.
- **An alarming reading of a transient state.** A worktree showed a staged changeset that looked
  like a stranger's work in flight; a minute later it was clean. It was a peer's `git merge`
  aborting on instruction. Stopping to look was right; the inference was not.
- **Saturation diagnosed without measuring.** An agent spawn failed with a fork error and the
  first hypothesis was machine saturation. Measured: 1138 processes against a limit of 8000,
  15 pseudo-terminals against 511, allocation succeeding. The failure was narrower than the story.
- **A cure that broke the thing it was cured into.** The gate fix in finding 2 was written, tested
  and reviewed while the local environment silently supplied the secrets its new import chain had
  begun to require. The defect was invisible until a required check that stands somewhere else
  refused it — and the first instinct on reading that red was to look for a broken test.

## Adversarial review

Findings 1, 2 and 4 were produced by one session and challenged by another on fresh context;
finding 4 survived as a defect but had its consequence overturned, and two of the challenger's own
five points corrected the challenger's brief in turn. Finding 3 refutes premises this
investigation itself had asserted earlier in the run.

**Declared weakness:** the challenging sessions are the same model family as the sessions that
produced the findings. Same-family agreement measures fidelity, not truth. The cluster in file
`02` was re-refuted cross-family; the findings in this file were not, and are stated at that
strength. The three self-corrections above are evidence the review had teeth, not evidence that
cross-family review was unnecessary.

## Adversarial review

Seat: **Codex `gpt-5.6-terra`** (OpenAI family, effort medium, read-only sandbox). It was pointed
specifically at the *correction* sentences in this file, not only at the original claims — a
correction reads as the safe part of a document and therefore gets less scrutiny, which is the
mechanism behind this repo's W113. Eleven objections. Four produced edits above; the rest are
recorded here.

**Acted on, in the text above:**

1. The arithmetic contradiction: "86% of the condition survives" alongside "does not reduce the
   risk". 1,293 − 179 = 1,114, i.e. a measured 14% reduction. The paragraph now says what does and
   does not change, and names the earlier wording as wrong.
2. "*had been the whole time*" — inspection at one commit cannot establish continuity. Narrowed to
   what was measured.
3. "*A package `__init__` is a tollbooth every submodule pays*" — stated as a universal law. Now
   scoped to a normal first import of a cold package (`sys.modules` caching and unusual loaders
   change it).
4. The counter-argument paragraph was a **false dichotomy** — keeping fail-fast at startup does not
   require utility packages to import settings. This was the most consequential objection: it
   changes the recommendation, and the corresponding PENDING-ARMS ledger line was amended the same
   day for the same reason.

**Recorded, standing, not edited:**

5. "*Five live consumers*" — "live" would need proof of router registration and production mounting;
   the set mixes static consumers with a conditional debug route.
6. The chain from "grant a non-client role" to "a machine credential that passes as staff" is
   untested end to end; other account-status, audience or scope checks could intervene.
7. "*on every request, across 35 path operations*" — the dependency's code shows the re-query; the
   count has no reproducible method attached.
8. "*The shared-cookie handover is safe by design, not by luck*" — header precedence and per-origin
   `localStorage` are code properties. "No loop and no broken render" is a browser claim and needs a
   browser.
9. The 53/45 split and "all 45 chains terminate" now carry a method note, but the reviewer's
   sharper point stands: "terminate" describes the shared configuration point every failing chain
   passes through, not proof that no chain fails for an additional reason.
10. "*The probe gets no attendance row*" — the callee's guard supports it; a deployed version could
    differ, and "roughly 288" assumes a perfect scheduler.
11. "*1138 processes against a limit of 8000 … the failure was narrower than the story*" — those
    three values rule out some saturation modes, not per-user limits, memory, FDs or cgroups. It
    corrects the earlier hypothesis without identifying the cause.

### Third seat: findings 1-3, independently re-derived

**Kimi K3**, fresh context, instructed to assume every claim wrong until re-derived from the live
files and the git history rather than from this file's own text.

| Finding | Verdict | Evidence it produced |
|---|---|---|
| 1 — the merged cure that does not run | CONFIRMED | walked the commit history itself: `148006575` (#4353) patched `team_members.py` in place; `3ff7b6fa6` (#4363) later deleted that file and moved the fix into `team.py` |
| 2 — "not a client" as a staff proxy | CONFIRMED | grepped all four call sites at `3ff7b6fa6^`: all four carried the literal `role == "client"` test; on current `main` all four route through `is_human_team_member` |
| 3 — `merge_group` falls into the full-battery branch | CONFIRMED | read `immune-enforcement.yml` directly; `pull_request.base.sha`/`.head.sha` are unset on that event and both resolve empty, and the branch's own comment shows it was written for `workflow_dispatch` |

Three of three, from a different family, by walking the history rather than re-reading this file —
which is the distinction that makes it worth recording. Finding 4's result is above: confirmed as a
statement about the six months it described, refuted as a statement about today.
