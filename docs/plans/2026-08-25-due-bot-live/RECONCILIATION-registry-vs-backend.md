# Reconciliation — the frozen tool registry against the backend it must call

B9 wired the FIRST of the ten frozen tools and found a contract mismatch. That prompted a
reconciliation of all ten. **Zero of the ten MATCH.** Eight SHAPE_DRIFT, one WRONG_QUESTION,
one ABSENT. Every verdict below was verified by reading the cited file:line, twice — once by
the recon lane, and the load-bearing ones again by the orchestrator.

## Why this was predictable in hindsight

F5 froze the registry "verbatim" from the research capture (Qwen §4). That capture designed a
tool surface a *model* would find natural — clean prefixed IDs, tidy status enums, one
mutation per tool. It was never checked against this backend's actual routes. The freeze is
sound as a *contract for the bot*; it was simply never a description of the CRM.

## The three cross-cutting mismatches

1. **The ID vocabulary does not exist.** The registry declares `CL-[0-9]{4,10}`,
   `PR-[0-9]{4,10}`, `USR-[0-9]{3,8}` (`registry/envelope.py:45-49`). Every backend table
   uses plain integer PKs (`client_id: int`, `practice_id: int`). No route accepts or returns
   a prefixed ID anywhere.
2. **The status enum shares ZERO values with the live one.** Registry: `draft,
   doc_collection, ready_to_submit, submitted, in_review, approved, rejected, archived`.
   Live and enforced (`crm_practices.py:233-240`): `inquiry, waiting_documents,
   sending_invoice, on_process, completed, cancelled`. `PracticeType` likewise has zero
   overlap; `DocumentType` is a free-text column on the backend, not an enum at all.
3. **`create_reminder` has no backing surface at all** — no `reminders` table, model or route
   exists in the backend.

## The finding that matters more than any of them

**F7's stated authorization boundary does not exist for three of the four mutation paths.**

F7 reads: *"CRM routes independently enforce `assigned_to`; endpoint authorization is the
boundary; the local authorizer is early-deny only."* Measured:

| mutation tool | backing route | enforces scope? |
|---|---|---|
| `update_practice_status` | `crm_practices.py:1067` `update_practice` | **YES** — admin OR `created_by`/`assigned_to`, else 403, plus a state-machine transition check |
| `mark_document_received` | `:2289` `update_required_document` / `:1666` `add_document_to_practice` | **NO** — neither has any ownership gate |
| `open_practice` | `:388` `create_practice` | **NO** — zero authorization helpers in its whole body |
| `create_reminder` | — | route does not exist |

`create_practice` was re-verified directly: `get_current_user` (authentication) is present,
and `is_crm_admin` / `get_crm_user_filter` / `verify_client_access` /
`get_practices_user_filter` appear **zero** times across its ~250 lines. Any authenticated
user can open a practice against any client and assign it to anyone.

This is live today and has nothing to do with the bot. It is lower severity than it sounds —
every authenticated user is Bali Zero staff — but it is exactly the `assigned_to` scoping the
rest of the CRM does enforce, silently absent here.

## Orchestrator ruling

**1. The registry moves toward the backend, not the reverse.** The backend is live, carries
real client data, and its vocabulary is enforced by a state machine and referenced by
migrations. The registry is a frozen sketch. Where they disagree on IDs, status values,
practice types or document types, the backend wins and the registry is amended. This does NOT
reopen F5's *design principles* — enums over free text, IDs over names, one mutation per tool,
`additionalProperties:false` — which stand and are the reason the mismatch was findable at all.

**2. Mutation tools do not arm until their endpoint enforces scope.** The local early-deny
must NOT be promoted to the boundary to close this gap. That would put the security control
in the layer F7 explicitly says is not authoritative, in a process the CRM does not trust, and
it would be defeated by any other caller of the same route. Either the endpoint gains the
check, or the tool stays dark. `update_practice_status` is the only R3 whose premise currently
holds.

**3. `create_reminder` leaves v1 unless a surface is built for it.** A tool with no backing
route is not a tool. This is a scope call, recorded so it is not silently discovered by
whoever wires R1.

**4. The PII shape is a reuse signal, not a new problem.** The client routes return
`passport_number`, `npwp`, `tax_id`, `date_of_birth` in cleartext.
`services/rag/agentic/team_crm_tools.py` already solves this for the same audience: it returns
`client_name`/`practice_type`/`status`/dates only and self-gates server-side. `get_practice`
also carries a working non-owner PII scrub (`PRACTICE_CLIENT_CONTACT_FIELDS`,
`crm_practices.py:1052-1058`). Reuse those two patterns; do not invent a third.

## What this does not change

Everything ships dark, the switchboard stays the owner's, and no lane may park work behind
this document. The executor seam B9 built is unaffected — it was built against the frozen
contract deliberately, which is exactly why the mismatch surfaced as a report instead of as a
silently-rewritten schema.

## Addendum — what "the registry moves toward the backend" actually costs, and when

The ruling above is unchanged. Two things it did not weigh, recorded before anyone acts on it:

**1. It invalidates measured evidence — but less than it first appears.** `registry/tools.py`'s
own docstring says it "stays byte-compatible with that measured evidence rather than silently
disconnecting from it", referring to lane B4's golden-suite evaluations. Those were run against
**Qwen3-14B**, the local model — which Directive #1 §1.1 has since demoted to the *third lane of
degradation*, R0 tools only, with `qwen3.7-plus` via TP1 as the primary brain. So amending the
registry does not disconnect the shipping brain from its evidence; it disconnects a fallback
from its evidence.

That is still a real cost, not zero: the local read-only lane genuinely uses those tools, and
after an amendment its goldens no longer describe what ships. **The price is re-running the
golden suite against the amended shape, on the brain that is actually primary.** Payable, and
it must be paid in the same lane that amends the registry — not deferred, or the registry ends
up describing something nobody measured.

**2. It must come AFTER the endpoint scope work, not in parallel.** The mutation routes are
being brought up to enforce `assigned_to` (lane `crm-mutation-scope`). If the registry is
migrated toward today's endpoint shapes while those shapes are still changing, it migrates
toward an intermediate state and has to move twice. Order: endpoints settle → registry migrates
to the settled shape → goldens re-run against it.
