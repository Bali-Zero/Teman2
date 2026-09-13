import { writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
const repo = process.cwd();
const load = (file: string) => import(pathToFileURL(resolve(repo, file)).href);
const { enumerateScenarios, runWalk, CORPUS_TODAY } = await load('apps/mouth/scripts/visa-oracle/generate-walk-corpus.ts');
const { mapOracleFactsToApplicantFacts } = await load('apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/fact-mapper.ts');
const { REVIEW_REASON_COPY } = await load('apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/engine-adapter.ts');
const scenarios = enumerateScenarios();
const tourism = scenarios.find((s: {label: string}) => s.label === 'offshore/tourism');
scenarios.push({label: 'edge/tourism/unsure', overrides: {...tourism.overrides, review_gate: 'not_certain'}});
scenarios.push({label: 'edge/tourism/unsure-answer', overrides: {...tourism.overrides, entry_pattern: 'unsure'}});
for (const [label, overrides] of [
  ['edge/bridging/unknown-location', {in_indonesia: 'unsure', holds_stay_permit: 'yes', stay_permit_code: 'E31A', permit_expiry: '2027-01-01', category: 'tourism'}],
  ['edge/bridging/unknown-status', {in_indonesia: 'yes', holds_stay_permit: 'yes', stay_permit_code: 'unsure', permit_expiry: '2027-01-01', category: 'tourism'}],
  ['edge/voa/unknown-nationality', {...tourism.overrides, nationalities: 'unsure', stay_days: '30'}],
] as const) scenarios.push({label, overrides});
const rows = scenarios.map((scenario: {label: string; overrides: Record<string, string>}) => {
  const { asked, facts } = runWalk(scenario.overrides);
  return { label: scenario.label, asked, interview: facts,
    request: mapOracleFactsToApplicantFacts(facts, {assessmentId: 'a98d6f70-4c13-4b34-9522-446b7d483430', collectedAt: CORPUS_TODAY}) };
});
writeFileSync('/tmp/visaoracle-audit-20260911/inputs.json', JSON.stringify({review_copy: REVIEW_REASON_COPY, rows}, null, 2));
