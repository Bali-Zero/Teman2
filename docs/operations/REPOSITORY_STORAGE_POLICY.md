# Repository storage policy

This document is the source of truth for deciding what belongs in the
Nuzantara repository and what must live outside it. The goal is a predictable
checkout: source and reproducible inputs stay close to the code; runtime state,
generated deliverables, recovery material, and sensitive data do not become
part of the project tree by accident.

## Four storage zones

| Zone                         | Location                                | What belongs there                                                                                                                                                                                                        |
| ---------------------------- | --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Versioned repository         | `nuzantara/`                            | Source, tests, migrations, manifests, small deterministic fixtures, operational scripts, and documentation required to understand or reproduce the system.                                                                |
| Local development state      | ignored paths inside `nuzantara/`       | Installed dependencies and project-scoped tool state that require their conventional path: application `.venv/`, root `node_modules/`, `.worktrees/`, `.mcp-servers/`, IDE state, and `.secrets/`.                        |
| External working data        | `~/Desktop/Nuzantara-External-Data/`    | Large public/reference corpora and other local inputs that are not versioned. Preserve the original repo-relative path below a dated directory; use an ignored symlink only when code still requires the historical path. |
| Archive or sensitive storage | Desktop archive on the appropriate host | Generated artifacts go to `~/Desktop/Nuzantara-Repo-Archive/<YYYY-MM-DD>/`. Client/OSINT/biometric material is Pro-only and goes to an approved Pro location, never to the Air checkout.                                  |

## Decision rule

Keep an item in Git only when at least one of these is true:

1. A clean checkout needs it to build, test, deploy, or understand the system.
2. It is a deterministic source input whose provenance and review history must
   travel with the code.
3. A production contract explicitly requires that exact repository path and no
   external-path or environment-variable contract exists yet.

Everything else is either local development state, external working data, or
an archive. Ignoring a path in Git is not enough: ignored deliverables and
corpora still need an explicit home outside the checkout.

## Canonical external locations

| Material                                                    | Canonical location                                                                                   | Notes                                                                                                                                                                                                      |
| ----------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Generated screenshots, render experiments, one-off reports  | `~/Desktop/Nuzantara-Repo-Archive/<YYYY-MM-DD>/`                                                     | Each dated archive has a README and preserves repo-relative paths.                                                                                                                                         |
| Large non-versioned reference corpus                        | `~/Desktop/Nuzantara-External-Data/<YYYY-MM-DD>/repo-relative/`                                      | Symlinks inside the checkout may preserve legacy code paths. Do not commit them. The Air migration made on 2026-08-06 has its own README and SHA-256 manifest.                                             |
| WhatsApp, OSINT, client documents, or other UU PDP material | Pro only: `~/Desktop/Nuzantara-PII-Quarantine/<YYYY-MM-DD>-<batch>/` or the owning Pro service store | Never copy raw material to Air or a cloud prompt.                                                                                                                                                          |
| WR3 accumulated voice corpus                                | Pro only: `~/Desktop/Zantara-Voice-Corpus/`                                                          | Voice samples are biometric material. Rendering and corpus growth happen on Pro.                                                                                                                           |
| Worktree recovery patches                                   | `~/Desktop/Nuzantara-Repo-Archive/<YYYY-MM-DD>/recovery/.agent-receipts/`                            | The checkout keeps an ignored `.agent-receipts` compatibility symlink because recovery writers still resolve that exact path. Remove the symlink only after those writers gain an external-state contract. |

## Current operational exception

`apps/war-room/output/` is ignored runtime state, but several WR2/WR3 producers,
reviewers, and assemblers still exchange artifacts through that exact path. Do
not move it during general cleanup. First make the output root configurable,
migrate every consumer, and verify an end-to-end render/review cycle. Until
then, path compatibility is more important than cosmetic cleanliness.

## Checks

Run both guards from the repository root:

```bash
# CI contract: all tracked root entries are explicitly allowed
python3 scripts/root_guard.py --check

# Local contract: ignored and untracked root entries are also inspected
python3 scripts/root_guard.py --workspace
```

The workspace check permits only documented development dependencies and tool
state. A handoff note, ad-hoc `drafts/` directory, export, dump, or generated
report at the root fails the check even when Git would ignore it. The
`root-workspace-guard` pre-commit hook runs this mode on every local commit;
CI independently runs the tracked-only `--check` mode.

Before moving a non-versioned item:

1. Search code, workflows, launch agents, and docs for the exact path.
2. Check open processes and active worktrees.
3. Preserve a repo-relative destination and a README in the external archive.
4. Compare file count and SHA-256 manifest before removing the source copy.
5. Re-run both root guards and the narrow consumer tests.

## Contributor handoff

When an external item is needed, do not silently recreate a private copy in the
repo. Read the dated archive README, restore or symlink the documented relative
path, and record any new canonical location in this policy. If the data is
sensitive or the host is Air, stop and route the work to Pro.
