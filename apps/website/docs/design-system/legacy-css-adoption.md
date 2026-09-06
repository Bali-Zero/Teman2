# R19 legacy CSS adoption and deletion plan

Audit basis: immutable seed `687075491cccf496a66da657ed4b16c31d87db41`. The imported `src/app/globals.css` is 6,517 lines and remains coordinator-owned. This lane changes none of it.

Deletion must follow verified consumer adoption; selector removal is never bundled into the primitive dependency commit.

## Shared selectors to adopt first

| Legacy selector | Current consumers | Adopt with | Coordinator deletion gate |
| --- | --- | --- | --- |
| `.wrap` (`globals.css:87`) | Services, Journal, Reviews, Portal, SecondHome, Contact, Team, Footer | `Container` | Remove only after every listed consumer renders through `Container`; keep section-specific sizing in local modules. |
| `.eyebrow` (`globals.css:91`) | Services, Journal, Reviews, Portal, Evoa, Entry, Contact, Team, Footer | `SectionHeading` for section introductions; local semantic text for card/category labels | Remove only after the final non-heading label has its owning module style. Do not force every label into `SectionHeading`. |
| `.textlink` (`globals.css:101`) | Services, Journal, Reviews, Contact, Team | `TextLink` | Remove after all five consumers adopt the component or an explicit domain-local link style. |
| `.button`, `.button:hover`, `.button.light`, `.button.copper`, `.button.copper:hover` (`globals.css:105-132`) | page assist, Reviews, Evoa, SecondHome, Contact, Team | `Button`, `ButtonLink` | Remove after consumer-by-consumer visual comparison. Map `light` to `secondary`; map `copper` to `copper`. |
| `.services-intro`, `.services-intro h2`, `.services-intro p` (`globals.css:6453-6468`) | Services only | `SectionHeading` | Service lane confirms narrow and wide heading rhythm before deletion. |

## Service-card split

The `.tool` block at `globals.css:2864-3190` mixes reusable card surface with service-only illustration and interaction rules. The service lane should adopt `Card` for the article boundary, then move only genuine service rules into its own CSS Module:

- retain locally: `.tools`, `.tool-index`, `.tool-art`, `.tool-ui`, per-service accent variables, `.service-description`, and `.service-contact`;
- replace with `Card`: `.tool` background, border, radius, padding, and shadow declarations;
- delete as unconsumed if the new service routes still contain no matching controls: `.tool h2`, `.tool label`, `.tool .tool-prompt`, `.tool input`, `.tool select`, `.tool input::placeholder`, `.tool option`, `.tool .small`, `.tool .chips`, `.tool .chips button`, and `.tool .chips button[aria-pressed="true"]`;
- delete as stale after link adoption: `.tool .textlink .arrow` and `.tool:hover .textlink .arrow`; the seed markup has no `.arrow` descendant in Services.

The hover lift on `.tool:hover, .tool:focus-within` is domain behavior, not part of `Card`. Keep or remove it in the service module based on the rendered comparison rather than inheriting it into the primitive.

## Journal-card split

Journal currently duplicates card surfaces in `.feature` (`globals.css:3681`), `.news-main > article` (`globals.css:3765`), and `.news-side article` (`globals.css:3843`). The Journal lane may use `Card` for article boundaries while retaining image ratios, editorial grid, carousel controls, story indices, and headline scales in its own module.

After that adoption:

- remove duplicated paper/background/border/radius/shadow declarations from `.feature` and `.news-main > article`;
- keep `.feature` overflow only if the image treatment needs clipping;
- keep `.news-side article` structural spacing and dividers locally;
- remove the second token set `--r15-paper`, `--r15-line`, `--r15-copper`, and `--r15-ink` (`globals.css:3664-3668`) only after every Journal declaration resolves to `--bz-*` variables inside the scoped route.

## Global shell proposal

The coordinator owns the only eventual global patch. Once Services and Journal prove adoption, it may replace the original `:root` color/type variables (`globals.css:2-11`) with aliases to the frozen `--bz-*` values and then remove the duplicated generic selectors above. Until that point, the scoped module and imported globals intentionally coexist.

No deletion is safe based only on selector names. The gate is a wide/narrow rendered comparison plus the existing keyboard tests for every listed consumer.
