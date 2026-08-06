// Prova su DOM REALE (jsdom) che il repaint guard di renderThreads non ricostruisce
// la lista quando i dati non sono cambiati — la causa dei thread che si accalcavano
// dall'alto ogni 5s. Guidato DENTRO il realm con w.eval: `els`/`state` sono const di
// script-scope e NON esistono su window (solo le function declaration ci finiscono) —
// una sonda che legge w.els misura il proprio metodo d'accesso, non la pagina.
// Richiede jsdom: `node --test`-free, si esegue a mano o via npm test dell'app.
const fs=require("fs");
let JSDOM;
try { ({ JSDOM } = require("jsdom")); } catch {
  // Exit 1, non 0: "non ho potuto verificare" non deve leggersi come "verificato".
  console.error("jsdom mancante — installa con: npm install (devDependency di questa app)");
  process.exit(1);
}
const html=fs.readFileSync(require("path").join(__dirname,"viewer.html"),"utf8");
const dom=new JSDOM(html,{runScripts:"dangerously",url:"http://localhost/",
  beforeParse(w){ w.fetch=()=>new Promise(()=>{}); w.EventSource=function(){}; }});
const w=dom.window;
let fails=0; const ok=(c,m)=>{console.log((c?"  ok   ":"  FAIL ")+m); if(!c)fails++;};
const errs=[]; w.addEventListener("error",e=>errs.push(e.message||String(e)));

setTimeout(()=>{
  // guido DENTRO il realm: els/state sono const di script-scope, invisibili da window
  const E=s=>w.eval(s);
  ok(E("typeof renderThreads")==="function","renderThreads definita");
  ok(E("!!els.threads")===true,"els.threads risolve il contenitore reale");

  E(`window.__mk=(id,b)=>({thread_id:id,counterpart_name:"C"+id,
      last_message_at:"2026-08-06T10:00:00Z",last_body:b,unread_count:0,human_handling:false});`);

  E(`state.threads=[__mk(1,"a"),__mk(2,"b"),__mk(3,"c")]; renderThreads();`);
  ok(E("els.threads.querySelectorAll('.thread').length")===3,"prima pittura: 3 righe");
  ok(E("els.threads.querySelectorAll('[data-thread-id]').length")===3,"ogni riga ha data-thread-id");

  E("window.__n0=els.threads.querySelector('.thread');");
  E("renderThreads();");   // stessi dati
  ok(E("els.threads.querySelector('.thread')===window.__n0")===true,
     "stessi dati: STESSO nodo -> zero ricostruzione (niente salto)");

  E(`state.threads=[__mk(9,"nuovo"),__mk(1,"a"),__mk(2,"b"),__mk(3,"c")]; renderThreads();`);
  ok(E("els.threads.querySelectorAll('.thread').length")===4,"thread nuovo: ridisegna (4 righe)");
  ok(E("els.threads.querySelector('.thread')!==window.__n0")===true,"ordine cambiato davvero");

  ok(errs.length===0,`zero errori JS a runtime (${errs.length}${errs.length?": "+errs[0]:""})`);
  console.log(fails?`\n${fails} FALLITI`:"\nTUTTI VERDI su DOM reale");
  process.exit(fails?1:0);
},700);
