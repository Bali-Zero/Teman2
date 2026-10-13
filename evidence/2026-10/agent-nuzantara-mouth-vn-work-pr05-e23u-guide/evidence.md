# Evidence PR-05 E23U

## grep diplomatic missions in guides (EN/ID/IT)

0 hits

## E23U rows

apps/mouth/src/content/articles/immigration/e23-employee-kitas-guide.it.mdx:93:| **E23U** | Personale Domestico Diplomatico | Collaboratore domestico di un diplomatico straniero | Staff domestico privato dei
apps/mouth/src/content/articles/immigration/e23-employee-kitas-guide.mdx:91:| **E23U** | Diplomat Household | Household assistant of a foreign diplomat | Private household staff of diplomats  
apps/mouth/src/content/articles/immigration/e23-employee-kitas-guide.id.mdx:93:| **E23U** | Rumah Tangga Diplomat | Asisten rumah tangga diplomat asing | Staf rumah tangga pribadi diplomat

## llms-full.txt (committed, stale) diplomatic missions hits

33092:Applicants for the D12 typically must demonstrate a credible intent to invest, which
48628:The ARTOTEL Group, which operates the Mangkuluhur Suites property, has in recent yea
182641:| **E23U** | Diplomat Household | For domestic staff employed by diplomatic miss
268510:| Who can hold | Indonesian citizens, foreigners with KITAS/KITAP, Indonesi

## generator

cd apps/mouth && LLMS_GENERATE_ARTICLES_ONLY=1 npx --no-install tsx scripts/generate-llms-full.ts (wired into mouth npm build)
Drift when run: llms-full.txt +277082/-277125, llms-id.txt +72933/-70210, llms.txt +5/-5 (~350k lines, > 400 limit). Not committed; reverted. Build regenerates on deploy.

## Codex RT (gpt-5.6-sol, high, read-only): verdict = no defects; E23U semantics match rulepack-prod-028 line 978.

.../src/content/articles/immigration/e23-employee-kitas-guide.id.mdx | 2 +-
.../src/content/articles/immigration/e23-employee-kitas-guide.it.mdx | 2 +-
.../mouth/src/content/articles/immigration/e23-employee-kitas-guide.mdx | 2 +-
3 files changed, 3 insertions(+), 3 deletions(-)

Codex rollout confirms model gpt-5.6-sol.
