# Council reviews of PR #6304 (B2.1 ENGINE) — finding F4 discharged here

The #6304 gate found that its `council-journal.jsonl` names two seats but that
a reader cannot follow the journal to any review FILE on disk. This directory
is that cure, and it is deliberately PARTIAL — for a reason that is measured,
not editorial.

## What is here, in full

| file | seat | bytes | sha256 |
|---|---|---|---|
| `kimi-k3-refutation-round1.txt` | kimi-code/k3, refuter, round 1 | 11041 | `7f46880936a75ef91e48bad3f9fb9f5f7540868eb5fd518045507bacb81290fb` |
| `gemini-3.1-pro-round1.txt` | gemini-3.1-pro, second reader (does NOT count toward quorum) | 1053 | `2ad3a16a109bccf3166e9bb010581ff47eedf485cb20ee604dd33867241fff06` |

Both were scanned before being committed: zero matches for NPWP / passport /
KITAS / email / phone / credential patterns. They are review prose about code,
and they carry no client data.

## What is NOT here, and why — with the receipts that make the claim checkable

The Codex seat's raw output is 3.4 MB across two files and the Dux's own
bundle-and-review working file is another 228 KB. Committing 3.6 MB of raw
transcript into the repo to satisfy a traceability finding would trade one
defect for a worse one. They stay in the session scratchpad of window
`6d08443a` (`.../scratchpad/`), and they are named here with their byte counts
and sha256 so that a reader can verify the file they are shown is the file that
ran:

| file (session scratchpad, NOT in the repo) | bytes | sha256 |
|---|---|---|
| `codex_round1.txt` | 755205 | `0ce588f25c6799a76b28c202cd668e8007369ac34045498c4124d8123116b4f9` |
| `codex_r1_slice1.txt` | 2690939 | `e9312a9c4456715011baced8463bf7aed08ed6dea37e1cb8431f714ec07e5475` |
| `review_full.md` (Dux working file) | 227942 | `89a8a3ff2e1ca80d624ed0ca4a8c1c0b0003a42c8e70efe826f8d7ef1a064ebb` |

The honest caveat #6304's own pack already records: the Codex seat NEVER wrote
a numbered report. It exhausted its context twice — the Dux's error, having fed
it a 228 KB bundle — and its three findings reached the pack as hypotheses it
checkpointed on its way out. All three reproduced and all three were cured, but
the proof in each case is the Dux's own reproduction, not a seat verdict. A
file containing a report that was never written cannot be persisted; what is
persisted instead is the transcript it did produce, by hash, and this sentence.

A scratchpad is session-local and does not survive the machine. If the staff
room wants these transcripts durable, that is an archival decision (where, and
with what retention) and it belongs to Zero, not to this PR.
