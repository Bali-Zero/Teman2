# codex-gpt-5.6-sol — dispatched, ran, did not deliver

`codex exec -m gpt-5.6-sol -c model_reasoning_effort=xhigh --sandbox read-only --skip-git-repo-check`
was dispatched on the candidate with an adversarial brief (over-match, under-match, two authorities
disagreeing, the language-vocabulary trap, perimeter, vacuous tests). It ran to **251,565 tokens**,
hit its own context checkpoint, and terminated having written **77 bytes** of stdout — the literal
string `Checkpoint salvato. La review continua automaticamente nella nuova finestra.` — and no
report.

This file exists so the seat is not silently dropped from the council. **A seat that did not deliver
is not a seat that agreed.**

## What survived, and what was done with it

Its planning trace (stderr) named two leads before it died:

1. _"Synthetic probes already show both over-match and under-match cases."_
2. _"Source and tests appear to persist verbatim private conversation content; do not reproduce it
   in report."_

Neither was re-dispatched. Both were converted into a direct measurement by the Dux, which is
strictly better evidence than a model's report of a measurement:

- **Lead 1** became a 32-guilt / 23-innocence census run against the guard on disk. It found
  **over-match 0/23** and **under-match 2/32** — and the two misses were the same shape,
  `are you an AI?` and `sei un'intelligenza artificiale?`. Those are now in the phrase table, in
  all five languages, and the post-cure census is 0 and 0. The lead was real and it was answered.
- **Lead 2** was checked and is a false positive with a true instinct: the two Italian sentences are
  the owner's own probe messages to the sandbox number and carry no identifier. Their provenance is
  now stated in the module docstring so the next reader does not have to make the judgement again,
  and a grep of the whole diff for credential and identifier shapes returns zero hits.

## The reusable part

A read-only reviewer pointed at a worktree will explore until its budget is gone unless the brief
bounds what it may read. This brief did not, and 251k tokens bought two sentences. Next time: name
the files it may open, forbid the exploration, and ask for the **census** rather than for a verdict
— a verdict is what a model produces last, and it is the first thing lost when the budget runs out.
