import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { execFileSync } from 'node:child_process';

// Separate owner-authorized WIP backup. This is never the final acceptance gate.
const root = '/Users/nuzantara/nuzantara/.worktrees/infra-website-r19-pro';
const branch = 'codex/website-pro-continuation';
const base = 'b740b2cc3e94b1a46c9e9811bb369289fc21ea3d';
const review = 'apps/website/docs/reviews/2026-09-07-full-site-review';
const old = 'output/checkpoints/2026-09-07-pro-slice';
const relativeCheckpoint = 'output/checkpoints/2026-09-07-pre-design';
const clearance = 'output/playwright/website-r19-full-site/clearance-fix';
const checkpoint = path.join(root, relativeCheckpoint);
const original = '/Users/nuzantara/website-handoffs/2026-09-07-r19';
const run = (command, args, options = {}) => execFileSync(command, args, {cwd: root, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024, ...options});
const read = file => JSON.parse(fs.readFileSync(file, 'utf8'));
const sha = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const write = (file, value) => fs.writeFileSync(file, JSON.stringify(value, null, 2) + '\n');
const fail = message => { throw new Error(message); };
const nul = value => value.split('\0').filter(Boolean);
const same = (a,b) => JSON.stringify(a) === JSON.stringify(b);
const describe = file => {
  const s = fs.lstatSync(file);
  if (s.isSymbolicLink()) return {symlink: fs.readlinkSync(file), mode: s.mode & 0o7777};
  if (!s.isFile()) fail('Unexpected archive leaf: ' + file);
  return {sha256: sha(file), bytes: s.size, mode: s.mode & 0o7777};
};
const inventory = dir => Object.fromEntries(fs.readdirSync(dir).sort().map(name => [name, describe(path.join(dir,name))]));
const excluded = relative => ['output/checkpoints','output/design'].some(p => relative === p || relative.startsWith(p+'/')) || relative.split('/').some(p => ['node_modules','.next','.playwright-cli'].includes(p)) || relative.endsWith('.tsbuildinfo') || ['fixture-preview.log','preview-runtime.log'].includes(path.basename(relative));
const safe = relative => { if (path.isAbsolute(relative) || relative.split('/').includes('..') || /[\n\r\0]/.test(relative)) fail('Unsafe relative path'); };
const walk = (relative, result) => {
  safe(relative); if (excluded(relative)) return;
  const file = path.join(root, relative); const s = fs.lstatSync(file);
  if (s.isFile() || s.isSymbolicLink()) {result.add(relative); return;}
  if (!s.isDirectory()) fail('Unexpected filesystem entry: ' + relative);
  for (const name of fs.readdirSync(file).sort()) walk(relative + '/' + name, result);
};
const flatten = (dir, prefix = '') => fs.readdirSync(dir).sort().flatMap(name => {
  const relative = prefix ? prefix + '/' + name : name;
  return fs.lstatSync(path.join(dir,name)).isDirectory() ? flatten(path.join(dir,name),relative) : [relative];
}).sort();

if (fs.realpathSync(process.cwd()) !== fs.realpathSync(root)) fail('Wrong cwd');
if (run('git',['branch','--show-current']).trim() !== branch || run('git',['rev-parse','HEAD']).trim() !== base) fail('Wrong branch/base');
const finalGateSha256 = '51aadffeab49d646b6834f2c67dbf0094ff51db68490402fd35030e914d4d9bc';
if (sha(path.join(root,review,'build-final-checkpoint.mjs')) !== finalGateSha256) fail('Final acceptance gate changed');
run('git',['diff','--check']);
if (fs.existsSync(checkpoint)) fail('New checkpoint already exists; refuse overwrite');
const oldInventory = inventory(path.join(root,old));
for (const entry of read(path.join(root,review,'prior-checkpoint-preservation.json')).files) {
  const actual = describe(path.join(root,entry.path));
  if (actual.sha256 !== entry.sha256 || actual.bytes !== entry.bytes) fail('Prior checkpoint drift');
}
const originalInventory = inventory(original);
const relocation = read(path.join(root,old,'RELOCATION.json'));
if (fs.existsSync(relocation.oldPath)) fail('Old external finished checkpoint unexpectedly exists');
if (!same(Object.entries(originalInventory).map(([name,entry]) => ({name,...entry})),relocation.originalTransferInventory)) fail('Original transfer differs from relocation preservation record');
const inherited = read(path.join(root,old,'source-manifest.json'));
const initial = read(path.join(original,'source-manifest.json'));
if (Object.keys(inherited).length !== 224 || Object.keys(initial).length !== 152) fail('Unexpected inherited manifest count');
if (sha(path.join(original,'source-manifest.json')) !== '98e3c9790ff423c703bef5bb91dfa2bdd0a3d12533993cc9c4c91422f995bdae') fail('Original transfer manifest hash changed');
const source = read(path.join(root,clearance,'source-after.json'));
const verifySource = () => {
  if (source.comparedFiles !== 101 || source.files.length !== 101 || source.changes.length !== 1 || source.changes[0].path !== 'apps/website/src/app/globals.css' || source.changes[0].currentSha256 !== '3f0646dcc931a1626d7af0012c112dbd28412a6c31b9848db3974801475df51d') fail('Unexpected clearance source snapshot');
  for (const file of source.files) if (sha(path.join(root,file.path)) !== file.currentSha256) fail('Source changed after clearance snapshot: ' + file.path);
};
verifySource();
const checks = Object.fromEntries(['tests','build','typecheck'].map(name => {
  const receipt = read(path.join(root,clearance,name+'.json'));
  if (receipt.exitCode !== 0 || receipt.error || receipt.signal || receipt.cwd !== root || receipt.log !== path.join(root,clearance,name+'.log') || sha(receipt.log) !== receipt.sha256) fail('Clearance execution receipt mismatch: '+name);
  return [name,{receipt:clearance+'/'+name+'.json',log:clearance+'/'+name+'.log',sha256:receipt.sha256,exitCode:receipt.exitCode,startedAt:receipt.startedAt,finishedAt:receipt.finishedAt}];
}));
if (!/Tests\s+11 passed/.test(fs.readFileSync(path.join(root,clearance,'tests.log'),'utf8').replace(/\x1b\[[0-9;]*m/g,''))) fail('Expected affected 11-test summary missing');
const focused = read(path.join(root,clearance,'clearance-metrics.json'));
if (!same(focused.results.map(x=>x.width).sort((a,b)=>a-b),[360,390,768,1440])) fail('Focused widths missing');
for (const row of focused.results) if (row.gap !== 24 || row.link.height !== 44 || row.scrollWidth !== row.width || row.points.length !== 9 || row.points.some(x=>x.hitsLink !== true) || row.clickDestination !== 'http://127.0.0.1:3100/services') fail('Focused correction proof mismatch');
const visual = read(path.join(root,review,'claude-review-receipt.json'));
if (visual.exitCode !== 0 || visual.isError || visual.timedOut || visual.status !== 'success' || visual.readInputs.some(x => x.unchangedAtCompletion !== true)) fail('Visual receipt incomplete or changed');
const visualVerdict = fs.readFileSync(path.join(root,review,'claude-visual-review.md'),'utf8').match(/^\*\*(PASS|FAIL)\*\*/m)?.[1];
if (visualVerdict !== 'FAIL') fail('Historical failed review must remain unchanged for this WIP checkpoint');
for (const file of visual.readInputs) {
  const actualPath = path.isAbsolute(file.path) ? file.path : path.join(root,file.path);
  const preservedPath = actualPath === path.join(root,'apps/website/src/app/globals.css') ? path.join(root,clearance,'globals.before.css') : actualPath;
  if (sha(preservedPath) !== file.sha256AtRead) fail('Historical reviewed input not preserved: ' + file.path);
}
for (const entry of read(path.join(root,review,'claude-review-artifact-verification.json')).artifacts) {
  const actual = describe(path.join(root,review,entry.path));
  if (actual.sha256 !== entry.sha256 || actual.bytes !== entry.bytes) fail('Initial visual review artifact changed');
}
const interrupted = read(path.join(root,review,'claude-clearance-receipt.json'));
if (interrupted.exitCode !== 143 || interrupted.status !== 'no_final_result' || interrupted.acceptanceVerdict !== 'UNPARSED' || interrupted.timedOut) fail('Interrupted follow-up receipt mismatch');
for (const file of ['REPORT.md','coverage-matrix.md','review-resolution.md']) {
  const content = fs.readFileSync(path.join(root,review,file),'utf8');
  if (!content.includes('Active-work update') || !content.includes('palette') || !content.includes('143')) fail('WIP document status missing: ' + file);
}

const selected = new Set();
for (const relative of new Set([...Object.keys(initial),...Object.keys(inherited)])) walk(relative, selected);
const deleted = [];
const allowed = relative => relative.startsWith('apps/website/') || relative.startsWith('.agents/skills/website/') || relative.startsWith('proofs/architecture/') || ['apps/bali-zero-magazine/lib/contracts/website-read.ts','apps/bali-zero-magazine/lib/server/website-read-authority.ts','apps/bali-zero-magazine/lib/server/verified-media-bytes.ts','apps/bali-zero-magazine/lib/server/media.ts'].includes(relative);
for (const relative of nul(run('git',['diff','--name-only','-z',base,'--']))) {
  if (!allowed(relative)) fail('Unreviewed tracked change: ' + relative);
  if (fs.existsSync(path.join(root,relative))) walk(relative,selected); else deleted.push(relative);
}
for (const relative of nul(run('git',['ls-files','--others','--exclude-standard','-z','--','apps/website','.agents/skills/website','.claude/skills/website','.codex/skills/website','.qwen/skills/website','proofs/architecture','apps/bali-zero-magazine/lib/contracts/website-read.ts','apps/bali-zero-magazine/lib/server/website-read-authority.ts','apps/bali-zero-magazine/lib/server/verified-media-bytes.ts']))) walk(relative,selected);
for (const relative of [review,'apps/website/docs/reviews/2026-09-07-pro-slice','output/playwright/website-r19-pro','output/playwright/website-r19-full-site']) walk(relative,selected);
walk('.agents/skills/website/references/state.md',selected);
const names = [...selected].sort();
if (names.some(excluded)) fail('Checkpoint recursion/excluded path selected');
for (const relative of [`${review}/fixture-preview-startup.log`,`${review}/integrated-typecheck.log`,`${review}/claude-review-receipt.json`,`${review}/claude-clearance-receipt.json`,`${clearance}/source-after.json`,`${clearance}/sweep-metrics.json`,`${clearance}/preview-startup.log`,'.agents/skills/website/references/state.md']) if (!selected.has(relative)) fail('Required evidence omitted: ' + relative);
const manifest = Object.fromEntries(names.map(relative => [relative,describe(path.join(root,relative))]));
fs.mkdirSync(checkpoint);
const pngs = names.filter(name=>name.startsWith(clearance+'/') && name.endsWith('.png')).map(name=>{
  const bytes=fs.readFileSync(path.join(root,name));
  if (bytes.subarray(0,8).toString('hex') !== '89504e470d0a1a0a') fail('Invalid PNG signature');
  return {path:name,width:bytes.readUInt32BE(16),height:bytes.readUInt32BE(20),...manifest[name]};
});
write(path.join(checkpoint,'POST_CLEARANCE_SCREENSHOTS.json'),{checkedAt:new Date().toISOString(),scope:'File integrity inventory only; not visual acceptance',count:pngs.length,files:pngs});
write(path.join(checkpoint,'STATE.json'),{
  checkpoint_type:'pre-design-in-progress',acceptance:'pending',wholeSiteAccepted:false,productionArmed:false,
  reason:'Owner redirected work to palette and typography. Preserve the technical state before product design changes.',
  technicalJournal:'Local technical proof complete; production transport is not wired or armed.',
  initialReview:{verdict:'FAIL',blockingFinding:'VR-1: homepage Explore all services link occluded by lifted tools',receipt:review+'/claude-review-receipt.json',sourceBytes:'Original reviewed globals.css is preserved as '+clearance+'/globals.before.css; other read inputs still hash-match.'},
  correction:{currentSourceSnapshot:clearance+'/source-after.json',currentSourceFilesVerified:source.comparedFiles,sourceChanges:source.changes,checks,focusedProof:{receipt:clearance+'/clearance-metrics.json',widths:[1440,768,390,360],linkHeightPx:44,clearancePx:24,hitPointsPassed:36,realClicksPassed:4},postClearancePngCount:pngs.length,sweepReceipt:clearance+'/sweep-metrics.json',sweepLimit:'Preserved as supplied by capture owner; this checkpoint does not assert a completed independent visual follow-up.'},
  interruptedFollowup:{receipt:review+'/claude-clearance-receipt.json',exitCode:143,status:'no_final_result',verdict:null,reason:'Owned child stopped after the coordinator relayed the owner palette/type direction.'},
  historicalEvidence:{preCorrectionWebsiteTests:56,architectureTests:93,initialRouteViews:24,initialPngs:73,limit:'Historical scope is preserved; these are not newly rerun post-correction suites.'},
  finalAcceptanceGate:{path:review+'/build-final-checkpoint.mjs',sha256:finalGateSha256,status:'Unchanged; still requires PASS. This WIP snapshot neither executes nor relaxes that gate.'},
  designProposals:'Parallel ephemeral output/design proposals are excluded; product sources are frozen for this snapshot.',
});
write(path.join(checkpoint,'source-manifest.json'),manifest);
write(path.join(checkpoint,'deleted-paths.json'),deleted.sort());
fs.writeFileSync(path.join(checkpoint,'files.nul'),names.join('\0')+'\0');
fs.writeFileSync(path.join(checkpoint,'git-status.txt'),run('git',['status','--short']));
fs.writeFileSync(path.join(checkpoint,'working-tree.patch'),run('git',['diff','--binary','--full-index',base,'--'],{encoding:'buffer'}));
const listener = run('lsof',['-nP','-iTCP:3100','-sTCP:LISTEN']);
const pids = [...new Set(run('lsof',['-nP','-iTCP:3100','-sTCP:LISTEN','-t']).trim().split('\n'))];
if (pids.length !== 1 || !listener.includes('127.0.0.1:3100')) fail('Unexpected preview listener');
if (!run('lsof',['-nP','-a','-p',pids[0],'-d','cwd','-Fn']).split('\n').includes('n'+root+'/apps/website')) fail('Wrong preview cwd');
const http = [];
for (const route of ['/','/journal']) {
  const response = await fetch('http://127.0.0.1:3100'+route); await response.arrayBuffer();
  const row = {route,status:response.status,cacheControl:response.headers.get('cache-control'),xRobotsTag:response.headers.get('x-robots-tag')};
  if (row.status !== 200 || !row.cacheControl?.includes('private') || !row.cacheControl?.includes('no-store') || !row.xRobotsTag?.includes('noindex')) fail('Preview safety mismatch');
  http.push(row);
}
write(path.join(checkpoint,'PREVIEW.json'),{checkedAt:new Date().toISOString(),listenerCount:1,pid:Number(pids[0]),bind:'127.0.0.1:3100',cwd:root+'/apps/website',process:run('ps',['-p',pids[0],'-o','pid=,ppid=,command=']).trim(),http,runtimeCheckpointed:false});
run('tar',['-czf',path.join(checkpoint,'overlay.tar.gz'),'--null','-T',path.join(checkpoint,'files.nul')],{env:{...process.env,COPYFILE_DISABLE:'1'}});
const members = run('tar',['-tzf',path.join(checkpoint,'overlay.tar.gz')]).trim().split('\n').sort();
if (!same(members,names)) fail('Archive members differ');
const extraction = fs.mkdtempSync(path.join(checkpoint,'.verify-'));
run('tar',['-xpf',path.join(checkpoint,'overlay.tar.gz'),'-C',extraction],{env:{...process.env,COPYFILE_DISABLE:'1'}});
if (!same(flatten(extraction),names)) fail('Extraction members differ');
for (const [relative,expected] of Object.entries(manifest)) for (const dir of [root,extraction]) if (!same(describe(path.join(dir,relative)),expected)) fail('Hash/mode/link drift: ' + relative);
verifySource();
run('git',['diff','--check']);
if (!same(inventory(path.join(root,old)),oldInventory) || !same(inventory(original),originalInventory)) fail('Historical checkpoint/transfer changed');
const artifact = name => ({file:name,...describe(path.join(checkpoint,name))});
const checkpointReceipt = {
  createdAt:new Date().toISOString(),checkpoint_type:'pre-design-in-progress',acceptance:'pending',wholeSiteAccepted:false,machine:'Pro',worktree:root,branch,baseCommit:base,checkpointDirectory:checkpoint,gitCommitCreated:false,
  archive:artifact('overlay.tar.gz'),manifest:{...artifact('source-manifest.json'),entries:names.length},trackedPatch:{...artifact('working-tree.patch'),binary:true},filesList:artifact('files.nul'),deletedPathsFile:artifact('deleted-paths.json'),status:artifact('git-status.txt'),preview:artifact('PREVIEW.json'),state:artifact('STATE.json'),postClearanceScreenshots:artifact('POST_CLEARANCE_SCREENSHOTS.json'),
  initialTransfer:{manifest:path.join(original,'source-manifest.json'),sha256:sha(path.join(original,'source-manifest.json')),entries:152},
  priorCheckpoint:{directory:path.join(root,old),archiveSha256:oldInventory['overlay.tar.gz'].sha256,entries:224,unchanged:true,recursivelyIncluded:false},
  collection:'Union of 152 original paths, 224 prior checkpoint paths at CURRENT content, current scoped tracked/untracked changes, both complete review folders including ignored logs, both Playwright evidence trees. Prior checkpoint archive itself remains separate and unchanged.',
  excluded:['all output/checkpoints recursively','parallel output/design proposals','node_modules','.next','*.tsbuildinfo','.playwright-cli','active fixture-preview.log','active preview-runtime.log'],
  restore:'Start from exact base in an authorized isolated worktree, overlay tar preserving modes/symlinks, apply deleted-paths.json if any, verify manifest. Do not also apply working-tree.patch, which duplicates tracked final bytes. Install inherited dependencies, build then typecheck sequentially. Runtime is not included.',
  producer:'/root/final_visual_receipt',independentSecondVerification:'Pending separate verifier; see its later receipt.',
};
write(path.join(checkpoint,'CHECKPOINT.json'),checkpointReceipt);
fs.rmSync(extraction,{recursive:true});
write(path.join(checkpoint,'VERIFIED.json'),{verifiedAt:new Date().toISOString(),checkpoint_type:'pre-design-in-progress',acceptance:'pending',verifier:'/root/final_visual_receipt (checkpoint producer)',archiveSha256:checkpointReceipt.archive.sha256,manifestSha256:checkpointReceipt.manifest.sha256,checkpointSha256:sha(path.join(checkpoint,'CHECKPOINT.json')),exactArchiveMembers:members.length,extractedEntriesVerified:names.length,liveWorkingTreeEntriesVerified:names.length,byteHashesModesAndSymlinkTargetsCompared:true,sourceFilesStillEqualClearanceSnapshotBeforeAndAfterArchive:source.comparedFiles,originalTransferPathsIncluded:152,priorCheckpointPathsIncludedAtCurrentContent:224,priorCheckpointUnchanged:true,originalTransferUnchanged:true,checkpointsRecursivelyExcluded:true,designProposalsExcluded:true,extractionRemoved:!fs.existsSync(extraction),mismatches:[]});
console.log(JSON.stringify({checkpoint,entries:names.length,archive:checkpointReceipt.archive,manifest:checkpointReceipt.manifest,checkpointSha256:sha(path.join(checkpoint,'CHECKPOINT.json')),priorCheckpointUnchanged:true,originalTransferUnchanged:true,mismatches:[]},null,2));
