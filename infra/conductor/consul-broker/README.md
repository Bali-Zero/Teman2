# Pro stdio broker provisioning

This package prepares a concrete privileged installation; it does not activate
it during development. It creates no scheduler, daemon, listener, or model
process. Native inference remains under the ordinary caller UID. `_nuz_consul`
only executes the broker's bounded PostgreSQL verbs from JSON stdin.

The separate-user and root-owned-code pattern reuses
`scripts/provision_zantara_codex.sh`; that existing WA identity is never changed
or reused. Unlike its shared Homebrew venv, this release carries its own Python
and wheel dependencies. `sudo -n -l` was measured to require a password on Pro;
the final reviewed installation therefore requires an operator OS action.

## Fixed interface and protected paths

| Item | Binding |
| --- | --- |
| Caller | `nuzantara`, using `sudo -n -u _nuz_consul` |
| Sudo target | `/usr/local/libexec/nuzantara-consul-broker`, zero arguments |
| Protocol | One bounded JSON request on stdin; broker controls verbs and size |
| Code/interpreter/dependencies | `/usr/local/lib/nuzantara-consul/releases/<SHA256SUMS digest>`; root owned, no group/other writes |
| Active/previous binding | Root-owned `current` / `previous` relative symlinks |
| Configuration | `/var/db/nuzantara-consul/config.json`, `_nuz_consul`, mode 0600 |
| Grant directory | `/var/db/nuzantara-consul/grants`, root:`_nuz_consul`, mode 0750 |
| Grants | `<canonical UUID>.json`, root:`_nuz_consul`, mode 0440; never overwritten |

Configuration has exactly `database_dsn` and `grants_dir`. The latter must equal
the fixed directory above. The DSN uses the new `nuzantara_consul` database role;
it is prepared outside Git and never printed. The production loader rejects
alternative config/grant paths. A UUID selects a preissued grant; callers cannot
supply grant contents or filesystem paths through the wrapper.

## Build before requesting privilege

Run on Pro in a fresh disposable directory, as the ordinary user. The builder
rejects root, Mini, and M5. It uses existing uv **0.12.3**, the official Astral
CPython **3.11.15+20260807** macOS arm64 archive, and the exact SHA-256 pinned in
`build_bundle.py`. These are the same [Python distributions used by uv](https://docs.astral.sh/uv/concepts/python-versions/);
the pin was checked against the [official release metadata](https://api.github.com/repos/astral-sh/python-build-standalone/releases/tags/20260807).
No global Python, environment, service, or credentials are changed.

```bash
# Execute from the reviewed checkout on Pro, with its existing venv.
source /Users/nuzantara/nuzantara/.venv/bin/activate
/Users/nuzantara/nuzantara/.venv/bin/python \
  infra/conductor/consul-broker/build_bundle.py \
  --repo "$PWD" --output /tmp/consul-release-reviewed
```

The builder copies the static internal import closure from `scripts.consul_broker`
(including package initializers), installs only hash-checked wheels from the
scoped lock copied from `requirements-prod.lock.txt`, and dereferences only
contained Python symlinks. It omits PBS's preinstalled pip/setuptools site
packages, which isolated startup does not use. It moves the tree before an isolated import smoke,
checks native library references against bundled/system paths, then reports the
release digest. `provenance.json` records source hashes, asset identity, uv
version, and dependency-lock hash. Review this actual bundle and digest before
any privileged command. Runtime startup ignores caller site packages,
`PYTHONPATH`, cwd imports, and inherited environment.
The installer rejects ACLs on protected directories and removes copied ACLs and
extended attributes before checking the immutable release. Embedded Mach-O
signatures remain in the hash-checked file bytes.

## DBA and installation checklist

1. Confirm Pro local `nuzantara_dev`, migrations 279/306/307, and that the four
   metadata tables contain only the approved receipt/mission material.
2. Review `role.sql`: four named tables and two named sequences, no DDL rights,
   no update/delete of Research OS objects, and no client-table privileges.
   Its PUBLIC-grant assertion aborts if the role inherits broader table access.
   The installer does not connect to PostgreSQL or execute this SQL.
3. A DBA applies the reviewed role SQL and provisions login material through a
   protected procedure. Prepare the mode-0600 config outside Git. Do not use the
   existing administrator, WA broker, or read-only role for this write service.
4. Prepare the preissued, expiring grant bundle through the existing governance
   flow. Check its UUID, scope, frozen review, and revocation semantics.
5. Run the read-only check, then obtain the operator's privileged action on the
   fully reviewed package and digest:

```bash
bash scripts/provision_consul_broker.sh --check
# Hash-only preflight also accepts --bundle PATH --sha256 REVIEWED_RELEASE_DIGEST.
# Operator-only; placeholders refer to already prepared, reviewed artifacts.
sudo /bin/bash scripts/provision_consul_broker.sh --apply \
  --bundle /tmp/consul-release-reviewed --sha256 REVIEWED_RELEASE_DIGEST \
  --config /protected/location/consul-config.json \
  --grant PREISSUED_GRANT_UUID /protected/location/grant.json
```

6. Recheck service UID, root ownership, sudoers with `visudo -c`, and immutable
   import verification. The first protocol check requires an actual preissued
   grant and lease through the existing `admit`/`check` lifecycle; no ungranted
   readiness verb exists. The role
   and grant checks remain authoritative; installing a sudo target grants no
   mission by itself. Native operational effects remain outside this package.

## Rollback

`sudo /bin/bash scripts/provision_consul_broker.sh --rollback` verifies the prior
immutable release and atomically repoints `current`. It preserves configuration,
grants, users, database rows, other brokers, and all retained releases. It does
not revive expired grants or ownership. With no prior binding, it refuses.
For immediate disablement, the operator revokes the relevant grant through the
broker or removes this package's sudoers entry; do not delete shared state.
