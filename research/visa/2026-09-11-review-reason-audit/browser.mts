import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { homedir } from 'node:os';
import { pathToFileURL } from 'node:url';
const load = (p: string) => import(pathToFileURL(resolve(process.cwd(), p)).href);
const { chromium } = await load('node_modules/playwright/index.mjs');
const { computeNextNode } = await load('apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/flow.ts');
const input = JSON.parse(readFileSync('/tmp/visaoracle-audit-20260911/inputs.json', 'utf8')).rows.find((r: {label: string}) => r.label === 'edge/tourism/unsure');
const history = [{kind: 'framing'}];
for(let i = 0; i < 100; i++) {
  const next = computeNextNode(history.at(-1), input.interview);
  history.push(next);
  if(next.kind === 'verdict') break;
}
if(history.at(-1)?.kind !== 'verdict') throw new Error('No verdict history');
const token = readFileSync(resolve(homedir(), '.config/nuzantara/visa-signing/driver-token'), 'utf8').trim();
const browser = await chromium.launch({headless: true});
try {
  const page = await browser.newPage({viewport: {width: 1280, height: 1000}});
  const captures: unknown[] = [];
  await page.route('**/api/visa-oracle/evaluate*', async (route: any) => {
    const url = new URL(route.request().url());
    url.searchParams.set('traffic_source', 'synthetic_driver');
    await route.continue({url:url.href, headers: {...route.request().headers(), 'x-visa-driver-token': token}});
  });
  page.on('response', async (response: any) => {
    if(response.url().includes('/api/visa-oracle/evaluate')) {
      const body = await response.json().catch(() => null);
      captures.push({status:response.status(),body});
    }
  });
  await page.addInitScript(({history, facts}: any) => {
    const savedAtIso = new Date().toISOString();
    sessionStorage.setItem('visa-oracle:v2:resume:v1', JSON.stringify({schemaVersion:1, savedAtIso,
      expiresAtIso:new Date(Date.now()+3600000).toISOString(), snapshot:{schemaVersion:1, attempt:0,history,facts,updatedAtIso:savedAtIso}}));
  }, {history, facts:input.interview});
  await page.goto('https://balizero.com/visa-oracle', {waitUntil:'domcontentloaded', timeout:30000});
  await page.getByText("Some of your answers need a person's judgment before we can confirm a path.", {exact:true}).waitFor({timeout:30000});
  await page.screenshot({path:'/tmp/visaoracle-audit-20260911/live-uncertainty.png',fullPage:true});
  writeFileSync('/tmp/visaoracle-audit-20260911/browser.json',JSON.stringify({url:page.url(),text:await page.locator('body').innerText(),captures},null,2));
} finally { await browser.close(); }
