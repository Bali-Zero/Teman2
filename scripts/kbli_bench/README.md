# KBLI Navigator P2b benchmark — tooling + resume runbook

Design: `research/operations/2026-08-19-kbli-navigator-phase2-codex-chat-design.md` §8.
State at 2026-08-20: **tooling ready, corpus frozen, RUN SUSPENDED** — the ChatGPT Pro seat
(both the serving model `terra` and the judge `sol` ride it) hit its usage limit; codex answers
`try again at Aug 22nd, 2026 8:30 AM`. Never pay for credits (standing rule); never substitute
another seat (the benchmark measures THE product, which serves through this seat).

## Frozen artifacts

| artifact | where | identity |
| --- | --- | --- |
| corpus (29 q: 8 structured / 18 known-gap / 3 out-of-corpus probes) | `scripts/kbli_bench/p2b_corpus.json` | sha256 `487bc9509d01456eb37a588c3ee942f4956731502697aef94f1a2ee1294008e7` (pre-freeze fix of a meta count: earlier draft said 17 known-gap; measured 18) |
| scoring + judge-prompt tool | `scripts/kbli_bench/score_p2b.py` | deterministic tuple checker verified on an 8-case guilt+innocence corpus this session |
| Swift harness (run + extract) | app repo (M5, no remote) `Tests/benchrunner/main.swift`, commit `112241c0d89406477e1a63b3dc8aeb4ab9355632` | compiled on Pro: `xcrun --sdk macosx swiftc Sources/{Models,KBLIStore,KBLIContextPackage,KBLIAnswerGate,KBLICodexRunner}.swift Tests/benchrunner/main.swift -o /tmp/benchrunner` RC=0 |
| harness build inputs on Pro | `pro:/tmp/kbli-p2b-bench` (rsync of app repo) + `pro:/tmp/benchrunner` | bundled dataset `Resources/KBLI_2025_FINAL_CLEAN.json` sha256 `a5721756d5b2…` — the app's rev; field-diff vs canonical `3dafab17…` on all Swift-decoded fields was ZERO (measured 2026-08-19 BKPM audit) |
| old-brain probes (all auth-dead 7/7) | `scripts/kbli_bench/oldbrain_probes/` | probe1 ~11:0x, probe2 12:0x UTC 2026-08-20; run probe3 at resume for the ≥3-probe absence corroboration |

Independent verification done 2026-08-20 (generator≠grader): harness spot-read (no retry at
line 232, model pinned by `KBLICodexRunner.buildArgv()` at line 215, real `KBLIAnswerGate.check`
×4), and an extract-mode guilt+innocence smoke run by the conductor (25200→"100%" rejected with
`actual:49`; 51101→"49%" accepted).

## Resume sequence (after 2026-08-22 08:30 WITA — verify seat first)

```bash
# 0) seat probe (expect a reply, not the usage-limit error)
ssh pro 'PATH=/opt/homebrew/bin:/usr/bin:/bin codex exec --sandbox read-only --skip-git-repo-check --ephemeral -m gpt-5.6-terra - <<< "Reply with exactly: SEAT-OK" 2>&1 | tail -2'

# 1) old-brain probe 3 (on Mini, record verbatim into oldbrain_probes/probe3.txt)
timeout 110 ~/.openclaw/bin/openclaw agent --agent zantara-kbli --local --json \
  --message "Untuk KBLI 51101 angkutan udara berjadwal, berapa batas kepemilikan asing?" 2>&1 | tail -6

# 2) full new-brain run on Pro (serial, ~87 codex calls; rebuild binary first if /tmp was cleaned)
scp scripts/kbli_bench/p2b_corpus.json pro:/tmp/p2b_corpus.json
ssh pro 'cd /tmp && KBLI_JSON=/tmp/kbli-p2b-bench/Resources/KBLI_2025_FINAL_CLEAN.json \
  /tmp/benchrunner run /tmp/p2b_corpus.json /tmp/p2b_answers.jsonl --runs 3'
scp pro:/tmp/p2b_answers.jsonl scripts/kbli_bench/results/

# 3) judge prompts (sol, one per question, all runs inline)
python3 scripts/kbli_bench/score_p2b.py prompts scripts/kbli_bench/p2b_corpus.json \
  scripts/kbli_bench/results/p2b_answers.jsonl /tmp/p2b_judge_prompts
# for each prompt: ssh pro codex exec -m gpt-5.6-sol (read-only, ephemeral, stdin) → /tmp/p2b_judge_out/<qid>.json

# 4) score + floors
python3 scripts/kbli_bench/score_p2b.py score scripts/kbli_bench/p2b_corpus.json \
  scripts/kbli_bench/results/p2b_answers.jsonl /tmp/p2b_judge_out > scripts/kbli_bench/results/p2b_score.json

# 5) session hand-check: 100% of flagged + the seeded 20% random sample in the score JSON
# 6) report in research/operations/2026-08-2X-kbli-navigator-p2b-benchmark.md
#    (manifest: app commit, bundled dataset sha, codex --version, model id, corpus sha,
#    rubric + run count) → adversarial gate → PR → gate decision on the §8 floors.
```

A→B ordering (§8): this run is on build **A** (OpenClaw compiled-but-unreachable). Only on a
green gate does P2c delete the OpenClaw path (build **B**) and re-run the new-brain suite on B.
