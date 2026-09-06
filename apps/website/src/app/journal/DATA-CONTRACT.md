# Journal data contract

The development site treats every Journal entry as a source-bound record. A future CMS adapter must provide the fields represented by `JournalArticle` in `src/content/journal.ts`:

- `title`: the published title, preserved without rewriting;
- `slug`: the stable Bali Zero story identifier;
- `image`: a local, authorized image path and meaningful alternative text;
- `category`: the published category, or `null` when the source does not expose one;
- `date`: an ISO date plus its human-readable label, or `null` when it cannot be verified;
- `sourceUrl`: the destination inherited from the source record;
- `finalSourceUrl`: the destination observed after redirects, when verified;
- `verificationStatus`: `pending`, `verified`, `unavailable` or `development-only`.

Only `verified` records may enter the public `/journal` selector. Records with a missing date or category remain explicit rather than receiving inferred values. Reading time, summaries and article bodies are not part of this source-only contract.

The initial six records were verified read-only on 6 September 2026. Each requested URL returned HTTP 200, retained the same final URL and exposed a matching article H1, publication date and category. Legacy `/news` query and category URLs are deliberately absent from this index because browser verification showed that they preserve parameters without changing the rendered story set.

Local article publication is a separate contract. It requires an authorized `JournalArticleDocument`, complete editorial content, a public indexing decision and an independently verified source. Until those inputs exist, the reusable article template has no route and is exercised only with the excluded development fixture.
