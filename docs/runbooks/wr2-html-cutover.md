# WR2 HTML renderer cutover runbook (Canva → HTML/CSS)

> **DO NOT execute the cutover steps until the SHADOW run has proven the HTML lane
> on a throwaway draft AND Antonello approves the live flip (Legge 5 — live client
> delivery).** Until then the HTML worker no-ops (kill-switch OFF) and Canva runs
> unchanged. This runbook is the recorded procedure, gated.

## What the HTML lane replaces
The Canva apply chokepoint: transition `drafts_imaged_facted → drafts_imaged_checked`
is rendered by `com.balizero.wr2.canva-apply`. The HTML lane (`wr2_html_render_apply.py`
+ `com.balizero.wr2.html-apply`) renders the same `drafts_imaged_checked` drafts to
HTML/CSS→PNG, uploads to Drive, and notifies Antonello+Damar over WhatsApp (24h window).

## Pre-flight (before any flip)
1. Migration 222 applied to prod (`drive_url`, `drive_url_shadow`, `lease_heartbeat_at`,
   status CHECK + enum parity). Verify: `SELECT 1 FROM information_schema.columns
   WHERE table_name='war_room_drafts' AND column_name='lease_heartbeat_at';`
2. Deploy worktree synced: `scripts/wr2_html_render_apply.py`,
   `scripts/wr2_html_renderer/*`, `infra/launchagents/com.balizero.wr2.html-apply.plist`
   present in `~/Desktop/nuzantara-deploy`.
3. Pro-local venv `~/Desktop/nuzantara-deploy/.venv-wr2-html` exists; `--selftest` OK.
   **If missing** (it evaporates on every deploy-worktree re-add — scar W81/html-venv):
   `bash scripts/setup_wr2_html_venv.sh` recreates it reproducibly (~3-5 min), then re-run `--selftest`.
4. SHADOW run done on a throwaway draft, Drive output inspected by hand.

## SHADOW run (safe — no WA, no status flip to real)
```bash
# kill-switch ON, shadow ON
psql "$DATABASE_URL" -c "INSERT INTO system_settings(key,value) VALUES('wr2_html_renderer_enabled','true') ON CONFLICT(key) DO UPDATE SET value='true';"
source ~/Desktop/nuzantara-deploy/.venv-wr2-html/bin/activate
WR2_HTML_SHADOW=1 WR2_VISION_REQUIRED=1 DATABASE_URL=... \
  python ~/Desktop/nuzantara-deploy/scripts/wr2_html_render_apply.py --draft-id <throwaway-uuid>
# => status rendered_shadow, drive_url_shadow set, NO WhatsApp. Inspect the Drive folder WR2-SHADOW-<id>.
```

## CUTOVER (real — ONLY after shadow OK + Antonello approval)
1. **Have Antonello + Damar message the Meta number +62 821-3465-159** (opens the 24h
   window — without this the link enqueues but the worker marks it failed + ops alert).
2. **Stop Canva from racing** (do this BEFORE flipping the route, W-finding #9):
   ```bash
   launchctl bootout gui/$UID/com.balizero.wr2.canva-apply
   launchctl disable gui/$UID/com.balizero.wr2.canva-apply
   ```
3. **Flip the supervisor route** in `scripts/wr2_supervisor.py` — change BOTH maps:
   - `("drafts_imaged_facted", "drafts_imaged_checked"): "com.balizero.wr2.canva-apply"`
     → `"com.balizero.wr2.html-apply"`
   - `NONTERMINAL_TO_NEXT_STAGE["drafts_imaged_checked"]: "com.balizero.wr2.canva-apply"`
     → `"com.balizero.wr2.html-apply"`
   (Commit + deploy-pull so the deploy worktree picks it up.)
4. **Bootstrap the HTML LaunchAgent**:
   ```bash
   launchctl bootstrap gui/$UID ~/Library/LaunchAgents/com.balizero.wr2.html-apply.plist
   ```
   (copy the plist from the repo to `~/Library/LaunchAgents/` first)
5. Kill-switch already ON from shadow; ensure `WR2_HTML_SHADOW` is UNSET for real runs.
6. First real carousel: Antonello + Damar receive the Drive link over WhatsApp.

## ROLLBACK (instant)
1. `psql -c "UPDATE system_settings SET value='false' WHERE key='wr2_html_renderer_enabled';"`
   (HTML worker no-ops immediately)
2. Revert the supervisor route to `com.balizero.wr2.canva-apply` + deploy-pull.
3. `launchctl enable + bootstrap com.balizero.wr2.canva-apply`.
Canva path was never modified — it resumes intact.

## Ops alerts (NOT the carousel link — Legge 5)
- 24h window closed at enqueue → Telegram ops alert with draft_id + drive_url, asking to
  re-open the window (recipient messages the Meta number). The link is NEVER delivered via
  Telegram; it lives on Drive and is sent only over WhatsApp.
- render_failed after WR2_HTML_MAX_ATTEMPTS (3) → ops alert.
