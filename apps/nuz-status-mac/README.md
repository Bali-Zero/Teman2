# NuzStatus

Native macOS control surface for Nuzantara operational health.

The app is intentionally thin: it runs `scripts/nuz_status.py` from the repo root,
renders the same checks as the CLI, and exposes only safe automated fixes. It does
not talk directly to Fly, GitHub, SSH, or production data.

## Run

```bash
cd apps/nuz-status-mac
swift run NuzStatus
```

Open in Xcode with:

```bash
xed apps/nuz-status-mac
```
