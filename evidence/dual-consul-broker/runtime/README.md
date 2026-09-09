# Native runtime qualification: strict configuration and catalog

These observations qualify the exact installed native executables below for the
isolated launcher's configuration and discovery path. They do not establish
served Astra identity, native turn behavior on Pro/Mini, remote cancellation, a
service-UID deployment, or operational effects. No inference call was made.

| Host | Native version | Install layout | Catalog entries, including hidden | Astra available |
| --- | --- | --- | --- | --- |
| Pro (`Nuzantara`) | `codex-cli 0.149.0` | npm native Mach-O executable | 8 | No |
| Mini (`mini-pro2`) | `codex-cli 0.148.0` | Native Homebrew Cask | 7 | No |
| Air-M5 | `codex-cli 0.147.0` | npm native Mach-O executable | 9 | No |

The [Pro](pro-catalog.json), [Mini](mini-catalog.json), and
[M5](m5-catalog.json) catalogs were collected with the same six producer modules.
Each records its executable SHA-256, runtime version, profile hash, configuration
and authentication-context hashes, complete hidden-inclusive catalog, zero
inference calls, and stopped local process group. Provider descriptions and
account values are excluded. A model listed in discovery is not evidence that
an inference response came from that model; Astra was not listed at all.

The launcher accepts only the three observed version/executable-hash pairs in
[`codex_shadow_launch.py`](../../../scripts/conductor/codex_shadow_launch.py).
It refuses unknown bytes before executing `--version` or making an OAuth
snapshot. A different build with a familiar version string is refused. The
resolver preserves the existing direct npm executable and adds only Mini's
observed `/opt/homebrew/Caskroom/codex/0.148.0/bin/codex` path. It does not execute
a Node wrapper, change `PATH` globally, install software, or admit future versions.

All three use the unchanged profile hash
`e20525ea18dfcfa3b9d086543a0e3b6cd609ba1d2f9fadc875c0df89a27f8278`.
Strict configuration validation passed with private temporary `HOME`,
`CODEX_HOME`, and cwd; read-only sandbox; disabled tools, delegation, MCP, hooks,
plugins, skills, apps, and web search; and `shell_environment_policy` with no
inherited environment or configured values. The native process still uses the
ordinary caller UID. This is independent of the protected PostgreSQL helper.

## Primary protocol evidence

Each installed binary generated its own JSON schemas offline with
`app-server generate-json-schema --experimental --out <private-directory>`.
The selected [Pro](pro-schema-selection.json), [Mini](mini-schema-selection.json),
and [M5](m5-schema-selection.json) summaries bind eight generated request schemas
by SHA-256 and name the consumed fields actually present: initialization,
configuration, account read, model list, thread start/resume, turn start, and
turn interrupt. `GetAccountParams` is recorded under the logical
`AccountReadParams` label. These checks establish field presence, not execution
of every RPC or complete behavioral equivalence. Native strict launch plus
config/account/catalog RPCs were exercised separately by the catalog probes.

Schema generation used `env -i`, the already installed direct binary, and a
temporary native home. It did not read account credentials or run inference.
The M5 generator emitted a missing temporary `CODEX_HOME` alias warning and
still exited zero with all eight selected schemas present. No runtime changes
were made to resolve it.

## Binding lifecycle and provenance

The [Pro](pro-config-lifecycle.json) and [M5](m5-config-lifecycle.json) checks read
effective configuration twice in each of two fresh launcher contexts. All four
hashes on each host matched; differing-field lists were empty within and across
processes. The raw configurations were compared in memory and not retained.
This observation does not promise stable configuration or authentication in
future launches. The consumer must discover again and compare the complete
binding before admission and before a native turn. A changed binding needs a
fresh reviewed grant; no path-removing normalization was introduced.

The [Pro](pro-candidate-catalog.json) and
[Mini](mini-candidate-catalog.json) candidate diagnostics preceded the canonical
launcher edit. Temporary source copies admitted only the observed candidate
version; Mini also used its explicit native Cask path. Their distinct producer
hashes are retained and labeled `candidate_diagnostic`. Each candidate compared
the local source auth file before and after and recorded
`source_auth_unchanged: true`. No auth bytes or account identifiers are retained.
That extra comparison applies to the candidate calls; the canonical catalog
receipts do not invent an additional auth-file measurement.

The canonical catalogs bind producer manifest
`4b1b826d87f27204930ce87f9548465f7d054c125931445734e0eede5de88ec5`
at collection. The shared adapter subsequently received the broker callback-order
correction in the same worktree. These historical receipts therefore do not
claim to have run that later broker source or the final integration. The pinned
launcher and its profile remain the ones collected. Final source review and
broker integration evidence have separate scope.

The [qualification receipt](qualification.json) records commands, assembly
time, source hashes, raw selected-artifact origins, successful targeted tests
(`132 passed in 5.94s`), Ruff, and the corrected interpreter/path diagnostics.
Its recording timestamp is not an invented test-start time. JSON presentation
may be normalized; parsed values are checked against the collected files.
The artifact manifest binds the retained files, excluding itself. No raw
reasoning, credentials, full configuration, or client data is retained.
