import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawn, spawnSync} from 'node:child_process';

// Independent, bounded follow-up to VR-1. Never overwrite the first FAIL evidence.
const cwd='/Users/nuzantara/nuzantara/.worktrees/infra-website-r19-pro';
if(fs.realpathSync(process.cwd())!==fs.realpathSync(cwd)) throw new Error('Wrong worktree');
const dir=path.join(cwd,'apps/website/docs/reviews/2026-09-07-full-site-review');
const input=path.join(dir,'claude-clearance-input.md');
const outputs={review:'claude-clearance-review.md',receipt:'claude-clearance-receipt.json',trace:'claude-clearance-tool-trace.json',auth:'claude-clearance-auth-route.json'};
for(const name of Object.values(outputs)) if(fs.existsSync(path.join(dir,name))) throw new Error('Refuse to overwrite review evidence: '+name);
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const prompt=fs.readFileSync(input);
const env={...process.env};
for(const key of ['ANTHROPIC_API_KEY','ANTHROPIC_BASE_URL','ANTHROPIC_AUTH_TOKEN','CLAUDE_CODE_USE_BEDROCK','CLAUDE_CODE_USE_VERTEX']) delete env[key];
const authRun=spawnSync('/Users/nuzantara/.local/bin/claude',['auth','status'],{cwd,env,encoding:'utf8'});
let auth={exitCode:authRun.status};
try{const j=JSON.parse(authRun.stdout);auth={...auth,loggedIn:j.loggedIn,authMethod:j.authMethod,apiProvider:j.apiProvider,subscriptionType:j.subscriptionType};}catch{auth.status='unparseable';}
fs.writeFileSync(path.join(dir,outputs.auth),JSON.stringify(auth,null,2)+'\n');
if(auth.exitCode!==0||!auth.loggedIn||auth.authMethod!=='claude.ai'||auth.apiProvider!=='firstParty'||auth.subscriptionType!=='max') throw new Error('Sanctioned MAX route not confirmed; no reviewer launched.');
const version=spawnSync('/Users/nuzantara/.local/bin/claude',['--version'],{cwd,env,encoding:'utf8'}).stdout.trim();
const args=['--print','--model','opus','--effort','xhigh','--safe-mode','--restricted','--tools','Read','--allowedTools','Read','--permission-mode','dontAsk','--permission-prompts','none','--strict-mcp-config','--mcp-config','{"mcpServers":{}}','--no-session-persistence','--disable-slash-commands','--no-chrome','--output-format','stream-json','--verbose'];
const startedAt=new Date().toISOString();
const run=spawn('/Users/nuzantara/.local/bin/claude',args,{cwd,env,stdio:['pipe','pipe','pipe']});
const rawHash=crypto.createHash('sha256'),stderrHash=crypto.createHash('sha256');
let buffer='',result=null,parseErrors=0,stderrBytes=0,timedOut=false;
const models=new Set(),reads=new Map(),trace=[];
const consume=line=>{
  if(!line.trim())return;
  let e;try{e=JSON.parse(line);}catch{parseErrors++;return;}
  if(e.type==='system'&&e.subtype==='init') trace.push({type:'init',model:e.model,tools:e.tools,permissionMode:e.permissionMode});
  if(e.message?.model)models.add(e.message.model);
  if(e.type==='assistant')for(const c of e.message?.content||[]){
    if(c.type!=='tool_use')continue;
    const p=c.input?.file_path;trace.push({type:'tool',name:c.name,path:p||null});
    if(p&&!reads.has(p)){let hash=null;try{if(fs.statSync(p).isFile())hash=sha(fs.readFileSync(p));}catch{}reads.set(p,{path:p,sha256AtRead:hash});}
  }
  if(e.type==='result'){result=e;for(const m of Object.keys(e.modelUsage||{}))models.add(m);}
};
run.stdout.on('data',b=>{rawHash.update(b);buffer+=b.toString();let nl;while((nl=buffer.indexOf('\n'))>=0){consume(buffer.slice(0,nl));buffer=buffer.slice(nl+1);}});
run.stderr.on('data',b=>{stderrHash.update(b);stderrBytes+=b.length;});
const timeout=setTimeout(()=>{timedOut=true;run.kill('SIGTERM');},600000);
const progress=setInterval(()=>process.stdout.write(JSON.stringify({status:'reviewer_running',elapsedSeconds:Math.round((Date.now()-Date.parse(startedAt))/1000),observedReadTools:trace.filter(e=>e.type==='tool').length})+'\n'),45000);
run.stdin.end(prompt);
run.on('close',(exitCode,signal)=>{
  clearTimeout(timeout);clearInterval(progress);consume(buffer);
  const answer=typeof result?.result==='string'?result.result:'No final reviewer answer. See receipt.';
  const acceptanceVerdict=answer.match(/^\*\*(PASS|FAIL)\*\*/m)?.[1]??'UNPARSED';
  const receipt={startedAt,finishedAt:new Date().toISOString(),scope:'Independent follow-up to VR-1 only, with immediate homepage regression surroundings',vendor:'Anthropic',route:'claude CLI / claude.ai firstParty MAX subscription; paid key and alternate endpoint env removed',cliVersion:version,args,requestedModel:'opus',runtimeModels:[...models],backendIdentityLimit:'Runtime model identifiers are provider-reported; auxiliary model role and backend infrastructure are not independently attestable.',auth,exitCode,signal,timedOut,status:result?.subtype||'no_final_result',isError:result?.is_error??null,acceptanceVerdict,verdictParseLimit:'Text marker extraction; coordinator must read and accept the complete final answer.',durationMs:result?.duration_ms??null,numTurns:result?.num_turns??null,observedTools:[...new Set(trace.filter(e=>e.type==='tool').map(e=>e.name))],restriction:'Read only; safe mode; restricted; strict empty MCP; no Chrome; no permission prompts; no session persistence. Not an independent OS sandbox penetration test.',inputPromptSha256:sha(prompt),inputPromptUnchangedAtCompletion:sha(fs.readFileSync(input))===sha(prompt),rawStreamSha256:rawHash.digest('hex'),rawStreamRetained:false,rawThoughtsRetained:false,stderrSha256:stderrHash.digest('hex'),stderrBytes,stderrRetained:false,parseErrors,readInputs:[...reads.values()].map(r=>({...r,unchangedAtCompletion:r.sha256AtRead===null?null:(fs.existsSync(r.path)&&sha(fs.readFileSync(r.path))===r.sha256AtRead)}))};
  fs.writeFileSync(path.join(dir,outputs.review),answer);
  fs.writeFileSync(path.join(dir,outputs.receipt),JSON.stringify(receipt,null,2)+'\n');
  fs.writeFileSync(path.join(dir,outputs.trace),JSON.stringify(trace,null,2)+'\n');
  process.stdout.write(JSON.stringify({exitCode,status:receipt.status,acceptanceVerdict,models:receipt.runtimeModels,readCount:reads.size,timedOut})+'\n');
  process.exitCode=exitCode||0;
});
