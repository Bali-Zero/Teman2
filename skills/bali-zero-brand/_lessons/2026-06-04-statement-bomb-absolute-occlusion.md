---
date: 2026-06-04
discovered_in: wr2-render-resolver-fix-verify-run (carousel 7bca3639-6526-4257-ab04-fb8cebd2c8df)
failure_pattern: statement-bomb layout renders text-zone underneath absolute hero+gradient overlay divs → statement body invisible in PDF
root_cause_article: Article 6.1 (hierarchy) + Article 5.5 (gradient-overlay stacking)
upstream_worker: layout-composer
severity: critical
---

# statement-bomb absolute-occlusion bug — body text invisible behind hero placeholder

## What went wrong (verbatim from this run)

Slide 4 of carousel `wr2-render-resolver-fix-verify-run` is a `statement-bomb` layout with body `DO NOT PUBLISH`. The HTML structure (slides/04.html) is:

```html
<body>
  <div class="hero" data-zone-type="hero-photo-pending"></div>   <!-- position:absolute; inset:0; background:black -->
  <div class="gradient" data-zone-type="overlay"></div>          <!-- position:absolute; inset:0; gradient -->
  <div class="statement" data-zone-type="text">DO NOT PUBLISH</div>  <!-- position:static (default) -->
  <div class="logo" data-zone-type="logo"></div>
</body>
```

The `.statement` div has NO explicit `position` or `z-index`. Because `.hero` and `.gradient` are `position:absolute; inset:0` and appear EARLIER in source order, they stack on top of `.statement` (paint order: later-in-source absolute > earlier-in-source static is ONLY true when both have same stacking context — but absolute on solid black background covering inset:0 occludes the static element below). PDF page 4 renders as pure black with only the logo visible. Body text is in the DOM but invisible.

## Why it happened (root cause)

The `statement-bomb.md` template in layout-composer was designed assuming hero presence (real image with gradient overlay). When `is_hero_image=true` but no imagegen output exists, composer writes `data-zone-type="hero-photo-pending"` placeholder div with `background:black`. The placeholder covers full viewport, occluding the statement underneath. Composer's hex-leak check + render_warnings caught the missing image but did NOT detect the resulting CSS-stacking occlusion of the text-zone.

Two compounding errors:
1. **Statement element has no z-index** — even with a real hero image, the statement should be `position:relative; z-index:2` to guarantee paint order above absolute backgrounds.
2. **Hero-photo-pending placeholder is solid black** — should be `background:transparent` or `background:var(--color-bg-photo-pending-grey)` so that the missing-image state is visible AND text underneath stays legible.

## Counter-example (how it was avoided before)

`evidence-carved` layout (slide 2 of this same carousel) renders correctly because it has NO absolute-inset hero zone — the heading/body/scope structure is in normal flow with explicit layout grid. PDF page 2 shows all text legibly. Pattern: when the layout's text-zone is in normal document flow without conflicting absolute siblings, no occlusion possible.

Production carousels with statement-bomb that DID render correctly (e.g. Golden Visa S5 closing in carousel 2026-05-12) had REAL hero JPGs with chiaroscuro lighting — the actual photo provided contrast against which the white statement was legible despite the same stacking ambiguity. The bug was latent until hero placeholder pathway was exercised.

## Detection heuristic for future runs

For ANY slide with `layout_family: statement-bomb` in slides.json:

1. Grep the rendered HTML for `class="statement"` and check if its CSS has explicit `position: relative` (or `absolute`) AND `z-index >= 2`. If not → flag.
2. If `is_hero_image=true` AND `hero_images=[]` (composer render_warning fires) → REQUIRE the hero placeholder div to use a non-opaque background OR REQUIRE statement to have z-index. Either fixes occlusion.
3. Vision-sweep the PDF page corresponding to the statement-bomb slide. If page is >90% black pixels (or one solid color) with ONLY logo visible → renderer-bug:absolute-occlusion. Hard fail.
4. Cross-template scan: any other layout (cover-photo, etc.) that uses both an absolute-inset hero zone AND a static text-zone child has the same latent bug. Audit `statement-bomb.md`, `cover-photo.md`, and any others sharing this pattern.
