# Bounded review resolution

The independent Claude review accepted the local fixture proof and reported no
local release blockers. The following changes were made after its final
response; it did not re-review these edits. The builder reran all 102 tests,
build and sequential typecheck, then inspected fresh desktop/mobile captures.
The original reviewed images are preserved under reviewed-before-fixes/;
review-provenance.json binds their hashes and the source inputs read.

| Finding | Resolution |
| --- | --- |
| 1: Brand accessible label differs from visible name | Removed redundant aria-label; the visible Journal name names the link. Browser lookup by visible name succeeds. |
| 2: Doubled hero gutter | Removed outer horizontal padding. Browser measures hero and story left edges at 64px desktop, 20px mobile. Header/footer alignment refinement is deferred. |
| 3: Detached bottom rule on image-less card | Grid items align at start; short cards no longer stretch to match the illustrated card. |
| 4: Image-first headline hierarchy | Deferred as optional composition; retained the approved image-first lead. |
| 5: Empty third homepage column | Omit empty side column and use two columns above 1050px when no side stories exist. |
| 6: Missing text-only slide evidence | Added desktop/mobile home-text-only screenshots. Text-led cards intentionally use natural height; a fixed carousel height remains an optional refinement. No blank media frame or substitute photograph is introduced. |
| 7: Hover effect on inert fixture | Image zoom selector applies only to anchor destinations. |
| 8: Skip destination focus | Added tabIndex=-1 on main; browser Enter activates the skip link and focuses journal-content. |
| 9: Ordered-list semantics | Added explicit list role. No Safari/VoiceOver execution is claimed. |
| 10: Home sample marker | Feature and other story date blocks now include Sample story in fixture mode. |
| 11: Small navigation targets | Added vertical padding/minimum height; measured heights at least 32px on both checked viewports. |
| 12: Repeated synthetic rationale | Retained; explicitly synthetic data is intended to exercise the same contract, not serve as finished editorial copy. |

The two medium findings partly concerned inherited Journal presentation. They
were corrected because the changes were small, directly relevant and did not
alter the R19 direction. The reviewer measured static images and did not use a
screen reader; its contrast estimates and standards references are not a full
accessibility certification. Production suggestions remain unarmed prerequisites,
not authorizations to expose source data or add invented correction prose.

Final browser evidence: evidence/browser-after-review.txt and
evidence/browser-home-after-review.txt. Final screenshots keep the original
filenames at output/playwright/website-r19-pro/, with the extra text-only pair.
The unavailable screenshot was taken before cosmetic fixes and remains labeled
as evidence of that earlier default-state check.
