# WR2 Instagram Caption Editor — Design

## Goal

Before WR2 Control publishes a carousel to Instagram, show the automatically generated caption in the confirmation popover and let the operator edit it. The exact visible text must be the text sent to the Instagram publisher.

## Operator flow

1. The operator clicks **Pubblica su IG**.
2. WR2 Control asks the existing WR2 caption generator for the default caption.
3. The popover shows that caption in a multiline editor with a live `characters / 2200` counter.
4. **Verifica (dry-run)** and **Pubblica ora** remain disabled while the caption is loading, blank, or longer than 2,200 characters.
5. Dry-run keeps the editor open so the same reviewed caption can be published afterward.
6. The explicit **Pubblica ora** click remains the final Legge 5 gate.

## Technical shape

- Reuse `scripts/wr2_ig_caption.py`; do not duplicate caption-writing logic in Swift.
- Extend `scripts/wr2_ig_publish_remote.py` with:
  - `--print-caption`, to return the generated default without login or upload;
  - `--caption-file <path>`, to publish the operator-approved text safely, including newlines and punctuation.
- WR2 Control loads the generated caption asynchronously when opening the popover.
- WR2 Control writes the edited caption to a temporary UTF-8 file only for the publish process, passes that file to the client, and deletes it when the process ends.
- The existing Fly endpoint and Instagram publisher remain unchanged because they already accept `caption`.

## Failure handling

- A caption-generation failure is shown in the popover and blocks dry-run/publish.
- Blank or whitespace-only captions are blocked.
- Captions over 2,200 characters are shown in red and blocked.
- Shell interpolation is not used for caption contents; only the temporary file path is shell-escaped.

## Verification

- Python tests prove generated-caption fallback, file override, blank-file rejection, and caption-only behavior.
- Swift tests prove blank/limit/over-limit validation.
- Full Swift unit suite and app build must pass.
- A local UI inspection must show the generated caption, editor, counter, and disabled states.
- After verification, synchronize the committed sources and rebuilt app to Air-M5, Pro, and Mini without overwriting unrelated local changes.

## Out of scope

- Changing the caption-writing style or hashtag policy.
- Changing the Instagram backend or approval model.
- Automatic publishing without the operator confirmation click.
