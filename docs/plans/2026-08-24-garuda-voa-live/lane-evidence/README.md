# lane-evidence

These are the assembly-line Evidence Packs (`brief.yml` + `pack.yml` per lane)
for five of the build lanes behind the GARUDA VOA product: L1 retention, L3
checkout, L4 practice, L4 store follow-up, and the L2/VOA composition seam.
Their CODE already merged into `main`, across PRs #4950, #4952, #4955, #4959,
#4960, #4968, #4972.

They are preserved here — verbatim, byte-identical to the copies that lived
on `feature/garuda-voa` — because that integration branch is dead and will be
deleted, and this is otherwise the only record of how each lane's work was
built and adversarially reviewed at the time.

**This directory is archival, not live evidence for any open PR.** That is
also why it does not live under `evidence/` at the repo root: this repo's
evidence-resolution machinery (`scripts/ci/evidence_paths.py`,
`scripts/evidence_pack_lint.py`, wired into `harness-floor.yml`) treats
anything under `evidence/*/pack.yml` as a claim that THIS diff needs a real
Gear-3 gate verdict. Every one of these five packs self-declares `gear: 3`
(true of the original work) — landing them under `evidence/` would demand
five independent graders adjudicate five file copies that change no
behavior, which is ceremony without adjudication. Putting them here instead,
beside this plan's `MANDATE.md`, keeps the record without spending a gate on
it.
