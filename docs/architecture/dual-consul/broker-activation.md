# Protected broker and native canary activation

This increment connects the native text adapter to the existing Autonomous Lab
and Research OS lifecycle through a protected Pro helper. The runnable consumer
is [`scripts.conductor.consul_native`](../../../scripts/conductor/consul_native.py).
It accepts only the fixed synthetic text `Reply with exactly
DUAL_CONSUL_NATIVE_OK. Do not use tools.` and one invocation per approved grant.
It creates no scheduler, daemon, listener, arbitrary prompt runner, or automatic
model fallback. This document describes prepared code and activation steps;
it does not assert that the privileged helper has been installed or a live
broker-authorized turn has completed.

For window responsibilities and the offline `consul_packet prepare/assemble`
commands, see [dual-consul windows](../../runbooks/dual-consul-windows.md).
The preparation CLI never issues approvals or installs protected grants.

The [runtime qualification](../../../evidence/dual-consul-broker/runtime/README.md)
records strict isolated launch and complete hidden-inclusive catalogs on the
exact Pro 0.149.0, Mini 0.148.0, and M5 0.147.0 executables. **Astra was absent on
all three hosts.** Those probes made zero inference calls. The later
[0.153.4 qualification](../../../evidence/dual-consul-astra/README.md) observes
Astra on all three hosts and two completed synthetic M5 turns; the launcher
prefers that side-by-side, hash-pinned runtime where installed. The earlier
[native shadow experiment](native-shadow.md) records two Terra turns on M5 under
an independent synthetic callback; it is not evidence of an Astra response or
of this new PostgreSQL broker path. Selecting another model would require an
explicitly scoped grant and separate evidence, never a silent substitution.

## Consumer, authorization, and completion

1. The ordinary caller launches the pinned native executable in a disposable
   private home. Configuration, account context, requested model, and effort
   are discovered before admission. `--discover` emits only the selected binding
   and performs no inference. An unavailable model is refused.
2. The existing review/issuer process prepares an expiring grant for that exact
   mission, literal input hash, model, effort, runtime/configuration/host/auth
   binding, ActionIntent, ApprovalReceipt, and cross-family VerificationReceipt.
   The review targets the exact ActionIntent hash. A grant UUID selects an
   already installed protected file; caller-supplied JSON is not an approval.
3. [`ConsulBrokerClient`](../../../scripts/conductor/consul_broker_client.py)
   reaches the fixed Pro helper over bounded stdin JSON, using local transport
   on Pro or the existing `ssh pro` route from another host. The helper runs
   under `_nuz_consul`, verifies its kernel UID and Pro placement, and loads
   protected configuration and grant files before connecting to PostgreSQL.
   Native inference stays under the ordinary caller UID and receives no broker
   database credential or grant-installation permission.
4. The helper's closed verbs are `admit`, `check`, `cancel`, and `checkpoint`.
   Admission uses the existing Lab run, ownership lease, and PostgreSQL locks.
   The adapter reads config/account again immediately before its `turn` check;
   the authoritative broker check follows that discovery and precedes
   `turn/start`. A started ExecutionAttempt is persisted once per exact approval.
   Another admission or spend after that point returns `needs_reconcile`.
   The fixed canary's lease budget is derived from shared helper, RPC and turn
   deadlines, with a margin for cleanup. Admission refuses a grant whose
   remaining approval or review window cannot cover that budget; the lease
   remains capped by grant expiry. No grant extension or renewal is implied.
5. After the native reply, a fresh `complete` check validates ownership,
   generation, expiry, revocation, and the exact attempt binding. It records the
   completion generation. `checkpoint` requires that generation before saving
   a selected OperationalReceipt and a fenced terminal Lab result. Raw response
   text and reasoning are excluded from the helper protocol.

The [broker implementation](../../../apps/backend-rag/backend/services/autonomous_lab/consul_native_broker.py)
uses the existing lease guard and Lab state store. It distinguishes a started
attempt from confirmed completion: PostgreSQL cannot make a provider call and
its receipt one atomic transaction. A lost or rejected completion remains a
reconciliation case; retrying does not mint another invocation. Replaying an
already committed receipt still checks current authority and matching result
under the existing owner/generation; it does not reopen the run.

A completed reply passes the canary only when its full text is exactly
`DUAL_CONSUL_NATIVE_OK`. A different marker or an observed incomplete response
is a known failed invocation, with a consumed grant. An interrupted or
unconfirmed outcome remains a reconciliation case. These statuses do not
grant another spend. Selected unknown usage-counter names are reported without
their values; unsafe or excess names are represented by an omission flag.

The consumer's literal input hash does not cover expanded native system
instructions or thread history. Native checkpoint identity remains
`request_observed` from `native_thread_configuration`, with inference-response
identity unknown. Native token counters remain distinct and are not a hard
total-consumption cap. Tool activity is disabled and unexpected tool/delegation
events fail the transport. This scope is a synthetic text canary, not a general
effect executor or a qualification of recovered sessions across processes.

## Prepared interface and privilege boundary

The [provisioning package](../../../infra/conductor/consul-broker/README.md)
contains the concrete bundle builder, immutable interpreter/dependency closure,
fixed wrapper, sudoers rule, and separately reviewed database-role SQL. Its
default installer mode is a read-only check. Applying it requires a privileged
Pro action; development and tests do not create that service identity or grant.

| Boundary        | Prepared binding                                                                 |
| --------------- | -------------------------------------------------------------------------------- |
| Helper identity | `_nuz_consul`, distinct from root and ordinary model callers                     |
| Entry           | `/usr/local/libexec/nuzantara-consul-broker`, no arguments                       |
| Release         | Root-owned `/usr/local/lib/nuzantara-consul/releases/<manifest digest>`          |
| Database access | Separate `nuzantara_consul` role restricted to the named Lab/ROS metadata tables |
| Configuration   | Service-owned mode-0600 `/var/db/nuzantara-consul/config.json`                   |
| Grant           | Root-owned mode-0440 UUID file under the fixed protected grants directory        |
| Broker input    | Bounded, closed JSON fields; no command, SQL, path, prompt, or approval payload  |

The database setup is separate from filesystem provisioning. The native broker
requires the existing Research OS and lease schema plus
[migration 307](../../../apps/backend-rag/backend/db/migrations_v2/307_consul_native_broker.sql),
which adds the native resource prefix and completion-generation projection.
The DBA reviews table contents and inherited PUBLIC access before authorizing
the metadata writer role. The installer does not execute SQL or copy an existing
administrator credential. Actual role creation, service identity, immutable
installation, protected grant issuance, and a live broker canary must each have
their own observation before being reported active.

Two fresh isolated launcher contexts on Pro and M5 returned identical
configuration hashes in the recorded config-only checks. No ephemeral path was
normalized away. This permits a candidate pre-issued binding to be compared on
a later launch; it does not preserve authorization automatically. Every launch
discovers again, and every changed runtime/configuration/account/input binding
requires a newly reviewed grant. Model selection grants no OS privileges.

The sudoers entry authorizes the ordinary caller UID, which also hosts the
native process. Tool restrictions on that process are enforced by the native
sandbox; the kernel boundary protects the helper's database credentials and
protected files. It does not make the control channel unreachable to every
process under the caller UID. A grant still authorizes only its exact mission
and single attempt. This increment cannot re-admit a terminal or expired run
under a new grant, and receipt replay after lease expiry needs reconciliation.

## Stages and rollback

| Stage                       | Required observation                                                                        | Advance or rollback behavior                                             |
| --------------------------- | ------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| Local preparation           | Targeted tests, source review, exact bundle/source hashes                                   | Keep existing installed binding unchanged                                |
| Shadow                      | Per-host strict configuration and catalog, no inference effects                             | Refuse unsupported binary, model, effort, or binding                     |
| Staging                     | Isolated PostgreSQL lifecycle tests and immutable helper checks                             | Preserve unknown attempts for reconciliation; do not replay spend        |
| Authorized synthetic canary | Installed UID/role/grant plus one exact native turn, fresh completion fence, stored receipt | Revoke on failure; distinguish local stop from remote status             |
| Wider operation             | Separately scoped effects, runtime/model proof, comparable metrics, and reviewed grants     | Bind the previous verified release while retaining revocations and state |

The new runtime receipts establish only the shadow row. Unit or isolated database
tests and source review do not by themselves establish installed service
identity, a live model turn, or fleet activation. Astra's observed absence prevents
an Astra canary on those older bindings. The 0.153.4 receipts resolve catalog
availability; an actual broker canary still requires installed authority and
fresh admission.

The consumer attempts grant revocation on an invocation/checkpoint exception and
always attempts native local cancellation. Broker transport timeouts preserve
unknown remote outcome. Native interrupt acknowledgment and process termination
are distinct: the earlier M5 experiment observed `rpc_error`, no interrupt
acknowledgment, local group stopped, and `remote_cancelled: null`. That result
must not be upgraded to remote cancellation on another runtime.

The installer rollback verifies and repoints `current` to the prior immutable
release; with no prior binding, it refuses. It preserves grants, configuration,
users, database rows, and revocations. Disable or revoke the current grant before
replacement; rollback must not reactivate expired owners or approvals. Migration
307's rollback refuses while native rows violate the restored synthetic-only
constraint; it never deletes those rows automatically.

The runtime catalog receipts bind the six producer files as collected, before
the subsequent shared adapter callback-order correction. Their exact source
hashes remain historical evidence; they do not claim a run of the final broker
source. Final broker review, database verification, package verification, and
privileged activation are separate receipts. Existing CI selection and the
Autonomous Lab scheduler remain unchanged.
