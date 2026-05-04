# Hosting `subhi-tutor-install.sh` as a GitHub Gist

Operator notes for Antonello on how to host the install script so Subhi
can fetch + run it on Day 1.

## Why a gist (and not a repo file)

Subhi needs to download the install script anonymously — no auth, no
clone of the main repo first. A file inside `balizero/nuzantara` (private
repo) requires a PAT for the `curl` to succeed. A **public** gist is
anonymous-readable, so `bash <(curl -sL …)` works on a fresh MacBook
that has nothing installed yet (not even `gh`).

The script content itself does not contain secrets — it prompts Subhi
for the GitHub PAT interactively and accepts ENTER-to-skip. The PAT
travels via WhatsApp out-of-band, never via the gist.

## Step 1: Create gist

From the Pro repo root (`~/Desktop/nuzantara`):

```bash
gh gist create scripts/subhi/subhi-tutor-install.sh \
  --public \
  --desc "Subhi MacBook tutor installer (Bali Zero, $(date +%Y-%m-%d))"
```

Copy the gist URL printed.

## Step 2: Get raw URL

```bash
GIST_ID=<id-from-step-1>
gh api gists/$GIST_ID --jq '.files | to_entries[0].value.raw_url'
```

This raw URL is what Subhi runs:

```bash
bash <(curl -sL '<raw-url>')
```

The raw URL is stable across `gh gist edit` operations — Subhi never
needs to update his bookmark when Antonello pushes a fix.

## Step 3: Test before sending to Subhi

Recommended: dry-run on Antonello's Mini Pro2 (clean macOS account or
test user) to verify the full flow works end-to-end.

```bash
bash <(curl -sL '<raw-url>') 2>&1 | tee /tmp/install-test.log
```

Verify:
- Exit code 0
- No `ERR` lines (red `✗`)
- All 16 steps print an `OK` line (green `✓`)
- `~/zantara-onboarding/.claude/settings.json` has the username
  substituted (no `__SUBHI_USERNAME_PLACEHOLDER__` left)
- If PAT pasted: `chmod` shows `0600` on `settings.json`

## Step 4: Update gist when script changes

Bug fixes or step additions:

```bash
gh gist edit <gist-id> scripts/subhi/subhi-tutor-install.sh
```

Raw URL stays stable. Subhi never updates his bookmark.

## Step 5: Send to Subhi (WhatsApp template, bahasa)

> Halo Subhi 👋
>
> Ini installer untuk MacBook kamu. Run command ini di Terminal pas
> kamu di kantor besok pagi:
>
> ```
> bash <(curl -sL '<raw-url>')
> ```
>
> ~25-30 menit. Saya jaga via WA video call sambil install jalan.
> PAT GitHub saya kirim via WA terpisah (untuk paste di Step 14).
>
> — Antonello

## What the gist is NOT

- **Not** a long-term distribution channel for Bali Zero code. It only
  hosts the installer bootstrap. After Step 12, Subhi has cloned
  `balizero/nuzantara` and uses the main repo for everything.
- **Not** a place for secrets. The script prompts for PAT interactively
  and reads it via `read -r -s` (no echo, no logging). The gist content
  is pure shell logic.
- **Not** the rsync target. Per addendum B, the memory mirror flows
  Pro → Subhi Mac via Tailscale `rsync`, not via gist or git.

## Reference

- Spec: `docs/superpowers/specs/2026-05-04-subhi-tutor-design-addendum-B.md`
- Plan: `docs/superpowers/plans/2026-05-04-subhi-tutor-implementation.md` T6
- Sibling scripts: `scripts/subhi/subhi-memory-mirror.sh`,
  `scripts/subhi/subhi-mirror-publish.sh` (Pro side, separate concern)
