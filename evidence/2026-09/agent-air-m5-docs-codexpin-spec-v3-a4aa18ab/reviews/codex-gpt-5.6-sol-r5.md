FINDINGS:

1. **MINOR — A: gate r5’s four reported instances are closed by the two general rules.**
   - **I1: Yes.** §5bis.3’s `alt` table now generates `drop` per alternative and both whole-arm polarities independent of pattern spelling. The target demonstrates this with `167483363793d9b2:alt#1:widen` and `:neutralise` at line 84, `ac6dc4f641d4266b:alt:widen/:neutralise` at line 85, and `c21200da23f1dc4e:alt:widen/:neutralise` at line 188. The I1 mini exposes the previously missing member as surviving `a09562b09056cd3c:alt:neutralise`, while the complete suite kills it.
   - **I2: Yes, for the carrier instance.** §5bis.3 rule 4 replaces prefix spelling recognition with a closed command catalogue and resolved-command rule. A resolved `"$SH_BIN"` reaches the shell entry and produces `MASKED l.4 sh string: andor,test`; an unresolved variable produces `UNSUPPORTED ... non-literal command word`; `timeout`, `sudo`, `nohup`, `nice`, `find`, and other prefixes are unsupported commands. This closes the exact masked-carrier silence found by r5.
   - **I3: Yes.** §5bis.3’s `setopt` row and atomic-units rule operate per option unit. The mini generates `1adc77ac9ebfc68c:setopt#1:remove`, `#2:remove`, and `#3:remove` for `set -eu -o pipefail`; deleting `pipefail` is therefore independently represented.
   - **I4: Yes.** `env-drop` is removed and the new `assign` kind operates per assignment word. Target line 270 has independent members `b9a04673c49fc0c4:assign#1:drop` and `:assign#2:drop`; the env mini likewise has `65d84f2aefee0737:assign#1:drop` and `#2:drop`. The amended `reassert:remove` rule also deletes only one assignment word on multi-assignment lines.

2. **BLOCKER — B: YES. The installer still contains accepted guard calls whose fail-open deletion has neither a generated member nor an S3 error.** At installer line 131, `_verify_root_owned_dir "$RUNTIME_DIR" "trust root"` is the sole invocation that applies the line 117–129 trust-root checks to `RUNTIME_DIR`. Deleting line 131, or replacing it with `:`, bypasses the symlink, existence, owner, group, and writable-mode refusal checks. §5bis.3 rule 4 expressly accepts calls to target-defined functions, but none of the 18 kinds generates a member for an ordinary function call. The 53-error receipt has no error at line 131. The same hole occurs at line 261 (`_verify_extracted_tree "$EXTRACT_DIR" "$VERSION"`) and line 267 (`_verify_extracted_tree "$DEST" "$VERSION"`): deleting either call bypasses the corresponding extracted-tree or reuse verification, with no member and no error. This is the same general granularity class, now caused by treating a function body’s internal sites as sufficient coverage for deletion of the call that activates all of them.

3. **BLOCKER — C: the atomicity rule still gives a supported refusal-bearing unit only one polarity.** §5bis.3 rule 1, in the added hunk beginning at line 842, first says every refusal-bearing condition gets both polarities, but then exempts `while`/`until`, generating only `never`. The claim that the other polarity merely causes a timeout is not true for the accepted grammar:
   ```sh
   verify_next() { false; }
   choose() {
       while verify_next; do
           return 0
       done
       return 78
   }
   choose
   ```
   All constructs and commands are supported by rules 3–4. `cond:always` changes the refusal path into immediate success through `return 0`; it does not loop. Nevertheless, the table generates only `cond:never` for the `while`, and the non-test operand `verify_next` receives no constants. This directly violates the owner’s unconditional requirement that every refusal-bearing unit have both the always-refusing and fail-open polarities.

4. **BLOCKER — C: a supported code carrier can itself be deleted without coverage.** Installer line 110 is `trap _cleanup EXIT`. Rule 4 accepts `trap`, recursively parses `_cleanup`, and reports `MASKED` only when the action contains a site. Because `_cleanup` is merely an accepted target-function call, line 110 produces neither a site nor an error—the receipt contains no line-110 diagnostic. Deleting the line disables the line 98–109 cleanup guarantee for staging and temporary pin files. Recursive inspection of carrier contents does not cover deletion of the carrier that makes those contents execute.

5. **MAJOR — D: the universal closure claims are not supported by the included evidence and are contradicted by the current installer.** The aggregate claims—138/182 for the wrapper, 140/196 plus 53 errors for the installer, and the six new wrapper members being killed—are supported by the receipts. The claims in §5bis.3 rule 1 that “each” refusal-bearing unit gets both polarities and in rule 5 that every relevant atomic unit has its own member are not: the rule text itself excludes the second loop polarity, while accepted function-call guards at installer lines 110, 131, 261, and 267 have no generated ids. The supplied feasibility runs test the listed/generated members; they cannot establish completeness against deletions that the generator never emits.

VERDICT: REWORK