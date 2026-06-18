# WhatsApp Corpus Registry

Local-only utilities for the 2026-05-26 WhatsApp corpus archive.

## Privacy Contract

- Do not call cloud LLMs.
- Do not output raw message text.
- Do not output message snippets.
- Do not output phone numbers.
- Do not output raw source paths in shareable reports.
- Use `file_id` and `path_hash` for per-file references.

## Build Registry

Run from repo root with the repo virtualenv active:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_registry \
  --root "$HOME/Desktop/wa-chats-MASTER-2026-05-26" \
  --output-dir research/personal/wa-corpus/registry \
  --target-total 105530
```

Outputs:

- `research/personal/wa-corpus/registry/registry.sqlite`
- `research/personal/wa-corpus/registry/registry_summary.md`

The SQLite registry stores metadata only: source bucket, hashed ZIP source tag,
parser type, file hash, path hash, line count, message-start count, timestamp
min/max, and parser warning codes. It intentionally avoids raw message bodies
and raw paths.

The registry keeps two export counts:

- `message_start_count`: baseline count that preserves the original 105k brief
  rule.
- `normalized_message_start_count`: diagnostic count that also accepts invisible
  Unicode-prefixed WhatsApp timestamp lines.

## Classify Chats

Run the privacy gate classifier after the registry exists:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.classify_chats \
  --registry-db research/personal/wa-corpus/registry/registry.sqlite \
  --output-dir research/personal/wa-corpus/classification
```

Outputs:

- `research/personal/wa-corpus/classification/chat_classification.sqlite`
- `research/personal/wa-corpus/classification/classification_summary.md`

The classifier is deterministic and metadata-only. It does not inspect message
bodies. It uses source buckets, hashed ZIP source tags, message counts, parser
warnings, and normalized count deltas to assign each file to a conservative
processing gate:

- `deny_content_mining_until_owner_allowlist`
- `local_only_team_analysis_after_owner_approval`
- `manual_review_before_content_mining`
- `manual_review_before_any_use`

All categories are pre-flight safety labels. They are not semantic claims about
the conversation contents.

## Resolve Review References Locally

Shareable reports intentionally expose only `file_id`, `path_hash`, and hashed
`source_tag`. To review a file on the Pro, resolve a specific reference in the
terminal:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.resolve_refs \
  --root "$HOME/Desktop/wa-chats-MASTER-2026-05-26" \
  --file-id wa-file-0421
```

This command prints raw local paths, so do not redirect its output into tracked
repo files.

## Build Owner Review Manifest

Generate a private manifest for owner decisions before any content mining:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_review_manifest \
  --root "$HOME/Desktop/wa-chats-MASTER-2026-05-26" \
  --classification-db research/personal/wa-corpus/classification/chat_classification.sqlite \
  --output-dir research/personal/wa-corpus/review \
  --limit 80
```

Outputs:

- `research/personal/wa-corpus/review/review_manifest.local.tsv`
- `research/personal/wa-corpus/review/review_manifest_summary.md`

The `.local.tsv` file contains raw local paths and is ignored by git. Use its
blank `owner_decision` column to create the next allowlist/denylist:

- `allow_team_local`
- `allow_business_local`
- `deny_personal`
- `deny_sensitive`
- `unknown_hold`

## Compile Allow/Deny/Hold Decisions

Compile the private review manifest into local-only lists:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.compile_review_decisions \
  --review-manifest research/personal/wa-corpus/review/review_manifest.local.tsv \
  --output-dir research/personal/wa-corpus/decisions \
  --apply-safe-defaults
```

Outputs:

- `research/personal/wa-corpus/decisions/review_decisions.local.tsv`
- `research/personal/wa-corpus/decisions/content_allowlist.local.jsonl`
- `research/personal/wa-corpus/decisions/content_denylist.local.jsonl`
- `research/personal/wa-corpus/decisions/content_holdlist.local.jsonl`
- `research/personal/wa-corpus/decisions/review_decisions_summary.md`

Only `content_allowlist.local.jsonl` may feed the next local parser/indexer.
Never parse files from the denylist or holdlist.

## Parse Allowed Messages

Parse only the allowlist into an ignored local SQLite database:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.parse_allowed_messages \
  --allowlist research/personal/wa-corpus/decisions/content_allowlist.local.jsonl \
  --output-dir research/personal/wa-corpus/analysis
```

Outputs:

- `research/personal/wa-corpus/analysis/allowed_messages.local.sqlite`
- `research/personal/wa-corpus/analysis/allowed_messages_summary.md`

The SQLite file stores raw parsed message text and raw sender labels. It is
ignored by git and must stay on the Pro.

## Review Case Windows and Compile Local Actions

After domain events and case windows exist, build the owner review workbook for
the top operational windows:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_case_window_manual_review
```

Outputs:

- `research/personal/wa-corpus/review/case_window_review_workbook.local.tsv`
- `research/personal/wa-corpus/review/case_window_context.local.tsv`
- `research/personal/wa-corpus/review/case_window_manual_review_summary.md`

The workbook and context TSV are local-only and ignored by git. The context TSV
contains redacted previews for owner review; the tracked summary contains only
aggregate counts.

After setting `owner_decision=approve` on selected workbook rows, compile only
approved rows into a local CRM/ops queue:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.compile_case_window_actions
```

Outputs:

- `research/personal/wa-corpus/actions/case_window_actions.local.tsv`
- `research/personal/wa-corpus/actions/case_window_actions_summary.md`

Rows left blank, held, denied, duplicated, or marked `no_action` do not become
actions.

## Build Client Captain Academy

Build local-only training and replay examples for Zantara Client Captain from
the anonymous case-window artifact:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_client_captain_academy \
  --case-windows-db research/personal/wa-corpus/analysis/allowed_case_windows.local.sqlite \
  --output-dir research/personal/wa-corpus/client-captain \
  --summary research/personal/wa-corpus/client-captain/client_captain_academy_summary.md \
  --json
```

Outputs:

- `research/personal/wa-corpus/client-captain/client_captain_academy.local.sqlite`
- `research/personal/wa-corpus/client-captain/training_examples.local.jsonl`
- `research/personal/wa-corpus/client-captain/client_captain_academy_summary.md`

The `.local.sqlite` and `.local.jsonl` files are ignored by git and must stay on
the Pro. The summary is aggregate-only. The Captain is always the case owner;
team names in local examples are specialist lanes, not ownership assignment.
This builder does not read raw message bodies, does not send WhatsApp messages,
does not mutate CRM records, and does not call cloud LLMs.

## Build Client Captain Shadow Mode

Build deterministic local-only Shadow Mode diagnoses and draft intents from the
Client Captain Academy replay artifact:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_client_captain_shadow \
  --academy-db research/personal/wa-corpus/client-captain/client_captain_academy.local.sqlite \
  --output-dir research/personal/wa-corpus/client-captain-shadow \
  --summary research/personal/wa-corpus/client-captain-shadow/client_captain_shadow_summary.md \
  --json
```

Outputs:

- `research/personal/wa-corpus/client-captain-shadow/client_captain_shadow.local.sqlite`
- `research/personal/wa-corpus/client-captain-shadow/client_captain_shadow_summary.md`

Shadow Mode can diagnose, draft intent, coach the operator, and require human
approval. It cannot send WhatsApp messages and cannot mutate CRM records. The
summary is aggregate-only; the `.local.sqlite` artifact stays local on the Pro.
Each draft also writes five deterministic depth layers:

1. signal readout
2. case diagnosis
3. captain decision
4. draft gate
5. operator coaching

Every layer preserves the same runtime contract: `send_whatsapp=false`,
`crm_mutation=false`, and `requires_human_approval=true`.

## Build Case Memory Cards

Build compact local case memory cards from Client Captain Shadow drafts:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_case_memory_cards \
  --client-shadow-db research/personal/wa-corpus/client-captain-shadow/client_captain_shadow.local.sqlite \
  --output-dir research/personal/wa-corpus/case-memory-cards \
  --summary research/personal/wa-corpus/case-memory-cards/case_memory_cards_summary.md \
  --json
```

Outputs:

- `research/personal/wa-corpus/case-memory-cards/case_memory_cards.local.sqlite`
- `research/personal/wa-corpus/case-memory-cards/case_memory_cards_summary.md`

Each card is a compact local memory object for one shadow case: status, risk,
next best action, assigned lane, latest movement, blocker code, and review rank.
The builder reads only Client Captain Shadow outputs, not raw message text. It
cannot send WhatsApp messages, cannot mutate CRM records, and keeps human
approval mandatory.

## Build Next Best Action Rankings

Build top-three local next best actions from Case Memory Cards:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_next_best_action_ranker \
  --case-memory-db research/personal/wa-corpus/case-memory-cards/case_memory_cards.local.sqlite \
  --output-dir research/personal/wa-corpus/next-best-actions \
  --summary research/personal/wa-corpus/next-best-actions/next_best_actions_summary.md \
  --json
```

Outputs:

- `research/personal/wa-corpus/next-best-actions/next_best_actions.local.sqlite`
- `research/personal/wa-corpus/next-best-actions/next_best_actions_summary.md`

For every case card, the ranker writes three ordered actions with urgency score,
impact score, combined score, reason code, and assigned lane. The ranker is
deterministic and local-only: it does not read raw WhatsApp text, does not call a
cloud LLM, does not send WhatsApp messages, and does not mutate CRM records.

## Build Operator Action Inbox

Build one local operator review item per case from the top-ranked next best
action:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_operator_action_inbox \
  --next-best-actions-db research/personal/wa-corpus/next-best-actions/next_best_actions.local.sqlite \
  --output-dir research/personal/wa-corpus/operator-action-inbox \
  --summary research/personal/wa-corpus/operator-action-inbox/operator_action_inbox_summary.md \
  --json
```

Outputs:

- `research/personal/wa-corpus/operator-action-inbox/operator_action_inbox.local.sqlite`
- `research/personal/wa-corpus/operator-action-inbox/operator_action_inbox_summary.md`

The inbox selects the top-ranked action per case and turns it into a review
queue with priority label, queue bucket, assigned lane, reason code, scores, and
operator instruction. It is deterministic and local-only: it does not read raw
WhatsApp text, does not call a cloud LLM, does not send WhatsApp messages, and
does not mutate CRM records.

## Build Operator SLA Clock

Build one local SLA clock per operator inbox item:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_operator_sla_clock \
  --operator-inbox-db research/personal/wa-corpus/operator-action-inbox/operator_action_inbox.local.sqlite \
  --output-dir research/personal/wa-corpus/operator-sla-clock \
  --summary research/personal/wa-corpus/operator-sla-clock/operator_sla_clock_summary.md \
  --json
```

Outputs:

- `research/personal/wa-corpus/operator-sla-clock/operator_sla_clock.local.sqlite`
- `research/personal/wa-corpus/operator-sla-clock/operator_sla_clock_summary.md`

The SLA Clock turns each inbox item into a deadline, aging counter, due status,
breach risk, and escalation label. It is deterministic and local-only: it does
not read raw WhatsApp text, does not call a cloud LLM, does not send WhatsApp
messages, and does not mutate CRM records. Human approval remains mandatory for
every clock.

## Build Breach War Room

Build the local owner/lane war room from urgent SLA clocks:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_breach_war_room \
  --operator-sla-clock-db research/personal/wa-corpus/operator-sla-clock/operator_sla_clock.local.sqlite \
  --output-dir research/personal/wa-corpus/breach-war-room \
  --summary research/personal/wa-corpus/breach-war-room/breach_war_room_summary.md \
  --json
```

Outputs:

- `research/personal/wa-corpus/breach-war-room/breach_war_room.local.sqlite`
- `research/personal/wa-corpus/breach-war-room/breach_war_room_summary.md`

The Breach War Room filters SLA clocks into the owner/lane hot queue. Breached
or overdue clocks become `critical` owner review items; high-risk clocks become
`hot` lane review items. It is deterministic and local-only: it does not read
raw WhatsApp text, does not call a cloud LLM, does not send WhatsApp messages,
and does not mutate CRM records. Human approval remains mandatory for every
war-room item.

## Build Case Timeline Synthesizer

Build local operational timelines from case memory, operator inbox, SLA clock,
and breach war room artifacts:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_case_timeline_synthesizer \
  --case-memory-db research/personal/wa-corpus/case-memory-cards/case_memory_cards.local.sqlite \
  --operator-inbox-db research/personal/wa-corpus/operator-action-inbox/operator_action_inbox.local.sqlite \
  --operator-sla-clock-db research/personal/wa-corpus/operator-sla-clock/operator_sla_clock.local.sqlite \
  --breach-war-room-db research/personal/wa-corpus/breach-war-room/breach_war_room.local.sqlite \
  --output-dir research/personal/wa-corpus/case-timelines \
  --summary research/personal/wa-corpus/case-timelines/case_timelines_summary.md \
  --json
```

Outputs:

- `research/personal/wa-corpus/case-timelines/case_timelines.local.sqlite`
- `research/personal/wa-corpus/case-timelines/case_timelines_summary.md`

The Case Timeline Synthesizer composes one operational timeline per case using
existing local artifacts only. Each timeline can include case memory, operator
action, SLA clock, and war-room events. It is deterministic and local-only: it
does not parse raw WhatsApp text, does not call a cloud LLM, does not send
WhatsApp messages, and does not mutate CRM records. Human approval remains
mandatory for every timeline row and event.

## Build Evidence Gap Detector

Build closure blockers from the local case timeline artifact:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_evidence_gap_detector \
  --case-timelines-db research/personal/wa-corpus/case-timelines/case_timelines.local.sqlite \
  --output-dir research/personal/wa-corpus/evidence-gaps \
  --summary research/personal/wa-corpus/evidence-gaps/evidence_gaps_summary.md \
  --json
```

Outputs:

- `research/personal/wa-corpus/evidence-gaps/evidence_gaps.local.sqlite`
- `research/personal/wa-corpus/evidence-gaps/evidence_gaps_summary.md`

The Evidence Gap Detector converts each local case timeline into an explicit
closure blocker: client response confirmation, document evidence, immigration
status proof, payment reconciliation, or lane review. It is deterministic and
local-only: it does not parse raw WhatsApp text, does not call a cloud LLM, does
not send WhatsApp messages, and does not mutate CRM records. Human approval
remains mandatory for every evidence gap.

## Build Case Closure Judge

Build case-level closure judgments from the local evidence gap artifact:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_case_closure_judge \
  --evidence-gaps-db research/personal/wa-corpus/evidence-gaps/evidence_gaps.local.sqlite \
  --output-dir research/personal/wa-corpus/case-closure-judge \
  --summary research/personal/wa-corpus/case-closure-judge/case_closure_judge_summary.md \
  --json
```

Outputs:

- `research/personal/wa-corpus/case-closure-judge/case_closure_judge.local.sqlite`
- `research/personal/wa-corpus/case-closure-judge/case_closure_judge_summary.md`

The Case Closure Judge turns evidence gaps into one closure decision per case:
owner review blocked, evidence upload blocked, lane review blocked, or ready to
close when no closure blockers remain. It is deterministic and local-only: it
does not parse raw WhatsApp text, does not call a cloud LLM, does not send
WhatsApp messages, and does not mutate CRM records. Human approval remains
mandatory for every closure judgment.

## Build Owner Approval Console

Build owner-only approval items from the local case closure artifact:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_owner_approval_console \
  --case-closure-db research/personal/wa-corpus/case-closure-judge/case_closure_judge.local.sqlite \
  --output-dir research/personal/wa-corpus/owner-approval-console \
  --summary research/personal/wa-corpus/owner-approval-console/owner_approval_console_summary.md \
  --json
```

Outputs:

- `research/personal/wa-corpus/owner-approval-console/owner_approval_console.local.sqlite`
- `research/personal/wa-corpus/owner-approval-console/owner_approval_console_summary.md`

The Owner Approval Console filters closure judgments down to the decisions that
need owner review now: client recovery follow-up, immigration status escalation,
document evidence request, payment reconciliation, or owner case review. It is
deterministic and local-only: it does not parse raw WhatsApp text, does not call
a cloud LLM, does not send WhatsApp messages, and does not mutate CRM records.
Owner approval remains mandatory before every client-facing message or
operational mutation.

## Build Owner Decision Packs

Build readable owner decision packets from the local owner approval artifact:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_owner_decision_packs \
  --owner-approval-db research/personal/wa-corpus/owner-approval-console/owner_approval_console.local.sqlite \
  --output-dir research/personal/wa-corpus/owner-decision-packs \
  --summary research/personal/wa-corpus/owner-decision-packs/owner_decision_packs_summary.md \
  --json
```

Outputs:

- `research/personal/wa-corpus/owner-decision-packs/owner_decision_packs.local.sqlite`
- `research/personal/wa-corpus/owner-decision-packs/owner_decision_packs_summary.md`

The Owner Decision Pack turns each owner approval row into a compact local-only
packet with the decision type, risk brief, recommended decision, and draft
action type. It is deterministic and local-only: it does not parse raw WhatsApp
text, does not call a cloud LLM, does not send WhatsApp messages, and does not
mutate CRM records. Owner approval remains mandatory before every client-facing
message or operational mutation.

## Build Owner Brief Renderer

Build readable owner briefs from the local owner decision pack artifact:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_owner_brief_renderer \
  --owner-packs-db research/personal/wa-corpus/owner-decision-packs/owner_decision_packs.local.sqlite \
  --output-dir research/personal/wa-corpus/owner-brief-renderer \
  --summary research/personal/wa-corpus/owner-brief-renderer/owner_brief_renderer_summary.md \
  --json
```

Outputs:

- `research/personal/wa-corpus/owner-brief-renderer/owner_brief_renderer.local.sqlite`
- `research/personal/wa-corpus/owner-brief-renderer/owner_brief_renderer_summary.md`

The Owner Brief Renderer turns each decision pack into a readable owner brief
with priority, lane, owner focus, risk, recommended decision, draft action, and
safety lock. It is deterministic and local-only: it does not parse raw WhatsApp
text, does not call a cloud LLM, does not send WhatsApp messages, and does not
mutate CRM records. Rendered brief markdown intentionally omits case IDs and
pack IDs.

## Build Approval Routing Queue

Build owner approval route items from the local owner brief artifact:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_approval_routing_queue \
  --owner-briefs-db research/personal/wa-corpus/owner-brief-renderer/owner_brief_renderer.local.sqlite \
  --output-dir research/personal/wa-corpus/approval-routing-queue \
  --summary research/personal/wa-corpus/approval-routing-queue/approval_routing_queue_summary.md \
  --json
```

Outputs:

- `research/personal/wa-corpus/approval-routing-queue/approval_routing_queue.local.sqlite`
- `research/personal/wa-corpus/approval-routing-queue/approval_routing_queue_summary.md`

The Approval Routing Queue turns each owner brief into a local owner review
route with next actor, route bucket, queue status, and allowed decisions:
approve, reject, or defer. It is deterministic and local-only: it does not
parse raw WhatsApp text, does not call a cloud LLM, does not send WhatsApp
messages, and does not mutate CRM records. It prepares owner decisions but does
not automatically approve anything.

## Build Approve/Reject Ledger

Build immutable local owner decision slots from the approval routing queue:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_approve_reject_ledger \
  --approval-routing-db research/personal/wa-corpus/approval-routing-queue/approval_routing_queue.local.sqlite \
  --output-dir research/personal/wa-corpus/approve-reject-ledger \
  --summary research/personal/wa-corpus/approve-reject-ledger/approve_reject_ledger_summary.md \
  --json
```

Outputs:

- `research/personal/wa-corpus/approve-reject-ledger/approve_reject_ledger.local.sqlite`
- `research/personal/wa-corpus/approve-reject-ledger/approve_reject_ledger_summary.md`

The Approve/Reject Ledger opens one immutable decision slot per approval route.
Each slot starts as `awaiting_owner_decision` / `pending` and keeps the allowed
owner decisions: approve, reject, or defer. It is deterministic and local-only:
it does not parse raw WhatsApp text, does not call a cloud LLM, does not send
WhatsApp messages, and does not mutate CRM records. Pending means no owner
approval has been invented by the system.

## Build Owner Decision Event Capture

Capture explicit local owner decisions from the Approve/Reject Ledger:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_owner_decision_event_capture \
  --ledger-db research/personal/wa-corpus/approve-reject-ledger/approve_reject_ledger.local.sqlite \
  --output-dir research/personal/wa-corpus/owner-decision-events \
  --summary research/personal/wa-corpus/owner-decision-events/owner_decision_event_capture_summary.md \
  --json
```

Optional local owner event input:

```bash
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_owner_decision_event_capture \
  --ledger-db research/personal/wa-corpus/approve-reject-ledger/approve_reject_ledger.local.sqlite \
  --owner-events-jsonl research/personal/wa-corpus/owner-decision-events/owner_events.local.jsonl \
  --output-dir research/personal/wa-corpus/owner-decision-events \
  --summary research/personal/wa-corpus/owner-decision-events/owner_decision_event_capture_summary.md \
  --json
```

Outputs:

- `research/personal/wa-corpus/owner-decision-events/owner_decision_event_capture.local.sqlite`
- `research/personal/wa-corpus/owner-decision-events/owner_decision_event_capture_summary.md`

The Owner Decision Event Capture records approve, reject, or defer only when an
explicit local owner event is provided. Missing events remain
`awaiting_owner_input` / `pending`; the system never invents approval. It is
deterministic and local-only: it does not parse raw WhatsApp text, does not call
a cloud LLM, does not send WhatsApp messages, and does not mutate CRM records.
Human approval remains mandatory before every client-facing message or
operational mutation.

## Build Post-Decision Work Order Queue

Convert captured owner decisions into internal work orders:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_post_decision_work_order_queue \
  --owner-events-db research/personal/wa-corpus/owner-decision-events/owner_decision_event_capture.local.sqlite \
  --output-dir research/personal/wa-corpus/post-decision-work-orders \
  --summary research/personal/wa-corpus/post-decision-work-orders/post_decision_work_order_queue_summary.md \
  --json
```

Outputs:

- `research/personal/wa-corpus/post-decision-work-orders/post_decision_work_order_queue.local.sqlite`
- `research/personal/wa-corpus/post-decision-work-orders/post_decision_work_order_queue_summary.md`

The Post-Decision Work Order Queue turns owner decision events into internal
tasks only. Pending owner decisions remain blocked, approved decisions become
operator-review work orders, and deferred or rejected decisions create no
external action. It is deterministic and local-only: it does not parse raw
WhatsApp text, does not call a cloud LLM, does not send WhatsApp messages, and
does not mutate CRM records. Human approval remains mandatory before every
client-facing message or operational mutation.

## Build Operator Execution Packets

Convert post-decision work orders into internal operator execution packets:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_operator_execution_packets \
  --work-orders-db research/personal/wa-corpus/post-decision-work-orders/post_decision_work_order_queue.local.sqlite \
  --output-dir research/personal/wa-corpus/operator-execution-packets \
  --summary research/personal/wa-corpus/operator-execution-packets/operator_execution_packets_summary.md \
  --json
```

Outputs:

- `research/personal/wa-corpus/operator-execution-packets/operator_execution_packets.local.sqlite`
- `research/personal/wa-corpus/operator-execution-packets/operator_execution_packets_summary.md`

The Operator Execution Packets artifact translates internal work orders into
the exact packet an operator can review. Pending owner decisions stay blocked,
approved packets remain behind a human-review gate, deferred packets wait for
owner revisit, and rejected packets stop with no external action. It is
deterministic and local-only: it does not parse raw WhatsApp text, does not call
a cloud LLM, does not send WhatsApp messages, and does not mutate CRM records.
Human approval remains mandatory before every client-facing message or
operational mutation.

## Build Operator Packet Review Console

Convert operator execution packets into review-console rows:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_operator_packet_review_console \
  --packets-db research/personal/wa-corpus/operator-execution-packets/operator_execution_packets.local.sqlite \
  --output-dir research/personal/wa-corpus/operator-packet-review-console \
  --summary research/personal/wa-corpus/operator-packet-review-console/operator_packet_review_console_summary.md \
  --json
```

Outputs:

- `research/personal/wa-corpus/operator-packet-review-console/operator_packet_review_console.local.sqlite`
- `research/personal/wa-corpus/operator-packet-review-console/operator_packet_review_console_summary.md`

The Operator Packet Review Console is an internal owner/team reading surface.
It groups packet work into review states and buckets: waiting owner decision,
ready for human review, deferred owner revisit, or rejected closed. It is
deterministic and local-only: it does not parse raw WhatsApp text, does not call
a cloud LLM, does not send WhatsApp messages, and does not mutate CRM records.
Human approval remains mandatory before every client-facing message or
operational mutation.

## Build Owner Decision Intake

Convert explicit owner decisions from the review console into replayable local
events:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_owner_decision_intake \
  --review-console-db research/personal/wa-corpus/operator-packet-review-console/operator_packet_review_console.local.sqlite \
  --owner-decisions-jsonl research/personal/wa-corpus/owner-decision-compiler/owner_decisions.local.jsonl \
  --output-dir research/personal/wa-corpus/owner-decision-intake \
  --summary research/personal/wa-corpus/owner-decision-intake/owner_decision_intake_summary.md \
  --json
```

Outputs:

- `research/personal/wa-corpus/owner-decision-intake/owner_decision_intake.local.sqlite`
- `research/personal/wa-corpus/owner-decision-intake/owner_events.local.jsonl`
- `research/personal/wa-corpus/owner-decision-intake/owner_decisions_template.local.jsonl`
- `research/personal/wa-corpus/owner-decision-intake/owner_decision_intake_summary.md`

The Owner Decision Intake accepts only explicit `approve`, `reject`, or `defer`
records for owner-actionable review items. Captured decisions are exported as
`owner_events.local.jsonl`, which can be replayed through
`build_owner_decision_event_capture` and the downstream work-order / packet /
review-console chain. Missing decisions remain awaiting owner input and are
listed in the local `owner_decisions_template.local.jsonl` edit template;
operator ready and closed items cannot be changed through this intake. It is
deterministic and local-only: it does not parse raw WhatsApp text, does not call
a cloud LLM, does not send WhatsApp messages, and does not mutate CRM records.
Human approval remains mandatory before every client-facing message or
operational mutation.

## Build Owner Decision Replay

Replay explicit owner decisions through the full local-only chain:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_owner_decision_replay \
  --ledger-db research/personal/wa-corpus/approve-reject-ledger/approve_reject_ledger.local.sqlite \
  --review-console-db research/personal/wa-corpus/operator-packet-review-console/operator_packet_review_console.local.sqlite \
  --owner-decisions-jsonl research/personal/wa-corpus/owner-decision-compiler/owner_decisions.local.jsonl \
  --output-dir research/personal/wa-corpus/owner-decision-replay \
  --summary research/personal/wa-corpus/owner-decision-replay/owner_decision_replay_summary.md \
  --json
```

Outputs:

- `research/personal/wa-corpus/owner-decision-replay/owner_decision_replay.local.sqlite`
- `research/personal/wa-corpus/owner-decision-replay/owner_decision_replay_summary.md`
- `research/personal/wa-corpus/owner-decision-replay/owner-decision-intake/`
- `research/personal/wa-corpus/owner-decision-replay/owner-decision-events/`
- `research/personal/wa-corpus/owner-decision-replay/post-decision-work-orders/`
- `research/personal/wa-corpus/owner-decision-replay/operator-execution-packets/`
- `research/personal/wa-corpus/owner-decision-replay/operator-packet-review-console/`

The Owner Decision Replay is the deterministic case-closure loop for owner
decisions. It regenerates owner decision intake, owner event capture,
post-decision work orders, operator packets, and the final review console from
one explicit owner-decision JSONL file. Empty decision files are valid and keep
the chain waiting for owner input; the runner never invents approval, rejection,
or deferral. It is local-only: it does not parse raw WhatsApp text, does not call
a cloud LLM, does not send WhatsApp messages, and does not mutate CRM records.
Human approval remains mandatory before every client-facing message or
operational mutation.

## Build Owner Decision Inbox

Build the local owner-editable inbox from review-console rows:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_owner_decision_inbox \
  --review-console-db research/personal/wa-corpus/operator-packet-review-console/operator_packet_review_console.local.sqlite \
  --output-dir research/personal/wa-corpus/owner-decision-inbox \
  --summary research/personal/wa-corpus/owner-decision-inbox/owner_decision_inbox_summary.md \
  --json
```

Outputs:

- `research/personal/wa-corpus/owner-decision-inbox/owner_decision_inbox.local.sqlite`
- `research/personal/wa-corpus/owner-decision-inbox/owner_decisions_template.local.jsonl`
- `research/personal/wa-corpus/owner-decision-inbox/owner_decision_inbox_summary.md`

The Owner Decision Inbox selects only owner-actionable review rows: waiting
owner decision and owner revisit. The JSONL template is intentionally blank for
`owner_decision`, so the system never invents approval, rejection, or deferral.
After explicit owner decisions are recorded through
`build_owner_decision_cockpit`, compile that cockpit template through
`build_owner_decision_compiler` before feeding the resulting
`owner_decisions.local.jsonl` into the intake/replay path. The inbox is
deterministic and local-only: it does not parse raw WhatsApp text, does not call
a cloud LLM, does not send WhatsApp messages, and does not mutate CRM records.
Human approval remains mandatory before every client-facing message or
operational mutation.

## Build Owner Decision Cockpit

Record explicit owner decisions into a compiler-compatible local template:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_owner_decision_cockpit \
  --owner-inbox-db research/personal/wa-corpus/owner-decision-inbox/owner_decision_inbox.local.sqlite \
  --decision operator-packet-review-item-pending=approve \
  --decision-note operator-packet-review-item-pending="owner approved recovery follow-up" \
  --output-dir research/personal/wa-corpus/owner-decision-cockpit \
  --summary research/personal/wa-corpus/owner-decision-cockpit/owner_decision_cockpit_summary.md \
  --json
```

Optional local JSONL input:

```bash
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_owner_decision_cockpit \
  --owner-inbox-db research/personal/wa-corpus/owner-decision-inbox/owner_decision_inbox.local.sqlite \
  --owner-inputs-jsonl research/personal/wa-corpus/owner-decision-cockpit/owner_inputs.local.jsonl \
  --output-dir research/personal/wa-corpus/owner-decision-cockpit \
  --summary research/personal/wa-corpus/owner-decision-cockpit/owner_decision_cockpit_summary.md \
  --json
```

Outputs:

- `research/personal/wa-corpus/owner-decision-cockpit/owner_decision_cockpit.local.sqlite`
- `research/personal/wa-corpus/owner-decision-cockpit/owner_decisions_template.local.jsonl`
- `research/personal/wa-corpus/owner-decision-cockpit/owner_decision_cockpit_summary.md`

The Owner Decision Cockpit is the owner input surface before the compiler. It
accepts only explicit `approve`, `reject`, or `defer` decisions for inbox items,
keeps missing decisions blank as `awaiting_owner_input`, rejects duplicates,
unknown review items, invalid actors, and invalid decisions, then writes the
full template expected by `build_owner_decision_compiler`. Inline `--decision`
arguments are the quickest path when the owner wants to approve, reject, or
defer without hand-editing JSONL. It is deterministic and local-only: it does
not parse raw WhatsApp text, does not call a cloud LLM, does not send WhatsApp
messages, and does not mutate CRM records. Human approval remains mandatory
before every client-facing message or operational mutation.

## Build Owner Decision Compiler

Compile an edited Owner Decision Inbox template into clean intake-ready owner
decisions:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_owner_decision_compiler \
  --owner-inbox-db research/personal/wa-corpus/owner-decision-inbox/owner_decision_inbox.local.sqlite \
  --edited-template-jsonl research/personal/wa-corpus/owner-decision-cockpit/owner_decisions_template.local.jsonl \
  --output-dir research/personal/wa-corpus/owner-decision-compiler \
  --summary research/personal/wa-corpus/owner-decision-compiler/owner_decision_compiler_summary.md \
  --json
```

Outputs:

- `research/personal/wa-corpus/owner-decision-compiler/owner_decision_compiler.local.sqlite`
- `research/personal/wa-corpus/owner-decision-compiler/owner_decisions.local.jsonl`
- `research/personal/wa-corpus/owner-decision-compiler/owner_decision_compiler_summary.md`

The Owner Decision Compiler is a narrow binder, not a second decision engine. It
matches every edited template row back to `owner_decision_inbox.local.sqlite`,
imports the allowed decision enum from Owner Decision Intake, rejects blank,
invalid, duplicate, unknown, missing, or tampered rows, and records whether each
timestamp was owner supplied or filled with compile time. The output JSONL uses a
single `review_item_id` reference per row so `build_owner_decision_intake` can
consume it deterministically. It does not parse raw WhatsApp text, does not call
a cloud LLM, does not send WhatsApp messages, and does not mutate CRM records.
Human approval remains mandatory before every client-facing message or
operational mutation.

## Build Owner Decision Pipeline

Run the local owner-decision path without hand-wiring the Cockpit, Compiler, and
Replay paths:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_owner_decision_pipeline \
  --ledger-db research/personal/wa-corpus/approve-reject-ledger/approve_reject_ledger.local.sqlite \
  --review-console-db research/personal/wa-corpus/operator-packet-review-console/operator_packet_review_console.local.sqlite \
  --decision operator-packet-review-item-pending=approve \
  --decision-note operator-packet-review-item-pending="owner approved recovery follow-up" \
  --output-dir research/personal/wa-corpus/owner-decision-pipeline \
  --summary research/personal/wa-corpus/owner-decision-pipeline/owner_decision_pipeline_summary.md \
  --json
```

Outputs:

- `research/personal/wa-corpus/owner-decision-pipeline/owner_decision_pipeline.local.sqlite`
- `research/personal/wa-corpus/owner-decision-pipeline/owner_decision_pipeline_summary.md`
- `research/personal/wa-corpus/owner-decision-pipeline/owner-decision-inbox/`
- `research/personal/wa-corpus/owner-decision-pipeline/owner-decision-cockpit/`
- `research/personal/wa-corpus/owner-decision-pipeline/owner-decision-compiler/`
- `research/personal/wa-corpus/owner-decision-pipeline/owner-decision-replay/`

The Owner Decision Pipeline runs Inbox, Cockpit, Compiler, and Replay in order,
passing the Cockpit template path explicitly into the Compiler. If even one
owner input is missing, the pipeline stops at the Cockpit with
`awaiting_owner_input` and does not run Compiler or Replay, avoiding the manual
path error where an incomplete template reaches the compiler. It is
deterministic and local-only: it does not parse raw WhatsApp text, does not call
a cloud LLM, does not send WhatsApp messages, and does not mutate CRM records.
Human approval remains mandatory before every client-facing message or
operational mutation.

## Build Team Captain Shadow Mode

Build aggregate Team Captain findings from the Client Captain Shadow artifact:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_team_captain_shadow \
  --client-shadow-db research/personal/wa-corpus/client-captain-shadow/client_captain_shadow.local.sqlite \
  --operator-review-console-db research/personal/wa-corpus/operator-packet-review-console/operator_packet_review_console.local.sqlite \
  --output-dir research/personal/wa-corpus/team-captain-shadow \
  --summary research/personal/wa-corpus/team-captain-shadow/team_captain_shadow_summary.md \
  --json
```

Outputs:

- `research/personal/wa-corpus/team-captain-shadow/team_captain_shadow.local.sqlite`
- `research/personal/wa-corpus/team-captain-shadow/team_captain_shadow_summary.md`

Team Captain reads no raw message text. It groups Client Captain drafts by
specialist lane and writes one aggregate finding per lane, plus six depth layers
per lane:

1. lane workload
2. risk pressure
3. behavior pattern
4. motivation plan
5. accountability nudge
6. team escalation gate

This is the "family but firm" layer: it motivates, coaches, and flags
accountability when the operator is not using the system well. It still cannot
send WhatsApp messages and cannot mutate CRM records.

When `--operator-review-console-db` is provided, Team Captain also reads the
local Operator Packet Review Console and writes `team_operator_coaching_cards`.
Those cards are the operational discipline layer: warm push for operator-ready
packets, protective stop when owner decision is missing, closure discipline for
rejected packets, and firm correction when a ready packet is routed to the wrong
operator lane. The cards store no packet IDs, case IDs, work-order IDs, raw text,
source paths, or free-text console instructions. If an upstream console row ever
violates the no-send/no-CRM/human-approval contract, Team Captain records only a
boolean contract-violation marker and emits a safe firm correction card. The
summary also reports only the aggregate count of input contract violations from
Client Shadow and Operator Console inputs.

## Build Owner Captain Shadow Mode

Build the owner-level governance artifact from Client and Team Captain Shadow:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_owner_captain_shadow \
  --client-shadow-db research/personal/wa-corpus/client-captain-shadow/client_captain_shadow.local.sqlite \
  --team-shadow-db research/personal/wa-corpus/team-captain-shadow/team_captain_shadow.local.sqlite \
  --output-dir research/personal/wa-corpus/owner-captain-shadow \
  --summary research/personal/wa-corpus/owner-captain-shadow/owner_captain_shadow_summary.md \
  --json
```

Outputs:

- `research/personal/wa-corpus/owner-captain-shadow/owner_captain_shadow.local.sqlite`
- `research/personal/wa-corpus/owner-captain-shadow/owner_captain_shadow_summary.md`

Owner Captain sees only aggregate Client and Team Captain outputs. It writes one
global owner finding plus seven depth layers:

1. operational volume
2. risk concentration
3. team bottleneck
4. client experience risk
5. automation leverage
6. governance boundary
7. owner decision

Owner Captain is a governance and decision-support artifact, not an autonomous
sender. It cannot send WhatsApp messages, cannot mutate CRM records, includes no
raw text, and requires human approval for every decision. If Client Shadow or
Team Captain inputs violate the no-send/no-CRM/human-approval contract, Owner
Captain reports only the aggregate input contract violation count and keeps the
output itself safe.

## Build Cloud Export Manifest

Before importing more chat archives from cloud storage, save a local rclone
metadata listing and convert it into a privacy-safe manifest:

```bash
source .venv/bin/activate
rclone lsjson gdrive: --recursive --files-only --include "*WhatsApp Chat*.zip" \
  > research/personal/wa-corpus/drive/drive_lsjson.local.json
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_drive_export_manifest \
  --lsjson research/personal/wa-corpus/drive/drive_lsjson.local.json \
  --output-db research/personal/wa-corpus/drive/drive_export_manifest.local.sqlite \
  --summary research/personal/wa-corpus/drive/drive_export_manifest_summary.md \
  --json
```

Outputs:

- `research/personal/wa-corpus/drive/drive_lsjson.local.json`
- `research/personal/wa-corpus/drive/drive_export_manifest.local.sqlite`
- `research/personal/wa-corpus/drive/drive_export_manifest_summary.md`

The `.local.json` and `.local.sqlite` files are ignored by git and must stay on
the Pro. The summary is aggregate-only: no raw cloud paths, no raw file names,
and no cloud file ids. This step does not download ZIPs or parse message text;
it only creates a resolver manifest for the next local import pass.

## Import Selected Cloud ZIPs Locally

After the manifest exists, import a bounded batch into the local corpus. The
default command is a dry-run; add `--execute` only when importing on the Pro:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.import_drive_exports \
  --manifest-db research/personal/wa-corpus/drive/drive_export_manifest.local.sqlite \
  --download-dir research/personal/wa-corpus/drive/downloads.local \
  --corpus-root "$HOME/Desktop/wa-chats-MASTER-2026-05-26" \
  --limit 10 \
  --json
```

Execute mode:

```bash
PYTHONPATH=. python -m scripts.whatsapp_corpus.import_drive_exports \
  --manifest-db research/personal/wa-corpus/drive/drive_export_manifest.local.sqlite \
  --download-dir research/personal/wa-corpus/drive/downloads.local \
  --corpus-root "$HOME/Desktop/wa-chats-MASTER-2026-05-26" \
  --rclone-bin /opt/homebrew/bin/rclone \
  --limit 10 \
  --execute \
  --json
```

Outputs:

- `research/personal/wa-corpus/drive/downloads.local/drive-wa-*.zip`
- `$HOME/Desktop/wa-chats-MASTER-2026-05-26/03_drive-imports/drive-wa-*/chat-*.txt`
- `research/personal/wa-corpus/drive/drive_import_summary.md`

The importer resolves Drive files by private ID when present, not by filename.
It extracts only `.txt` chat files and renames them to anonymized local names.
Media files are ignored. The downloaded ZIPs and raw chat text are local-only
and must stay on the Pro. Re-run the registry/classification pipeline after a
batch import, then create a source-scoped review manifest:

```bash
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_review_manifest \
  --root "$HOME/Desktop/wa-chats-MASTER-2026-05-26" \
  --classification-db research/personal/wa-corpus/classification/chat_classification.sqlite \
  --output-dir research/personal/wa-corpus/review \
  --source 03_drive-imports \
  --limit 80
```

Do not feed imported cleartext directly to cloud LLMs.

## Full Cleartext Local Corpus

When the owner explicitly authorizes full local processing, parse every readable
TXT chat into an ignored cleartext SQLite database:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.parse_full_corpus
```

Outputs:

- `research/personal/wa-corpus/full/full_messages.local.sqlite`
- `research/personal/wa-corpus/full/full_corpus_parse_summary.md`

The SQLite database contains raw message text and is ignored by git. It also
contains an FTS5 index for local cleartext search.

Set aside only explicit spicy/intimate conversation candidates:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.quarantine_spicy_conversations
```

Outputs:

- `research/personal/wa-corpus/full/spicy_quarantine.local.sqlite`
- `research/personal/wa-corpus/full/spicy_quarantine.local.tsv`
- `research/personal/wa-corpus/full/usable_after_spicy_quarantine.local.tsv`
- `research/personal/wa-corpus/full/spicy_quarantine_summary.md`

Mine business and memory value signals only from the usable file list:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.mine_full_gold_signals
```

Outputs:

- `research/personal/wa-corpus/full/full_gold_signals.local.sqlite`
- `research/personal/wa-corpus/full/full_gold_signals_summary.md`
- `research/personal/wa-corpus/full/full_corpus_gold_research.md`

## Analyze Allowed Temporal Metrics

Build aggregate temporal metrics from the ignored parsed-message DB:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.analyze_allowed_temporal \
  --input-db research/personal/wa-corpus/analysis/allowed_messages.local.sqlite \
  --output-db research/personal/wa-corpus/analysis/allowed_temporal.local.sqlite \
  --summary research/personal/wa-corpus/analysis/allowed_temporal_summary.md
```

Outputs:

- `research/personal/wa-corpus/analysis/allowed_temporal.local.sqlite`
- `research/personal/wa-corpus/analysis/allowed_temporal_summary.md`

The temporal analyzer reads only aggregate-safe columns and denies accidental
reads from `body_text`, `sender_raw`, and `local_path`.

## Analyze Allowed Signals

Run deterministic aggregate signal analysis over the ignored parsed-message DB:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.analyze_allowed_signals \
  --messages-db research/personal/wa-corpus/analysis/allowed_messages.local.sqlite \
  --output-dir research/personal/wa-corpus/analysis
```

Outputs:

- `research/personal/wa-corpus/analysis/allowed_signal_hits.local.sqlite`
- `research/personal/wa-corpus/analysis/allowed_signal_summary.md`

The signal report is aggregate-only. Signal codes are routing hints for the
next local extractor, not legal or client-level conclusions.

## Extract Allowed Candidates

Extract hashed structured candidates from the ignored parsed-message DB:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.extract_allowed_candidates \
  --messages-db research/personal/wa-corpus/analysis/allowed_messages.local.sqlite \
  --output-dir research/personal/wa-corpus/analysis
```

Outputs:

- `research/personal/wa-corpus/analysis/allowed_candidates.local.sqlite`
- `research/personal/wa-corpus/analysis/allowed_candidates_summary.md`

The candidate SQLite stores hashed body/value references only. It is still
ignored by git because hashes are local review aids, not publishable evidence.

## Extract Document Requirements

Extract aggregate document-requirement signals from the ignored parsed-message
DB and the ignored hashed-candidate DB:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.extract_document_requirements \
  --messages-db research/personal/wa-corpus/analysis/allowed_messages.local.sqlite \
  --candidates-db research/personal/wa-corpus/analysis/allowed_candidates.local.sqlite \
  --output-db research/personal/wa-corpus/analysis/allowed_document_requirements.local.sqlite \
  --summary research/personal/wa-corpus/analysis/allowed_document_requirements_summary.md
```

Outputs:

- `research/personal/wa-corpus/analysis/allowed_document_requirements.local.sqlite`
- `research/personal/wa-corpus/analysis/allowed_document_requirements_summary.md`

The tracked summary is aggregate-only. The ignored SQLite stores hashes,
message indexes, timestamps, category codes, evidence codes, and counters; it
does not store raw message text or raw extracted document values.

## Analyze Immigration Lifecycle

Build aggregate immigration lifecycle stages from the ignored local message,
candidate, and signal databases:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.analyze_immigration_lifecycle \
  --messages-db research/personal/wa-corpus/analysis/allowed_messages.local.sqlite \
  --candidates-db research/personal/wa-corpus/analysis/allowed_candidates.local.sqlite \
  --signal-db research/personal/wa-corpus/analysis/allowed_signal_hits.local.sqlite \
  --output-db research/personal/wa-corpus/analysis/allowed_immigration_lifecycle.local.sqlite \
  --summary research/personal/wa-corpus/analysis/allowed_immigration_lifecycle_summary.md
```

Outputs:

- `research/personal/wa-corpus/analysis/allowed_immigration_lifecycle.local.sqlite`
- `research/personal/wa-corpus/analysis/allowed_immigration_lifecycle_summary.md`

The lifecycle analyzer classifies aggregate message-level stages such as
`lead_intake`, `identity_passport`, `sponsor_company`,
`application_submission`, `appointment_biometric`, `approval_issuance`,
`extension_renewal_expiry`, and `problem_escalation`. The tracked summary
contains aggregate counts only.

## Extract Tax/Payment Signals

Extract aggregate tax, invoice, reporting, payment, and amount-reference
signals from ignored local databases:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.extract_tax_payment_signals \
  --messages-db research/personal/wa-corpus/analysis/allowed_messages.local.sqlite \
  --candidates-db research/personal/wa-corpus/analysis/allowed_candidates.local.sqlite \
  --signals-db research/personal/wa-corpus/analysis/allowed_signal_hits.local.sqlite \
  --output-db research/personal/wa-corpus/analysis/allowed_tax_payment.local.sqlite \
  --summary research/personal/wa-corpus/analysis/allowed_tax_payment_summary.md
```

Outputs:

- `research/personal/wa-corpus/analysis/allowed_tax_payment.local.sqlite`
- `research/personal/wa-corpus/analysis/allowed_tax_payment_summary.md`

The ignored SQLite stores only local identifiers, hashes, category codes,
timestamps, and counters. The tracked summary contains aggregate counts only.

## Build Follow-Up Risk Queue

Build aggregate local follow-up/risk queue signals:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_followup_risk_queue \
  --messages-db research/personal/wa-corpus/analysis/allowed_messages.local.sqlite \
  --signal-db research/personal/wa-corpus/analysis/allowed_signal_hits.local.sqlite \
  --temporal-db research/personal/wa-corpus/analysis/allowed_temporal.local.sqlite \
  --output-db research/personal/wa-corpus/analysis/allowed_followup_risk.local.sqlite \
  --summary research/personal/wa-corpus/analysis/allowed_followup_risk_summary.md
```

Outputs:

- `research/personal/wa-corpus/analysis/allowed_followup_risk.local.sqlite`
- `research/personal/wa-corpus/analysis/allowed_followup_risk_summary.md`

The queue is heuristic and local-only. Use it as an anonymous review queue, not
as a client-facing or legal conclusion.

## Build Domain Event Index

Normalize the derived domain extractor outputs into one ignored local event
table:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_domain_event_index \
  --document-db research/personal/wa-corpus/analysis/allowed_document_requirements.local.sqlite \
  --lifecycle-db research/personal/wa-corpus/analysis/allowed_immigration_lifecycle.local.sqlite \
  --tax-db research/personal/wa-corpus/analysis/allowed_tax_payment.local.sqlite \
  --followup-db research/personal/wa-corpus/analysis/allowed_followup_risk.local.sqlite \
  --output-db research/personal/wa-corpus/analysis/allowed_domain_events.local.sqlite \
  --summary research/personal/wa-corpus/analysis/allowed_domain_events_summary.md
```

Outputs:

- `research/personal/wa-corpus/analysis/allowed_domain_events.local.sqlite`
- `research/personal/wa-corpus/analysis/allowed_domain_events_summary.md`

The event index reads only derived extractor DBs. It does not read the raw
parsed-message DB and its tracked summary contains only aggregate event counts.

## Analyze Document/Lifecycle Gaps

Build aggregate coverage matrices between immigration lifecycle stages and
document requirement events:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.analyze_document_lifecycle_gaps \
  --events-db research/personal/wa-corpus/analysis/allowed_domain_events.local.sqlite \
  --output-db research/personal/wa-corpus/analysis/allowed_document_lifecycle_gaps.local.sqlite \
  --summary research/personal/wa-corpus/analysis/allowed_document_lifecycle_gaps_summary.md
```

Outputs:

- `research/personal/wa-corpus/analysis/allowed_document_lifecycle_gaps.local.sqlite`
- `research/personal/wa-corpus/analysis/allowed_document_lifecycle_gaps_summary.md`

This analyzer reads only the derived domain event index and reports aggregate
coverage/gap counts. A gap means no same-message document event was detected; it
does not prove a missing client document.

## Build Case Windows

Group the derived domain events into anonymous local case windows:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_case_windows \
  --events-db research/personal/wa-corpus/analysis/allowed_domain_events.local.sqlite \
  --output-db research/personal/wa-corpus/analysis/allowed_case_windows.local.sqlite \
  --summary research/personal/wa-corpus/analysis/allowed_case_windows_summary.md
```

Outputs:

- `research/personal/wa-corpus/analysis/allowed_case_windows.local.sqlite`
- `research/personal/wa-corpus/analysis/allowed_case_windows_summary.md`

The case windows are anonymous local review units. They are built from the
derived domain event index, not from the raw parsed-message DB.

## Build Case Window Review Queue

Build an anonymous local review queue from dense or high-risk case windows:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_case_window_review_queue \
  --input-db research/personal/wa-corpus/analysis/allowed_case_windows.local.sqlite \
  --output-tsv research/personal/wa-corpus/analysis/allowed_case_window_review.local.tsv \
  --summary research/personal/wa-corpus/analysis/allowed_case_window_review_summary.md
```

Outputs:

- `research/personal/wa-corpus/analysis/allowed_case_window_review.local.tsv`
- `research/personal/wa-corpus/analysis/allowed_case_window_review_summary.md`

The TSV stays local-only and ignored by git. The tracked summary keeps only
aggregate counts and queue reason frequencies.

## Analyze Signal Matrix

Build aggregate matrices from signal hits:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.analyze_allowed_signal_matrix \
  --input research/personal/wa-corpus/analysis/allowed_signal_hits.local.sqlite \
  --output-db research/personal/wa-corpus/analysis/allowed_signal_matrix.local.sqlite \
  --summary research/personal/wa-corpus/analysis/allowed_signal_matrix_summary.md
```

Outputs:

- `research/personal/wa-corpus/analysis/allowed_signal_matrix.local.sqlite`
- `research/personal/wa-corpus/analysis/allowed_signal_matrix_summary.md`

The matrix reads only `signal_hits` fields, never raw message text.

## Build Analysis Inventory

Build a run checklist of local analysis artifacts:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_analysis_inventory \
  --analysis-dir research/personal/wa-corpus/analysis \
  --summary research/personal/wa-corpus/analysis/analysis_inventory_summary.md
```

Outputs:

- `research/personal/wa-corpus/analysis/analysis_inventory_summary.md`

The inventory inspects only local SQLite table names, table row counts, summary
titles, and line counts. It does not select raw message text, sender labels, or
local paths.

## Privacy Audit

Run the report privacy audit before committing generated WhatsApp reports:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.audit_privacy_outputs
```

The audit scans tracked files under `research/personal/wa-corpus/`, skips local
and database artifacts, and prints only `repo/path<TAB>pattern_label` findings.

Use `--include-untracked` when you want to scan local scratch reports before
sharing them:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.audit_privacy_outputs --include-untracked
```
