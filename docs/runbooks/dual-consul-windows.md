# Dual-consul windows: preparation and activation boundaries

Status: 2026-09-06. This runbook connects the existing components; it does not
qualify a general-purpose native executor or transfer mission ownership.
Authority: [accepted v4 contract](../architecture/dual-consul/common-contract.md).
The owner ruling in [PR #5821](https://github.com/Bali-Zero/Teman2/pull/5821)
assigns Astra and Fable equal consul powers and reciprocal review. It retains
the existing mechanical gates, including Opus, until explicitly superseded.
Fable is opened by the owner, not auto-routed by this procedure.

## Window arrangement

Start with four windows, not four copies of the complete campaign context:

| Window       | Responsibility                           | Context passed                                                   |
| ------------ | ---------------------------------------- | ---------------------------------------------------------------- |
| Consul lead  | Own the mission and integration decision | Mission ID, scope, acceptance tests, dependencies                |
| Other consul | Independently review frozen work         | Exact tree/artifact hashes, diff, evidence, unresolved questions |
| Worker A     | One disjoint implementation lane         | Owned files, interfaces, bounded task, tests                     |
| Worker B     | Another independent lane                 | Its own files and interfaces; no duplicate task ownership        |

There is one lead per mission and at most four workers **across all windows**.
The ceiling is not a target. Child agents count toward it. Additional windows
do not provide additional authority or automatically share conversation memory.

Create each writer's worktree through the existing broker:

```bash
"$PROJECT_PYTHON" scripts/agent_start.py --lane ops --task-id campaign-lane-a --ttl-min 120
"$PROJECT_PYTHON" scripts/agent_start.py --lane infra --task-id campaign-lane-b --ttl-min 120
```

`PROJECT_PYTHON` must name the existing virtualenv executable on this host.
On Air-M5, the inspected activation script contains an obsolete Pro path;
verify the interpreter instead of relying on that activation script. Open each
writer in its returned worktree. The review window reads the frozen producer
tree and must not edit it. Shared lockfiles require serialized PRs.

Record the mission ID, role, native session ID, exact worktree/branch/head,
owned files, acceptance command, evidence references, and next action in the
handoff. Use only opaque IDs and redacted metadata. Do not copy whole chat
transcripts or client data. Do not resume by choosing a global "latest" file.

When a canonical Research OS handoff exists, validate it with the existing CLI:

```bash
PYTHONPATH=packages/research-os-core "$PROJECT_PYTHON" -m research_os.cli validate \
  --contract conductor_handoff --file "$MISSION_HANDOFF"
```

Schema validity and a local handoff are **not** an ownership transfer. Lab owns
lifecycle; Research OS owns immutable evidence; PostgreSQL owns current grants,
leases, revocations and fences. Resume/takeover requires fresh authoritative
checks. A text handoff cannot enable privileged execution while that broker is
uninstalled. Interactive worktree collaboration remains a distinct mode.

## Prepare the existing text canary

The only native consumer covered here asks for `DUAL_CONSUL_NATIVE_OK`, with
tools disabled. It is not an arbitrary-prompt launcher. Discovery spends no
inference and returns the runtime, config, host and authentication-context
digests, requested model/effort and an unbound thread.

```bash
PYTHONPATH=.:apps/backend-rag:packages/research-os-core "$PROJECT_PYTHON" \
  -m scripts.conductor.consul_native --discover \
  --mission-id "$MISSION_UUID" --model gpt-6-astra --effort medium
```

Keep its exact JSON as a local discovery artifact. All packet-tool paths below
must be absolute, have existing real directories, and contain no symlink
components. On macOS use `/private/tmp`, not its `/tmp` symlink. Outputs must
not already exist and are created mode 0600. Inputs must be bounded JSON.

First obtain the IDs and exact hashes of the existing canonical ActionItem and
RequestedActionSpec. Do not generate placeholder references to get past a gate.
The offline tool checks their shape, not their existence in Research OS.

```bash
PYTHONPATH=.:apps/backend-rag:packages/research-os-core "$PROJECT_PYTHON" \
  -m scripts.conductor.consul_packet prepare \
  --discovery "$DISCOVERY_FILE" --producer astra \
  --action-item-id "$ACTION_ITEM_ID" --action-item-hash "$ACTION_ITEM_HASH" \
  --requested-action-spec-id "$SPEC_ID" --requested-action-spec-hash "$SPEC_HASH" \
  --output "$PREPARED_FILE"
```

This creates only a canonical ActionIntent and its binding. `--producer fable`
supports the reverse producer/reviewer direction; it does not select or launch
a Claude runtime and is not proof that Fable wrote or reviewed anything.

The other consul reviews the **exact intent hash**. Obtain authentic canonical
VerificationReceipt and ApprovalReceipt from their authorized producers, with
the native criteria version and required scope. Never use test fixtures as
real receipts. After that, assemble their content:

```bash
PYTHONPATH=.:apps/backend-rag:packages/research-os-core "$PROJECT_PYTHON" \
  -m scripts.conductor.consul_packet assemble \
  --prepared "$PREPARED_FILE" --approval "$APPROVAL_FILE" --review "$REVIEW_FILE" \
  --grant-id "$GRANT_UUID" --output "$GRANT_FILE"
```

Assembly reuses NativeGrant validation at the current UTC time. Changed
bindings, self-review, mismatched hashes, invalid IDs and expired receipts are
refused. It does not certify issuer authenticity, establish record existence,
check live revocation, install a grant, connect to PostgreSQL or invoke a model.
Only the protected issuer can establish provenance and install the artifact.

## Activation, observation and rollback

Follow [broker activation](../architecture/dual-consul/broker-activation.md)
and the [provisioning instructions](../../infra/conductor/consul-broker/README.md).
Build the isolated bundle on Pro from a reviewed worktree; verify its exact
manifest digest. The dedicated OS identity, metadata-only database role,
protected service configuration and genuine grant are separate prerequisites.
No administrator credential is passed to a model or stored in these packets.

Only after those steps does `consul_native --grant-id "$GRANT_UUID"` admit a
single invocation through the protected Pro helper. The final receipt must
distinguish completed, failed and reconciliation-required outcomes. Never
retry an uncertain invocation merely because the first terminal window died.
Rollback rebinds a previously installed immutable release; it does not revive
revoked grants. No prior release means no rollback target.

The full campaign still requires qualified multi-turn/resume adapters, observed
delegation under the global worker limit, and live ownership-transfer proof.
Passing this canary or the offline packet tests does not establish those claims.
