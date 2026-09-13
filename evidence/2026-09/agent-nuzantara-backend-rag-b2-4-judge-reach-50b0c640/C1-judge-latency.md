# C1 — real support-judge latency on Pro (I97 condition C1)

Measured 2026-09-13 ~20:10Z on Pro.

**Packages**: five REAL sealed packages built by the PRODUCTION builder
(`POST /api/wa-package/build`, `dlp=True`, `history=[]`, `thread_epoch=0`) inside
the `rag` machine `1781e5eda03438`, for five SYNTHETIC questions (no client
data): PT PMA registration time, PT PMA minimum paid-up capital, E33G documents,
Sanur-Nusa Penida ferry schedule (off-domain), overstay fine per day. The wires
were kept in the session scratchpad only; nothing of their content is recorded here.

**Judge**: `CodexSupportJudge` shape unchanged — `RUBRIC.format(query=history[-1].content, context="\n\n".join(chunk.text))`,
`CodexExecClient` fixed argv, model `MODEL_TERRA` (`gpt-5.6-terra`), codex-cli 0.154.0,
`CODEX_HOME=~/.codex-acct2`. **Declared difference from the daemon**: the daemon runs
as `zantara-codex` with its own login and pinned CLI; this run used the nuzantara
user's acct2 seat (no sudo on Pro to run as `zantara-codex`). Same binary family,
same model, same adapter argv.

| pkg                             | chunks | prompt chars | container verdict (today)        | 1 rep wall s | 1 rep verdict | 3 concurrent wall s | votes | majority      |
| ------------------------------- | ------ | ------------ | -------------------------------- | ------------ | ------------- | ------------------- | ----- | ------------- |
| PT PMA registration time        | 7      | 7173         | UNAVAILABLE / absent, score 0.08 | 7.53         | SUPPORTED     | 6.32                | S,S,S | SUPPORTED     |
| PT PMA paid-up capital          | 7      | 5815         | UNAVAILABLE / absent, 0.08       | 6.31         | SUPPORTED     | 6.49                | S,S,S | SUPPORTED     |
| E33G documents                  | 7      | 16736        | UNAVAILABLE / absent, 0.08       | 6.99         | SUPPORTED     | 7.12                | S,S,S | SUPPORTED     |
| Nusa Penida ferry (off-domain)  | 6      | 5798         | UNAVAILABLE / absent, 0.06       | 6.00         | NOT_SUPPORTED | 6.34                | N,N,N | NOT_SUPPORTED |
| overstay fine per day           | 3      | 3416         | UNAVAILABLE / absent, 0.06       | 6.29         | UNKNOWN       | 7.22                | N,N,N | NOT_SUPPORTED |
| extra rep (PT PMA registration) | —      | —            | —                                | 6.29         | SUPPORTED     | —                   | —     | —             |

**Summary**: single repetition n=6, p50 **6.30 s**, max **7.53 s**; three concurrent
repetitions n=5, p50 **6.49 s**, max **7.22 s** (the daemon runs the three reps
concurrently, semaphore 4).

**Budget decision**: T_exec = 45 s (`WA_BROKER_DEADLINE_S` unset on Fly), daemon
net margin 1.0 s -> budget ~44 s; `judge_budget = min(20 s, 0.45 * budget) = 19.8 s`,
2.6x the measured concurrent max. Remaining for generation >= ~37 s against the
measured 8.5-10.1 s generations on outbox 363. UNAVAILABLE is not the normal path
at these numbers. Constants unchanged: `_JUDGE_BUDGET_CAP_S = 20.0`, `_JUDGE_BUDGET_FRACTION = 0.45`.

**Side observation (defect reproduced)**: all five production builds sealed
`support_verdict=UNAVAILABLE`, `support_judge=absent`, scores 0.06-0.08 — the
same shape as wa_outbox 422-424, on questions a real judge calls SUPPORTED.
