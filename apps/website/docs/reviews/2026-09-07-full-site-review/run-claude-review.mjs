import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawn, spawnSync} from 'node:child_process';

const cwd='/Users/nuzantara/nuzantara/.worktrees/infra-website-r19-pro';
const dir=path.join(cwd,'apps/website/docs/reviews/2026-09-07-full-site-review');
const input=path.join(dir,'claude-review-input.md');
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const env={...process.env};
for(const key of ['ANTHROPIC_API_KEY','ANTHROPIC_BASE_URL','ANTHROPIC_AUTH_TOKEN','CLAUDE_CODE_USE_BEDROCK','CLAUDE_CODE_USE_VERTEX']) delete env[key];
const authRun=spawnSync('/Users/nuzantara/.local/bin/claude',['auth','status'],{cwd,env,encoding:'utf8'});
let auth={exitCode:authRun.status};
try {const j=JSON.parse(authRun.stdout);auth={...auth,loggedIn:j.loggedIn,authMethod:j.authMethod,apiProvider:j.apiProvider,subscriptionType:j.subscriptionType};}catch{auth.status='unparseable';}
fs.writeFileSync(path.join(dir,'claude-auth-route.json'),JSON.stringify(auth,null,2)+'\n');
if(!auth.loggedIn||auth.authMethod!=='claude.ai'||auth.apiProvider!=='firstParty'||auth.subscriptionType!=='max') throw new Error('Sanctioned MAX route not confirmed; no reviewer launched.');
const version=spawnSync('/Users/nuzantara/.local/bin/claude',['--version'],{cwd,env,encoding:'utf8'}).stdout.trim();
const args=['--print','--model','opus','--effort','xhigh','--safe-mode','--restricted','--tools','Read','--allowedTools','Read','--permission-mode','dontAsk','--permission-prompts','none','--strict-mcp-config','--mcp-config','{"mcpServers":{}}','--no-session-persistence','--disable-slash-commands','--no-chrome','--output-format','stream-json','--verbose'];
const startedAt=new Date().toISOString();
const run=spawn('/Users/nuzantara/.local/bin/claude',args,{cwd,env,stdio:['pipe','pipe','pipe']});
const rawHash=crypto.createHash('sha256');
const stderrHash=crypto.createHash('sha256');
let buffer='',result=null,parseErrors=0,stderrBytes=0,timedOut=false;
const models=new Set(), reads=new Map(), trace=[];
run.stdout.on('data',b=>{
  rawHash.update(b); buffer+=b.toString();
  let nl;
  while((nl=buffer.indexOf('\n'))>=0){
    const line=buffer.slice(0,nl);buffer=buffer.slice(nl+1);if(!line.trim())continue;
    let e;try{e=JSON.parse(line);}catch{parseErrors++;continue;}
    if(e.type==='system'&&e.subtype==='init') trace.push({type:'init',model:e.model,tools:e.tools,permissionMode:e.permissionMode});
    if(e.message?.model)models.add(e.message.model);
    if(e.type==='assistant')for(const c of e.message?.content||[]){
      if(c.type==='tool_use'){
        const p=c.input?.file_path;trace.push({type:'tool',name:c.name,path:p||null});
        if(p&&!reads.has(p)){let hash=null;try{if(fs.statSync(p).isFile())hash=sha(fs.readFileSync(p));}catch{}reads.set(p,{path:p,sha256AtRead:hash});}
      }
    }
    if(e.type==='result'){result=e;for(const m of Object.keys(e.modelUsage||{}))models.add(m);}
  }
});
run.stderr.on('data',b=>{stderrHash.update(b);stderrBytes+=b.length;});
const timeout=setTimeout(()=>{timedOut=true;run.kill('SIGTERM');},600000);
const progress=setInterval(()=>process.stdout.write(JSON.stringify({status:'reviewer_running',elapsedSeconds:Math.round((Date.now()-Date.parse(startedAt))/1000),observedReadTools:trace.filter(e=>e.type==='tool').length})+'\n'),45000);
run.stdin.end(fs.readFileSync(input));
run.on('close',(exitCode,signal)=>{
  clearTimeout(timeout);clearInterval(progress);
  const receipt={startedAt,finishedAt:new Date().toISOString(),vendor:'Anthropic',route:'claude CLI / claude.ai firstParty MAX subscription; paid key and alternate endpoint env removed',cliVersion:version,args,requestedModel:'opus',runtimeModels:[...models],backendIdentityLimit:'Runtime model identifiers are reported by CLI/provider response; backend infrastructure is not independently attestable.',auth,exitCode,signal,timedOut,status:result?.subtype||'no_final_result',isError:result?.is_error??null,durationMs:result?.duration_ms??null,numTurns:result?.num_turns??null,observedTools:[...new Set(trace.filter(e=>e.type==='tool').map(e=>e.name))],restriction:'Read only; safe mode; restricted; strict empty MCP; no Chrome; no permission prompts; no session persistence. Runtime tool inventory recorded in sanitized trace. Not an independent OS sandbox penetration test.',inputPromptSha256:sha(fs.readFileSync(input)),rawStreamSha256:rawHash.digest('hex'),rawStreamRetained:false,rawThoughtsRetained:false,stderrSha256:stderrHash.digest('hex'),stderrBytes,stderrRetained:false,parseErrors,readInputs:[...reads.values()].map(r=>({...r,unchangedAtCompletion:r.sha256AtRead===null?null:(fs.existsSync(r.path)&&sha(fs.readFileSync(r.path))===r.sha256AtRead)}))};
  fs.writeFileSync(path.join(dir,'claude-visual-review.md'),result?.result||'No final reviewer answer. See receipt.');
  fs.writeFileSync(path.join(dir,'claude-review-receipt.json'),JSON.stringify(receipt,null,2)+'\n');
  fs.writeFileSync(path.join(dir,'claude-tool-trace.json'),JSON.stringify(trace,null,2)+'\n');
  process.stdout.write(JSON.stringify({exitCode,status:receipt.status,models:receipt.runtimeModels,readCount:reads.size,timedOut})+'\n');
  process.exitCode=exitCode||0;
});
