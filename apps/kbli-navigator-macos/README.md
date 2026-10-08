# KBLI Navigator

## Provenance

This is the ONE official home of the native macOS app (owner decision 2026-10-07).

- **Imported** 2026-10-07 as a source-only copy (no git history) of the restored repo, commit
  `e15a920` (branch `candidato/2026-09-17`). The app installed on the fleet was built from its
  parent, `3fa3e9b`.
- **Full-history archive**: `~/kbli-navigator-app` on M5, and the Drive tar
  `gdrive:M5-archive-2026-10-06/logo-tar/kbli-navigator-app.tar`.
- **Not imported** (size or redundancy): `Resources/KBLI_2025_FINAL_CLEAN.json` (37 MB duplicate;
  `build.sh` copies the canonical from `data/source_documents/` at every build), the two
  `Bali-Threshold-2026*.pdf` book PDFs (49 MB each; `build.sh` reads them from `KBLI_BOOK_PDF_DIR`,
  default `$HOME/kbli-navigator-app/Resources`, and fails loudly if absent), `KBLI-2025-Content/*.pdf`,
  every `.build-*` directory, `bali-threshold-images-2026-06-23/`, `BaliZero_RUPS2026_*.pdf`,
  `docs/gates/`, `docs/brand-ref/`, large screenshots. No image over 200 KB was imported except
  the app icon (`Resources/AppIcon.icns`, 920 KB), which is a legitimate bundle input.
- **Build** (needs Xcode, so on Pro; M5 has no Xcode): `bash build.sh --variant internal`.

A native macOS app to navigate Indonesian **KBLI 2025** business codes with their **Bali PMA
moratorium** status, read the *Bali Threshold 2026* book + 20 articles, and chat with **Zantara**,
a KBLI-grounded assistant.

Minimal, clean, immediate. Built for Bali Zero. Runs native on M5 + Pro + Mini.

## Features

- **Search** — 1559 KBLI codes by code or activity (IT/EN/ID, fuzzy: "villa" finds "vila"). Each
  result shows a semantic Bali-status badge (green open / red blocked / grey needs-review).
- **Detail card** — code, title, national PMA vs **Bali status**, an amber **moratorium callout**
  (the 2026 news: open nationally, blocked in Bali), scope, and per-scale licensing.
- **Media** — the book as a native PDF (EN/ID), 20 articles + 13 chapters rendered in-app.
- **Chat** — ask Zantara about a code or the moratorium. Grounded on the real dataset (NLM-style:
  never invents a code or status), fluent like GPT. One brain on the Mini, reached locally or via SSH.

## Build

Requires Xcode-beta (for the SwiftUI macro plugin) on the build machine. No Swift Package Manager.

One codebase, two variants (2026-08-09 app split, `--variant internal|bkpm`, default `internal`):

- **INTERNAL** (`KBLI Navigator - INTERNAL.app`, `com.balizero.kbli-navigator.internal`) — everything
  above: full Media (20 articles + 13 chapters + book), balizero.com links, Chat. Ships to the
  M5/Pro/Mini fleet and the office team zip.
- **BKPM** (`KBLI Navigator - BKPM.app`, `com.balizero.kbli-navigator.bkpm`) — Media keeps the book
  only (2 PDFs + 13 chapters); the 20 articles are excluded from the bundle at build time, not just
  hidden in the UI. Every link/connection to balizero.com is removed. Chat is unchanged. Built on
  demand, never fleet-installed.

The variant is picked at build time and baked into the bundle as the `BZVariant` Info.plist key;
`Sources/Variant.swift` reads it at runtime (`AppVariant.current`) — the one place any view asks
which variant it's running in.

```sh
./build.sh                                # → build/KBLI Navigator - INTERNAL.app (default)
./build.sh --variant internal             # same, explicit
./build.sh --variant bkpm                 # → build/KBLI Navigator - BKPM.app
open "build/KBLI Navigator - INTERNAL.app"
```

## Test

Standalone Swift test runners (no XCTest, no SPM):

```sh
swiftc -framework Combine Sources/Models.swift Sources/KBLIStore.swift Tests/storetest/main.swift -o /tmp/t && KBLI_JSON="$PWD/Resources/KBLI_2025_FINAL_CLEAN.json" /tmp/t
# similarly: Tests/uitest, Tests/mediatest, Tests/runnertest
```

QA snapshot (off-screen, no GUI): `"build/KBLI Navigator - INTERNAL.app/Contents/MacOS/KBLINavigator" --snapshot 55203 out.png`

## Deploy (M5 + Pro + Mini)

```sh
./deploy/install-3mac.sh         # build INTERNAL once, rsync to all 3, re-sign on each (Gatekeeper),
                                 # then content-probe the deployed dataset hash per machine
./deploy/check-fleet.sh          # read-only: canonical vs Resources vs deployed bundles (drift receptor)
```

Run the install on **Pro** (only Pro has Xcode; M5 cannot build). The remote targets are derived
from the driver host (`hostname -s`): Pro installs locally and deploys to `m5 mini`, M5 to `pro mini`,
Mini to `m5 pro`. `./deploy/install-3mac.sh --print-targets` shows them without building. Override with
`KBLI_REMOTE_TARGETS="m5 mini"` (refused, rc=2, if it lists the driver). Set `KBLI_BOOK_PDF_DIR` for the book PDFs.

BKPM is never fleet-installed — it's built on demand (`./build.sh --variant bkpm`) and handed off
outside this repo's deploy scripts.

Both build paths refresh `Resources/KBLI_2025_FINAL_CLEAN.json` from the repo canonical and
commit that refresh — the fleet only ever serves what the monorepo canonical says.

## Team distribution (office Macs, no ssh)

```sh
./deploy/make-team-installer.sh  # → ~/Desktop/KBLI-Navigator-Team-<date>.zip (INTERNAL variant)
```

The zip carries the .app + a double-clickable `Install KBLI Navigator.command` (right-click →
Open the first time) that installs to /Applications and does the Gatekeeper strip+re-sign
locally, plus bilingual EN/ID instructions. Chat tab degrades gracefully off M5/Pro/Mini
(no ssh to the Mini from team machines — by design). Re-run + re-share after every canonical
dataset change.

## Chat backend (one-time, on the Mini)

```sh
python3 deploy/arm-openclaw-zantara-kbli.py   # idempotent: fixes config + creates agent
# then, interactively on the Mini, to enable real GPT-5.5:
ssh mini ; codex login
```

See `PROVENANCE.md` for reuse, data provenance, and the 4-LLM review.
