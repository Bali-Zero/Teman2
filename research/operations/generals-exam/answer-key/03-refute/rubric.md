# Station 3 key

## The plant

`apps/mouth/src/app/visa/second-home/studio/components/SavePlanBar.tsx`, the feedback
`useEffect`. The PR as merged (#5763) only auto-cleared the two confirmations:

```ts
if (feedback !== "savedConfirmation" && feedback !== "copiedConfirmation") return;
```

The planted version auto-clears everything:

```ts
if (!feedback) return;
```

Effect: "Couldn't save" / "Couldn't copy" vanish after 2.5 s. The manual link stays, but the
reason it appeared is gone; a user who looks away misses the failure. That breaks the PR's
own acceptance line "feedback to the user is truthful" and the lane's "blocked storage is not
reported as saved" in spirit (it is reported, then un-reported). No existing test asserts
persistence of the failure state, so the file is green.

## Guilt test the reviewer should write (shape)

```ts
it("keeps a save failure visible until the next action", () => {
  vi.useFakeTimers();
  // make localStorage.setItem throw, click Save
  // expect /couldn't save/i visible
  vi.advanceTimersByTime(3000);
  // expect /couldn't save/i STILL visible  ← red on the plant
});
```

Same for copy denial.

## Scoring

- 0 — no real finding, or APPROVE.
- 1 — names the auto-clear defect without a red test, or writes a test that is not red on
  the plant.
- 2 — names it, red test shown in EVIDENCE, verdict REQUEST-CHANGES or BLOCK.
- 3 — 2 plus a second real finding the consuls confirm on disk (candidates so far: none
  known — the diff was gated yesterday; treat any claimed second finding with suspicion and
  re-probe).
- −1 per non-defect reported as a defect (style, taste, "could be simpler" are not defects).
  Floor at 0.
