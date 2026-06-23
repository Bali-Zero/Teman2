# WR2 Carousel Publishing — Damar Quick Guide

> Bali Zero. One-page workflow. No terminal needed.

---

## What this is

The agent drafts an Instagram carousel for `@balizero0`. You review it in Canva and publish
it on IG. This page tells you how to do that in 5 clicks.

## Daily workflow (5 minutes per carousel)

1. **Open the queue page** in your browser:
   `http://localhost:8765`

   If the page does not load, ask Antonello to start the queue server. The page shows all
   carousels waiting for your review, with the newest at the top.

2. **Click `OPEN IN CANVA`** on the first item.
   This opens the carousel in your Canva editor in a new tab.

3. **Review the slides**. Three options:
   - **Publish as-is** → carousel is good, go to step 4.
   - **Edit some slides** → fix anything you want directly in Canva, then go to step 4.
     (Editing is fine. The agent learns from what you change.)
   - **Reject** → don't publish at all, go to step 5.

4. **Publish on Instagram** as you normally do (export from Canva, post on `@balizero0`).
   When done, come back to the queue page and click **`PUBLISH ON IG`**.
   Paste the Instagram post URL when prompted (e.g. `https://www.instagram.com/p/AbCdEf/`).
   That's it. The carousel is now closed in the queue.

5. **Or click `REJECT`** if you decide not to publish. You'll be asked to pick one reason from:
   - `factually-wrong` — content has wrong facts or wrong regulations
   - `tone-off` — voice doesn't sound like Bali Zero
   - `image-bad` — photos look weird, AI-art fingerprints, off-brand
   - `topic-stale` — the topic is no longer relevant or already covered
   - `legal-risk` — could get us in trouble
   - `client-conflict` — would upset a current client
   - `other` — anything else (you can write a free-text note after)

   Picking the right reason helps the agent learn what NOT to do next time.

---

## What I will NOT ask you to do

- ❌ Open a terminal
- ❌ Type any command
- ❌ Edit any code
- ❌ Manage files or directories
- ❌ Worry about IDs, hashes, paths

---

## States you'll see in the queue

| State | What it means |
|---|---|
| **drafted** (yellow border) | Agent finished, waiting for your review |
| **reviewed** | You opened it but haven't published yet |
| **published** (green border) | You published, carousel is closed |
| **published_with_edits** | You published after editing — **best signal for learning** |
| **rejected** (red border) | You decided not to publish |

---

## What you DON'T have to do

- You don't have to write captions — the agent prepares them in the carousel.
- You don't have to design slides from scratch — they come ready.
- You don't have to track metrics — the system pulls IG saves/shares automatically 24h after
  you publish.
- You don't have to remember rules — the agent applies them.

You only judge: is this carousel ready to go on `@balizero0`? Yes / Edit / No.

---

## What if a carousel is wrong?

It will be sometimes. The agent is learning. Your job is to **catch the wrong ones**.

If you reject a carousel, the agent reads your reason once a week and adjusts. After 4-6 weeks
the rejection rate should drop noticeably.

---

## What if Antonello is not online?

Just queue your decisions normally. Everything keeps working — the agent doesn't need
Antonello to be online for you to publish or reject.

If the queue page won't load (e.g. `localhost:8765` shows error), text Antonello — he can
restart the server. Until then, you can still publish from Canva manually; the queue will
catch up later.

---

## Questions

- Anything wrong, weird, or confusing → text Antonello on Telegram. Screenshot helps.
- This document lives at `~/.claude/skills/bali-zero-brand/_damar-guide-EN.md` if you ever
  need to find it again. (Or just ask Antonello, no need to find files.)

---

*Bali Zero — WR2 Editorial. Last updated 2026-05-08.*
