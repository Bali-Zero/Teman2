# Codex trailer attribution correction

This one-time note corrects the interpretation of five historical commits. It
preserves their Git messages and the original evidence. The declared builder seat
for this correction is **Codex Astra-2 (OpenAI; runtime variant not exposed)**.

## Observed records

On 2026-09-05 UTC, GitHub reported the five PRs below as `MERGED` with the listed
merge commits. All five commits are ancestors of the fetched `origin/main`
snapshot `2a97d99f610c3c43bae65925ee2978008bc41ec5`.

Each merge message contains this exact line, including its lowercase casing:

```text
Co-authored-by: Codex Opus 4.8 (1M context) <noreply@anthropic.com>
```

The #5778 message additionally retains two embedded copies with the prefix
`Co-Authored-By:`. These are observations of message text, not proof of which
provider or model executed the work.

| PR                                                     | Verified merge commit                      | Evidence path beneath `evidence/2026-09/`                   | Build-seat line |
| ------------------------------------------------------ | ------------------------------------------ | ----------------------------------------------------------- | --------------- |
| [#5785](https://github.com/Bali-Zero/Teman2/pull/5785) | `5c20db71243a5bc10e32d355558e7540807f9594` | `agent-air-m5-infra-b03b-required-contract-checks/pack.yml` | 7               |
| [#5782](https://github.com/Bali-Zero/Teman2/pull/5782) | `12e3871175e2288bee7bacfceadb84a469450e5d` | `agent-air-m5-mouth-v01b-fallback-edit/pack.yml`            | 6               |
| [#5781](https://github.com/Bali-Zero/Teman2/pull/5781) | `7efca77f245dbadcb0c2f9a4c71cf54c9fb70294` | `agent-air-m5-mouth-s01b-consent-reservation/pack.yml`      | 5               |
| [#5778](https://github.com/Bali-Zero/Teman2/pull/5778) | `cd407c561304c6b0ea9b1318aa1103ba12d7c49a` | `agent-air-m5-mouth-b04b-category-boundary/pack.yml`        | 5               |
| [#5777](https://github.com/Bali-Zero/Teman2/pull/5777) | `5011c114ea4353ea933cba54837a49e85b656d4f` | `agent-air-m5-mouth-x03-article-claims/pack.yml`            | 6               |

At those exact commits, each listed `lanes` entry has `role: build` and a seat
beginning `OpenAI GPT-6`, followed by an explicit qualification that the exact
variant is not exposed. That is the historical pack's declaration; this note does
not endorse its specific model label as independently verified runtime metadata.

## Interpretation and limits

The correction's session/dispatch attribution is **Codex Astra-2 (OpenAI; runtime
variant not exposed)**. It identifies the collaborating builder seat and is a
declared attribution. The Git messages and historical pack fields can be verified
independently as text; neither authenticates a runtime model. Treat the legacy
Anthropic-addressed trailer as a mislabel for these Codex-attributed lanes, not as
evidence of an Anthropic build. Independent reviewers remain distinct from the
builder. This note makes no finding about other commits or their authors.

## Reproduce

Use a clone with the history of `main` available. For each row, set `SHA`, `PR`
and `PACK` to its exact values (`PACK` includes `evidence/2026-09/`), then run:

```bash
git fetch origin main
git merge-base --is-ancestor "$SHA" origin/main
git show -s --format=%B "$SHA"
git show "$SHA:$PACK"
gh pr view "$PR" --json number,state,mergeCommit,url
```

The ancestry command must exit zero; the PR must be `MERGED` with `mergeCommit.oid`
equal to `SHA`; the Git message and build-seat declaration must match the records
above. The message command displays the original commit metadata locally. The
note reproduces only the relevant machine-attribution trailer. Existing commits
are immutable inputs to this correction; no history rewrite is requested.
