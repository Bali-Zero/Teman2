# Astra round 6 — re-bind to v7 → ACCEPT

Seat: codex `gpt-6-astra`, `model_reasoning_effort=xhigh`, `--sandbox read-only`, Pro, 2026-09-11 ~04:35–04:55 WITA, cwd the v6 worktree at 497d384998 on origin/main 6a1772454552. Task: verify the v6→v7 delta contains only the four round-5 corrections, that they implement 25–28 as meant, that the D6 sentence holds, that the perimeter wording is coherent with the #5337 fence, and confirm the pins; then re-bind. Verdict: ACCEPT — Astra's imperator approval on the v7 packet hash (the approval `army-map.md:98-99` requires from both imperators). The one LOW (wording of "UPSTREAM of the leg call") is left unapplied so that the approved bytes are the shipped bytes; the Terminal route supplies the controlling interpretation, as the note itself says. Verbatim final message (`codex exec -o`):

VERDICT: ACCEPT

This reading re-binds Astra's approval of the packet to the v7 sha256 below.

- **Delta:** `e238dfd51a → 497d384998` contains only the declared changes. The three working files match that commit; `git diff --check` passes.
- **25–28 resolved:** (g1) characterizes unchanged finalizer behavior and records vulnerabilities; (g2) requires upstream suppression and terminal delivery. Mechanism and Terminal route are compatible. The bilingual construction and corrected citations implement the requested edits.
- **D6:** Fable’s sentence is correct for the post-B2.3b successful fenced terminal write: no generation means `abstained_at = NULL`; the scored package retains its frozen `evidence_score`. Those two columns alone cannot distinguish this from generated-supported delivery. B3’s disposition, route and package reference suffice for this board. **No additional Zero queue item is required**; independently queryable suppression telemetry would require a separate scope decision, without repurposing `abstained_at`.
- **Perimeter:** the sibling table and B2 §2 consistently permit B2.1’s branch and B2.3b’s telemetry work. #5337 remains suspended, its veto logic untouched, with a fresh base required after B2.3b.
- **Pins confirmed on inspected `origin/main = 6a1772454552ccbdf8941e576360eb4d9514c908`:** `wa_finalize.py:890-894` = egress-veto DEFECT; `:905-909` = cautioned SEND; `:896-898` = caution log. `wa_codex_leg.py:580-581` = unbuildable fall-off; `:928-945` = post-generation finalization; `wa_outbox_worker.py:1026-1027` = retry-path exception.

**LOW, wording only:** Mechanism’s “UPSTREAM of the leg call” should read “before broker offer/generator invocation”; the explicit Terminal route already supplies that controlling interpretation.

```text
3122b69eb86bb17565e3e9504a24f76e99ca89be8106b9330b1deab471473f0a  research/operations/2026-09-11-bot-staff-room/README.md
2da397defe2251747f1d9be44be4f9592ec5e9934416b86ea885d73eb0d6b6ed  research/operations/2026-09-11-bot-staff-room/B1-design.md
2f137a50c5400899f2cc493fab4b7d1d214d8e3ce5b0a135872a76f70588dd4b  research/operations/2026-09-11-bot-staff-room/B2-engine.md
```
