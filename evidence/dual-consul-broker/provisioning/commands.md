# Pro disposable bundle verification

These commands built and checked a disposable bundle under UID 501 on Pro.
They installed no service user, sudoers policy, grant, configuration, or database
role. `verification-final.json` is the selected output of the final checks;
the observed `_nuz_consul` account and installed binding were both absent.

## Exact final build

The M5 source-only archive contained the 74 files listed in
`build-input-manifest.json`. Its SHA-256 was
`58a1155fb7f1cfbd4c1ee4d05351a057670095f26093e7cbfddce2c489255158`.
It was copied to Pro's ordinary-user disposable directory and extracted without
adding any environment, credential, or client-data file.

```bash
# Pro, ordinary user; source-final was created from the reviewed source archive.
cd /tmp/consul-broker-build.5xSE42/source-final
/Users/nuzantara/nuzantara/.venv/bin/python -B \
  infra/conductor/consul-broker/build_bundle.py \
  --repo /tmp/consul-broker-build.5xSE42/source-final \
  --output /tmp/consul-broker-build.5xSE42/release-final
```

Actual successful final output:

```json
{"status": "release_verified", "uid": 501}
{"release_sha256": "ad2fc4b24a11d1eda3798044414a105a4459d905bbfc6dbcafe200edfb72807c"}
```

The bundle contains 1,532 manifest entries, 65 internal Python source files,
official CPython 3.11.15+20260807, and seven pinned wheel dependencies. The full
runtime `SHA256SUMS` and binary assets remain on Pro; only selected source hashes,
provenance, commands, and output are retained here. `source-binding.json` records
the comparison against the final current worktree; it reported no drift.

## Independent offline checks

```bash
/usr/bin/env -i HOME=/var/empty PATH=/usr/bin:/bin \
  /tmp/consul-broker-build.5xSE42/release-final/python/bin/python3 -I -S -B \
  /tmp/consul-broker-build.5xSE42/release-final/verify.py
/bin/bash /tmp/consul-broker-build.5xSE42/source-final/scripts/provision_consul_broker.sh \
  --check --bundle /tmp/consul-broker-build.5xSE42/release-final \
  --sha256 ad2fc4b24a11d1eda3798044414a105a4459d905bbfc6dbcafe200edfb72807c
/usr/sbin/visudo -cf /tmp/consul-broker-build.5xSE42/release-final/control/sudoers
```

All three commands returned zero. The import check used isolated startup after
the bundle moved away from its build path. Native load references remained
inside the bundle or system libraries. This is an ordinary-user import check;
the `--immutable` root-ownership check remains part of the privileged installer.

The exact negative probe is retained as `negative-probe.txt`. It runs the real
entry point with `{}` on stdin and records/blocks network connects or child
process launches with Python audit hooks. The helper refused that malformed,
ungranted request with exit 1; the probe itself returned zero, with no audited
effect attempt and empty stderr.

```bash
# negative-probe.py was copied byte-for-byte from retained negative-probe.txt.
/usr/bin/env -i HOME=/var/empty PATH=/usr/bin:/bin \
  /tmp/consul-broker-build.5xSE42/release-final/python/bin/python3 -I -S -B \
  /tmp/consul-broker-build.5xSE42/negative-probe.py \
  /tmp/consul-broker-build.5xSE42/release-final
```

## Focused local checks and diagnostic history

```bash
/Users/balizero/nuzantara/.venv/bin/python -B -m pytest \
  scripts/tests/test_provision_consul_broker.py -q
/Users/balizero/.local/bin/ruff check infra/conductor/consul-broker/*.py \
  scripts/tests/test_provision_consul_broker.py
/bin/bash -n scripts/provision_consul_broker.sh
/bin/sh -n infra/conductor/consul-broker/wrapper.sh
```

The focused suite passed 25 tests. Ruff and shell syntax passed. No workflow or
general PR test suite was added. Earlier temporary attempts stopped on two
diagnosed issues: unused PBS setuptools data violated the restricted filename
policy; the next check identified missing `rfc8785` and Tcl self-identifiers
mistaken for external load dependencies. Those issues were corrected and tested.
`release-3` passed before the final backend token-counter correction and is
retained only as an older diagnostic artifact; `release-final` is the reviewed
source binding above. No earlier or final bundle was activated.
