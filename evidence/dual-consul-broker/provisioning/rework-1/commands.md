# Rework 1: exact build and offline verification

The original proof remains in the parent directory. This revision supersedes
its `ad2fc4b24a11d1eda3798044414a105a4459d905bbfc6dbcafe200edfb72807c`
release after the native review corrections. No prior artifact was activated.

The source-only input archive had SHA-256
`2864b6b87e25955d579e86ee01360778146f05a2d39bde4d571889a72efe29b2`,
verified after transfer to Pro. `build-input-manifest.json` lists its 75 files.
The runtime closure now contains 66 Python files, including the shared native
canary contract. Both the backend worker and parent reported source freeze
before this build.

```bash
cd /tmp/consul-broker-build.5xSE42/source-rework-1
/Users/nuzantara/nuzantara/.venv/bin/python -B \
  infra/conductor/consul-broker/build_bundle.py \
  --repo /tmp/consul-broker-build.5xSE42/source-rework-1 \
  --output /tmp/consul-broker-build.5xSE42/release-rework-1
```

Actual successful build output:

```json
{"status": "release_verified", "uid": 501}
{"release_sha256": "e17182ca4e2f65ba711431dac3db97d7778a24feeb1cadf69e24258691f4f4c8"}
```

The new manifest contains 1,533 entries. The first installed-mode check correctly
rejected the temporary wheel installation's `site-packages/.lock`, mode `0666`.
The real installer already strips group/other writes in private staging. This
offline rehearsal applied the same symbolic mode normalization to the
ordinary-user temporary bundle, then repeated the check. It changed no file
content and the release digest stayed the same. It performed no `chown`, user
creation, sudoers installation, or database action.

```bash
/bin/chmod -R u-s,g-s,go-w /tmp/consul-broker-build.5xSE42/release-rework-1
/usr/bin/env -i HOME=/var/empty PATH=/usr/bin:/bin \
  /tmp/consul-broker-build.5xSE42/release-rework-1/python/bin/python3 -I -S -B \
  /tmp/consul-broker-build.5xSE42/release-rework-1/verify.py
/bin/bash /tmp/consul-broker-build.5xSE42/source-rework-1/scripts/provision_consul_broker.sh \
  --check --bundle /tmp/consul-broker-build.5xSE42/release-rework-1 \
  --sha256 e17182ca4e2f65ba711431dac3db97d7778a24feeb1cadf69e24258691f4f4c8
/usr/sbin/visudo -cf /tmp/consul-broker-build.5xSE42/release-rework-1/control/sudoers
/usr/bin/env -i HOME=/var/empty PATH=/usr/bin:/bin \
  /tmp/consul-broker-build.5xSE42/release-rework-1/python/bin/python3 -I -S -B \
  /tmp/consul-broker-build.5xSE42/negative-probe.py \
  /tmp/consul-broker-build.5xSE42/release-rework-1
```

The mode guard was executed by extracting the unchanged shell helper functions
before the installer's argument loop and calling only `verify_installed_modes`
against this temporary bundle. All post-normalization checks returned zero.
The negative probe source is retained at `../negative-probe.txt`; it again ran
the real entry with `{}`, observed refusal and no audited network/process
attempts. `verification-rework-1.json` preserves the initial mode rejection as
well as the successful selected outputs. The service identity and installed
binding were still absent.

`source-binding.json` records a new comparison of all 75 input files and the 10
package/test sources against the current worktree, with no drift. Byte hashes
are source/content evidence; the installer's independent mode and ownership
checks remain necessary. The actual root-owned `--immutable` and live rollback
steps remain unexecuted and require the operator's privileged installation.
