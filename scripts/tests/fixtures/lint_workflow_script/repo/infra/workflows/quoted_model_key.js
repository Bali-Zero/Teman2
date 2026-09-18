// DOCUMENTED LIMIT (item 2, PR3e, 2026-09-18, gate-10 obs 2): a QUOTED model key is
// not recognised by this lint -- _neutralize_js blanks the quotes along with the
// string content, so `"model"` is invisible to MODEL_KEY_RE by the time
// _entry_key_is_model runs. Reported unpinned BY DESIGN (documented, not fixed --
// see the module docstring and _entry_key_is_model's own docstring). Use a bareword
// model: key instead (see clean.js) to satisfy RULE 1. prettier-ignore below keeps the
// quoted key from being auto-stripped by Prettier's own quote-props: as-needed default.
phase("Run");
// prettier-ignore
const answer = await agent(`do the thing`, {
  "model": "sonnet",
  label: `worker`,
});
