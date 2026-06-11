# Runbook — WR2 IG-metrics feedback loop (Damar → published)

Closes the loop between "Damar publishes a WR2 carosello on Instagram by hand"
and "the IG-metrics scraper has a published item with a URL to scrape". Before
this, 43 caroselli sat at `applied_ready_for_damar`, `0` were `published`, and
the weekly IG analyst stayed blocked on "insufficient data".

Two strati:

- **STRATO 1** — `scripts/wr2_queue_writer.py`: the reusable writer. Given a
  deterministic `ref_code` + IG URL, advances the matching queue item to
  `published` in the exact shape the scraper consumes. Usable standalone (manual
  CLI) — closes the loop even without WhatsApp.
- **STRATO 2** — `scripts/wr2_damar_publish_consumer.py` + LaunchAgent: polls
  the local wa-mirror Postgres for Damar's WhatsApp messages and drives STRATO 1
  automatically.

Everything is Pro-local (wa-mirror → local Postgres → `human-review-queue.json`).
No PII leaves the machine (Law 2). wa-mirror is the source by Zero's decision;
the only field acted on is a public IG URL.

---

## How Damar uses it

After publishing a carosello on Instagram, Damar sends ONE WhatsApp message from
his number (+628213454726) — wording is flexible, three things must appear:

```
PUBBLICATO WR2-A8274F https://instagram.com/p/XYZ
```

- a publish word (`PUBBLICATO` / `Published`),
- the **ref-code** of the carosello (`WR2-XXXXXX`),
- the **Instagram post URL**.

Word order, extra text, emoji and newlines are tolerated. A bad/missing ref-code
is NEVER mis-applied — it lands in the unmatched queue (below).

### Where does the ref-code come from?

Each carosello has a stable ref-code = `WR2-` + 6 hex of sha1(item_id). List the
pending ones with their codes:

```bash
python scripts/wr2_queue_writer.py list-ready
```

> STRATO 2b (not yet built): auto-notify Damar with the ref-code when a carosello
> reaches `applied_ready_for_damar`. Until then, send him the code from
> `list-ready` (or via the `applied_ready_for_damar` handoff).

---

## Manual operation (STRATO 1 — works today, no setup)

```bash
# find the ref-code
python scripts/wr2_queue_writer.py list-ready

# mark one published (after Damar publishes)
python scripts/wr2_queue_writer.py mark-published WR2-A8274F https://instagram.com/p/XYZ
# -> {"status":"published","ok":true,...}
```

Idempotent: re-running with the same URL is a no-op (`already_published`); a
different URL is refused (`conflict`); an unknown ref-code is `not_found`; a
non-IG URL is `invalid_url` — none of these write.

The scraper picks the item up on its next daily run, ≥24h after `published_at`.

---

## Automatic operation (STRATO 2 — requires activation)

### One-time activation (operator — Antonello)

STRATO 2 is **dormant** until these manual steps (each touches an off-limits /
hot-zone surface, deliberately left to the operator):

1. **Add Damar to wa-mirror** so his messages are captured. Edit
   `apps/wa-mirror/.env` (OFF-LIMITS for the agent): add `+628213454726` to
   `WA_MIRROR_ACCOUNTS`, his name to `WA_MIRROR_ACCOUNT_NAMES`, his email to
   `WA_MIRROR_ACCOUNT_EMAILS`. Then Damar scans the QR once
   (`bash ~/scripts/wa-mirror-launcher/start-one.sh damar --qr`).

   > NOTE (Law 2): mirroring Damar's number captures his WhatsApp conversations
   > into the OSINT-scoped store. This is Zero's explicit choice for this channel.
   > The consumer reads ONLY Damar's rows and acts ONLY on the publish-command
   > pattern; it never forwards message content anywhere.

2. **Dry-run the consumer once** (no writes) to confirm DB reachability + parsing:

   ```bash
   set -a; . apps/wa-mirror/.env; set +a
   apps/backend-rag/.venv/bin/python scripts/wr2_damar_publish_consumer.py --once --dry-run
   ```

3. **Install the LaunchAgent** (polls every 5 min):
   ```bash
   cp infra/launchagents/com.nuzantara.wr2-damar-publish-consumer.plist ~/Library/LaunchAgents/
   launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.nuzantara.wr2-damar-publish-consumer.plist
   launchctl kickstart -k gui/$(id -u)/com.nuzantara.wr2-damar-publish-consumer
   ```

### Kill switch

```bash
echo '{"enabled": false}' > ~/.agent/wr2-damar-consumer.config   # pause (read live each tick)
launchctl bootout gui/$(id -u)/com.nuzantara.wr2-damar-publish-consumer   # full stop
```

### Disambiguation queue

Parsed-but-unresolved commands (wrong ref-code, conflict, etc.) are appended to
`~/.agent/state/wr2_damar_unmatched.jsonl` and the run exits non-zero. Inspect:

```bash
tail ~/.agent/state/wr2_damar_unmatched.jsonl
```

Resolve by hand with the right ref-code via `mark-published`.

### State files

- cursor: `~/.agent/state/wr2_damar_consumer.json` (last processed row id)
- unmatched: `~/.agent/state/wr2_damar_unmatched.jsonl`
- log: `~/logs/wr2-damar-publish-consumer.log`

---

## Guarantees

- **Exact ref-code match** — never fuzzy, never "the only pending one".
- **Never writes on uncertainty** — not_found / conflict / invalid / wrong_state
  all write nothing.
- **Idempotent** — cursor + STRATO 1 no-op/conflict make re-runs safe.
- **Scraper-compatible output** — `engagement_metrics` is cleared to `None`
  (a dict-of-Nones is truthy and the scraper skips truthy em — a latent bug in
  the 43 first-prod items, fixed by the writer).

## Tests

```bash
apps/backend-rag/.venv/bin/python -m pytest \
  apps/backend-rag/backend/tests/unit/scripts/test_wr2_queue_writer.py \
  apps/backend-rag/backend/tests/unit/scripts/test_wr2_damar_publish_consumer.py -q
```
