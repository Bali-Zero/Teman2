# wa-mirror Email Manifest Runbook (FIX 4 — 2026-05-26)

> Operator-side runbook for the `team_member_email` env wiring. Code shipped in
> commit `65f2a47ba` (PR #870) was correct; the only gap was data — accounts.json
> never declared `email` fields and `start-one.sh` never exported the env.

## What changed

| Layer        | Before                                            | After                                                          |
| ------------ | ------------------------------------------------- | -------------------------------------------------------------- |
| Schema       | `whatsapp_message_context.team_member_email`      | unchanged                                                      |
| Code         | `account.email ?? ""` → propagates to SQL $21     | unchanged (shipped 2026-05-26 in `message_capture.ts`)         |
| **Manifest** | `~/.wa-mirror.accounts.json` had no `email` field | each of 9 accounts now declares `email` (8 real, Candra blank) |
| **Launcher** | `start-one.sh` exported only `WA_MIRROR_ACCOUNTS` | also exports `WA_MIRROR_ACCOUNT_EMAILS={...}` JSON map         |
| **Helper**   | `get_account_names_for()` only                    | new `get_account_email_for()` in `_lib.sh`                     |

## Email mapping (verified 2026-05-26 vs CRM `team_members` table)

| Name   | Phone (E.164)   | Email                      | Source                       |
| ------ | --------------- | -------------------------- | ---------------------------- |
| Adit   | +628213454725   | adit@balizero.com          | CRM team_members             |
| Vino   | +628213454727   | vino@balizero.com          | CRM team_members             |
| Sahira | +628213454723   | sahira@balizero.com        | CRM team_members             |
| Krisna | +6282326357501  | krisna@balizero.com        | CRM team_members             |
| Surya  | +628133946856   | surya@balizero.com         | CRM team_members             |
| Asya   | +62881038467246 | asya@balizero.com          | CRM team_members             |
| Ari    | +628213454721   | **ari.firda@balizero.com** | CRM team_members (subdomain) |
| Damar  | +628213454726   | damar@balizero.com         | CRM team_members             |
| Candra | +628213454730   | _(blank)_                  | not in CRM                   |

**Trap**: Ari's email uses `firda` subdomain. If a future operator types
`ari@balizero.com` the CRM join breaks. The manifest is the SSOT.

## Files patched (operator-side, all outside repo)

```
~/.wa-mirror.accounts.json                # +email field on every entry
~/scripts/wa-mirror-launcher/_lib.sh      # +get_account_email_for() helper
~/scripts/wa-mirror-launcher/start-one.sh # +ACCOUNT_EMAILS_JSON capture
                                          # +WA_MIRROR_ACCOUNT_EMAILS env export
```

Backups preserved:

```
~/.wa-mirror.accounts.json.pre-email-2026-05-26
```

(`_lib.sh` and `start-one.sh` are not gitignored but live under `~/scripts/`,
so there's no in-repo backup mechanism. The diffs are documented below.)

## Operator action required to activate

```bash
# 1. Confirm patches landed
grep '"email":' ~/.wa-mirror.accounts.json | head -3
grep -n 'get_account_email_for\|WA_MIRROR_ACCOUNT_EMAILS' \
     ~/scripts/wa-mirror-launcher/_lib.sh \
     ~/scripts/wa-mirror-launcher/start-one.sh

# 2. Smoke-test the helper
source ~/scripts/wa-mirror-launcher/_lib.sh
get_account_email_for "+628213454725"   # expect: {"+628213454725": "adit@balizero.com"}
get_account_email_for "+628213454730"   # expect: (empty — Candra has no email)

# 3. Restart bridges to pick up the new env
bash ~/scripts/wa-mirror-launcher/start-all.sh

# 4. Empirical verification — next direct-chat message should have
#    team_member_email populated:
psql nuzantara_dev -c "
  SELECT team_member_phone, team_member_email, COUNT(*) AS n
  FROM whatsapp_message_context
  WHERE created_at > NOW() - INTERVAL '10 minutes'
  GROUP BY 1, 2;
"
```

## Diff reference for `~/scripts/wa-mirror-launcher/`

`_lib.sh` (after `get_account_names_for`):

```bash
# Returns JSON object {e164: email} for ACCOUNT_EMAILS env (FIX 4 2026-05-26).
# Empty if no email set for that account.
get_account_email_for() {
    local e164="$1"
    python3 -c "
import json
data = json.load(open('$ACCOUNTS_JSON'))
for a in data['accounts']:
    if a['e164'] == '$e164':
        email = a.get('email', '').strip().lower()
        if email:
            print(json.dumps({'$e164': email}))
        break
" 2>/dev/null || true
}
```

`start-one.sh` (after `ACCOUNT_NAMES_JSON=...`):

```bash
ACCOUNT_EMAILS_JSON=$(get_account_email_for "$E164")   # FIX 4 2026-05-26
```

`start-one.sh` (in the env exports block):

```bash
WA_MIRROR_ACCOUNT_EMAILS="${ACCOUNT_EMAILS_JSON:-{}}" \
```

The `${...:-{}}` default means: if Candra (or any future name-only entry)
has no email, the bridge sees `{}` rather than an undefined env, and the
code's `account.email ?? ""` already handles "no entry for this phone"
correctly.

## Why this fix is data-side, not code-side

Code commit `65f2a47ba` (PR #870, FIX 4) introduced:

- `WaMirrorAccount.email?: string`
- `CapturedMessageRecord.teamMemberEmail: string`
- SQL `team_member_email = $21` (split from `$4` phone)
- `account.email ?? ""` default

Code was complete and correct. The gap was that:

1. Manifest never declared the email per account.
2. Launcher never read it from manifest.
3. Bridge therefore always saw `account.email === undefined` → `""` default
   → empty `team_member_email` column on every row.

This runbook is the catch-up for the data + glue layer.

## Sister scars

- `cicatrix-scars.md` § FIX 4 2026-05-26 (code-side)
- Operator-side: this runbook
