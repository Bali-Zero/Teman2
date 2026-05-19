## Summary

<!-- What changed, and why. -->

## AI Developer Close-Out

- Agent / automation:
- Started from branch or worktree:
- Main checkout dirty at start: yes/no
- Dirty files resolved by: committed / moved to branch / ignored local-only / blocked
- Close-out command: `./scripts/ai_dev_closeout.sh --strict`

## Verification

- [ ] Relevant tests/lint/typecheck run
- [ ] `git diff --check`
- [ ] If MDX content changed, locale/base/serialization checked
- [ ] If operational scripts changed, `bash -n` and safe dry-run/check run
- [ ] If backend code changed, backend venv used and import chain checked

## Known Blockers Or Pre-Existing Failures

<!-- Name exact commands and why the failure is or is not related to this diff. -->
