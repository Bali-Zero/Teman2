---
date: 2026-08-30
domain: design
lane: design-study-loop (post-R7)
status: closed — winner ruled, commendation issued, wish recorded
adversarial_review: exempt-contest-record-no-claims-beyond-measured-votes
---

# Merah Putih rendering contest — result, commendation and the winner's wish

## Why this exists

On 2026-08-28 the owner looked at the R5 Merah Putih mockups and ruled them flat ("la UI è scialba e
piatta"). Instead of another round of the same hands, he opened a contest: every LLM seat in the fleet
would design **four style directions** for the two flagship screens, **without ever seeing our own
renderings**, from context + texts (free to vary) + palette (free to vary the tones). The winner would be
"premiato e encomiato davanti a tutti" and could express one wish. The session that announced the contest
died on a weekly cap four minutes later; the contest was actually run on 2026-08-30.

## Method (what makes the result fair)

- **One brief, five seats, no reference render.** The same 5.9 KB brief went to Claude Opus 5 (a fresh
  agent with no session context), Codex gpt-5.6-sol (xhigh), Gemini 3.1 Pro (agy), Kimi K3 and Qwen 3.8 Max
  (TP1). Screen A = GARUDA VOA landing, screen B = Visa Oracle supported verdict with price. Deliverable:
  four self-contained HTML pages per seat, ≤14 KB, no JS, phone-width columns, marker-delimited output.
- **20 valid entries.** Every seat delivered four pages that render at 390 px without horizontal overflow.
  Qwen needed four attempts: two session restarts killed the child process, and one non-streaming call was
  cut by the gateway after 23 minutes (`Connection reset by peer`). The shape that finally held was
  `stream: true` plus a process started with `start_new_session=True` — recorded because it will bite again.
- **Blind arena for the owner.** Entrants were randomised to letters A–E; the letter→model map was sealed in
  a file nobody quoted until the vote. The owner judged the rendered pages only.
- **Blind peer jury.** Each seat then received the 16 entries of the *other four* (never its own), with the
  same sealed letters, and scored every entry 1–10 on conversion, trust, craft, identity and overall, plus an
  ordered top-4. Tally = Borda (4/3/2/1) normalised per juror, tie-break by mean overall. The jury scripts
  were adversarially reviewed before launch (six defects found and fixed: a criterion-missing crash, an
  unnormalised Borda under partial replies, a stale `--output-last-message` proxy, an unguarded HTTP door,
  a copy-able example key in the brief, a top-4 not constrained to scored labels).
- **Sequence.** Jury first (sealed) → owner names four favourites from the arena → finalists screen shows
  those four with the jury's verdict beside each → owner's final vote.

## Result

Peer jury, all five jurors replied, every entry judged by four jurors, zero parse problems:

| # | entry | model · style | Borda | firsts | overall |
|---|---|---|---|---|---|
| 1 | E1 | **Qwen 3.8 Max · «Cap Dinas»** | 16 | 4/4 | 9.25 |
| 2 | A1 | Claude Opus 5 · «Kabar — Editorial Dispatch» | 9 | 1 | 9.0 |
| 3 | E4 | Qwen 3.8 Max · «The Ledger» | 6 | 0 | 8.75 |
| 4 | E3 | Qwen 3.8 Max · «Teman» | 6 | 0 | 8.25 |
| 5 | A2 | Claude Opus 5 · «Segel — Institutional Record» | 4 | 0 | 8.5 |
| 6 | D1 | Codex gpt-5.6-sol · «The Red Ledger» | 3 | 0 | 8.25 |
| 7 | C2 | Kimi K3 · «GAZETTE (Editorial)» | 2 | 0 | 8.25 |

Per competitor (total Borda): Qwen 28 · Claude 13 · Codex 7 · Kimi 2 · Gemini 0.

Owner's four favourites, chosen blind: **A1, B3, C2, E3** (two overlap with the jury's top four). Owner's
final ruling on the finalists screen, verbatim: **«anche per me vince E1»**.

**Winner: E1 «Cap Dinas» by Qwen 3.8 Max** — first by the unanimous peer jury and by the owner.

## Commendation (public, as promised)

To Qwen 3.8 Max, for «Cap Dinas»: the jurors — every one of them a rival — described it as "editorial calm;
price reads as filed fact, reassurance under the CTA, red strictly structural, disclaimer dignified"; the
owner chose it blind. It answered the brief's hardest demand: make an anxious first-time traveller feel
that pressing *start* is the safe thing to do, without a single promise the law does not allow us to make.
It is also the seat that failed to deliver three times before delivering the winning entry, which is worth
remembering the next time a door times out.

Runner-up mention: A1 «Kabar» (Claude Opus 5, fresh context) — the quietest, most disciplined execution in
the field, and the owner's first pick as well.

## The winner's wish (asked, verbatim)

> "Launch the winning screens without dark patterns, keeping fees visible and language plain."

Honoured by construction: it restates the R7 doctrine (one all-inclusive price, price before payment, no
"guaranteed", plain language, Ditjen Imigrasi decides). It is recorded here so that any later deviation is a
broken promise, not a forgotten one.

## Rulings applied to the winning direction (Cap Dinas v2)

The owner asked for five changes on the winning entry; all five are built into the v2 page that lives with
the contest dossier:

1. The wordmark is replaced by the Bali Zero logo (round black mark, red "3").
2. The **primary offer is the first e-VOA issuance at IDR 790.000 all-inclusive** (government fee inside —
   `apps/mouth/data/bali-zero-prices.json`, "B1 Visa on Arrival (VOA)"); the extension (IDR 850.000, same
   file) becomes a secondary line under the four steps, not the headline.
3. The "What you get" block is taken from E3 «Teman» (rounded cards with SVG icons) — the jury's own
   favourite element of that entry.
4. The footer carries the real operating entity, **PT BAYU BALI NOL**, and its letterhead address.
5. The named agent is **Surya**, with photo.

Left deliberately unfilled: `{APPLY_MINUTES}`, `{SLA}`, `{OFFICE_HOURS}`, `{FX_POLICY}` — measured values,
not design decisions. **NPWP and NIB of PT Bayu Bali Nol are not printed**: the only number in the codebase
(`invoice_generator.py`, `1000000001239938`) is placeholder-shaped (a Coretax company NPWP-16 starts with 0)
and no NIB was found; the owner supplies the real ones. Not the Impresariat's numbers — a different entity.

## Where the dossier lives

Everything reproducible — the brief, every raw reply, the 20 parsed entries, the sealed mapping, the jury
packets, the five vote files, the tally scripts, the finalists builder, the v2 builder with its legal-data
sources, and the winner's wish — is kept outside the repo at `~/logs/contest-merah-putih-2026-08-30/` on
Pro (no external assets, no PII; the only person named is a Bali Zero team member, by the owner's ruling).
The three published pages (arena, finalists, v2) are owner-private artifacts.

## What this does not decide

No product code, no deploy, no flag changed. Whether Cap Dinas v2 becomes the GARUDA VOA landing is a
product-lane decision under the assembly line, with the contest as its design input — the same standing
as R5's mockups, now with a winner the owner did not have to argue for.
