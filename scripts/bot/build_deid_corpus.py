#!/usr/bin/env python3
"""
De-identify a local WhatsApp export into blind-benchmark fixtures.

Part of the WhatsApp OpenAI-provider shipping mandate (2026-08-15) —
`research/operations/2026-08-15-adr-wa-runtime-openai-provider.md`. Builds
the input corpus for `scripts/bot/wa_blind_bench.py`. This script is a
HARNESS: it is designed and unit-tested against synthetic fixtures, but it
has NOT been run against a real Zantara WA export in this PR (no export
path was available in this session). Confirm the real export's shape
against `_load_records()` before the first live run — and read
"CORPUS ELIGIBILITY" below before trusting ANY output it produces.

PRIVACY CONTRACT (absolute, not a preference — CLAUDE.md §14, SYMBIOSIS
Law 2, UU PDP). Tightened 2026-08-15 by orchestrator corpus gate (a second
veto, after the first on the adapter/wiring):
    - De-identification runs 100% LOCAL. No network call in this file
      other than an OPTIONAL local Ollama pass (`--use-ollama-ner`),
      which now FORCES `OLLAMA_HOST` to loopback in the subprocess
      environment rather than trusting an ambient value — the `ollama`
      CLI honors `OLLAMA_HOST` from the environment, and an unenforced
      "local-only" claim in the earlier draft was exactly that: a claim,
      not a control. See `_ollama_ner_pass`.
    - Reuses `scripts/_redact_pii.py::Redactor` (reuse-first: the repo's
      existing 4-pass fail-closed PII redactor — NPWP/NIB/KITAS/passport/
      phone/email/IBAN/CRM names) rather than hand-rolling a second regex
      set that could disagree with the first.
    - TWO INDEPENDENT scans must both pass before a fixture is eligible:
      (1) `_has_residual_pii` — a narrow regex net for phone/email/long
      digit runs that survived redaction; (2) `_independent_pii_scan` — a
      SEPARATELY authored, broader heuristic (honorific+capitalized-name
      shapes, address markers, ID-document-keyword-near-a-digit-run,
      Title-Case bigrams) that does not share code or patterns with (1) or
      with the Redactor. The orchestrator's point: a single scan (or an
      optional best-effort NER pass that silently no-ops on failure) is
      not enough to call a corpus "safe" — it is enough to call it
      "attempted". `--use-ollama-ner` remains purely ADDITIVE and
      best-effort; it is NEVER load-bearing for the eligibility decision.
    - Data-minimized by construction: fixture `id` is a pure run-local
      sequence number, NOT derived from sender identity or source file
      path (an earlier draft hashed both into the output — a stable
      pseudonymous fingerprint is still personal-data-shaped and was
      unnecessary for a benchmark). No sender identifier and no path
      reference of any kind — hashed or not — is ever written to output.
    - Fails CLOSED: either scan tripping, or the independent scan raising
      an exception (treated as "could not verify", never as "assume
      clean"), drops the record — a dropped fixture costs nothing; a
      leaked one costs everything.
    - Output files are written `chmod 0600` explicitly (not left to
      process umask) — see `_write_jsonl_private`.
    - Default output directory is `.local.`-suffixed and MUST stay outside
      git (see the `*.local.*` pattern already used by
      `scripts/whatsapp_corpus/`) — de-identification is defense in
      depth, not a certification that the output is safe to publish.

CORPUS ELIGIBILITY: `main()` exits non-zero if `--execute` was requested
and zero eligible fixtures resulted (whether because 0 input records were
found, or all of them were dropped) — an empty corpus must never read as a
successful build. This is a harness-correctness property, not a business
guarantee: passing the two automated scans is necessary, not sufficient,
for a corpus to be safe to hand to an external model provider. Per the
orchestrator: no fixture produced here is eligible for use against the
subscription-backed Codex provider without an INDEPENDENT human privacy/legal review pass — this
script cannot and does not certify that on its own.

**R28 ROLE-AWARE / MULTI-TURN CONTRACT (2026-08-18).** Default CLI and
library behavior now requires structured JSONL records with an explicit
`role` (`user` or `assistant`) and a non-empty local `conversation_id`.
Only user turns become benchmark targets; each target carries up to the 12
prior independently redacted/scanned role-labelled turns from the same
conversation. The grouping identifier is held only in memory and is never
serialized, hashed, logged, or written. If any turn fails either privacy
scan, the conversation's accumulated history is cleared before a later
target can be emitted — the builder never bridges over an unverified gap.

Standard `.txt` exports do not encode a safe canonical staff/client role.
They therefore produce zero eligible fixtures in the default mode instead
of guessing from sender names. `--allow-legacy-single-turn` exists only for
reproducing the historical role-blind harness and is an explicit opt-in; its
output cannot settle quality on the real role-aware task.

Usage:
    PYTHONPATH=. python3 scripts/bot/build_deid_corpus.py \\
        --input-dir "$HOME/Desktop/wa-export" \\
        --output-dir research/personal/wa-bench-corpus/fixtures.local

    # Dry run (default): reports counts, writes nothing.
    # --execute: actually writes the fixture files.

Input format (best-effort, see `_load_records`):
    - `.txt` files in the standard WhatsApp chat-export line format:
      "DD/MM/YY, HH:MM - Sender: message text" (one line per message;
      multi-line messages continue on following lines with no
      timestamp-prefix, appended to the previous record).
    - `.jsonl` files: one JSON object per line with `{"text": str,
      "role": "user"|"assistant", "conversation_id": str}` in default
      role-aware mode. Additional fields such as `sender`/`timestamp` are
      ignored and never written.
    Unparseable lines are counted and skipped, never guessed at.
    Sender text is parsed only transiently from `.txt` line headers; it is
    never hashed, stored, used to guess a role, or written to output.

Output: one JSONL file per language bucket (`fixtures_en.local.jsonl`,
`fixtures_it.local.jsonl`, `fixtures_id.local.jsonl`, plus
`fixtures_other.local.jsonl`), each role-aware line
`{"id": str, "language": str, "role": "user", "history": [{"role":
str, "text": str}], "text": str}`. `id` is a pure sequence number and
`history` is capped at 12 prior turns; neither sender nor conversation ID is
serialized.
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import re
import subprocess
import sys
from collections import deque
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

# Reuse-first: the repo's existing fail-closed PII redactor.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from scripts._redact_pii import RedactionError, Redactor  # noqa: E402

logger = logging.getLogger("build_deid_corpus")

# K3 binding correction (Kimi K3 diagnostic, 2026-08-15): the ONLY env vars
# the `ollama run <model>` subprocess (`_ollama_ner_pass` below; the prompt
# itself goes over stdin, not argv — R6-4, round 6) is ever handed — an
# explicit allowlist, not `dict(os.environ)` minus a
# blocklist. `PATH` to resolve the binary and anything it shells out to;
# `HOME` because Ollama's own config/model cache defaults to `~/.ollama`;
# `USER`/`LANG`/`LC_ALL`/`TMPDIR` are conventional POSIX process-hygiene
# vars a CLI tool may reasonably expect. `OLLAMA_HOST` is NOT in this set
# — it's always force-set separately to the loopback address regardless of
# what's ambient (see `_ollama_ner_pass`), so an allowlisted ambient value
# would be redundant at best.
_OLLAMA_SUBPROCESS_ENV_ALLOWLIST = frozenset({"PATH", "HOME", "USER", "TMPDIR", "LANG", "LC_ALL"})

_WA_LINE_RE = re.compile(
    r"^(?:‎)?(?P<date>\d{1,2}/\d{1,2}/\d{2,4}),?\s+(?P<time>\d{1,2}:\d{2}(?::\d{2})?)"
    r"\s*[-–]\s*(?P<sender>[^:]+):\s*(?P<text>.*)$",
)

# --- Scan A: narrow residual-PII net, run after the Redactor -------------
# Deliberately crude and over-inclusive (a bare 8-digit run also matches a
# regulation number like "45/2024" would not, but a KITAS number would) —
# for a benchmark fixture, dropping too aggressively costs nothing.
_RESIDUAL_PHONE_RE = re.compile(r"(?:\+?62|0)8\d{8,11}")
_RESIDUAL_LONG_DIGIT_RUN_RE = re.compile(r"\d{8,}")
_RESIDUAL_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}")

# G1 binding correction (orchestrator corpus gate / Gemini diagnostic,
# 2026-08-15): `_RESIDUAL_LONG_DIGIT_RUN_RE` only matches CONTIGUOUS
# digits — a phone or NIK written with separators (`0812 3456 7890`,
# `3171 2345 6789 0123`, the everyday WA-typing style) has no 8-digit
# contiguous run at all and escaped both this scan AND Scan B's
# `_ID_DOC_NEAR_DIGITS_RE` (which needs a keyword nearby the digits — a
# bare NIK with no "KTP"/"NIK" text next to it escapes that one too).
# Candidates are further filtered in `_has_residual_pii` (digit-count
# threshold + explicit date/amount shape exclusion) rather than trying to
# encode all of that in the regex itself — see `_is_date_or_amount_shape`.
#
# R6-1(b) binding correction (Kimi K3 round-6 review): the separator class
# was missing `,` — the everyday thousands-grouping character in both
# amounts ("2,500,000") AND, critically, in a NIK/phone number someone
# typed with commas instead of spaces/dots ("3171,2345,6789,0123"). That
# exact shape escaped this scan entirely (no space/dot/dash present, only
# commas) before this fix — comma-separated digit runs are now captured
# and routed through the same date/amount-shape exclusion as every other
# separator style, not silently exempt from being scanned at all.
#
# R8-8 binding correction, 2026-08-15 (Kimi K3 round-8 review): `/` used
# to be deliberately excluded from this class — the comment that used to
# sit here argued that including it would make this scan eat every
# timestamp-shaped and citation-shaped string. That reasoning was right
# about the RISK but the tradeoff it chose left a real gap: a NIK/phone
# number typed with slashes instead of spaces/dots/commas
# ("3171/2345/6789/0123") escaped this scan entirely, the same class of
# hole R6-1(b) closed for commas. `/` is now INCLUDED, and the
# over-matching risk the old comment predicted is handled the same way
# amounts already are: `_is_date_or_amount_shape` below now also
# recognizes `DD/MM/YYYY`-shaped (and `DD-MM-YYYY`) dates — not just the
# `YYYY-MM-DD`/`YYYY/MM/DD` shape it already had — each validated against
# the REAL calendar via `datetime.date`, so "15/08/2026" stays exempt
# while "3171/2345/6789/0123" (16 digits, no valid day/month/year
# grouping) does not. A short legal citation ("UU 6/2023",
# "Permenkumham 22/2023") never reaches this regex's own 8-character
# minimum span in the first place (`6/2023` is 6 characters), so it was
# never at risk from this change.
_RESIDUAL_SPACED_DIGIT_RUN_RE = re.compile(r"\d[\d\s.,\-/]{6,}\d")
# Capture groups added (LOW binding correction, 2026-08-15, live-gate round
# 5): the SHAPE alone (`\d{4}[-/]\d{1,2}[-/]\d{1,2}`) matches "6208-15-15"
# just as readily as "2026-08-15" — a NIK/phone number that happens to be
# formatted with date-like separators would pass this regex and be
# EXEMPTED from the PII scan despite month=15 (there is no month 15) making
# it impossible as a real date. The regex now only confirms the SHAPE;
# `_is_date_or_amount_shape` below validates the captured year/month/day
# form a real calendar date before treating a candidate as a genuine date
# (pass 2, live-gate round 5 orchestrator refinement — see that function's
# docstring: a bare 1-12/1-31 range check still accepts calendar-impossible
# values like "2026-02-30", so the year is now captured too and passed to
# `datetime.date()`).
_ISO_DATE_SHAPE_RE = re.compile(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$")
# R8-8 addition, 2026-08-15 (Kimi K3 round-8 review): day-first shape
# (`DD/MM/YYYY` / `DD-MM-YYYY`) — the everyday Indonesian/Italian written
# date order, and distinct from `_ISO_DATE_SHAPE_RE` above by construction
# (that one requires the FIRST group to be exactly 4 digits; this one
# requires the LAST group to be exactly 4 digits and the first two to be
# 1-2 digits each), so a candidate can match at most one of the two, never
# both ambiguously. Deliberately requires a 4-digit year (matching
# `_ISO_DATE_SHAPE_RE`'s own scope) — a 2-digit-year WA-timestamp-style
# date (`DD/MM/YY`) typed inside message TEXT (not the timestamp itself,
# which `_WA_LINE_RE` already strips into its own capture group) is not
# covered; not needed for this fix's scope, since `_WA_LINE_RE`'s own
# 2-digit-year dates never reach `record.text` at all.
_DMY_DATE_SHAPE_RE = re.compile(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$")
_GROUPED_AMOUNT_SHAPE_RE = re.compile(r"^\d{1,3}(?:[.,]\d{3})+$")

# R6-1(a) binding correction (Kimi K3 round-6 review): the amount-shape
# exemption above had no ceiling on TOTAL digit count — a 16-digit NIK
# written with thousands-style grouping ("3,171,234,567,890,123") matches
# `_GROUPED_AMOUNT_SHAPE_RE` exactly as readily as a genuine IDR amount and
# was exempted from the PII scan on shape alone. A NIK is ALWAYS 16 digits;
# a plausible Bali Zero client-facing amount tops out well below that (a
# PMA's >10 miliar per-KBLI investment threshold is 11 digits; one triliun
# rupiah is 13 digits). 13 total digits is chosen as the ceiling: it covers
# amounts up to ~9.999 triliun IDR (far above anything this benchmark's
# fixtures plausibly discuss) while excluding every 14+ digit grouped
# number, which cannot be a legitimate Bali Zero amount and IS the exact
# shape a 16-digit NIK or a padded phone number takes when comma/dot
# grouped. Residual, declared: a NIK-length run that is *itself* grouped
# into exactly 13-or-fewer total digits (impossible for a real 16-digit
# NIK, since grouping only adds separators, never removes digits) cannot
# arise from this shape — the ceiling is exact for NIK, not a heuristic
# guess.
_MAX_EXEMPT_AMOUNT_DIGITS = 13

# R15-1 addition, 2026-08-15 (Kimi K3 round-15 review, HIGH): the amount
# exemption above (`_GROUPED_AMOUNT_SHAPE_RE` + the digit ceiling) was
# CONTEXT-FREE — any thousands-grouped digit run under the ceiling was
# exempted regardless of what surrounded it. A non-contiguous phone number
# typed with dots ("+62.812.345.678", 11 digits) or a bare reference number
# ("123.456.789", 9 digits) matches the amount SHAPE exactly as readily as
# a genuine IDR figure and was silently exempted from the residual PII
# scan — the exact backstop scan this file's own docstring says exists for
# what the primary Redactor misses. Fixed: the amount exemption now
# requires an EXPLICIT currency/amount marker within a short window before
# or after the candidate span — `Rp`/`Rp.`/`IDR`/`USD`/`$`/`€`/`juta`/
# `miliar`/`ribu` (the reviewer's list) plus `rupiah` (the actual currency
# WORD, not just its abbreviations — added because this file's own
# pre-existing innocence fixtures write it out in full, e.g. "budget is
# 25.000.000 rupiah total" (R16-6 correction, 2026-08-15: this comment
# previously misquoted the fixture as "... IDR total" — the actual text in
# `test_build_deid_corpus.py` has always been "rupiah total"); the
# reviewer's list covers abbreviations, this is the same marker CLASS). Per
# this file's own declared fail-closed cost model two functions below
# (`_TITLECASE_BIGRAM_RE`'s comment: "the cost of a dropped legitimate
# fixture is zero, the cost of a leaked name is not") — with NO marker
# present, the span is now treated as PII-shaped (fixture dropped), never
# silently exempted on shape alone.
#
# R15-1b binding correction, 2026-08-15 (orchestrator live-gate on the
# frozen round-15 delivery): the pattern above was a bare substring match — the
# same "guard judges the FORM, not the ENTITY" class this repo's own scar
# catalogue tracks as a recurring family (cicatrix-superscar.md family
# #3). Proven empirically: the everyday Indonesian words "terpisah"
# ("separate") and "terpercaya" ("trustworthy") both CONTAIN the
# substring "rp" and satisfied the marker with no currency meaning
# whatsoever — "nomor terpisah: 62.812.345.678" ("separate number: ...")
# had "terpisah" inside the 30-char window and the amount exemption
# re-opened, letting the pointed phone number survive the residual scan
# again. Over-matching HERE is FAIL-OPEN, not fail-closed like the
# birth-marker case below — a marker that WIDENS an exemption re-opens
# exactly the HIGH-severity hole R15-1 was written to close, so this is
# not cosmetic. Fixed (this round): word-boundary anchored
# (`\b(?:rp\.?|idr|usd|juta|miliar|ribu|rupiah)\b`). R16-5 MICRO
# correction, 2026-08-15 (Kimi K3 round-16 review): the comment that used
# to sit here claimed the two currency SYMBOLS (`$`/`€`) are left without
# `\b` because "`\b` would never match adjacent to one anyway" — FALSE,
# verified empirically: `re.search(r"\b\$", "total$100")` DOES match (a
# word char sits immediately before `$`, which is exactly the transition
# `\b` fires on). The real reason is the opposite of what was claimed: a
# `\b` immediately before `$` requires a WORD character directly
# preceding it, which is exactly what is MISSING in the common client
# layout `" $100"` (a space precedes `$` — space-to-`$` is a
# non-word-to-non-word transition, no boundary there at all, verified via
# `re.search(r"\b\$", " $100")` returning no match) — anchoring `$`/`€`
# would BREAK that ordinary case, not merely be redundant for it.
#
# R16-2 binding correction, 2026-08-15 (Kimi K3 round-16 review, MEDIUM):
# word-boundary anchoring closed the SUBSTRING hole but left a second,
# independent one — the marker only had to appear SOMEWHERE in the
# `_CURRENCY_CONTEXT_WINDOW_CHARS`-char window, not adjacent to the
# candidate span itself. Proven empirically: "biaya Rp 2.500.000, hubungi
# 812.345.678" ("cost Rp 2,500,000, contact 812.345.678") — the ordinary
# shape of a real Bali Zero client message, price and phone number in the
# same sentence — exempted the PHONE NUMBER too, because "Rp" (a genuine,
# correctly-anchored whole-word marker for the AMOUNT earlier in the
# sentence) still fell inside the phone number's own 30-char window. Fixed:
# the marker must now be ADJACENT to the candidate span, not merely
# nearby — the pre-slice must END with a marker (optionally followed by
# light whitespace/`:`/`=` before the span itself, covering "Rp
# 2.500.000" and "Rp1.500.000" alike), OR the post-slice must START with
# one (optionally preceded by the same light separators, covering
# "2.500.000 rupiah"). `_CURRENCY_MARKER_ADJACENT_BEFORE_RE`/`_AFTER_RE`
# below implement this; plain `.search()` anywhere in the window (the
# R15-1/R15-1b approach) is retired. The phone-number scenario above is
# now correctly flagged: "Rp" sits many characters before "812.345.678",
# separated by the amount digits and ", hubungi " — neither adjacency
# check matches, so the marker found for the AMOUNT no longer leaks an
# exemption to an unrelated span later in the same message.
#
# R18-4 binding correction, 2026-08-15 (Kimi K3 round-18 review, LOW):
# `_CURRENCY_MARKER_RE` itself (the symbol that used to be defined here)
# became ARMED DEAD CODE after R17-1 gave the AFTER-side regex its own
# independent literal alternation — every remaining reference to this
# symbol was in a comment or docstring, none in an executable call-site
# (verified: 7 occurrences total, zero outside prose). A live-looking
# symbol that nothing actually runs is worse than no symbol at all here
# specifically, because BOTH of this subsystem's past regressions
# (R16-2b, R17-1) were caused by reusing `.pattern` off this exact
# symbol — keeping it on disk, unused, is an invitation for a THIRD
# reuse-and-regress cycle by a future edit that greps for "the currency
# marker regex" and finds this one first. Fixed: the symbol is DELETED.
# The two live alternations, `_CURRENCY_MARKER_ADJACENT_BEFORE_ALT`/
# `_AFTER_ALT` below, are now each other's own independent source of
# truth — there is no shared base pattern to reuse, by design. Every
# historical comment above/below that named `_CURRENCY_MARKER_RE` as a
# live authority is corrected in place to say "the since-removed
# `_CURRENCY_MARKER_RE`" instead, so the history stays readable without
# citing a symbol that no longer exists.
_CURRENCY_CONTEXT_WINDOW_CHARS = 30
# R16-2: light separators allowed BETWEEN the marker and the span itself
# (a space, or a light punctuation mark like ":"/"="); anything more than
# that (another word, a comma, an unrelated clause) is NOT adjacency.
#
# R18-5 (MICRO, F5, DECLARE-NOT-FIX), 2026-08-15 (Kimi K3 round-18
# review): the separator class `[ \t:=]` does not include `\n` — a
# genuinely multi-line WA message that splits a marker and its amount
# across lines (e.g. the marker at the end of one line, the amount
# starting mid-way into the next after some leading whitespace/indent —
# a shape `_iter_txt_records` can produce, since it joins a WA export's
# continuation lines with `\n`) can lose adjacency and the legitimate
# fixture gets dropped. Same class as R8-5's `\n`-across-lines gap, one
# subsystem over. Direction and cost are the same as every other
# over-match on THIS side of the file: fail-closed, a lost fixture, never
# a leaked one — so per the mandate's explicit disposition, NOT fixed
# this round. Empirical nuance, verified rather than assumed before
# declaring this: Python's `$` anchor has its own special case ("matches
# at end-of-string OR immediately before a single trailing newline that
# IS the last character") that happens to save the narrowest possible
# case — `_CURRENCY_MARKER_ADJACENT_BEFORE_RE.search("totalnya Rp\n")` is
# `True`, because the `\n` there is the pre_context slice's own last
# character. The gap is real, not phantom: it reproduces the moment
# anything (even a single space, from a real export's line-continuation
# indent) follows that `\n` before the digits start —
# `_has_spaced_digit_pii("totalnya Rp\n 25.000.000")` is `True` (wrongly
# flagged as PII-shaped, not exempt) — verified empirically before
# writing this note.
# R16-2b binding correction, 2026-08-15 (Codex gate, found on the R16-2
# adjacency implementation after round 16 (`af7763b21`) had already been
# delivered — MICRO-THAW, same pattern as R15-1b on §22): reusing
# the since-removed `_CURRENCY_MARKER_RE`'s `.pattern` verbatim for the
# BEFORE-adjacency regex regressed the documented "Rp." contract. That
# pattern's "rp\.?" branch was `\brp\.?\b` — trailing `\b` included.
# Appending the adjacency tail `[ \t:=]*$` to THAT pattern breaks on
# "Rp. " specifically two ways:
# (a) if the optional `.` is consumed, the trailing `\b` needs a
# word/non-word transition between `.` and the character after it — but
# `.` and a following space are BOTH non-word, so no boundary fires there,
# and the match attempt fails; (b) if the engine instead stops before
# consuming `.` (matching only "rp", where the p→. transition IS a valid
# boundary), the leftover "." is not itself in `[ \t:=]*` and the `$`
# anchor never reached — also fails. Net effect: "Rp. 25.000.000" was
# flagged (fail-closed direction, but still a regression against the
# explicitly documented "Rp/Rp." marker list) while "Rp 25.000.000" and
# "Rp25.000.000" kept working. Fixed: the BEFORE regex uses its OWN
# alternation, `_CURRENCY_MARKER_ADJACENT_BEFORE_ALT`, where the "rp\.?"
# branch drops its trailing `\b` — safe to drop here specifically because
# the adjacency tail `[ \t:=]*$` already enforces what may follow the
# marker (only light separators up to the span), which is a STRICTER
# right-boundary than a bare `\b` would provide, not a looser one (proven
# empirically: `" harp "`/`" corp "`/`" rpz"` — a marker substring
# embedded in or run into another word — still correctly fail to match,
# since neither the leading `\b` before "rp" nor the trailing tail
# constraint is satisfied for those shapes).
#
# R17-1 SUPERSESSION, 2026-08-15 (Kimi K3 round-17 review, MEDIUM — same
# honest-correction convention as ADR §19): the paragraph directly above
# used to end by declaring the AFTER regex UNCHANGED and safe on the
# reasoning that "the AFTER regex only requires a PREFIX match, with
# nothing constraining what follows 'rp'". That reasoning was WRONG, not
# merely unproven: a prefix match can stop matching BEFORE the optional
# `.`, and once it stops there, "nothing constrains what follows" cuts
# BOTH ways — nothing constrains a legitimate suffix, but ALSO nothing
# constrains an entirely UNRELATED word starting with "rp". Proven
# empirically: post-context " rp. palsu" AND " rp palsu" both matched the
# (still-`\b`-anchored) "rp\.?\b" branch at the very start — the engine
# matches "rp" (p→. or p→space is a valid `\b` either way), and the
# comprehension has no requirement that anything MORE be consumed — so
# "hubungi 812.345.678 rp. palsu" / "... rp palsu" both wrongly exempted
# the phone number, the exact class of fail-open hole R16-2 exists to
# close. The defect was never about the period-consumption mechanics
# R16-2b patched (that fix was correct FOR THE BEFORE SIDE) — it is that
# "rp" alone should never have been an AFTER-side marker at all: in
# Indonesian, currency stated AFTER a number is written "rupiah"/
# "juta"/"miliar"/"ribu"/"IDR"/"USD", never a bare "N rp". Fixed
# structurally, not by patching the period mechanics again: `rp\.?` is
# REMOVED from the AFTER alternation entirely — the AFTER pattern is now
# `(?:idr|usd|juta|miliar|ribu|rupiah)\b|[$€]`, still `\b`-anchored
# throughout (this pattern GRANTS an exemption, so it stays entity-
# anchored per the directional rule R16-1 established) — `_CURRENCY_
# MARKER_ADJACENT_BEFORE_ALT` above is UNAFFECTED and keeps its own
# `rp\.?` branch, since "Rp"/"Rp." legitimately precede an amount.
_CURRENCY_MARKER_ADJACENT_BEFORE_ALT = r"\brp\.?|\b(?:idr|usd|juta|miliar|ribu|rupiah)\b|[$€]"
_CURRENCY_MARKER_ADJACENT_BEFORE_RE = re.compile(
    r"(?:" + _CURRENCY_MARKER_ADJACENT_BEFORE_ALT + r")[ \t:=]*$", re.IGNORECASE,
)
_CURRENCY_MARKER_ADJACENT_AFTER_ALT = r"\b(?:idr|usd|juta|miliar|ribu|rupiah)\b|[$€]"
_CURRENCY_MARKER_ADJACENT_AFTER_RE = re.compile(
    r"^[ \t:=]*(?:" + _CURRENCY_MARKER_ADJACENT_AFTER_ALT + r")", re.IGNORECASE,
)

# R15-3 addition, 2026-08-15 (Kimi K3 round-15 review, MEDIUM): the date
# exemption validates only the CALENDAR (is this a real day that exists),
# never the NATURE of the data — a genuine birth date ("DOB saya
# 15/08/1990") is a real calendar date and was exempted exactly like any
# other date, but a date-of-birth is itself identifying PII (grep-verified
# RC=1: no birth-context handling existed anywhere in this file before
# this fix). Fixed: a birth-context marker within a short window BEFORE
# (not after — a birth date is typically introduced by a preceding label,
# unlike an amount which can be phrased either way) the candidate span
# VETOES the date exemption regardless of calendar validity — the span is
# then treated as PII-shaped, same fail-closed cost model as R15-1 above.
# `lahir` alone also matches inside `tanggal lahir` (a substring), so the
# pattern does not need to separately spell out the longer phrase.
#
# R16-1 binding correction, 2026-08-15 (Kimi K3 round-16 review, MEDIUM —
# ORCHESTRATOR-MANDATE DEFECT, same class as ADR §15's "Orchestrator-
# mandate defect": the R15-1b mandate that ordered word-boundary anchoring
# here analyzed only the exemption-WIDENING direction and applied the same
# fix to this VETO pattern "for entity-not-form consistency", without
# checking whether a veto has the OPPOSITE cost-model asymmetry. It does:
# for a pattern that WIDENS an exemption (the since-removed
# `_CURRENCY_MARKER_RE`, see R18-4 above),
# over-matching is fail-OPEN (bad) and under-matching is harmless — `\b`
# anchoring was correctly protective there. For a pattern that VETOES an
# exemption, the asymmetry flips: over-matching only drops an extra
# fixture (cost zero, this file's own declared model), while
# UNDER-matching is fail-OPEN — a birth-context word that the anchored
# `\b` pattern fails to catch lets a real birth date slip through
# EXEMPTED. Word-boundary anchoring regressed exactly that: proven
# empirically, "kelahiran saya 15/08/1990" ("my date of birth is
# 15/08/1990") — pre-R15-1b, the bare substring "lahir" matched inside
# "kelahiran" ("date of birth" as a noun) and correctly vetoed the
# exemption; post-R15-1b, `\blahir\b` requires "lahir" to be a WHOLE
# word, and "kelahiran" contains "lahir" only as a substring bounded by
# word characters on both sides (no `\b` fires inside a word) — the veto
# silently stopped firing and the date came back EXEMPT. Same reproduced
# for "anak itu dilahirkan 15/08/1990" ("the child was born on
# 15/08/1990"). Fixed: `_BIRTH_MARKER_RE` reverted to a bare substring
# match — no `\b` — since over-matching a veto is free and under-matching
# one is the actual danger; this is now the OPPOSITE choice from the
# since-removed `_CURRENCY_MARKER_RE` above (R18-4) on purpose, not an
# inconsistency to reconcile: **the general rule is directional, not
# "always anchor" or
# "never anchor"** — a pattern that GRANTS/WIDENS an exemption must be
# entity-anchored (over-match = fail-open = dangerous); a pattern that
# VETOES/NARROWS one may over-match freely (over-match = fail-closed =
# free) and must NOT be anchored tighter than the substrings it needs to
# catch. `tanggal lahir` stays covered as before (a substring match,
# either anchored or not).
#
# R16-3 addition, 2026-08-15 (Kimi K3 round-16 review, LOW): the veto only
# ever looked BEFORE the candidate span, on the (undocumented) assumption
# that a birth-context label always precedes the date. Proven false:
# "15/08/1990 itu tanggal lahir dia" ("15/08/1990, that's his date of
# birth") puts the label AFTER the date — the pre-only veto missed it and
# the date came back exempt. Fixed: the veto now checks a
# `_BIRTH_CONTEXT_WINDOW_CHARS`-char window on BOTH sides of the span (an
# OR, either side vetoes), same asymmetric-cost reasoning as R16-1 above —
# a birth marker found on either side and wrongly vetoing an unrelated
# date still only costs a dropped fixture, never a leaked one.
#
# R17-2 addition, 2026-08-15 (Kimi K3 round-17 review, MEDIUM): the
# marker vocabulary itself was incomplete — "birthday"/"b-day" (English)
# and "ulang tahun"/"ultah" (Indonesian, both meaning "birthday") contain
# none of the tokens above. Proven empirically: "my birthday is
# 15/08/1990", "ultah saya 15/08/1990", and "ulang tahun 15/08/1990" all
# came back exempt. Fixed, same directional rule as R16-1 (a veto pattern
# may over-match freely, so widening the vocabulary is always safe here):
# "date of birth" is DROPPED as its own alternative and replaced by the
# more general "birth" — "birth" is already a substring of "date of
# birth"/"birthday"/"birthdate", so this is a strict widening, not a
# narrowing (verified: "date of birth" still matches, via "birth"); "dob"
# is kept as its own token since it does NOT contain "birth" as a
# substring (it is an acronym, not a shortened spelling of the word).
# "ulang tahun"/"ultah"/"b-day" added as new literal alternatives.
#
# R18-2 addition, 2026-08-15 (Kimi K3 round-18 review, MEDIUM): still
# more vocabulary gaps — "bday" (no hyphen, distinct spelling from
# "b-day", which does NOT contain "bday" as a substring — both are
# needed), "d.o.b." (with periods, distinct from the "dob" token — the
# periods make it a different literal, not a substring match), and the
# Italian bucket (this corpus's `_LANG_MARKERS` includes `it`, so Italian
# is in-scope): "compleanno" ("birthday"), "nascita" (covers "data di
# nascita" = "date of birth", same substring-coverage logic as "birth"
# covering "date of birth"), and "nato"/"nata" (Italian "born",
# masculine/feminine). Proven empirically: "my bday 15/08/1990", "d.o.b.
# 15/08/1990", "compleanno 15/08/1990", "nato il 15/08/1990" all came
# back exempt before this fix. Same directional rule as R16-1/R17-2 (a
# veto pattern may over-match freely): "nato" as a substring will also
# match inside unrelated Italian words containing it (e.g.
# "coordinato") — declared, not a defect, since over-matching this VETO
# only costs a dropped fixture, never a leaked one.
_BIRTH_MARKER_RE = re.compile(
    r"lahir|ttl|dob|d\.o\.b|birth|born|bday|b-day|ulang tahun|ultah|compleanno|nascita|nato|nata",
    re.IGNORECASE,
)
_BIRTH_CONTEXT_WINDOW_CHARS = 40

# --- Scan B: independent, separately-authored heuristic -------------------
# Deliberately does NOT reuse any pattern from Scan A or from
# `scripts/_redact_pii.py` — the point of an independent scan is that it
# can catch what the first scan's specific blind spots miss, which it
# cannot do if it shares those blind spots.
#
# G2 binding correction (orchestrator corpus gate / Gemini diagnostic,
# 2026-08-15): both patterns below were CASE-SENSITIVE against literal
# Title-Case marker words ("Ibu", "Jl.", ...) — real WhatsApp chat is
# overwhelmingly lowercase ("ibu siti", "jl. sunset road"), so the
# original patterns matched almost nothing on real export text. Both now
# carry `re.IGNORECASE`. Verified empirically (not just reasoned about)
# BEFORE applying, on both axes: (a) guilt — `"ibu siti tinggal di jl.
# sunset road"` now matches both; (b) innocence — the existing clean-
# message fixtures ("Ciao, quanto costa il KITAS investor?", "Berapa
# biaya untuk PT PMA?", "How long does the visa process take?") still
# match NEITHER pattern under IGNORECASE, because both patterns anchor on
# a fixed, small marker-word alternation (honorific titles / street-type
# words) — case-insensitivity widens WHICH CASE the marker word can
# appear in, not WHAT counts as a marker.
#
# G2 CORRECTION, 2026-08-15 (Kimi K3 round-18 review, discovered while
# fixing R18-1, honest-correction convention as §19/§23): the paragraph
# above's closing claim — "case-insensitivity widens WHICH CASE the
# marker word can appear in, not WHAT counts as a marker" — was FALSE for
# `_HONORIFIC_NAME_RE` specifically, undetected until now. `re.IGNORECASE`
# is a GLOBAL compile flag: it also made the name-arm's `[A-Z]` character
# class match lowercase letters, not just the marker-word alternation —
# verified empirically against the PRE-R18-1 pattern:
# `_HONORIFIC_NAME_RE.search("makasih pak sudah bantu")` was already
# `True` before any R18 change, an over-match the G2 author never
# intended or noticed (the marker-word case DID widen as documented, but
# the name-shape requirement ALSO silently widened as an unnoticed side
# effect). R18-1 below corrects this as part of its own fix.
#
# R18-1 binding correction, 2026-08-15 (Kimi K3 round-18 review, MEDIUM):
# "ibu.siti rahayu" / "pak.budi santoso datang" (a dot-elided honorific +
# lowercase name, a real WA-typing shortcut) passed BOTH scans. Two
# CUMULATIVE causes, not one: (a) the mandatory `\s+` separator rejected
# the dot-attached, no-space shape entirely; (b) even fixing (a) alone is
# not enough to also satisfy the required innocence behavior below,
# because of the G2 CORRECTION above — the name-arm's IGNORECASE-widened
# `[A-Z]` was already accepting lowercase names on the spaced branch, so
# a naive separator-only fix would ALSO make "makasih pak sudah bantu"
# match (verified empirically), which must NOT happen: an honorific
# marker followed by an ordinary lowercase word (not a name) is extremely
# common casual Indonesian ("makasih pak", "iya bu", "gimana pak") and
# firing on all of it would make this detector nearly useless. Fixed with
# TWO branches, not a single separator tweak: (a) a NEW dot-attached
# branch, `\.\s*[A-Za-z][a-zA-Z'’-]{2,}`, allows a LOWERCASE name but only
# when the literal dot is present — the dot-attachment itself is the
# distinguishing signal of name elision (nobody writes "pak.sudah" to
# mean the common word); (b) the EXISTING spaced branch,
# `\.?\s+[A-Z][a-zA-Z'’-]{2,}`, is made GENUINELY case-sensitive on the
# name-arm via Python's scoped inline flag `(?i:...)` around ONLY the
# marker-word alternation — `re.IGNORECASE` is no longer passed as a
# global compile flag, so `[A-Z]` now means what it always claimed to
# mean. Marker-word case-insensitivity (the G2 intent) is fully
# preserved; only the accidental name-arm widening is removed.
#
# ADDENDUM, 2026-08-15 (Codex pre-freeze gate on this round's own
# implementation, integrated before commit): the two `Sig\.`/`Sig\.ra`
# alternatives baked their own literal dot INTO the marker token — with
# the new dot-attached branch also requiring ITS OWN leading `.`,
# "Sig.Rossi" would need TWO literal dots in the input to match via the
# `Sig\.` token (none exist), losing that shape entirely. Fixed: the dot
# moves OUT of the token and becomes the branch's own separator —
# `Sig(?:\.ra)?` (bare "Sig" matches "Signore" abbreviated; the optional
# `.ra` suffix covers "Sig.ra" = "Signora"). Verified empirically, not
# assumed, including the backtracking edge cases: "Sig.Rossi" matches via
# bare "Sig" + the dot-attached branch consuming ".Rossi"; "Sig.ra Rossi"
# matches via the full "Sig.ra" token (tried first, greedy) + the spaced
# branch on " Rossi" — NOT mis-parsed as "Sig" + "." + "ra" (the
# dot-attached branch's own `{2,}` minimum rejects "ra", only 2 characters,
# before reaching " Rossi"); "Sig.raffaele" still matches too, via
# backtracking to bare "Sig" once the greedy "Sig.ra" + spaced-branch path
# fails (no whitespace follows "Sig.ra" in "Sig.raffaele").
#
# R19-3 binding correction, 2026-08-15 (Kimi K3 round-19 review, LOW):
# the dot-attached branch described above is EXTRACTED out of this
# regex as of this round — moved to its own
# `_HONORIFIC_DOT_ATTACHED_CANDIDATE_RE` + `_has_honorific_dot_attached_name`
# further below (after the stopword frozenset both it and
# `_has_honorific_spaced_lowercase_name` share is defined), so it can
# carry the same stopword guard its spaced-lowercase sibling already
# has — see that pair's own comment for the inconsistency this closes.
# `_HONORIFIC_NAME_RE` below is now the SPACED-TITLECASE branch only;
# every paragraph above describing "the dot-attached branch" is
# historical narration of this pattern's PRIOR combined form, left
# intact rather than rewritten, per this file's own convention for
# correcting prior-round prose.
#
# R20-3 binding correction, 2026-08-15 (Kimi K3 round-20 review, LOW):
# the separator between the marker and the name allowed only an OPTIONAL
# LITERAL DOT (`\.?`) before the mandatory whitespace — real WA
# messages routinely punctuate an honorific with a colon or comma
# instead ("pak: Budi Santoso", "pak, Budi Santoso ok"), which this
# separator rejected entirely. Fixed: `\.?` widened to `[.:,]?` — any ONE
# of dot/colon/comma, still optional. This is a DETECTOR widening
# (grants nothing new to an EXEMPTION), so free under the R16-1
# directional rule.
#
# R20-3b micro-disposition, 2026-08-15 (Codex gate, in-flight during
# round 20 — MICRO-THAW, same pattern as R15-1b/R16-2b/R18-1b/R19-1b):
# F3's own finding text named "colon/HYPHEN-after-honorific" explicitly,
# but the delivered separator class omitted the hyphen — proven:
# "pak- budi santoso" and "bu- besok ya" both passed undetected. Fixed:
# the hyphen added to the class, `[.:,]?` → `[.:,-]?` (literal, no
# escape needed — a hyphen at the END of a character class is always
# literal in Python `re`, never a range operator; `ruff` confirmed
# clean on this form). Same DETECTOR-widening, free-under-R16-1
# reasoning as the rest of R20-3.
_HONORIFIC_NAME_RE = re.compile(
    r"\b(?i:Bapak|Ibu|Pak|Bu|Tuan|Nyonya|Sig(?:\.ra)?|Mr|Mrs|Ms|Dr)"
    r"[.:,-]?\s+[A-Z][a-zA-Z'’-]{2,}",
)

# R18-1b micro-disposition, 2026-08-15 (orchestrator live-gate finding on
# the frozen round-18 delivery — attribution: the gate, not Kimi).
# R18-1(b)'s scoped case-sensitivity fix above correctly closed the
# marker-followed-by-ordinary-lowercase-word over-match
# (`_HONORIFIC_NAME_RE` used to fire on ANY honorific + ANY lowercase
# word) but in doing so also closed the spaced-lowercase NAME case
# entirely — the single most common real WA shape: honorific + space +
# an all-lowercase name with no dot ("ibu siti rahayu", "pak budi
# santoso datang"). Verified empirically:
# `_independent_pii_scan("tolong ke ibu siti rahayu besok")` returns
# `[]` under R18-1's fix, though the SAME text matched (via the
# pre-R18-1 accidental global-IGNORECASE over-match) before it. This
# file's own cost model — "a dropped fixture costs zero, a leaked name
# does not" — means the pre-R18-1 behavior was on the SAFE side of this
# specific trade; R18-1 traded that safety for corpus utility (the
# "makasih pak sudah bantu" innocence requirement) without naming the
# fail-open residual it opened.
#
# Honesty note on the root cause: R18-1's own innocence requirement was
# correct for utility — a detector that fires on every honorific
# followed by any ordinary word is useless — but the right resolution is
# neither "flag every honorific+word" (the pre-R18-1, useless-detector
# behavior) nor "only flag titlecase/dot-attached" (R18-1's new,
# name-losing behavior). It needs a THIRD branch with a STOPWORD GUARD,
# which inverts the direction of the residual back onto this file's safe
# side: an unrecognized word after the marker (names are, by
# definition, not members of a short closed vocabulary) FLAGS — cost is
# a dropped fixture, free under the cost model; only a marker followed
# by a KNOWN common non-name word is exempted — cost is an over-drop,
# also free. Implemented as plain code around the match
# (`_has_honorific_spaced_lowercase_name` below) rather than folded into
# the regex itself — a pattern expressing "match this alternative UNLESS
# the captured group is one of N literal words" is a much harder read
# than a frozenset membership check.
#
# R19-1 binding correction, 2026-08-15 (Kimi K3 round-19 review, HIGH):
# R18-1b's guard above judged ONLY the FIRST word after the honorific —
# a single bridging stopword shields the real name that follows it.
# Proven: "pak minta budi santoso datang" and "ibu tolong siti rahayu"
# both passed BOTH scans entirely under R18-1b's single-word guard
# ("minta"/"tolong" is the checked word, is in the stoplist, and the
# guard stopped there without ever looking at "budi santoso"/"siti
# rahayu" behind it) — a fail-open regression in the very fix meant to
# close a fail-open hole. Fixed under the ADJACENT-PAIR rule: look at
# the next ~4 words after the honorific (any case, matching this file's
# other positional heuristics like `_ID_DOC_NEAR_DIGITS_RE`'s window),
# and flag if any TWO CONSECUTIVE words in that window are BOTH
# lowercase AND BOTH outside the stoplist — Indonesian names
# characteristically come in pairs (given name + family name: "budi
# santoso", "siti rahayu"), so requiring adjacency (not just two
# non-stopwords anywhere in the window) keeps the detector anchored to
# that shape rather than degrading into "any two content words nearby".
# Verified empirically against every case the mandate named: the two
# guilt scenarios above now flag (the pair sits one word past the
# bridging stopword); "makasih pak sudah bantu" stays unflagged ("sudah"
# is a stopword, so the only candidate pair (sudah, bantu) fails on its
# first member); "pak tolong kirim" stays unflagged (same reasoning,
# "tolong" fails the pair); the pre-existing R18-1b guilt cases ("pak
# budi santoso datang", "tolong ke ibu siti rahayu besok") are
# unaffected, since their name pair was already adjacent to the marker.
#
# R19-1b micro-disposition, 2026-08-15 (Codex pre-freeze gate on this
# round's own R19-1 implementation, integrated after round 19
# (`037d697c9`) had already been delivered — MICRO-THAW, same pattern as
# R15-1b/R16-2b/R18-1b). The pure ADJACENT-PAIR rule above closed the
# bridging-stopword hole but introduced its OWN declared residual —
# "pak budi ya" stayed unflagged, because "budi" (the real, single name
# word) had no adjacent non-stopword partner anywhere in the window.
# That residual is UNNECESSARY: it exists only because the pair rule was
# applied uniformly, even to the FIRST word right after the marker,
# where R18-1b's original single-word logic was already correct and
# never needed replacing — only the CASE where that first word is itself
# a stopword ever needed a smarter rule. Corrected to TWO-MODE
# semantics, which eliminates the "pak budi ya" residual entirely
# without reopening the bridging-stopword hole R19-1 closed: (a) if the
# word IMMEDIATELY after the honorific is a valid non-stopword candidate,
# that single word suffices to flag — this is exactly R18-1b's original
# rule, restored for this specific position; (b) only when that first
# word is NOT a qualifying candidate (a stopword, or too short/not
# lowercase to be a name) does the ADJACENT-PAIR rule from R19-1 apply,
# scanning the rest of the window for two consecutive non-stopword
# candidates. Verified empirically against the full case set: "pak budi
# santoso"/"pak budi ya" both flag via mode (a) (the residual is closed —
# "budi" alone, as the immediate first word, is now sufficient); "pak
# minta budi santoso"/"ibu tolong siti rahayu" still flag via mode (b)
# (the leading stopword disqualifies mode (a), and the pair "budi
# santoso"/"siti rahayu" behind it satisfies mode (b)); "pak tolong
# kirim"/"makasih pak sudah bantu" stay unflagged (mode (a) fails on the
# leading stopword, and mode (b) finds no adjacent pair — only one
# candidate word follows). Declared residual, STRICTLY NARROWER than
# R19-1's own (inherent to mode (b), the only case left needing a pair
# at all): a bridging-stopword followed by exactly ONE name word and
# nothing else that qualifies — "pak minta budi" (nothing follows
# "budi") or "pak tolong siti ya" (only a stopword follows "siti") —
# still escapes, since mode (b) never fires on a single candidate.
#
# R20-1 note, 2026-08-15 (Kimi K3 round-20 review, MEDIUM): the two-mode
# scan below is now SHARED with the dot-attached branch
# (`_has_honorific_dot_attached_name` further below) via
# `_has_honorific_name_after_marker` — see that function's own comment
# and `_HONORIFIC_DOT_MARKER_ONLY_RE` for why the dot branch needed the
# same mode (b) mirror.
#
# R20-3 note, 2026-08-15 (Kimi K3 round-20 review, LOW): same
# light-punctuation widening as `_HONORIFIC_NAME_RE` above (`\.?` →
# `[.:,]?`), for the same reason — "pak: budi santoso"/"pak, budi
# santoso ok" previously escaped this marker-only regex entirely (no
# match at all, so the whole two-mode scan never ran for those
# messages). Declared, INTENDED side effect: "bu, besok ya" (the R18-1b
# structural-innocence fixture) now REACHES this scan — it stays
# unflagged via the stopword guard on "besok" instead of via the comma
# blocking the match entirely; the verdict is unchanged, only the
# mechanism is, per the mandate's explicit callout — see the R20-3 note
# on `test_innocence_no_adjacent_non_stopword_pair_not_flagged`'s
# docstring (R20-4 below).
#
# R20-3b micro-disposition (Codex gate, in-flight during round 20 — see
# `_HONORIFIC_NAME_RE`'s own R20-3b comment for the full derivation):
# hyphen added to this separator class too, `[.:,]?` → `[.:,-]?` — "pak-
# budi santoso" previously escaped this marker-only regex entirely.
_HONORIFIC_MARKER_ONLY_RE = re.compile(
    r"\b(?i:Bapak|Ibu|Pak|Bu|Tuan|Nyonya|Sig(?:\.ra)?|Mr|Mrs|Ms|Dr)[.:,-]?\s+",
)
# R21-2 binding correction, 2026-08-15 (Kimi K3 round-21 review, LOW):
# this regex (then named `_HONORIFIC_DOT_MARKER_ONLY_RE`) required a
# LITERAL DOT (`\.\s*`) between the marker and the name — real WA
# messages punctuate this no-space-before-punctuation shape with a
# comma/colon/hyphen too, exactly as `_HONORIFIC_NAME_RE`/
# `_HONORIFIC_MARKER_ONLY_RE` above were already widened to accept
# (R20-3/R20-3b), but that widening was never carried to this sibling
# regex. Proven: "pak,budi santoso ok", "pak-budi santoso", and
# "pak:budi santoso" all passed undetected. Fixed: `\.` widened to
# `[.:,-]` — any ONE of dot/colon/comma/hyphen, still MANDATORY (this
# branch's entire purpose is "punctuation glued directly onto the
# marker, no space before it" — an OPTIONAL punct here would just
# duplicate `_HONORIFIC_MARKER_ONLY_RE`'s spaced branch). Renamed
# `_HONORIFIC_DOT_MARKER_ONLY_RE` -> `_HONORIFIC_ATTACHED_MARKER_ONLY_RE`
# (and every function built on it, "dot-attached" -> "attached")
# because "dot" no longer describes what it matches; per this file's
# convention, the historical narration above describing the R19-3/R20-1
# rounds that CREATED the old name is left intact (it correctly
# describes what those rounds did AT THE TIME), while the docstrings
# directly attached to the renamed symbols below — which describe LIVE
# behavior, not history — are updated in place. Verified empirically:
# the three guilt scenarios above now flag; "bu,tolong kirim" and
# "pak-sudah bantu" (comma/hyphen analogues of the existing
# stopword-guard innocence fixtures) stay unflagged, same mechanism as
# the pre-existing dot-form innocence cases.
_HONORIFIC_ATTACHED_MARKER_ONLY_RE = re.compile(
    r"\b(?i:Bapak|Ibu|Pak|Bu|Tuan|Nyonya|Sig(?:\.ra)?|Mr|Mrs|Ms|Dr)[.:,-]\s*",
)
_HONORIFIC_FOLLOWING_WORD_TOKEN_RE = re.compile(r"[A-Za-z'’-]+")
_HONORIFIC_NON_NAME_STOPWORDS = frozenset(
    {
        "sudah", "saja", "ya", "juga", "bisa", "mau", "tolong", "terima",
        "kasih", "makasih", "minta", "boleh", "nanti", "besok", "ini",
        "itu", "yang", "dulu", "dong", "deh", "kok", "sih", "belum",
        "lagi", "aja", "gak", "tidak", "jangan", "harus", "sedang",
        "masih", "baru", "mohon", "silakan",
    },
)
_HONORIFIC_FOLLOWING_WORDS_WINDOW = 4
# R21-3 binding correction, 2026-08-15 (Kimi K3 round-21 review, MEDIUM):
# mode (b)'s pair-scan used to run over a FIXED first-N-words window
# measured from the marker itself — a STACK of multiple leading
# bridging stopwords ("pak minta tolong dong budi santoso") consumes
# that whole window before the scan ever reaches the real name pair.
# Proven: with the pre-R21-3 fixed window, "pak minta tolong dong budi
# santoso" passed undetected (only "minta","tolong","dong","budi" fell
# inside the old 4-word window — "santoso", the pair partner, never
# did). Fixed below in `_has_honorific_name_after_marker`: leading
# stopwords are skipped first (bounded by this cap, so a pathological
# all-stopword run can't scan unboundedly), THEN the
# `_HONORIFIC_FOLLOWING_WORDS_WINDOW`-wide pair-scan runs starting
# after that skip — the window now follows the stopword stack instead
# of being consumed by it.
_HONORIFIC_STOPWORD_SKIP_CAP = 4


def _is_honorific_name_candidate(token: str) -> bool:
    """R19-1: True if `token` is a valid lowercase name-shaped word (3+
    characters, first char lowercase) that is NOT in the closed
    non-name stoplist. Used ONLY as the spaced branch's mode-(a) check
    (R21-1 binding correction below narrows this from its original
    "shared by mode (b) of both branches" scope — see
    `_is_honorific_pair_candidate`)."""
    return (
        len(token) >= 3
        and token[0].islower()
        and token.lower() not in _HONORIFIC_NON_NAME_STOPWORDS
    )


def _is_honorific_attached_mode_a_candidate(token: str) -> bool:
    """R19-3/R20-1 (renamed from `_is_honorific_dot_attached_mode_a_candidate`
    per R21-2): any-CASE variant of `_is_honorific_name_candidate`, used
    ONLY for the punct-attached branch's mode (a) — the original R19-3
    rule (case-insensitive on the WORD, guarded only by the stoplist) is
    preserved here rather than narrowed to lowercase-only, because the
    punct-attached form has no separate titlecase branch the way the
    spaced form does: "Sig.Rossi" (titlecase, no space) has nowhere else
    to be caught, while spaced titlecase names ("Ibu. Siti Rahayu") are
    covered independently by `_HONORIFIC_NAME_RE`."""
    return len(token) >= 3 and token.lower() not in _HONORIFIC_NON_NAME_STOPWORDS


# R21-1 binding correction, 2026-08-15 (Kimi K3 round-21 review, MEDIUM;
# gate triage reported a PARTIAL refutation on the spaced branch — see
# ADR §28 R21-1 for the full empirical trace of why that refutation
# does not hold up): mode (b)'s pair-scan, on BOTH branches, reused
# `_is_honorific_name_candidate` — a LOWERCASE-ONLY check, correct for
# the spaced branch's mode (a) (where lowercase is exactly what
# distinguishes a bridging name from `_HONORIFIC_NAME_RE`'s separate
# titlecase-spaced match) but never re-examined once mode (b) started
# reusing it for BOTH branches (R20-1). Proven: `_is_honorific_name_candidate`
# rejects "Budi" and "Siti" identically (`token[0].islower()` is False
# for both) — "ibu.tolong Siti rahayu" (punct-attached) stayed
# unflagged, and "pak minta Budi santoso" (spaced, WITHOUT a trailing
# word) ALSO stays unflagged; the mandate's spaced fixture
# ("pak minta Budi santoso datang") only appeared to already work
# because of an unrelated, purely-lowercase pair further in the same
# window ("santoso","datang") — not because "Budi" was recognized.
# Fixed: mode (b) now uses `_is_honorific_pair_candidate` (any case) on
# BOTH branches, uniformly — a bridging name pair may have EITHER
# member capitalized (typed quickly, or the more formal member of the
# pair). This corrects the R19-1b/R20-1 comments elsewhere in this
# module that describe mode (b) as "always lowercase-only" — those
# described mode (b)'s behavior correctly for the rounds that wrote
# them; as of R21-1 that is no longer accurate, per this file's own
# convention of correcting prior-round prose via a new dated paragraph
# rather than silent edits.
#
# R21-1b micro-disposition (orchestrator gate, in-flight during round 21
# — MICRO-THAW, same pattern as R15-1b/R16-2b/R18-1b/R19-1b/R20-3b):
# the gate's own initial triage of THIS round's R21-1 had called it a
# "partial refutation" (spaced branch already handles it) — corrected
# above in the same paragraph, since the fix already lands symmetrically
# on both branches and needed no code change for this correction, only
# a sharper record of WHY: "F1 is valid on both branches, there is no
# asymmetry" and Kimi's own "datang" example reproduced via the wrong
# (accidental) mechanism, not a valid isolation of the defect. Pinned by
# an additional canonical-reproduction test,
# `test_guilt_mixed_case_pair_flagged_on_spaced_branch_with_trailing_stopword`
# ("pak minta Budi santoso ya" — a trailing STOPWORD, which cannot
# itself supply a rescuing lowercase pair the way "datang" did).
def _is_honorific_pair_candidate(token: str) -> bool:
    """R21-1: any-CASE, stopword-guarded candidate check used ONLY for
    mode (b)'s adjacent-PAIR scan in `_has_honorific_name_after_marker`,
    shared by BOTH the spaced and punct-attached branches — see the
    R21-1 binding correction comment directly above for the full
    derivation and the empirical trace disproving the apparent
    spaced/punct-attached asymmetry."""
    return len(token) >= 3 and token.lower() not in _HONORIFIC_NON_NAME_STOPWORDS


def _has_honorific_name_after_marker(
    text: str,
    marker_only_re: re.Pattern[str],
    mode_a_is_candidate: Callable[[str], bool],
) -> bool:
    """R19-1b/R20-1/R21-1/R21-3: shared TWO-MODE scan used by both
    `_has_honorific_spaced_lowercase_name` (whitespace-separated marker)
    and `_has_honorific_attached_name` (punct-attached marker, R21-2
    rename) — see the module-level R19-1b comment above
    `_HONORIFIC_MARKER_ONLY_RE` and the R20-1/R21-2 comments above
    `_HONORIFIC_ATTACHED_MARKER_ONLY_RE` for the full derivation of each
    branch's history: (a) the word IMMEDIATELY after the marker flags
    alone if `mode_a_is_candidate` accepts it; (b) otherwise, LEADING
    STOPWORDS are skipped first (bounded by
    `_HONORIFIC_STOPWORD_SKIP_CAP`, R21-3 — so a STACK of bridging
    stopwords can't consume the pair-scan window before ever reaching
    the real name pair), then within the next
    `_HONORIFIC_FOLLOWING_WORDS_WINDOW` words past that skip, two
    ADJACENT non-stopword candidates of ANY CASE
    (`_is_honorific_pair_candidate`, R21-1 — a bridging NAME PAIR may
    have either member capitalized) are required."""
    for marker_match in marker_only_re.finditer(text):
        raw_words = text[marker_match.end() :].split()[
            : _HONORIFIC_STOPWORD_SKIP_CAP + _HONORIFIC_FOLLOWING_WORDS_WINDOW
        ]
        tokens = [
            (m.group(0) if (m := _HONORIFIC_FOLLOWING_WORD_TOKEN_RE.match(w)) else "")
            for w in raw_words
        ]
        if tokens and mode_a_is_candidate(tokens[0]):
            return True
        skip = 0
        while (
            skip < _HONORIFIC_STOPWORD_SKIP_CAP
            and skip < len(tokens)
            and tokens[skip]
            and tokens[skip].lower() in _HONORIFIC_NON_NAME_STOPWORDS
        ):
            skip += 1
        pair_window = tokens[skip : skip + _HONORIFIC_FOLLOWING_WORDS_WINDOW]
        for first, second in zip(pair_window, pair_window[1:]):
            if _is_honorific_pair_candidate(first) and _is_honorific_pair_candidate(second):
                return True
    return False


def _has_honorific_spaced_lowercase_name(text: str) -> bool:
    """R18-1b/R19-1/R19-1b: True if `text` contains an honorific marker
    followed by a spaced lowercase name — see
    `_has_honorific_name_after_marker` for the shared two-mode rule."""
    return _has_honorific_name_after_marker(
        text, _HONORIFIC_MARKER_ONLY_RE, _is_honorific_name_candidate,
    )


# R19-3 (see `_HONORIFIC_NAME_RE`'s own comment above for the full
# extraction rationale): the dot-attached branch used to live inside
# `_HONORIFIC_NAME_RE` with no stopword guard at all, an inconsistency
# against its spaced-lowercase sibling directly above — "makasih
# pak.sudah bantu" and "bu.tolong kirim" both flagged, while the spaced
# equivalents ("makasih pak sudah bantu", guarded by "sudah") did not.
# Fixed: the captured word is checked against the SAME
# `_HONORIFIC_NON_NAME_STOPWORDS` frozenset, case-insensitively — a
# stopword right after the dot is now exempted exactly as it is on the
# spaced branch. Verified empirically: "ibu.siti rahayu" (the R18-1
# guilt fixture) and "Sig.Rossi"/"Sig.ra Rossi"/"Sig.raffaele" (the
# ADDENDUM fixtures) all still flag; "makasih pak.sudah bantu" and
# "bu.tolong kirim" no longer do. (Historical note: "Sig.ra Rossi" was
# never actually caught by THIS branch — it matches `_HONORIFIC_NAME_RE`
# instead, via the spaced-titlecase form "Sig.ra" + " Rossi"; verified
# empirically before relying on it, not assumed, since R20-1 below
# restructures this branch's internals.)
#
# R20-1 binding correction, 2026-08-15 (Kimi K3 round-20 review, MEDIUM):
# this branch only ever had the mode-(a) single-word check the R19-1b
# analysis above calls "R18-1b's original rule" — it was NEVER given the
# mode-(b) bridging-pair mirror R19-1/R19-1b added to the spaced branch,
# and a dot-attached honorific cannot fall through to the SPACED
# function either (that one requires literal whitespace right after the
# marker, which a dot-attached form never has). Proven: "ibu.tolong siti
# rahayu" and "pak.minta budi santoso datang" both passed BOTH scans —
# the same fail-open class as the HIGH-severity R19-1. Fixed by
# extracting this branch's own marker-only regex
# (`_HONORIFIC_DOT_MARKER_ONLY_RE`) and routing it through the SAME
# `_has_honorific_name_after_marker` shared scan the spaced branch uses,
# with `_is_honorific_dot_attached_mode_a_candidate` (any-case) as its
# mode-(a) check — preserving titlecase dot-attached names like
# "Sig.Rossi" — and the shared, lowercase-only
# `_is_honorific_name_candidate` for mode (b), per the mandate's own
# instruction to reuse it rather than duplicate the logic. Verified
# empirically: the two guilt scenarios above now flag; "makasih
# pak.sudah bantu"/"bu.tolong kirim" stay unflagged (their only
# candidate pair fails on the leading stopword — no adjacent partner);
# "ibu.siti rahayu"/"Sig.Rossi"/"Sig.raffaele" (pure mode-(a) cases)
# remain unaffected. Declared residual, MIRRORING the spaced branch's own
# (R19-1b) exactly: a dot-attached bridging stopword followed by exactly
# ONE name word and nothing else that qualifies still escapes, since
# mode (b) never fires on a single candidate — inherent to the shared
# rule, not specific to this branch. The old
# `_HONORIFIC_DOT_ATTACHED_CANDIDATE_RE` (a single-capture regex, no
# room for a multi-word pair-scan) is REMOVED as dead code — zero
# call-sites remain after this restructure — per this file's own
# R18-4 dead-code-removal convention; the module-level comment above
# `_HONORIFIC_NAME_RE` still names it in historical narration of R19-3's
# extraction, left intact.
#
# R21-2 rename, 2026-08-15 (Kimi K3 round-21 review, LOW): renamed from
# `_has_honorific_dot_attached_name` — see the R21-2 binding correction
# above `_HONORIFIC_ATTACHED_MARKER_ONLY_RE` for why "dot" no longer
# describes this branch's separator class. Behavior otherwise unchanged
# by the rename itself (the mode-(b) any-case widening below is R21-1,
# a separate fix).
def _has_honorific_attached_name(text: str) -> bool:
    """R19-3/R20-1/R21-2: True if `text` contains a punct-attached
    honorific ("ibu.siti", "Sig.Rossi", "ibu.tolong siti rahayu",
    "pak,budi santoso", "pak-budi santoso") satisfying the shared
    two-mode rule — see `_has_honorific_name_after_marker` and the
    module-level R20-1/R21-2 comments above this function for the full
    derivation."""
    return _has_honorific_name_after_marker(
        text, _HONORIFIC_ATTACHED_MARKER_ONLY_RE, _is_honorific_attached_mode_a_candidate,
    )


_ADDRESS_MARKER_RE = re.compile(
    # No trailing `\b` after the alternation: "Jl." ends in a literal dot
    # (a non-word char), so `\bJl\.\b` can never match when followed by
    # whitespace — both sides of that boundary would be non-word chars,
    # and `\b` requires a word/non-word transition. Found by this file's
    # own test suite: "Jl. Sunset Road" matched only via the unrelated
    # titlecase-bigram heuristic, not this one. `\s+` after the
    # alternation already enforces separation from the following token,
    # so the middle `\b` was redundant for the other markers and actively
    # broken for "Jl.".
    #
    # R17-3 binding correction, 2026-08-15 (Kimi K3 round-17 review, LOW):
    # the required `\s+` between the marker and the rest of the address
    # meant a no-space WA-typing style ("jl.sunset road", "gang.mawar no
    # 3" — proven empirically, both used to pass Scan B undetected) missed
    # this scan entirely. Fixed: the literal dot moves out of the "Jl\."
    # alternative and becomes its own OPTIONAL suffix on the whole
    # alternation (`\.?`), and the mandatory `\s+` becomes optional
    # `\s*` — this is a DETECTOR (narrows what counts as PII-shaped
    # address text FURTHER, i.e. GRANTS nothing), so over-matching here is
    # fail-closed and free under the same directional rule R16-1
    # established; no anchoring tightened. Bonus, declared rather than
    # accidental: "jln mawar" (a further-abbreviated but real Indonesian
    # address marker) now also matches, via "Jl" + `\S+` consuming "n
    # mawar" — "jln" is itself a common abbreviation of "jalan", so this
    # widening is in-scope for what this marker class is trying to catch,
    # not an unrelated side effect. Residual, declared (not fixed this
    # round — out of the mandate's scope and, per the directional rule,
    # free): dropping the mandatory `\s+` also lets "Jalan" match as a
    # PREFIX of an unrelated Indonesian VERB with no address meaning at
    # all — "jalankan" ("run/execute [something]") now matches too
    # (verified empirically: `_ADDRESS_MARKER_RE.search("kita mau
    # jalankan program ini")` is truthy). Cost model is the same as every
    # other over-match on this DETECTOR: a legitimate business-verb
    # message could be wrongly treated as address-PII-shaped and dropped
    # from the corpus — a lost fixture, never a leaked one.
    #
    # R18-3 addition, 2026-08-15 (Kimi K3 round-18 review, MEDIUM): the
    # marker vocabulary itself was missing standard Indonesian address
    # abbreviations — "Gg." (for "Gang"), "Komp."/"Perum." (for
    # "Komplek"/"Perumahan"), and several street/complex-type words never
    # covered at all ("Dusun", "Kampung", "Ruko", "Blok"). Proven
    # empirically: "alamat: Gg. Melati II No. 4, Denpasar" passed BOTH
    # scans — not caught here (no "Gg" token existed) and not caught by
    # `_TITLECASE_BIGRAM_RE` either, because "Melati II" has no lowercase
    # letters in "II" for that heuristic's bigram shape to recognize;
    # "Komp."/"Perum." were previously caught ONLY by the accident of the
    # titlecase-bigram heuristic, which a lowercase variant ("komp. blok
    # c2") would evade entirely. Fixed: alternation extended to `Jl|Jalan|
    # Gg|Gang|Komp|Komplek|Perum|Perumahan|Banjar|Dusun|Kampung|Ruko|
    # Blok`, same `\.?\s*\S+` suffix — a DETECTOR widening, fail-closed
    # and free under the same directional rule. Residual, declared (not
    # fixed, out of scope, free per the directional rule): "Blok" as a
    # marker will over-match ordinary uses like "blok timur" ("east
    # block", a compass direction, not necessarily an address) — same
    # cost model as every other over-match on this detector.
    #
    # R19-2 binding correction, 2026-08-15 (Kimi K3 round-19 review,
    # MEDIUM): the short markers were unanchored PREFIXES of ordinary
    # Indonesian words with no address meaning — "komplain" ("complaint"),
    # "blokir" ("block/ban"), "gangguan" ("disturbance"), "kompensasi"
    # ("compensation") all matched via "Komp"/"Blok"/"Gang" as a bare
    # prefix (proven empirically before this fix). Unlike the earlier
    # over-matches this file's directional rule accepts as free (a
    # detector may over-match — cost is a dropped fixture), this class
    # is different: at corpus scale, ordinary business vocabulary this
    # common would starve the Indonesian-language bucket, not just drop
    # occasional fixtures — Scan B feeds a corpus-ELIGIBILITY gate, so
    # systematically excluding a whole register of common words is a
    # coverage bias, not a free cost. Fixed: a zero-width lookahead
    # `(?=[\s.])` right after the alternation requires the marker to be
    # followed by whitespace or a literal dot — a genuine word/token
    # boundary — before the existing `\.?\s*\S+` tail runs; this is a
    # NARROWING (grants nothing new), so no directional-rule conflict.
    # `Jln` (a common further-abbreviation of "Jalan"/"Jl") added as its
    # own explicit alternative, since the R17-3 "jln mawar" bonus used to
    # work only via "Jl" matching as an unanchored prefix of "jln" — the
    # new lookahead would otherwise silently lose that shape (the char
    # right after "Jl" in "jln" is "n", not whitespace/dot). Verified
    # empirically: guilt (now NOT flagged) — "komplain", "blokir",
    # "gangguan", "kompensasi"; innocence-regression (still flagged) —
    # "Gg. Melati II No. 4", "jl.sunset road", "gg.mawar no 3", "Jl
    # Sunset", "jln mawar" (via the new explicit token, not the old
    # prefix accident). Declared residual of this tightening: a
    # no-separator run like "KompGriya" no longer matches — never a real
    # WA-typing address form to begin with, so nothing legitimate is
    # lost.
    r"\b(?:Jl|Jln|Jalan|Gg|Gang|Komp|Komplek|Perum|Perumahan|Banjar|Dusun|Kampung|Ruko|Blok)"
    r"(?=[\s.])\.?\s*\S+",
    re.IGNORECASE,
)
# R6-1(c) binding correction (Kimi K3 round-6 review): `NIK` (Nomor Induk
# Kependudukan, the Indonesian national ID number) was absent from this
# alternation despite this file's own G1 comment above naming it as the
# exact PII shape Scan A's spaced-digit-run companion exists to protect.
# `KK` (Kartu Keluarga) and `SIM` (driving license) were investigated and
# DELIBERATELY excluded — empirically verified (before applying, not just
# reasoned about) to over-match ordinary casual text: "kk" is common
# Indonesian chat slang for "kakak" (sibling/informal address term, e.g.
# "kk, boleh tanya dong"), and "kk ini alamat RT 005 nya" — an innocent
# message naming a neighborhood administrative unit number, zero PII —
# matches `\bKK\b.{0,20}?\d{3,}` because "005" (the RT number) falls
# within 20 characters of the word "kk". `SIM` has the same shape risk
# ("sim card"). Adding either would trade a real innocence failure for a
# guilt case this scan doesn't need — the near-digits heuristic here is
# ADDITIVE to `_has_spaced_digit_pii`'s shape-only NIK detection (G1
# above), which already catches a bare NIK with no keyword nearby at all,
# so `KK`/`SIM` coverage is not load-bearing the way `NIK` is.
# R8-5 binding correction, 2026-08-15 (Kimi K3 round-8 review): without
# `re.DOTALL`, `.` in `.{0,20}?` never matches `\n` — and `_iter_txt_records`
# above joins a WA export's continuation lines with `\n` (multi-line
# messages, "regardless of sender"). A real WA message like
# "ini nomor paspor saya:\nA1234567" puts the keyword and the digits on
# DIFFERENT lines; without DOTALL, the window can't cross that newline and
# this pattern never matches at all — even though the digit run itself
# (7 digits, a typical Indonesian passport's number portion) is ALSO too
# short for either of Scan A's thresholds (`\d{8,}` / the 8-digit floor in
# `_has_spaced_digit_pii`), so the message escapes BOTH scans entirely.
# `re.DOTALL` lets the window cross line breaks, matching the keyword and
# the digit run regardless of which line each sits on.
#
# R20-2 binding correction, 2026-08-15 (Kimi K3 round-20 review, MEDIUM):
# the trailing `\b` right after the keyword alternation rejected
# Indonesian ENCLITIC suffixes ("-nya"/"-ku"/"-mu"/"-lah", possessive/
# emphatic particles glued directly onto the noun with no space) — since
# both the keyword and its suffix are word characters, there is no
# word/non-word transition for `\b` to fire on between them. Proven:
# "paspornya A1234567", "KTPnya 3171234567", "NIKnya 317123456789" all
# passed BOTH scans undetected, while the bare unsuffixed "paspor
# A1234567" was already caught — and the suffixed form is the MORE
# common one on real WhatsApp chat, not an edge case. Fixed: an optional
# non-capturing enclitic-suffix group, `(?:nya|ku|mu|lah)?`, inserted
# between the keyword alternation and the trailing `\b` — a DETECTOR
# widening (grants nothing), so free under the same directional rule
# R16-1 established; the `\b` itself is unmoved, now anchoring after the
# optional suffix instead of directly after the bare keyword. Verified
# empirically: all three suffixed guilt scenarios above now flag; the
# pre-existing unsuffixed "paspor A1234567" guilt case is unaffected
# (the suffix group matches empty, `\b` still fires immediately after
# "paspor" exactly as before).
#
# R21-5 binding correction, 2026-08-15 (Kimi K3 round-21 review, MICRO):
# the R20-2 enclitic group above named only `nya`/`ku`/`mu`/`lah` — two
# other common Indonesian enclitics, the interrogative/emphatic `-kah`
# and the emphatic `-pun`, were absent. Proven: "KTPkah 3171234567" and
# "KTPpun 3171234567" both passed undetected, same fail-open shape as
# R20-2's original finding. Fixed: `(?:nya|ku|mu|lah)?` widened to
# `(?:nya|ku|mu|lah|kah|pun)?` — a DETECTOR widening (grants nothing),
# free under the same R16-1 directional rule as R20-2 itself. Verified
# empirically: both new suffixed guilt scenarios now flag; the
# pre-existing R20-2 suffixes and the bare unsuffixed form are
# unaffected.
_ID_DOC_NEAR_DIGITS_RE = re.compile(
    r"\b(?:NPWP|NIB|KITAS|KITAP|paspor|passport|KTP|NIK)(?:nya|ku|mu|lah|kah|pun)?\b.{0,20}?\d{3,}",
    re.IGNORECASE | re.DOTALL,
)
# NOT extended to `re.IGNORECASE` — investigated, confirmed EMPIRICALLY
# harmful, deferred rather than "fixed" (orchestrator corpus gate,
# 2026-08-15). `_TITLECASE_BIGRAM_RE`'s selectivity comes entirely from
# requiring an actual capital letter — with `re.IGNORECASE` it degrades to
# "any two adjacent 3+-letter words", which flags ALL THREE of this file's
# own clean-message innocence fixtures ("quanto costa", "Berapa biaya",
# "How long" all match case-insensitively — verified with a standalone
# script before writing this comment). That is not a wider PII net, it is
# the heuristic losing its only signal. A real fix for ALL-CAPS/lowercase
# NAMES (as opposed to marker-anchored honorific/address phrases, which
# stay narrow because the marker word itself is a fixed small list) needs
# something smarter than a blanket case-insensitivity flip — left for a
# future pass, not applied here.
# Two-or-more consecutive Title-Case words — a coarse, intentionally
# aggressive name-shape detector. Expected to over-match on legitimate
# proper-noun phrases (institution names, regulation titles); that
# over-matching is accepted per the fail-closed posture — the cost of a
# dropped legitimate fixture is zero, the cost of a leaked name is not.
_TITLECASE_BIGRAM_RE = re.compile(r"\b[A-Z][a-z]{2,}\s+[A-Z][a-z]{2,}\b")


def _is_date_or_amount_shape(
    candidate: str,
    *,
    text: str = "",
    span: tuple[int, int] | None = None,
) -> bool:
    """True if `candidate` (a `_RESIDUAL_SPACED_DIGIT_RUN_RE` match) looks
    like an ISO-ish date (`2026-08-15`) or a thousands-grouped amount
    (`2.500.000` / `2,500,000`) rather than a phone/NIK-shaped number —
    G1 binding correction, 2026-08-15. Checked against the WHOLE matched
    span (`^...$`), not a substring search, so this can't accidentally
    exempt a genuine phone number that merely CONTAINS a date-shaped
    substring.

    `text`/`span` (R15-1/R15-3, Kimi K3 round-15 review): the full source
    text and this candidate's `(start, end)` offset WITHIN that text —
    both optional, default to no context available (`text=""`,
    `span=None`, in which case every window computed below is empty).
    Callers that have the surrounding text (`_has_spaced_digit_pii`
    below, via `re.Match.span()`) SHOULD pass both; a direct call with
    just `candidate` (this file's own unit tests exercising ONLY the
    shape/calendar logic) is still valid but gets the context-free
    defaults: no currency marker found (amount exemption requires one —
    see R15-1 below) and no birth marker found (date exemption is
    unaffected, since R15-3's veto is additive, not required).

    LOW binding correction, 2026-08-15 (Kimi K3, live-gate round 5, TWO
    passes). Pass 1 accepted the SHAPE alone — `_ISO_DATE_SHAPE_RE`
    matching `"6208-15-15"` (month=15, day=15) exactly as readily as
    `"2026-08-15"`, exempting a NIK/phone number formatted with date-like
    separators from the PII scan on the strength of a shape that is not
    actually a possible date (there is no 15th month). Pass 1's fix was a
    numeric range check (month 1-12, day 1-31) — the orchestrator's pass-2
    refinement flagged that a bare range check STILL wrongly accepts
    calendar-impossible-but-in-range values, e.g. `"2026-02-30"` (day 30
    is in [1, 31] but February never has a 30th; the same is true for any
    30/31-day-in-a-28/29/30-day-month combination). A range check cannot
    distinguish "structurally a date" from "actually a date on the
    calendar" — only the calendar itself (including leap-year February)
    can. Fixed by constructing a real `datetime.date(year, month, day)`
    and treating a `ValueError` as "not a real date" — this is the
    standard, well-tested way to ask "does the calendar contain this day"
    without hand-rolling per-month day-counts and leap-year rules (which
    `datetime.date` already implements correctly, including the
    divisible-by-4-except-100-except-400 leap rule). The regex now also
    captures the year (previously only month/day), since `datetime.date`
    needs all three fields — an out-of-range year (e.g. year 0) would
    itself raise `ValueError` and correctly fall through to "not a date".

    R8-8 addition, 2026-08-15 (Kimi K3 round-8 review): also recognizes
    the day-first shape (`_DMY_DATE_SHAPE_RE`, `DD/MM/YYYY`/`DD-MM-YYYY`)
    now that `/` is included in `_RESIDUAL_SPACED_DIGIT_RUN_RE`'s
    separator class — same real-calendar-date validation via
    `datetime.date`, same fall-through-to-amount-check posture on a
    calendar-impossible value.

    R15-3 addition, 2026-08-15 (Kimi K3 round-15 review, MEDIUM): calendar
    validity alone answers "is this shape a possible date", never "is
    this a date whose disclosure is itself PII". A birth date is a real
    calendar date and a genuine identifying fact — both branches above
    now VETO the exemption (return `False` instead of `True`) when a
    birth-context marker (`_BIRTH_MARKER_RE`) is found near the candidate
    span in `text`. A veto never widens what counts as PII beyond "this
    specific span, in this specific context" — a date with no birth
    marker nearby is completely unaffected.

    R16-3 addition, 2026-08-15 (Kimi K3 round-16 review, LOW): "near"
    above used to mean ONLY `_BIRTH_CONTEXT_WINDOW_CHARS` characters
    BEFORE the span, on the assumption a birth-context label always
    precedes the date it labels. Proven false: "15/08/1990 itu tanggal
    lahir dia" puts the label AFTER the date. The veto now checks BOTH
    sides (either side vetoing is enough) — see `_BIRTH_MARKER_RE`'s own
    module-level comment for the asymmetric-cost reasoning this shares
    with R16-1 below.

    R15-1 addition, 2026-08-15 (Kimi K3 round-15 review, HIGH): the amount
    branch below used to exempt on SHAPE alone (grouped digits under the
    ceiling) — context-free, so a non-contiguous phone number or a bare
    reference number typed with thousands-style separators
    ("+62.812.345.678", "123.456.789") was exempted exactly like a
    genuine IDR amount. Fixed: the amount branch now ALSO requires a
    currency/amount marker near the span — no marker means the span is
    no longer treated as an amount at all, regardless of shape or digit
    count. R18-4 correction, 2026-08-15 (Kimi K3 round-18 review, LOW):
    this paragraph used to cite a single symbol, `_CURRENCY_MARKER_RE`,
    as the live authority for both directions — that symbol has since
    been removed as dead code (see its own module-level R18-4 comment);
    the live authorities are now `_CURRENCY_MARKER_ADJACENT_BEFORE_ALT`
    (BEFORE the span) and `_CURRENCY_MARKER_ADJACENT_AFTER_ALT` (AFTER),
    each its own independent pattern since R17-1 removed the shared base
    entirely. See their own module-level comments for the fail-closed
    cost-model justification (dropping a legitimate fixture costs
    nothing; missing a real phone number does).

    R16-2 addition, 2026-08-15 (Kimi K3 round-16 review, MEDIUM): "near"
    above used to mean "anywhere in the `_CURRENCY_CONTEXT_WINDOW_CHARS`-
    char window", which let a marker that genuinely belongs to ONE amount
    earlier in a sentence exempt an unrelated span (a phone number) later
    in the same sentence — see `_CURRENCY_MARKER_ADJACENT_BEFORE_RE`/
    `_AFTER_RE`'s own module-level comment for the reproduced scenario.
    The marker must now be ADJACENT to the span (only light whitespace/
    `:`/`=` may sit between them), not merely co-located in a wide
    window — the exemption for R16-1's directional-asymmetry reasoning
    does NOT apply here: this pattern GRANTS an exemption, so tightening
    it is the safe direction, same as the R15-1b anchoring fix was for
    entity-vs-substring (opposite axis, same "grant = must be precise"
    principle)."""
    start, end = span if span is not None else (0, len(candidate))
    birth_before = text[max(0, start - _BIRTH_CONTEXT_WINDOW_CHARS) : start]
    birth_after = text[end : end + _BIRTH_CONTEXT_WINDOW_CHARS]
    birth_context_vetoes_date = bool(_BIRTH_MARKER_RE.search(birth_before)) or bool(
        _BIRTH_MARKER_RE.search(birth_after),
    )

    date_match = _ISO_DATE_SHAPE_RE.match(candidate)
    if date_match:
        year, month, day = (
            int(date_match.group(1)),
            int(date_match.group(2)),
            int(date_match.group(3)),
        )
        try:
            datetime.date(year, month, day)
        except ValueError:
            # Shape looks like a date but it is not one on the actual
            # calendar (impossible month/day, or Feb 30/31 etc.) — not a
            # real date, fall through (still may match the DMY or amount
            # shape below).
            pass
        else:
            return not birth_context_vetoes_date
    dmy_match = _DMY_DATE_SHAPE_RE.match(candidate)
    if dmy_match:
        day, month, year = (
            int(dmy_match.group(1)),
            int(dmy_match.group(2)),
            int(dmy_match.group(3)),
        )
        try:
            datetime.date(year, month, day)
        except ValueError:
            # Same fall-through posture as the ISO branch above.
            pass
        else:
            return not birth_context_vetoes_date
    amount_match = _GROUPED_AMOUNT_SHAPE_RE.match(candidate)
    if not amount_match:
        return False
    # R6-1(a): the amount shape alone is not enough — cap TOTAL digit count
    # so a 16-digit NIK written with thousands-style grouping cannot borrow
    # the amount exemption (see `_MAX_EXEMPT_AMOUNT_DIGITS`'s module-level
    # comment for why 13 is the exact ceiling, not a rounded guess).
    digit_count = sum(ch.isdigit() for ch in candidate)
    if digit_count > _MAX_EXEMPT_AMOUNT_DIGITS:
        return False
    # R15-1: shape + digit-ceiling are necessary but no longer sufficient —
    # an explicit currency/amount marker must appear near the span too.
    # R16-2: "near" means ADJACENT (see `_CURRENCY_MARKER_ADJACENT_BEFORE_RE`/
    # `_AFTER_RE`'s own module-level comment) — a plain `.search()` across
    # the whole window let a marker belonging to a DIFFERENT amount in the
    # same message exempt an unrelated span.
    pre_context = text[max(0, start - _CURRENCY_CONTEXT_WINDOW_CHARS) : start]
    post_context = text[end : end + _CURRENCY_CONTEXT_WINDOW_CHARS]
    marker_immediately_before = bool(_CURRENCY_MARKER_ADJACENT_BEFORE_RE.search(pre_context))
    marker_immediately_after = bool(_CURRENCY_MARKER_ADJACENT_AFTER_RE.search(post_context))
    return marker_immediately_before or marker_immediately_after


def _has_spaced_digit_pii(text: str) -> bool:
    """Separator-aware companion to `_RESIDUAL_LONG_DIGIT_RUN_RE` (G1,
    2026-08-15) — see the module-level comment on
    `_RESIDUAL_SPACED_DIGIT_RUN_RE` for why `/` is now INCLUDED in the
    separator class (R8-8, 2026-08-15): a NIK/phone number typed with
    slashes instead of spaces/dots/commas would otherwise escape this
    scan entirely. The over-match risk that inclusion would otherwise
    create (eating every `DD/MM/YYYY`/`DD-MM-YYYY` and ISO-shaped date) is
    what `_is_date_or_amount_shape` below exists to close — it now
    validates BOTH the ISO shape (`_ISO_DATE_SHAPE_RE`) and the day-first
    shape (`_DMY_DATE_SHAPE_RE`) against the real calendar via
    `datetime.date`, not merely a numeric range. A candidate span counts
    as PII-shaped only if it has at least 8 actual digit characters
    (matching the contiguous scan's own threshold) AND does not look like
    a real calendar date or a grouped amount. NOTE FOR MAINTAINERS: this
    date/amount exemption is not dead code to simplify away — dropping it
    reopens the slash-separated-NIK hole R8-8 closed.

    R15-1/R15-3 (Kimi K3 round-15 review): the full `text` and each
    match's `span()` are now passed through to `_is_date_or_amount_shape`
    so it can check for a currency marker (amount exemption) or a birth
    marker (date-exemption veto) in the surrounding context — see that
    function's own docstring for both."""
    for match in _RESIDUAL_SPACED_DIGIT_RUN_RE.finditer(text):
        candidate = match.group(0)
        digit_count = sum(ch.isdigit() for ch in candidate)
        if digit_count >= 8 and not _is_date_or_amount_shape(candidate, text=text, span=match.span()):
            return True
    return False


def _has_residual_pii(text: str) -> bool:
    """Scan A."""
    return bool(
        _RESIDUAL_PHONE_RE.search(text)
        or _RESIDUAL_LONG_DIGIT_RUN_RE.search(text)
        or _RESIDUAL_EMAIL_RE.search(text)
        or _has_spaced_digit_pii(text),
    )


def _independent_pii_scan(text: str) -> list[str]:
    """Scan B — independent of Scan A and of the Redactor.

    Returns a list of finding codes (empty = nothing flagged). Any
    exception raised while scanning is the CALLER's responsibility to
    treat as "could not verify" (fail closed), never as "assume clean" —
    this function itself does not swallow errors, by design, so a caller
    that forgets to handle that case fails loudly rather than silently.
    """
    findings: list[str] = []
    if (
        _HONORIFIC_NAME_RE.search(text)
        or _has_honorific_spaced_lowercase_name(text)
        or _has_honorific_attached_name(text)
    ):
        findings.append("honorific_name")
    if _ADDRESS_MARKER_RE.search(text):
        findings.append("address_marker")
    if _ID_DOC_NEAR_DIGITS_RE.search(text):
        findings.append("id_doc_near_digits")
    if _TITLECASE_BIGRAM_RE.search(text):
        findings.append("titlecase_bigram")
    return findings


# --- Language bucketing (fragile, disclosed) -------------------------------
# Same class of marker heuristic the bot corner documents as failing on
# real phrasings (`detect_language`'s known gaps,
# `.agents/skills/bot/SKILL.md` §1). Good enough to bucket SYNTHETIC/
# style-varied fixtures for a benchmark; do not promote into production.
_LANG_MARKERS: dict[str, frozenset[str]] = {
    "it": frozenset(
        {"ciao", "buongiorno", "grazie", "quanto", "costa", "vorrei", "posso", "perché", "come"},
    ),
    "id": frozenset(
        {"selamat", "berapa", "biaya", "saya", "mau", "bisa", "terima", "kasih", "mohon"},
    ),
    "en": frozenset(
        {"hello", "hi", "please", "thanks", "cost", "how", "what", "need", "would"},
    ),
}

_HISTORY_TURNS = 12


@dataclass(frozen=True)
class RawRecord:
    """One parsed record awaiting redaction/scanning. `text` is the raw
    message content; `source_file` is used ONLY for local dev logging
    (never serialized to any output — see `_iter_jsonl_records`'s
    `file_index` docstring for why even the FILE is referenced by an
    opaque ordinal, not this path, in any log line).

    R28 adds canonical `role` and a local-only `conversation_id` for
    structured JSONL input. Neither field is inferred from a sender name;
    `.txt` records leave both unset and are therefore ineligible in default
    role-aware mode. `conversation_id` exists only to key an in-memory
    history and is never serialized, hashed, or logged. Sender remains
    transient parser input and is never captured on this dataclass."""

    text: str
    source_file: Path  # local dev logging only — never serialized to output
    role: Literal["user", "assistant"] | None = None
    conversation_id: str | None = None  # local grouping only — never serialized


def _iter_txt_records(path: Path) -> Iterator[RawRecord]:
    """Parse one WhatsApp `.txt` export into records.

    Continuation lines (no timestamp prefix — WhatsApp wraps long messages
    across lines with no re-stamped header) are appended to the previous
    record's text, regardless of sender (a file with zero matching lines
    yields nothing; R8-14 binding correction, 2026-08-15, Kimi K3 round-8
    review: this docstring promised the caller (`_load_records`) COUNTS
    that case as unparsed, but nothing there actually did — the promise
    was aspirational, not implemented. `_load_records` now logs a warning,
    by opaque per-file ordinal (never the path — R6-3 discipline), when a
    `.txt` file yields zero records, so a genuinely empty/unparseable
    export is never silently indistinguishable from one with 0 legitimate
    messages).
    """
    current_text: str | None = None
    with path.open(encoding="utf-8", errors="replace") as f:
        for raw_line in f:
            line = raw_line.rstrip("\n")
            match = _WA_LINE_RE.match(line)
            if match:
                if current_text is not None:
                    yield RawRecord(text=current_text, source_file=path)
                current_text = match.group("text")
            elif current_text is not None and line.strip():
                current_text = current_text + "\n" + line
    if current_text is not None:
        yield RawRecord(text=current_text, source_file=path)


def _iter_jsonl_records(path: Path, *, file_index: int) -> Iterator[RawRecord]:
    """`file_index` is an OPAQUE per-file ordinal (R6-3, Kimi K3 round-6
    review) — never the filename or path. A real WhatsApp export filename
    is `WhatsApp Chat with <contact name>.txt`-shaped and the contact name
    is exactly the class of thing this whole script exists to keep out of
    every output surface, logs included; logging `path` here (as an
    earlier draft did) would have printed it straight into this script's
    own log stream regardless of what the redactor/scans do to the
    MESSAGE content. `file_index` is the file's position in `_load_records`'
    sorted listing — stable for a given input directory, tells the operator
    "which of N files", carries zero identity.

    R7-5 binding correction, 2026-08-15 (Kimi K3 round-7 review):
    `errors="replace"` was missing here while `_iter_txt_records` (its
    `.txt` sibling above) already has it — a single byte in a `.jsonl`
    input file that isn't valid UTF-8 used to raise `UnicodeDecodeError`
    straight out of the file iterator itself, which the per-line
    `try/except json.JSONDecodeError` below cannot catch (the failure
    happens while pulling the next line from `f`, before any JSON parsing
    is attempted) — killing the entire build over one bad byte in one
    input file. `errors="replace"` matches the txt path: a line mangled by
    the replacement (U+FFFD) becomes invalid JSON and is counted as
    unparseable by the existing mechanism, same fail-soft posture as every
    other malformed-input case in this file."""
    with path.open(encoding="utf-8", errors="replace") as f:
        for line_no, raw_line in enumerate(f, start=1):
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                obj = json.loads(raw_line)
            except json.JSONDecodeError:
                logger.warning(
                    "input file #%d (.jsonl), line %d — unparseable JSON, skipped",
                    file_index,
                    line_no,
                )
                continue
            # R6-7 binding correction (Kimi K3 round-6 review): a
            # syntactically valid JSONL line whose top-level value is NOT
            # an object (e.g. `[1, 2]` or `"just a string"`) used to reach
            # `obj.get("text")` directly and raise a raw `AttributeError`
            # — a crash, not the "counted and skipped" behavior this
            # module's own docstring promises for unparseable input. Guard
            # explicitly and treat it as the same class of malformed-input
            # line as unparseable JSON: logged (type only, never path —
            # R6-3) and skipped, never fatal.
            if not isinstance(obj, dict):
                logger.warning(
                    "input file #%d (.jsonl), line %d — JSON value is not an object "
                    "(got %s), skipped",
                    file_index,
                    line_no,
                    type(obj).__name__,
                )
                continue
            text = obj.get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            raw_role = obj.get("role")
            role: Literal["user", "assistant"] | None = (
                raw_role if isinstance(raw_role, str) and raw_role in {"user", "assistant"} else None
            )
            raw_conversation_id = obj.get("conversation_id")
            conversation_id = (
                raw_conversation_id.strip()
                if isinstance(raw_conversation_id, str) and raw_conversation_id.strip()
                else None
            )
            yield RawRecord(
                text=text,
                source_file=path,
                role=role,
                conversation_id=conversation_id,
            )


def _load_records(input_dir: Path) -> Iterator[RawRecord]:
    """R6-3 binding correction (Kimi K3 round-6 review): the "no files
    found" warning used to interpolate `input_dir` — the directory the
    operator typed on the command line, which they may reasonably have
    named after the export it holds (`~/Desktop/WhatsApp Chat with <name>
    export/`). Fail-closed per the class audit: never log the operator's
    `--input-dir` value verbatim here, even though (unlike a WA export
    filename) it is not automatically contact-named — the same "no path
    in this file's logs, ever" discipline this function's per-file
    callees now carry (see `_iter_jsonl_records`).

    R8-14 binding correction, 2026-08-15 (Kimi K3 round-8 review):
    `_iter_txt_records`'s own docstring promises a `.txt` file that yields
    zero records is "counted by the caller as unparsed" — this function IS
    that caller, and it never actually counted or logged anything for that
    case; the promise was aspirational. Now implemented: a `.txt` file
    that yields zero records logs a warning by opaque per-file ordinal
    (never the path — R6-3), the same convention `_iter_jsonl_records`
    already uses for its own per-line warnings.

    R9-2 binding correction, 2026-08-15 (Kimi K3 round-9 review): R8-14's
    zero-record warning covered only the `.txt` branch — the `.jsonl`
    branch counted nothing, so a `.jsonl` file consisting entirely of
    blank lines (or lines that all fail `_iter_jsonl_records`' own
    per-line skip checks) silently contributed zero records with no
    warning at all, same gap R8-14 closed for `.txt`. Both branches now
    share the same "yielded == 0 → warn by opaque per-file ordinal"
    posture."""
    files = sorted(input_dir.rglob("*.txt")) + sorted(input_dir.rglob("*.jsonl"))
    if not files:
        logger.warning("No .txt or .jsonl input files found under the given --input-dir")
    for file_index, path in enumerate(files, start=1):
        if path.suffix == ".txt":
            yielded = 0
            for record in _iter_txt_records(path):
                yielded += 1
                yield record
            if yielded == 0:
                logger.warning("input file #%d (.txt) yielded zero records", file_index)
        else:
            yielded = 0
            for record in _iter_jsonl_records(path, file_index=file_index):
                yielded += 1
                yield record
            if yielded == 0:
                logger.warning("input file #%d (.jsonl) yielded zero records", file_index)


def _guess_language(text: str) -> str:
    lowered = text.lower()
    words = set(re.findall(r"[a-zàèéìòù]+", lowered))
    scores = {lang: len(words & markers) for lang, markers in _LANG_MARKERS.items()}
    best_lang = max(scores, key=lambda lang: scores[lang])
    if scores[best_lang] == 0:
        return "other"
    return best_lang


def _ollama_ner_pass(text: str, *, model: str, timeout: float = 30.0) -> str:
    """OPTIONAL, ADDITIVE second local pass via Ollama for names the regex
    scans miss. NEVER load-bearing for eligibility (orchestrator corpus
    gate) — a text this pass fails to touch still has to clear both Scan A
    and Scan B before it is eligible.

    Loopback ENFORCED, not trusted: the `ollama` CLI reads `OLLAMA_HOST`
    from the process environment, so an ambient `OLLAMA_HOST` pointing at
    a remote host would otherwise make this "local-only" pass a silent
    cloud call. This function builds an explicit subprocess environment
    that FORCES `OLLAMA_HOST=http://127.0.0.1:11434`, overriding whatever
    the ambient environment says — the earlier draft claimed loopback-only
    without enforcing it, which the orchestrator correctly rejected as
    "claim, not control".

    Environment MINIMISED, not just host-forced (K3 binding correction,
    Kimi K3 diagnostic, 2026-08-15): the subprocess previously received
    `dict(os.environ)` — the FULL parent environment, including any API
    keys/tokens/credentials this process happens to be carrying (this
    repo's own secrets discipline puts several in plain env vars). None of
    that is needed to run `ollama run <model> <prompt>`. Only
    `_OLLAMA_SUBPROCESS_ENV_ALLOWLIST` is forwarded — an explicit,
    reviewed allowlist, not a "strip known-bad keys" blocklist (a
    blocklist only ever catches secrets someone thought to name).

    Best-effort beyond that: any failure (Ollama not installed, model not
    pulled, timeout, non-loopback misconfiguration surfacing as a
    connection error) logs a warning and returns the input UNCHANGED —
    this pass never blocks the pipeline and never raises.

    Prompt delivered via STDIN, not argv (R6-4 binding correction, Kimi K3
    round-6 review): `["ollama", "run", model, prompt]` put the WhatsApp
    text — already-redacted, but not yet Scan A/B verified at the point
    this pass runs — directly into this process's own argv, which is
    visible to any other process on the same machine via `ps`/`/proc`
    (and, historically, ARG_MAX truncation risk for a long chat export).
    `ollama run <model>` with no positional prompt reads the entire piped
    stdin as the prompt when stdin is not a tty — the documented
    non-interactive invocation shape — so this function now passes
    `input=prompt` to `subprocess.run` and drops `prompt` from `cmd`
    entirely; the text never touches argv.
    """
    prompt = (
        "Replace every personal name, company name, and street address in "
        "the following text with the placeholder [NAME-REDACTED]. Keep "
        "everything else, including regulation numbers and visa codes, "
        "unchanged. Return ONLY the resulting text, nothing else.\n\n"
        f"TEXT:\n{text}"
    )
    forced_env = {k: v for k, v in os.environ.items() if k in _OLLAMA_SUBPROCESS_ENV_ALLOWLIST}
    forced_env["OLLAMA_HOST"] = "http://127.0.0.1:11434"
    try:
        result = subprocess.run(
            ["ollama", "run", model],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=forced_env,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        # Exception TYPE only, never str(e) — P1-privacy (orchestrator
        # corpus gate, 2026-08-15), now defense-in-depth rather than the
        # primary control: since R6-4 moved the prompt to `input=`, `cmd`
        # is `["ollama", "run", model]` and no longer embeds the WhatsApp
        # text, so `subprocess.TimeoutExpired.__str__` (which renders
        # `cmd`, never `input`) can no longer leak it either way — but
        # type-only logging stays the rule here regardless of which
        # exception field currently happens to be safe.
        logger.warning("Ollama NER pass unavailable (%s) — text unchanged", type(e).__name__)
        return text
    if result.returncode != 0:
        logger.warning("Ollama NER pass failed (rc=%d) — text unchanged", result.returncode)
        return text
    cleaned = result.stdout.strip()
    return cleaned or text


def _mkdir_private(path: Path) -> None:
    """Create `path` (and any missing parents) with the leaf directory at
    0700, immune to the process umask, and ENFORCED even if the directory
    already existed with looser permissions — the directory-level
    counterpart to `_write_jsonl_private`'s 0600-from-creation discipline
    (K5, orchestrator corpus gate, 2026-08-15). `Path.mkdir(mode=...)`
    alone is not enough on either count: the umask still narrows `mode`
    unless cleared first, and `exist_ok=True` on an already-existing
    directory does not retroactively fix its permissions — hence the
    explicit `os.chmod` after, unconditionally. Only the LEAF directory is
    guaranteed 0700; any missing PARENT directories are created by
    `Path.mkdir(parents=True)` at their own default (umask-derived)
    permissions, mirroring `mkdir -p` — this call is about the corpus/
    bench output directory itself, not about hardening every ancestor
    directory in its path.

    R9-8 binding correction, 2026-08-15 (Kimi K3 round-9 review, MICRO):
    the directory-component twin of the leaf-file symlink hole R8-13
    closed for `wa_blind_bench.py::_open_private` —
    `Path.mkdir(parents=True, exist_ok=True)` silently accepts a
    pre-planted symlink at `path` whose target is a directory (no
    `O_NOFOLLOW` equivalent for `mkdir`), and the unconditional
    `os.chmod` below FOLLOWS a symlink to its target by default, so a
    symlink leaf would get its chmod applied to whatever directory it
    points at, not `path` itself. Refused explicitly before the chmod.
    (R11-6 text correction, 2026-08-15, Kimi K3 round-11 review: the
    `Path.mkdir(parents=` / `True, exist_ok=True)` code-span above was
    split mid-token across a line break — rejoined; the sibling docstring
    in `wa_blind_bench.py::_open_private` was already correct.)

    R10-6 honesty note, 2026-08-15 (Kimi K3 round-10 review, MICRO): the
    check above is check-then-chmod, not atomic — a real TOCTOU window
    exists between `path.is_symlink()` and `os.chmod`. This protects
    against a symlink PRE-PLANTED before this function runs (the stated
    threat model, matching `_write_jsonl_private`'s O_NOFOLLOW), not a
    TOCTOU-proof guarantee against a same-user attacker racing this exact
    call — out of scope here (local same-user race, not the pre-planted-
    symlink class this fix targets)."""
    prior_umask = os.umask(0o077)  # deny group/other read+write+execute
    try:
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
    finally:
        os.umask(prior_umask)
    if path.is_symlink():
        raise OSError("refusing to chmod a symlink leaf directory")
    os.chmod(path, 0o700)


def _write_jsonl_private(path: Path, rows: list[dict]) -> None:
    """Write JSONL private FROM CREATION, not chmod-after — AND re-tighten
    an already-existing looser file WITHOUT destroying its content on a
    failed tighten (MEDIUM binding correction, 2026-08-15, live-gate round
    5, two passes).

    Pass 1 (`os.fchmod(fd, 0o600)` right after `os.open`): `os.open(...,
    mode=0o600)` sets the permission bits ONLY at the moment the file is
    actually CREATED by this call (`O_CREAT` without `O_EXCL`) — if `path`
    already exists (a prior 0o644 file from before this discipline
    existed, or one written by another tool), the `mode` argument is
    silently ignored by the OS and the file keeps its PRE-EXISTING
    permissions; this function would then write PII-bearing content into a
    file that stayed group/other-readable the whole time. The
    umask-clearing below only protects the CREATE case, not the
    reopen-existing case — a gap identical in shape to `_mkdir_private`'s
    original bug for directories (K5), just for files.

    Pass 2 (deferred truncation, orchestrator refinement on pass 1): the
    FIRST fix opened with `O_TRUNC` up front, so a `os.fchmod` failure
    still left the fail-closed path with the file ALREADY zeroed by the
    open call itself — "no new PII written" was true, but "pre-existing
    content destroyed" was a real, separate loss the fail-closed framing
    missed. Fixed by opening WITHOUT `O_TRUNC` (`O_WRONLY | O_CREAT`
    only), confirming `os.fchmod` succeeds FIRST, and only then explicitly
    truncating (`os.ftruncate(fd, 0)`) and resetting the write position
    (`os.lseek(fd, 0, os.SEEK_SET)`) before writing new content — a
    genuinely fail-closed path now means the file's ORIGINAL bytes survive
    intact if `os.fchmod` raises, not merely "no new bytes were added".

    Fail-closed: if `os.fchmod` raises (e.g. an unsupported filesystem),
    the fd is closed immediately, the file's pre-existing content is
    UNTOUCHED, and the exception propagates — this function never falls
    through to writing PII content into a file whose permissions it could
    not confirm, never leaks the fd, and never destroys data on the
    failure path.

    R13-3 binding correction, 2026-08-15 (Kimi K3 round-13 review): the
    "never destroys data on the failure path" claim above is UNQUALIFIED
    in the docstring's own words, but it only actually holds for a
    failure inside the GUARDED syscalls — `os.fchmod`/`os.ftruncate`/
    `os.lseek`. It does NOT hold for the one path outside that guard
    since R12-4's revert: `os.fdopen`. By the time `os.fdopen` runs,
    `os.ftruncate(fd, 0)` has ALREADY executed successfully — the
    pre-existing PII-bearing file's content is already zeroed on disk. If
    `os.fdopen` then fails, the residual is not "no data destroyed, one
    fd leaked" — it is BOTH: one leaked `fd` AND the pre-existing file
    already truncated (the truncate preceded the fdopen failure; there is
    no "before truncation" state left to preserve at that point). The
    gate explicitly DECLARES this residual rather than reordering the
    syscalls to avoid it (e.g. `os.fdopen` before `os.ftruncate`) — a
    reorder would introduce a new ownership-transfer mechanic at almost
    exactly the hazard class R11-2's wrap already demonstrated (round-12's
    own mechanical "fix" generated its own new hazard; a prose correction
    must not risk generating a twin one). See `research/operations/
    2026-08-15-adr-wa-runtime-openai-provider.md` §20 for the full
    decision record.

    R10-4 binding correction, 2026-08-15 (Kimi K3 round-10 review): the
    guarantee above ("any post-open failure closes the fd") only actually
    covered `os.fchmod` — `os.ftruncate`/`os.lseek` right after were
    NAKED, so an `OSError` from either (disk full on `ftruncate`, an
    unlikely-but-real `lseek` failure) leaked the fd and raised past this
    function without ever being closed, the same gap `wa_blind_bench.py`'s
    twin `_open_private` had. Fixed identically: both calls now sit
    inside the same close-then-reraise guard as `os.fchmod`.

    R11-2 (Kimi K3 round-11 review) moved `os.fdopen(fd, "w",
    encoding="utf-8")` INSIDE this same guard, reasoning that an
    `os.fdopen` failure would otherwise leak `fd`. R12-4 SUPERSEDES
    R11-2 and reverts it (Kimi K3 round-12 review): wrapping `os.fdopen`
    in a close-on-exception guard is itself hazardous in CPython.
    `os.fdopen` constructs an `io.TextIOWrapper` around an
    `io.FileIO(fd, closefd=True)` (the default); if construction fails
    PARTWAY THROUGH — after `FileIO` has already taken ownership of `fd`
    but before `fdopen` returns — CPython may have already closed `fd`
    itself as part of unwinding the partial object. A blind
    `os.close(fd)` in the `except` clause then either (a) raises
    `OSError: [Errno 9] Bad file descriptor` on an already-closed fd,
    masking the ORIGINAL exception, or (b) — worse, in a multithreaded
    process — closes a DIFFERENT, unrelated fd the OS has already
    recycled to the same integer, silently corrupting another part of
    the process. The round-11 reviewer offered both this "wrap" option
    and a "narrow" option (leave `os.fdopen` outside the guard); the
    round-11 gate mandate chose "wrap"; round-12 measured the CPython
    hazard above and mandates "narrow" instead. Reverted: `os.fdopen`
    sits OUTSIDE the guard again, covering only
    `os.fchmod`/`os.ftruncate`/`os.lseek` (R10-4's original scope). The
    accepted residual risk is narrower than it looks: `os.fdopen` does
    not allocate a new file descriptor (it wraps the one already open),
    so the realistic failure modes are a bad `mode` string (a programmer
    error) or a rare in-process memory-allocation failure while
    constructing the wrapper objects — neither is `EMFILE`/`ENFILE`
    (both are raised by calls that open a NEW fd, which `os.fdopen`
    never does; the R11-2 docstring's "errno 24 EMFILE/ENFILE" was
    itself factually wrong on top of being the wrong fix — `ENFILE` is
    errno 23, not 24, and neither applies here). On the rare
    `os.fdopen` failure this function now leaks `fd` (a single fd, once,
    in an already-abnormal process) rather than risking a double-close
    or a stolen fd — the preferred trade."""
    prior_umask = os.umask(0o177)  # deny group/other read+write+execute
    try:
        # R8-13 (MICRO, Kimi K3 round-8 review): O_NOFOLLOW — refuse to
        # follow a pre-planted symlink at `path`, so a symlink an attacker
        # placed here before this run cannot redirect the write.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    finally:
        os.umask(prior_umask)
    try:
        os.fchmod(fd, 0o600)
        os.ftruncate(fd, 0)
        os.lseek(fd, 0, os.SEEK_SET)
    except OSError:
        os.close(fd)
        raise
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def build_corpus(
    *,
    input_dir: Path,
    output_dir: Path,
    execute: bool,
    use_ollama_ner: bool,
    ollama_model: str,
    min_remaining_chars: int = 3,
    require_role_aware: bool = True,
) -> dict[str, object]:
    redactor = Redactor.load_default()
    # `agent-library/config/redaction-rules.yaml`'s `gate.min_remaining_chars:
    # 100` is tuned for the tool's original use case — whole context BLOBS
    # sent to an external LLM. Reused here at MESSAGE granularity (single
    # WhatsApp lines, routinely under 100 chars with zero PII — "Ok grazie"
    # is 9 chars), the 100-char floor drops every short message regardless
    # of content, discovered empirically by test-running this script against
    # a synthetic fixture BEFORE writing the unit tests (anti-hallucination
    # discipline: verify reuse-first assumptions, don't assume they hold at
    # a different granularity). Lowered here, not in the shared YAML — that
    # file's gate protects a different, still-valid use case for its other
    # callers and must not be weakened repo-wide for this script's benefit.
    redactor.config.gate.min_remaining_chars = min_remaining_chars

    buckets: dict[str, list[dict]] = {"en": [], "it": [], "id": [], "other": []}
    stats = {
        "read": 0,
        "redaction_failed": 0,
        "dropped_residual_pii": 0,
        "dropped_independent_scan": 0,
        "independent_scan_errors": 0,
        "dropped_role_unknown": 0,
        "context_resets": 0,
        "accepted_context_turns": 0,
        "kept": 0,
        "mode": "role-aware-multiturn" if require_role_aware else "legacy-single-turn",
    }
    sequence = 0
    histories: dict[tuple[Path, str], deque[dict[str, str]]] = {}

    def clear_history(key: tuple[Path, str] | None, *, source_file: Path) -> None:
        """Break context continuity after any unverified or unsafe turn.

        A missing conversation ID cannot be mapped back to one history. In
        that case fail closed by clearing every accumulated conversation from
        the same source file instead of bridging over an unattributable gap.
        """
        if key is not None:
            if histories.pop(key, None) is not None:
                stats["context_resets"] += 1
            return

        matching_keys = [history_key for history_key in histories if history_key[0] == source_file]
        for history_key in matching_keys:
            del histories[history_key]
        if matching_keys:
            stats["context_resets"] += 1

    for record in _load_records(input_dir):
        stats["read"] += 1
        conversation_key = (record.source_file, record.conversation_id) if record.conversation_id is not None else None
        if require_role_aware and (record.role is None or conversation_key is None):
            stats["dropped_role_unknown"] += 1
            clear_history(conversation_key, source_file=record.source_file)
            continue
        try:
            redacted = redactor.redact(record.text)
        except RedactionError as e:
            stats["redaction_failed"] += 1
            clear_history(conversation_key, source_file=record.source_file)
            # Exception TYPE only, never str(e) — P1-privacy. A
            # `RedactionError` message can itself embed a snippet of the
            # text a nested rule was applied to (`scripts/_redact_pii.py`
            # wraps inner exceptions with `f"... raised {type(e).__name__}:
            # {e}"`), so logging this exception's string content risks the
            # same class of leak this function's own fail-closed posture
            # exists to prevent — one class-audit finding covering every
            # log site in this file, not a single-line patch.
            logger.debug("Redaction failed, record dropped: %s", type(e).__name__)
            continue

        if use_ollama_ner:
            redacted = _ollama_ner_pass(redacted, model=ollama_model)

        # Scan A.
        if _has_residual_pii(redacted):
            stats["dropped_residual_pii"] += 1
            clear_history(conversation_key, source_file=record.source_file)
            continue

        # Scan B — independent. An exception here is FAIL CLOSED: the
        # record is dropped and counted separately, never treated as
        # having passed.
        try:
            findings = _independent_pii_scan(redacted)
        except Exception as e:  # noqa: BLE001 — fail-closed boundary
            stats["independent_scan_errors"] += 1
            clear_history(conversation_key, source_file=record.source_file)
            # Exception TYPE only, never str(e) — P1-privacy. This is a
            # bare `except Exception`, so whatever raises here is by
            # definition unanticipated; assuming its message is safe to
            # log is exactly the "claim, not control" pattern the
            # orchestrator corpus gate already rejected once in this file
            # (see `_ollama_ner_pass`'s docstring).
            logger.error(
                "Independent PII scan raised, record dropped (fail-closed): %s",
                type(e).__name__,
            )
            continue
        if findings:
            stats["dropped_independent_scan"] += 1
            clear_history(conversation_key, source_file=record.source_file)
            logger.debug("Independent scan flagged %s, record dropped", findings)
            continue

        language = _guess_language(redacted)
        history_rows: list[dict[str, str]] = []
        if require_role_aware:
            assert conversation_key is not None
            assert record.role is not None
            history = histories.setdefault(conversation_key, deque(maxlen=_HISTORY_TURNS))
            history_rows = [dict(turn) for turn in history]
            history.append({"role": record.role, "text": redacted})
            stats["accepted_context_turns"] += 1
            if record.role == "assistant":
                continue

        sequence += 1
        fixture: dict[str, object] = {
            "id": f"fixture-{sequence:06d}",
            "language": language,
            "text": redacted,
        }
        if require_role_aware:
            fixture["role"] = "user"
            fixture["history"] = history_rows
        buckets[language].append(fixture)
        stats["kept"] += 1

    if execute:
        _mkdir_private(output_dir)
        for language, fixtures in buckets.items():
            out_path = output_dir / f"fixtures_{language}.local.jsonl"
            _write_jsonl_private(out_path, fixtures)
            # R7-4 binding correction, 2026-08-15 (Kimi K3 round-7 review):
            # this used to log the FULL path, embedding the
            # operator-chosen `--output-dir` component — the same R6-3
            # class already fixed for `--input-dir` in `_load_records`
            # (a directory can be named after the export/contact it
            # holds). `out_path.name` alone is safe: it is always
            # `fixtures_<language>.local.jsonl`, generated by this
            # function, never operator-chosen.
            logger.info(
                "Wrote %d fixtures -> %s (chmod 0600) in the --output-dir you passed",
                len(fixtures),
                out_path.name,
            )
    else:
        logger.info("DRY RUN (pass --execute to write): %s", {k: len(v) for k, v in buckets.items()})

    stats["by_language"] = {k: len(v) for k, v in buckets.items()}
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input-dir", type=Path, required=True, help="Directory of .txt/.jsonl WA exports")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for fixtures.local.jsonl output")
    parser.add_argument("--execute", action="store_true", help="Actually write files (default: dry run, report only)")
    parser.add_argument(
        "--use-ollama-ner",
        action="store_true",
        help="Also run a local Ollama pass (loopback-enforced), additive only — never load-bearing for eligibility",
    )
    parser.add_argument("--ollama-model", default="qwen3.5:9b", help="Local Ollama model for --use-ollama-ner")
    parser.add_argument(
        "--min-remaining-chars",
        type=int,
        default=3,
        help="Redactor gate floor at MESSAGE granularity (default 3; the shared YAML's 100 is for context blobs)",
    )
    parser.add_argument(
        "--allow-legacy-single-turn",
        action="store_true",
        help=(
            "Opt in to the historical role-blind, single-turn corpus. Default CLI mode "
            "requires JSONL records with role=user|assistant and a non-empty local "
            "conversation_id, then emits up to 12 prior de-identified turns."
        ),
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if not args.input_dir.is_dir():
        # R6-3: never log the operator's --input-dir value verbatim — same
        # fail-closed discipline as `_load_records`' "no files found"
        # warning (see that function's docstring).
        logger.error("--input-dir does not exist or is not a directory")
        return 1

    stats = build_corpus(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        execute=args.execute,
        use_ollama_ner=args.use_ollama_ner,
        ollama_model=args.ollama_model,
        min_remaining_chars=args.min_remaining_chars,
        require_role_aware=not args.allow_legacy_single_turn,
    )
    logger.info("Done: %s", stats)

    if args.execute and stats["kept"] == 0:
        # CORPUS ELIGIBILITY (module docstring): an empty corpus must never
        # read as a successful build (esiste≠armato). Non-zero regardless
        # of WHY it's empty (no input files, or every record dropped).
        logger.error(
            "CORPUS INELIGIBLE: 0 fixtures produced (read=%d). Nothing usable was "
            "written despite --execute. This is not a success.",
            stats["read"],
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
