#!/bin/zsh
# head_mutants_trap_test.sh: the mutants' safety net, tried (#8492 gate A3a). Needs a committed tree; builds nothing.
#   1. `head_mutants.sh | head -n 1` (a closed pipe, SIGPIPE) leaves Sources/ exactly as committed;
#   2. the guilt: the same run with the PIPE trap switched off leaves Sources/ MUTATED, so the test can tell a net from no net;
#   3. staged Sources are refused (exit 4) and never mutated.
cd "${0:A:h}/../.." || exit 2
dirty() { ! git diff --quiet -- Sources || ! git diff --cached --quiet -- Sources; }
dirty && { echo "head_mutants_trap_test: Sources/ is not clean; commit first"; exit 4; }
fail=0
HM_TRAP_TEST=1 zsh Tools/design/head_mutants.sh 2>&1 | head -n 1 > /dev/null
if dirty; then echo "FAIL 1: a closed pipe left Sources/ mutated"; git checkout -q -- Sources; fail=1; else echo "ok 1: a closed pipe leaves Sources/ clean"; fi
HM_TRAP_TEST=1 HM_NO_PIPE_TRAP=1 zsh Tools/design/head_mutants.sh 2>&1 | head -n 1 > /dev/null
if dirty; then echo "ok 2: without the PIPE trap the run leaves the mutants in Sources/ (the test bites)"; git checkout -q -- Sources
else echo "FAIL 2: the guilt run left Sources/ clean: this test cannot tell a trap from none"; fail=1; fi
echo "// staged" >> Sources/FoldCensus.swift; git add Sources/FoldCensus.swift
zsh Tools/design/head_mutants.sh > /dev/null 2>&1; rc=$?
git reset -q HEAD -- Sources; git checkout -q -- Sources
if [ $rc = 4 ]; then echo "ok 3: staged Sources are refused (exit 4)"; else echo "FAIL 3: staged Sources gave exit $rc, not 4"; fail=1; fi
dirty && { echo "FAIL: the test left Sources/ dirty"; git checkout -q -- Sources; fail=1; }
exit $fail
