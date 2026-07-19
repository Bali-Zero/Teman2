# Bali Zero Magazine internal rollout

Status: repo-canon runbook for the internal OpenAI Sites deployment. The magazine is an observatory over existing collectors; it does not replace Intel Lake, MATA GARUDA, Regulatory Watcher, or NotebookLM.

## Runtime surfaces

- Front page: editorial magazine experience for internal readers.
- Research room: sanitized Notebook Insight and collector-backed research jobs.
- Operations room: guarded control plane for rerun, rebuild, quarantine, release, and research refresh.
- Machine ingress: SIWC dispatcher admission plus raw-body HMAC, nonce replay protection, bounded body sizes, and receipt-only outcomes.

## Pro LaunchAgents

Install only on Pro (`nuzantara@Nuzantara`):

```bash
cd /Users/nuzantara/Desktop/nuzantara
plutil -lint infra/launchagents/com.balizero.magazine.morning.plist
plutil -lint infra/launchagents/com.balizero.magazine.breaking.plist
cp infra/launchagents/com.balizero.magazine.*.plist /Users/nuzantara/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) /Users/nuzantara/Library/LaunchAgents/com.balizero.magazine.morning.plist
launchctl bootstrap gui/$(id -u) /Users/nuzantara/Library/LaunchAgents/com.balizero.magazine.breaking.plist
```

Do not install on Air-M5. The wrapper exits unless `hostname` is `Nuzantara` or `MAGAZINE_ALLOW_NON_PRO=true` is set for a local dry-run test.

## Cadence

- Morning edition: `06:15` WITA, after collector jobs. Target human-visible publish by `06:30` WITA.
- Breaking drain: every `600` seconds, meeting the 10-minute objective for qualified official-primary or two-independent-root-source signals.

## Required runtime inputs

Default state root: `/Users/nuzantara/.local/state/bali-zero-magazine`.

- `inputs/morning-YYYY-MM-DD.json`: `magazine-morning-input.v2` with projection paths for `intel-lake`, `mata-garuda`, `regulatory-watcher`, and `notebooklm`.
- `inputs/assets-YYYY-MM-DD.json`: asset intent manifest for morning publish.
- `inputs/breaking-ready.json`: `magazine-breaking-input.v2` for one qualified public candidate.
- `inputs/breaking-assets.json`: asset intent manifest for the Breaking packet.

Secrets are read from environment or Keychain service `bali-zero-magazine`. Never place secret values in plist arguments or logs.

Required publish variables:

- `MAGAZINE_BASE_URL`
- `MAGAZINE_SIWC_BEARER_TOKEN`
- `MAGAZINE_HMAC_KEY_ID`
- `MAGAZINE_HMAC_SECRET`
- `MAGAZINE_HMAC_AUDIENCE`
- `MAGAZINE_AUDIT_PRIVATE_KEY_B64`

Set `MAGAZINE_PUBLISH_ENABLED=false` for dry-run packet generation.

## Phase 0 Sites capability proof

Run this before broadening beyond owner/internal access:

1. Create or reuse the Sites project from `apps/bali-zero-magazine/.openai/hosting.json`; do not call `create_site` if `project_id` is already present.
2. Confirm D1 binding `DB` and R2 binding `MEDIA` with an inert probe version.
3. Deploy the probe privately, then verify effective policy with `get_site`.
4. Configure `custom` workspace access only for the internal Bali Zero workspace.
5. Verify browser auth denies anonymous users and returns `Cache-Control: no-store` for protected HTML and JSON.
6. Verify D1 rollback/CAS by forcing a conflicting publication transaction and confirming no partial head moved.
7. Verify private R2 by uploading one inert image and confirming it is served only through the authenticated media route.
8. Verify SIWC dispatcher admission on machine routes.
9. Verify raw-body HMAC rejection on modified bytes.
10. Verify nonce replay rejection with the same signed request.

If any check fails, do not broaden access and do not arm LaunchAgents.

## Deployed acceptance checklist

- Authenticated reader sees the magazine shell; anonymous reader sees protected shell only.
- All protected responses are `no-store`.
- Custom access denial remains active outside the allowed workspace.
- Morning edition publication is atomic.
- Breaking publication is atomic.
- Story quarantine removes story and associated media immediately.
- Asset rights revocation denies media on the next request.
- Role revocation takes effect on the next request for Research and Operations.
- Audit anchors block promotion on invalid or conflicting checkpoints.
- Quiet and partial morning editions render explicit notices.
- Research jobs are bounded, redacted, and actor-scoped.
- Operations intents are fenced, attested, terminal, and receipt-only.
- Keyboard navigation reaches the front page, Research, and Operations.
- Reduced-motion CSS disables motion-heavy affordances.
- Mobile layout keeps editorial cards, status strips, and action panels readable.

## Rollback

1. Disable launchd schedules:

```bash
launchctl bootout gui/$(id -u) /Users/nuzantara/Library/LaunchAgents/com.balizero.magazine.morning.plist || true
launchctl bootout gui/$(id -u) /Users/nuzantara/Library/LaunchAgents/com.balizero.magazine.breaking.plist || true
```

2. Revert the Sites deployment to the prior private version.
3. Keep D1/R2 data intact for forensics; do not delete buckets or databases during incident response.
