FINDINGS:

1. **MAJOR — Round-1 findings 1–6 and a–c are closed, but finding 7 is only partially closed.**
   - **1 closed:** `const` covers wrapper lines 49–55, 63–64, 140–141 through G0a–G0k; G0a/G0b/G0d/G0h/G0i and G8a–G8c use `static` killers that pin the five harness-patched constants (§5bis.3, §5bis.4, rows G0a–G0i/G8a–G8c).
   - **2 closed:** `neg` claims the eight `!` sites, including G3 at wrapper line 197; `redir` claims G1d line 171 and G2e line 181. Harness stdin is fixed to `/dev/null` (§5bis.3–4).
   - **3 closed:** §5bis.8 lines 1008–1021 discloses all six round-1 corrections and G6b/! from round 2; §5ter.3 step 8 states the severity order.
   - **4 closed:** §5ter.4(e), lines 1161–1168, removes both G2a killers while retaining the inventory and bypassing collection validation only for that selftest, so it reaches `SURVIVED`.
   - **5 closed:** §5ter.3 lines 1116–1118 defines `FO > FC > DX > EQ`.
   - **6 closed:** `test_refusal_reasons_are_pairwise_non_containing` statically checks all 13 texts (§5bis.4/§5bis.7).
   - **7 partial:** §5ter.3 lines 1074–1080 guarantees that each substring identifies exactly one collected node, closing ambiguous parameter/node matches. It does not prove that the matching node failed because of the isolated fault. Lines 1082–1085 explicitly leave that as a review-only authoring rule; step 7 requires only that *some* failing ID contain a declared substring. A collateral assertion inside that unique node can therefore still satisfy `killer_hit`.
   - **a closed:** G1d mutates the line-171 input redirection and is killed by NUL fixtures.
   - **b closed:** G3/! mutates wrapper line 197 and is killed by planted bad-semver fixtures.
   - **c closed on the specified PR-1 target:** wrapper lines 72 and 74 now use `/bin/mkdir` and `/bin/date`; a fresh byte diff confirmed these are the only changes from `wrapper_04dd.sh`. This removes the hostile-PATH distinction underlying G9b.

2. **MAJOR — The new `static` and exactly-one-node rules have no corresponding S3 selftest.** Section 5ter.4 tests UNCLAIMED, STALE-ANCHOR, NO-OP, NO-STMT, and one SURVIVED path, but never plants:
   - a `static` mutant with a run-based killer;
   - a run-mode mutant with a static killer;
   - a `killed_by` substring matching zero or multiple collected node IDs;
   - any `MODE-MISMATCH`.
   
   Thus an implementation that omits or weakens the new checks in §5ter.3 steps 1 and 8 can pass every mandated `--selftest` case. The ordinary full inventory happens to exercise G0a/G0b/G0d/G0h/G0i and G8a–G8c as static rows, but it is not a guilt test proving the checker rejects the inverse classification.

3. **MAJOR — The all-tests EQUIVALENT/mode evidence claim is not supported by the round-2 receipt chain.** Section 5ter.3 lines 1126–1133 says G0k, G1c, G7c and G9b had identical records across all 46 wrapper-running tests; §9 lines 1374–1376 consequently claims all 127 modes were measured. However:
   - `final_proof.sh` runs `modes.py`, not `modes_eq.py`;
   - `steps.jsonl` contains only the `modes` step;
   - for EQUIVALENT rows, `modes.py` substitutes five selected tests rather than running all 46;
   - `proto_s3.py` runs the whole suite but records only pass/fail survival, not all-test record equality.
   
   `modes_eq.py` appears intended to supply the missing proof, but no output from it exists in `receipts_r2`. My fresh attempt was **UNVERIFIED** because the read-only sandbox denied creation of its temporary tree. G0k is convincing by direct data-flow inspection—wrapper line 141 is overwritten at line 202 whenever line 268 can read `$2`—and G9b is plausible after lines 72/74, but the stated empirical proof was not recorded.

4. **MINOR — Two “deliberately not sites” justifications are factually too broad.** Section 5bis.3 lines 640–643 says deleting or changing every indented working assignment breaks every valid pin and is killed by every contract-P test. Deleting wrapper line 177, `_pin_line=""`, is behaviorally inert: every nonempty accepted input overwrites it at line 180, while an empty input exits on the line-count guard before `_pin_line` is read. Also, changing line 176 from `_pin_lines=0` to `-1` can accept a two-line pin whose last line is valid; that is an N-side failure, not something “every contract-P test” demonstrates. These exclusions may still be defensible as data flow, but the stated proof is false.

5. **MINOR — The command-option exclusion also overstates equivalence.** Section 5bis.3 lines 647–649 says dropping `mkdir -p` only changes an untagged error line. In the feasibility fixture, the sidecar directory already exists; changing wrapper line 72 to `/bin/mkdir "$SIDECAR_DIR" || return 0` makes `mkdir` fail and suppresses the heartbeat, which P.4/N.2 observe. This omission is currently caught by ordinary tests, but not for the reason the closed-inventory rationale gives.

6. **MINOR — The mode classifier’s first rule is broader than the declared FO semantics.** Section 5bis.6 lines 823–824 defines FO as the daemon starting when it should refuse, or starting with a different binary/version/`PYTHONPATH`. Section 5ter.3 line 1110 instead labels any new nonempty stdout as FO, even if the daemon never starts—for example the deliberately excluded `grep -q` deletion described at lines 647–648. This does not change kill/survive outcomes, but weakens the claim that every measured mode has the documented operational meaning.

Fresh command execution verified the two wrapper blob IDs and SHA-256 prefixes in §9, the exact two-line wrapper diff, and the receipt totals: 130 sites, 67 rows, 127 mutants, 123 MUST killed plus four EQUIVALENT survivors; the old-suite receipt contains 71 killed and 56 survivors. Fresh behavioral execution of G0k/G9b was UNVERIFIED because the sandbox prohibited writable temporary directories.

VERDICT: ACCEPT-WITH-NOTES