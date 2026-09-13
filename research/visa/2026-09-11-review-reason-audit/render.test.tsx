import { readFileSync, writeFileSync } from 'node:fs';
import { cleanup, render } from '@testing-library/react';
import { expect, it } from 'vitest';
import { buildEngineOutcome, REVIEW_REASON_COPY } from './engine-adapter';
import { OutcomeSheet } from '../_components/OutcomeSheet';
import { makeVisaOracleResponse } from './visa-oracle-test-fixture';
import type { VisaOracleEvaluateResponse } from './visa-oracle-contract';
import type { OracleFacts } from './tree';
const dir = '/tmp/visaoracle-audit-20260911/';
interface Row {label: string; state: string; envelope: VisaOracleEvaluateResponse}
interface Input {label: string; asked: string[]; interview: OracleFacts}
const census = JSON.parse(readFileSync(dir + 'census.json', 'utf8'));
const inputs: Input[] = JSON.parse(readFileSync(dir + 'inputs.json', 'utf8')).rows;
const rows: Row[] = census.clocks.current.rows;
const rendered: unknown[] = [];
it('renders all replay reviews through the real adapter and OutcomeSheet in both languages', () => {
  for (const row of rows) {
    const input = inputs.find((item) => item.label === row.label)!;
    const outcome = buildEngineOutcome(row.envelope, {facts: input.interview, editableQuestionIds: input.asked});
    expect(outcome.state, row.label).toBe(row.state);
    if (outcome.state !== 'HUMAN_REVIEW_REQUIRED') continue;
    for (const language of ['en', 'id'] as const) {
      const {container} = render(<OutcomeSheet outcome={outcome} language={language} facts={input.interview} />);
      const list = container.querySelector('.oracle-reason-list');
      for (const reason of outcome.reviewReasons) expect(list).toHaveTextContent(reason.message[language]);
      rendered.push({label: row.label, language, reasons: outcome.reviewReasons.map((r) => ({code:r.code, mapped:r.code in REVIEW_REASON_COPY, message:r.message[language]}))});
      cleanup();
    }
  }
});
it('renders all discovered codes using fixture envelope metadata, independently of reachability', () => {
  const codes = [...census.taxonomy.mapped, ...census.taxonomy.unmapped];
  for (const code of codes) {
    const response = makeVisaOracleResponse('HUMAN_REVIEW_REQUIRED');
    response.decision.review_reasons[0].code = code;
    const outcome = buildEngineOutcome(response);
    if(outcome.state !== 'HUMAN_REVIEW_REQUIRED') throw new Error('unexpected state');
    for (const language of ['en', 'id'] as const) {
      const {container} = render(<OutcomeSheet outcome={outcome} language={language} facts={{}} />);
      expect(container.querySelector('.oracle-reason-list')).toHaveTextContent(outcome.reviewReasons[0].message[language]);
      cleanup();
    }
  }
  expect(codes.length).toBe(38);
});
it('renders the unmodified actual synthetic production response', () => {
  const text = readFileSync(dir + 'live-response.txt', 'utf8');
  expect(text.split('\n')[0]).toBe('HTTP 200');
  const outcome = buildEngineOutcome(JSON.parse(text.slice(text.indexOf('\n') + 1)));
  expect(outcome.state).toBe('HUMAN_REVIEW_REQUIRED');
  for (const language of ['en', 'id'] as const) {
    const {container} = render(<OutcomeSheet outcome={outcome} language={language} facts={{}} />);
    expect(container.querySelector('.oracle-reason-list')).toHaveTextContent(language === 'en'
      ? "Some of your answers need a person's judgment before we can confirm a path."
      : 'Beberapa jawaban Anda memerlukan penilaian dari seseorang sebelum kami dapat mengonfirmasi jalur.');
    cleanup();
  }
  writeFileSync(dir + 'rendered.json', JSON.stringify(rendered, null, 2));
});

it('renders the separate client-verification fallback without trusting rejected engine details', async () => {
  const {buildDegradedHumanReviewOutcome} = await import('./outcome-fallbacks');
  const outcome = buildDegradedHumanReviewOutcome({});
  expect(outcome.reviewReasons[0].code).toBe('CLIENT_UNABLE_TO_VERIFY_DETAIL');
  expect(outcome.reviewReasons[0].code in REVIEW_REASON_COPY).toBe(false);
  for (const language of ['en', 'id'] as const) {
    const {container} = render(<OutcomeSheet outcome={outcome} language={language} facts={{}} />);
    expect(container.querySelector('.oracle-reason-list')).toHaveTextContent(outcome.reviewReasons[0].message[language]);
    cleanup();
  }
});
