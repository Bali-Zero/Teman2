import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

const root = '/Users/nuzantara/nuzantara/.worktrees/infra-website-r19-pro';
const review = path.join(root, 'apps/website/docs/reviews/2026-09-07-full-site-review');
const final = path.join(root, 'output/playwright/website-r19-full-site/final');
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const source = fs.readFileSync(path.join(final, 'focused-cli-result.txt'), 'utf8');
const match = source.match(/^### Result\n([\s\S]*?)\n### Ran/);
if (!match) throw new Error('Missing bounded Playwright result');
const focus = JSON.parse(match[1]);
const main = JSON.parse(fs.readFileSync(path.join(final, 'metrics.json'), 'utf8'));
const views = main.results.filter(x => x.decodeResults);
const mainSummary = {
  count: views.length,
  routes: [...new Set(views.map(x => x.route))],
  widths: [...new Set(views.map(x => x.width))],
  all200: views.every(x => x.status === 200),
  documentOverflowCount: views.filter(x => x.scrollWidth !== x.width).length,
  imageDecodeFailures: views.flatMap(x => x.decodeResults).filter(x => !x.decoded).length,
  pageErrors: views.flatMap(x => x.events).filter(x => x.type === 'pageerror').length,
  consoleErrors: views.flatMap(x => x.events).filter(x => x.type === 'console-error').length,
  navigationRequestEvents: views.flatMap(x => x.events).filter(x => x.type === 'requestfailed').length,
  noindexCount: views.filter(x => x.headers['x-robots-tag']?.includes('noindex')).length,
};
if (mainSummary.count !== 24 || !mainSummary.all200 || mainSummary.documentOverflowCount || mainSummary.imageDecodeFailures || mainSummary.pageErrors || mainSummary.consoleErrors || mainSummary.noindexCount !== 24) throw new Error(JSON.stringify(mainSummary));
const assertions = {
  sevenSkipLinksFocusMain: focus.focus.length === 7 && focus.focus.every(x => x.after.tag === 'MAIN' && x.after.id === 'main' && x.after.tabIndex === -1 && x.next.tag === 'A'),
  four404Recoveries: focus.notFound.length === 4 && focus.notFound.every(x => x.status === 404 && x.main === 1 && x.scrollWidth === x.width && x.recoveryHomeDestination === 'http://127.0.0.1:3100/' && x.recoveryServicesDestination === 'http://127.0.0.1:3100/services'),
  fourUniqueServiceNames: focus.serviceCardNames.length === 4 && new Set(focus.serviceCardNames.map(x => x.label)).size === 4 && focus.serviceCardNames.every(x => x.label.startsWith('Explore this service: ')),
  sixteenSectionCaptures: focus.sections.length === 16,
  menu360NoOverflowEscape: focus.mobileMenu.viewport === 360 && focus.mobileMenu.scrollWidth === 360 && focus.mobileMenu.expanded === 'true' && focus.mobileMenu.escape.expanded === 'false' && focus.mobileMenu.escape.active.startsWith('Menu'),
  serviceHeaderComfort44: focus.serviceControls.filter(x => ['All services', 'My Bali Zero ↗'].includes(x.text)).length === 2 && focus.serviceControls.filter(x => ['All services', 'My Bali Zero ↗'].includes(x.text)).every(x => x.height >= 44),
};
if (Object.values(assertions).some(x => !x)) throw new Error(JSON.stringify(assertions));
fs.writeFileSync(path.join(final, 'focused-metrics.json'), JSON.stringify(focus, null, 2) + '\n');
const pngs = fs.readdirSync(final).filter(x => x.endsWith('.png')).sort().map(name => {
  const p = path.join(final, name); const bytes = fs.readFileSync(p);
  if (bytes.subarray(0,8).toString('hex') !== '89504e470d0a1a0a') throw new Error('Not PNG: ' + name);
  return {path: path.relative(root, p), bytes: bytes.length, width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20), sha256: sha(bytes)};
});
for (const shot of focus.sections) if (!pngs.some(p => p.path.endsWith('/' + shot.screenshot))) throw new Error('Missing section PNG');
const checks = ['integrated-website-tests', 'integrated-architecture-tests', 'integrated-build', 'integrated-typecheck'].map(name => {
  const receiptPath = path.join(review, name + '.json');
  const receiptBytes = fs.readFileSync(receiptPath);
  const receipt = JSON.parse(receiptBytes);
  const logBytes = fs.readFileSync(path.join(root, receipt.log));
  const logHash = sha(logBytes);
  if (receipt.exitCode !== 0 || receipt.sha256 !== logHash) throw new Error('Validation receipt mismatch: ' + name);
  return {name, exitCode: receipt.exitCode, receiptSha256: sha(receiptBytes), logSha256: logHash, logBytes: logBytes.length, summaries: logBytes.toString().split('\n').filter(line => /Test Files|Tests |Duration|Compiled successfully|Generating static pages|tsc --noEmit/.test(line))};
});
fs.writeFileSync(path.join(final, 'screenshot-manifest.json'), JSON.stringify({verifiedAt: new Date().toISOString(), entries: pngs}, null, 2) + '\n');
const report = {verifiedAt: new Date().toISOString(), executor: '/root/final_visual_receipt', scope: 'Independent parsing, disk existence, hash and PNG-header verification of existing final captures and completed test logs; no browser/test/build rerun.', mainSummary, assertions, focusedSourceSha256: sha(Buffer.from(source)), focusedMetricsSha256: sha(fs.readFileSync(path.join(final, 'focused-metrics.json'))), screenshotCount: pngs.length, validationLogs: checks, captureLimitation: 'The unused home-journal-390.png element capture contains sticky-header occlusion. Reviewer input now uses full-page home-390.png. Original capture and 24-view metrics remain unchanged.'};
fs.writeFileSync(path.join(review, 'final-evidence-verification.json'), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify(report, null, 2));
