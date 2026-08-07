# fr/ru translation freshness — no recurring audit exists (MINUTE, options only)

**Date:** 2026-08-07
**Status:** UNRESOLVED — Legge-5 business decision, owner `operator[business]`
**Type:** MINUTE (measured findings + options; this document does not select among them)

## What this is

`apps/mouth/src/content/articles` serves five locales in production. The hourly
translation-freshness organ (`com.balizero.translate.hourly`, Pro) audits and
re-translates **two of them**. This document records the measured shape of the
other two — fr and ru — and three options, so that whether they get a recurring
freshness mechanism is a decision Zero can make explicitly, rather than a gap that
stays silent until someone re-discovers it.

**No article file, `LOCALES`, `OFFERED_LOCALES`, the plist, or
`translate-articles.py` was touched to produce this document.** Nothing here
changes runtime behavior.

## Measured today (2026-08-07), on a fresh worktree off `origin/main`

Commands and output, run in `/Users/balizero/nuzantara/.worktrees/ops-fr-ru-freshness-minute`
(branched from `origin/main` at fetch time, commit `269f9c8ee76f`):

```
$ find apps/mouth/src/content/articles -name "*.mdx" | wc -l
3356
$ for loc in en id it fr ru; do echo "$loc: $(find apps/mouth/src/content/articles -name "*.${loc}.mdx" | wc -l)"; done
en: 0
id: 797
it: 796
fr: 485
ru: 482
$ find apps/mouth/src/content/articles -name "*.mdx" | grep -vE '\.(id|it|fr|ru)\.mdx$' | wc -l
796   # English sources
```

3356 total = 796 English sources + 797 id + 796 it + 485 fr + 482 ru. This matches
the prior lane's measurement (same run, one hour apart) exactly — no drift between
the two measurements.

### The mechanism (verified, not inferred)

```
$ sed -n '424,425p' scripts/translate-articles.py
    parser.add_argument("--lang", choices=["id", "it", "ru", "fr", "both", "all"], default="both", ...
$ sed -n '456,459p' scripts/translate-articles.py
    if args.lang == "both":
        targets = ["id", "it"]
    elif args.lang == "all":
        targets = ["id", "it", "ru", "fr"]
```

```
$ ssh pro 'cat ~/Library/LaunchAgents/com.balizero.translate.hourly.plist'
...
<key>ProgramArguments</key>
<array>
    <string>/Users/nuzantara/nuzantara/.venv/bin/python</string>
    <string>/Users/nuzantara/nuzantara/scripts/translate-articles.py</string>
</array>
...
<key>StartCalendarInterval</key><dict><key>Minute</key><integer>30</integer></dict>
```

No `--lang` flag on the live plist → the script's `default="both"` fires →
`targets = ["id", "it"]`. This is mechanical, not a policy choice anyone made
about fr/ru: nobody set `--lang both` on purpose to exclude them, the flag was
simply never added.

Organ's own tally, this run (`ssh pro 'tail ~/logs/translate-hourly.log'`,
13:30 run, one hour after the prior lane's 12:30 measurement — identical
numbers, confirming id/it is stable and current):

```
13:30:06 [INFO] DONE in 0s: 0 new, 0 re-translated (stale source), 847 already fresh, 745 unstamped, 0 skipped, 0 FAILED
```

847 + 745 = 1592 = 796 × 2 (id + it). The id/it side has **0 stale** — it is
current. This document is only about the two locales the organ never looks at.

### fr/ru freshness state (re-measured via `--dry-run`, no article touched)

```
$ python3 scripts/translate-articles.py --lang fr --dry-run --category all | tail -2
Total: 796 articles x 1 languages — 311 CREATE, 16 RE-TRANSLATE, 221 fresh, 248 unstamped

$ python3 scripts/translate-articles.py --lang ru --dry-run --category all | tail -2
Total: 796 articles x 1 languages — 314 CREATE, 14 RE-TRANSLATE, 196 fresh, 272 unstamped
```

|                                                 | fr           | ru           | total   |
| ----------------------------------------------- | ------------ | ------------ | ------- |
| Served today (files on disk)                    | 485          | 482          | **967** |
| Never created (`CREATE`)                        | 311          | 314          | 625     |
| Stamped (fresh + stale)                         | 237 (221+16) | 210 (196+14) | **447** |
| **Unstamped — predates stamping, un-auditable** | 248          | 272          | **520** |
| Stale (hash-mismatch vs today's source)         | 16           | 14           | **30**  |

520/967 served files carry no freshness stamp at all (predate the 2026-07-28
stamping mechanism) — no tool that exists today, including a hypothetical
future one built on the current stamp format, can tell whether their content
still matches the English source. This is not a queue depth; it is a ceiling
on what stamping alone can ever audit for these two locales without a
baseline-stamping pass first.

### The 30 stale files: hash-stale, content-synced (checked, not stale in fact)

```
$ # 30 stale paths (16 fr + 14 ru) extracted from the two dry-runs above
$ while read -r p; do
    f="apps/mouth/src/content/articles/$p"
    grep -lE "811-399-0045|811399|8133805|813[- ]?3805" "$f"
  done < <(cat /tmp/stale_fr_paths.txt /tmp/stale_ru_paths.txt)
$ # (no output — 0 of 30 matched)
```

All 30 stale files trace to a single commit, `49add5459` (PR #3605, "four more
numbers were reaching clients, none of them ours") — a direct multi-language
hand-edit that changed a phone number in the rendered fr/ru prose without going
through the translator, so the stored source-hash no longer matches. **0 of the
30 still carry either retired number** (`+62 811-399-0045` or
`+62 813 3805 1876`) checked directly above. The hash is stale; the content is
not. Nobody should point a re-translation sweep at these 30 on the strength of
the hash alone.

### Exposure shape (why this is not purely internal bookkeeping)

- `LOCALES` (`apps/mouth/src/i18n/types.ts:14`) = `["en","id","it","ru","fr"]` — all
  five, and `content-locale.ts::resolveContentLocale` validates incoming locale
  requests against `LOCALES`, not `OFFERED_LOCALES`. A request for an available
  fr/ru file resolves to that locale, not to the English fallback.
- `OFFERED_LOCALES` (`apps/mouth/src/i18n/types.ts:27`) = `["en","id","it"]` — this
  is the picker-only list (`PublicNav.tsx`, `SecondHomeLanding.tsx`). fr/ru are
  not offered in the UI language switcher.
- `apps/mouth/src/app/sitemap.ts` — verified today, zero occurrences of
  `lang`/`locale`/`LOCALE`. It emits no language dimension, so search engines are
  not being pointed at fr/ru pages fresh; exposure is via direct URL,
  `?lang=fr`/`?lang=ru`, and a saved `blog-language` browser preference from a
  prior visit — not fresh organic indexing.

967 fr/ru pages are live, reachable, and served today; none of them sit behind
any recurring freshness mechanism, cron, or code path.

## What the 2026-07-29 ruling did and did not decide

`decision_fr_ru_withdrawn_from_the_picker_but_still_served_2026_07_29` (Zero,
PR #3435) removed fr/ru from `OFFERED_LOCALES` — the picker only — after
measuring that no organ maintained them (same `--lang both` finding as above,
then counted as 625 never-created files). That memo explicitly records the
residual as **declared, not resolved**:

> _"Le pagine fr/ru restano raggiungibili per URL diretto e continuano a
> divergere dall'inglese... Non sono più pubblicizzate — è il senso della
> decisione, non un effetto collaterale."_

It closed a `PENDING-ARMS` line about picker visibility. It did not rule on
whether the served files get any recurring freshness check. Reading it as
having settled maintenance would be treating an unratified silence as
doctrine — this document exists so that doesn't happen by default.

## Options (recorded verbatim; this document does not select among them)

**(A) Extend the recurring job to `--lang all`.**
Changes the plist's `ProgramArguments` (or adds `--lang all`) so the hourly
organ covers all five locales, same as it does id/it today. Accepts the
Ollama translation cost (roughly 2.5× the current per-run workload once the
625-file backlog is created) and the translation-quality tradeoffs of a
non-English-native model translating into fr/ru, both of which were the
explicit reasons the 2026-07-29 ruling gave for _not_ doing this at the time.

**(B) A freshness-only periodic check, no text generation.**
A cheap read-only job that reports fr/ru hash-drift (using the existing
`--dry-run`, which needs no Ollama call) on a schedule, without ever writing a
translation. Cost is near-zero. It is blind to the 520 unstamped files unless
a `--stamp-baseline` pass runs first to establish a starting point for them —
until then, "0 stale" from such a check would read as "current" when it
actually means "unauditable," which is the same shape of false-green this
document exists to avoid reproducing.

**(C) Formally ratify indefinite unmonitored drift for withdrawn locales.**
Record explicitly that fr/ru, having been withdrawn from the picker, are not
expected to have any freshness mechanism going forward — so that a future
session that finds this gap again does not have to re-derive it as a new
defect. This is a decision about acceptable risk on a client-facing surface
(967 pages, reachable, unaudited), which is why it needs `operator[business]`
sign-off rather than being inferred from the picker-only 2026-07-29 ruling.

## Not asserted here

This document does not claim fr/ru content is currently stale. The only
content-level check performed (the 30 hash-mismatches) found all 30
content-synced despite the stale hash. It does not recommend option A, B, or
C. It does not change `LOCALES`, `OFFERED_LOCALES`, the plist, or the
translator script.
