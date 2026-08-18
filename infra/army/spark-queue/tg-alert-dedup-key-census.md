# Telegram alert dedup-key census: which alerts share a dedup key and can mask each other

Read-only analysis — no plan to edit/commit/push anything.

The single Telegram gateway is `scripts/tg_notify.py`. **Step 0 (mandatory,
before judging anything): read the gateway's ACTUAL dedup semantics from the
code** — window lengths per tier, the reset-after-silence behavior, and the
state pruning — and state them in a short preamble with file:line anchors.
Judge every finding below against THOSE measured semantics, not against an
assumed model (an earlier draft of this task assumed keys dedup forever;
the gateway in fact uses finite windows + pruning — do not repeat that
mistake).

Then sweep every call-site of `tg_notify` (shell and Python) in `scripts/`
and `infra/` and extract: the KEY used, the TIER, and the SOURCE tag.

Questions to answer with evidence:

1. **Key collisions**: do two DIFFERENT failure conditions anywhere share
   one dedup key — so within one dedup window the second, different real
   alert is absorbed as a repeat of the first? List each colliding pair
   with file:line.
2. **Window-vs-recurrence mismatches**: keys whose dedup window is LONG
   relative to how often the underlying failure can meaningfully recur —
   where a genuine second incident inside the window goes silent. Use the
   window lengths you measured in step 0.
3. **Key cardinality bombs**: keys embedding unbounded identities
   (per-file, per-message ids) that defeat dedup entirely and can flood
   the channel (the W104 log-anomaly lesson: 288 messages/day when dedup
   fails open).

Why (families #2 and #3): alerting is the organism's pain sense; a dedup-key
defect is anesthesia. W107 proved alert-wrapper defects cluster — this is
the gateway-side half of that census.

Output: the step-0 preamble, then three markdown tables (one per question),
each row with file:line | key | condition | one-line consequence. N of M,
never a silent cap.
