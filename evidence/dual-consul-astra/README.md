# Astra runtime qualification — 2026-09-06

The owner requested that Astra be added after the earlier runtime catalogs did
not list it. The native consumer already defaults to `gpt-6-astra`; the missing
piece was a current Codex runtime. OpenAI's [official changelog](https://learn.chatgpt.com/docs/changelog)
records Astra support in 0.153.1 and its bundled-picker visibility fix in 0.153.4.

The exact Darwin ARM64 0.153.4 executable is installed side by side on Pro, Mini
and Air-M5 at `~/.local/share/nuzantara/codex/0.153.4/bin/codex`. The launcher
prefers that fixed path and still checks the executable SHA-256 before even
executing `--version` or copying an access-token snapshot. A present but unknown
binary fails closed; it does not fall through to another install. The ordinary
interactive CLI installations, global configurations, and account files were
not replaced. Removing the new side-by-side binary restores selection of the
previous qualified install; grants bound to a different runtime remain invalid.

## Observed results

| Surface | Evidence | Result |
| --- | --- | --- |
| Air-M5 strict hidden-inclusive catalog | `m5-catalog.json.gz` | Astra present; zero inference calls |
| Pro strict hidden-inclusive catalog | `pro-catalog.json.gz` | Astra present; zero inference calls |
| Mini strict hidden-inclusive catalog | `mini-catalog.json.gz` | Astra present; zero inference calls |
| M5 synthetic native invocation and same-mission resume | `m5-invoke.json` | Two completed turns; expected marker hashes; same thread |
| Actual canary consumer, discovery only | `m5-consumer-discovery.json` | Astra/medium binding produced; no inference or broker call |
| Launcher and producer tests | `package.json` | 27 passed; Ruff passed |

All catalog receipts are gzip-compressed exact JSON output from the existing
probe, with their original timestamps and seven-file producer manifests. They
record complete catalogs and confirmed local process-group shutdown. The native
profile remains unchanged: strict config, no tools, no MCP, no inherited service
credentials, and an access-only subscription snapshot without refresh authority.
The package receipt records the official npm archive's independently verified
SHA-512 and the selected executable's SHA-256.

The M5 invocation requested `medium` effort and returned the expected synthetic
marker twice. The runtime thread configuration identifies `gpt-6-astra`;
`identity_evidence` remains `request_observed` and `inference_model` remains null.
The last cumulative usage is 17,859 tokens; do not sum the cumulative counters
from both turns or add reasoning counters already included in output.

This supersedes the earlier **catalog-absence** finding for these new bindings.
Historical 0.147/0.148/0.149 receipts remain valid records of those executions.
This does not install the privileged broker, issue a grant, prove Pro/Mini model
inference, certify remote cancellation, or activate a broker-authorized canary.
No discovery result confers effect authority.
