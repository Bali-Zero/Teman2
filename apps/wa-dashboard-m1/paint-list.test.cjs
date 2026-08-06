// Corpus su paintList: colpevolezza (salta l'identico, preserva lo scroll,
// non raddoppia i listener) + innocenza (ridisegna quando cambia davvero).
const fs=require("fs");
const html=fs.readFileSync(process.argv[2] || require("path").join(__dirname,"viewer.html"),"utf8");
const src=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>m[1]).join("\n");
const fn=src.match(/function paintList[\s\S]*?\n\}/)[0];
eval(fn);

let fails=0;
const ok=(c,m)=>{ console.log((c?"  ok   ":"  FAIL ")+m); if(!c) fails++; };

function mkEl(rows){
  const el={ scrollTop:0, innerHTML:"", _rows:rows,
    querySelectorAll(){ return this._rows; } };
  Object.defineProperty(el,"innerHTML",{
    get(){return this.__h||"";},
    set(v){ this.__h=v; this._rows=this._pending||[]; }, configurable:true});
  return el;
}
const row=(k,top)=>({getAttribute:()=>k, offsetTop:top});

// 1. identico -> NON ridipinge
const a=mkEl([]); a.innerHTML="<b>x</b>";
const first=paintList(a,"<b>y</b>","data-k");
const second=paintList(a,"<b>y</b>","data-k");
ok(first===true,"prima pittura: ridipinge (true)");
ok(second===false,"stesso markup: SALTA (false) -> niente sfarfallio, niente listener doppi");

// 2. markup diverso -> ridipinge
ok(paintList(a,"<b>z</b>","data-k")===true,"markup cambiato: ridipinge (innocenza)");

// 3. scroll preservato quando la riga ancora resta
const b=mkEl([row("t1",0),row("t2",100),row("t3",200)]);
b.scrollTop=100;                       // sto guardando t2
b._pending=[row("tNEW",0),row("t1",100),row("t2",200),row("t3",300)]; // ne arriva una in cima
paintList(b,"<div>nuovo</div>","data-k");
ok(b.scrollTop===200,"riga arrivata in cima: lo scroll segue t2 (100 -> 200), il lettore non si muove");

// 4. ancora sparita -> ripiega sulla posizione precedente
const c=mkEl([row("t9",50)]);
c.scrollTop=50; c._pending=[];
paintList(c,"<div>vuoto</div>","data-k");
ok(c.scrollTop===50,"ancora sparita: ripiega sullo scroll precedente invece di saltare in cima");

// 5. in cima si resta in cima
const d=mkEl([row("t1",0)]); d.scrollTop=0; d._pending=[row("t2",0),row("t1",40)];
paintList(d,"<div>x</div>","data-k");
ok(d.scrollTop===0,"gia' in cima: resta in cima (il nuovo si vede subito)");

console.log(fails?`\n${fails} FALLITI`:"\n5/5 verdi");
process.exit(fails?1:0);
