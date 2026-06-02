#!/usr/bin/env python3
"""Generate an interactive, self-contained configurator.html.

The user opens it in a browser and clicks to choose theme / font pair / photo
mix — the live preview updates instantly. A "copy config" button outputs the
choices as JSON, which the skill then applies to the real carousel spec.

Usage: python configurator.py [--out configurator.html] [--assets <dir>]
"""
import argparse, pathlib, re

THEMES = [
    {"id": "dark-editorial", "label": "dark-editorial", "bg": "#0d0d0f", "fg": "#f0b429"},
    {"id": "light",          "label": "light",          "bg": "#f4f2ec", "fg": "#c2410c"},
    {"id": "warm-film",      "label": "warm-film",      "bg": "#ece4d6", "fg": "#b4541f"},
    {"id": "bold-gradient",  "label": "bold-gradient",  "bg": "linear-gradient(140deg,#6d28d9,#db2777)", "fg": "#fde047"},
    {"id": "crimson",        "label": "crimson",        "bg": "#7a1518", "fg": "#dcab84"},
    {"id": "pink-lime",      "label": "pink-lime",      "bg": "#ffffff", "fg": "#ec4899"},
    {"id": "blush",          "label": "blush",          "bg": "#f7d9e2", "fg": "#e35d92"},
    {"id": "magenta-noir",   "label": "magenta-noir",   "bg": "#0a0a0a", "fg": "#ff2e93"},
    {"id": "burgundy",       "label": "burgundy",       "bg": "#4b1226", "fg": "#ecc14f"},
]
FONTS = [
    {"id": "manrope",   "label": "Manrope",            "head": "'Manrope', sans-serif",   "weight": "800", "body": "'Manrope', sans-serif"},
    {"id": "fraunces",  "label": "Fraunces + Manrope", "head": "'Fraunces', serif",       "weight": "600", "body": "'Manrope', sans-serif"},
    {"id": "unbounded", "label": "Unbounded + Manrope","head": "'Unbounded', sans-serif", "weight": "800", "body": "'Manrope', sans-serif"},
]


def rescope(css: str) -> str:
    """Rescope theme selectors so they live under .ec-stage instead of <body>."""
    css = css.replace(":root {", ".ec-stage {", 1)
    css = css.replace("body[data-theme=", ".ec-stage[data-theme=")
    css = css.replace("body.ec-custom", ".ec-stage.ec-custom")
    css = css.replace("body.ec-font", ".ec-stage.ec-font")
    return css


TEMPLATE = r"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<title>editorial-carousel · конфигуратор</title>
<style>
__THEME_CSS__
</style>
<style>
  :root { color-scheme: light; }
  * { margin: 0; box-sizing: border-box; }
  body { font-family: 'Manrope', system-ui, sans-serif; background: #14141a; color: #ececf0;
         padding: 28px 32px 80px; }
  h1.app { font-size: 22px; font-weight: 800; margin-bottom: 4px; }
  .sub { color: #9a9aa6; font-size: 14px; margin-bottom: 22px; }
  .layout { display: grid; grid-template-columns: 360px 1fr; gap: 32px; align-items: start; }
  @media (max-width: 1100px){ .layout{ grid-template-columns: 1fr; } }
  .panel { background: #1d1d25; border: 1px solid #2a2a34; border-radius: 16px; padding: 20px; }
  .group { margin-bottom: 22px; }
  .group:last-child { margin-bottom: 0; }
  .group > .gl { font-size: 12px; letter-spacing: 1.5px; text-transform: uppercase; color: #8a8a96;
                 margin-bottom: 10px; font-weight: 700; }
  .tiles { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
  .tile { cursor: pointer; border: 2px solid transparent; border-radius: 10px; overflow: hidden;
          background: #25252e; text-align: left; }
  .tile .sw { height: 46px; display: flex; align-items: center; justify-content: flex-end; padding: 6px; }
  .tile .dot { width: 16px; height: 16px; border-radius: 50%; box-shadow: 0 0 0 2px rgba(255,255,255,.25); }
  .tile .tn { font-size: 10.5px; padding: 5px 6px; color: #c9c9d2; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .tile.active { border-color: #fff; }
  .fbtns { display: flex; flex-direction: column; gap: 8px; }
  .fbtn { cursor: pointer; border: 2px solid #2f2f3a; border-radius: 10px; background: #25252e;
          color: #ececf0; padding: 12px 14px; font-size: 15px; text-align: left; }
  .fbtn.active { border-color: #fff; }
  .fbtn .demo { font-size: 22px; line-height: 1; margin-top: 4px; color: #fff; }
  .seg { display: flex; gap: 8px; }
  .seg button { flex: 1; cursor: pointer; border: 2px solid #2f2f3a; border-radius: 10px;
                background: #25252e; color: #ececf0; padding: 10px; font-size: 14px; font-weight: 700; }
  .seg button.active { border-color: #fff; background: #2f2f3a; }
  .counts { display: flex; gap: 6px; flex-wrap: wrap; }
  .counts button { cursor: pointer; border: 2px solid #2f2f3a; border-radius: 9px; background: #25252e;
                   color: #ececf0; padding: 9px 13px; font-size: 14px; font-weight: 700; }
  .counts button.active { border-color: #fff; background: #2f2f3a; }
  .hint { font-size: 12px; color: #8a8a96; margin-top: 8px; line-height: 1.4; }
  .out { width: 100%; height: 92px; background: #0e0e13; color: #b9f5c8; border: 1px solid #2a2a34;
         border-radius: 10px; padding: 10px; font-family: 'JetBrains Mono', monospace; font-size: 12px;
         resize: vertical; }
  .copy { margin-top: 8px; cursor: pointer; border: 0; border-radius: 10px; background: #f0b429;
          color: #14141a; padding: 11px 16px; font-weight: 800; font-size: 14px; }
  .copy.ok { background: #34d399; }
  /* preview */
  .stagewrap { background: #1d1d25; border: 1px solid #2a2a34; border-radius: 16px; padding: 22px; }
  .filmstrip { display: flex; flex-wrap: wrap; gap: 18px; }
  .cell { display: flex; flex-direction: column; gap: 6px; }
  .cap { font-size: 11px; font-weight: 700; letter-spacing: .5px; color: #8a8a96; padding-left: 2px; }
  .thumb { width: 248px; height: 310px; overflow: hidden; border-radius: 10px; position: relative;
           box-shadow: 0 8px 24px rgba(0,0,0,.35); cursor: default; }
  .thumb.pickable { cursor: pointer; }
  .thumb.pickable:hover { outline: 2px solid #ffffff7a; }
  .thumb > .slide { transform: scale(0.22963); transform-origin: top left; }
  .thumb .pcam { position: absolute; top: 8px; right: 8px; z-index: 9; background: #000a;
                 color: #fff; font-size: 12px; padding: 3px 7px; border-radius: 7px; }
  .thumb .stag { position: absolute; bottom: 8px; left: 8px; z-index: 9; background: #000a;
                 color: #fff; font-size: 10px; font-weight: 700; padding: 2px 7px; border-radius: 6px; }
  .mctl { display: flex; gap: 5px; margin-top: 5px; }
  .mctl button { flex: 1; cursor: pointer; border: 1px solid #3a3a44; border-radius: 7px; background: #25252e;
                 color: #d6d6dd; font-size: 10.5px; padding: 5px 3px; }
  .mctl button.on { border-color: #fff; background: #2f2f3a; color: #fff; }
  .upl { display: block; margin-top: 5px; cursor: pointer; text-align: center; font-size: 10.5px;
         border: 1px dashed #4a4a56; border-radius: 7px; background: #1f1f27; color: #b9b9c4;
         padding: 6px 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .upl:hover { border-color: #fff; color: #fff; }
</style></head>
<body>
  <h1 class="app">editorial-carousel · конфигуратор</h1>
  <div class="sub">Кликай — превью меняется вживую. В конце нажми «Скопировать конфиг» и отдай его скиллу.</div>
  <div class="layout">
    <div class="panel">
      <div class="group">
        <div class="gl">Тема</div>
        <div class="tiles" id="tiles"></div>
      </div>
      <div class="group">
        <div class="gl">Шрифт</div>
        <div class="fbtns" id="fbtns"></div>
      </div>
      <div class="group">
        <div class="gl">Слайдов</div>
        <div class="counts" id="nslides">
          <button data-n="5">5</button><button data-n="6" class="active">6</button>
          <button data-n="7">7</button><button data-n="8">8</button>
          <button data-n="9">9</button><button data-n="10">10</button>
          <button data-n="11">11</button><button data-n="12">12</button>
        </div>
        <div class="hint">В реальной карусели число = сколько слайдов ты написала; здесь — только для превью.</div>
      </div>
      <div class="group">
        <div class="gl">Нумерация</div>
        <div class="seg" id="numbering">
          <button data-num="counter" class="active">01 / 06</button>
          <button data-num="ghost">Большая</button>
          <button data-num="none">Нет</button>
        </div>
      </div>
      <div class="group">
        <div class="gl">Считать с</div>
        <div class="seg" id="scope">
          <button data-scope="all" class="active">С обложки</button>
          <button data-scope="skip-cover">Без обложки</button>
          <button data-scope="middle">Середина</button>
        </div>
      </div>
      <div class="group">
        <div class="gl">Режим</div>
        <div class="seg" id="seg">
          <button data-mode="text" class="active">Только текст</button>
          <button data-mode="mix">Медиа на слайдах</button>
        </div>
      </div>
      <div class="group" id="photogroup" style="display:none">
        <div class="gl">Тип по умолчанию</div>
        <div class="seg" id="deftype">
          <button data-t="photo" class="active">📷 Фото</button>
          <button data-t="video">🎬 Видео</button>
        </div>
        <div class="gl" style="margin-top:14px">Источник по умолчанию</div>
        <div class="seg" id="defsource">
          <button data-s="own" class="active">Своё</button>
          <button data-s="ai">Генерировать (AI)</button>
        </div>
        <div class="gl" style="margin-top:14px">Сколько слайдов с медиа</div>
        <div class="counts" id="counts">
          <button data-c="0" class="active">0</button>
          <button data-c="1">1</button>
          <button data-c="2">2</button>
          <button data-c="3">3</button>
          <button data-c="manual">Выберу сам</button>
        </div>
        <div class="hint">Авто: 1→обложка · 2→обложка+3-й · 3→+предпоследний. «Выберу сам» — кликай слайды. На каждом медиа-слайде ниже: 📷/🎬, своё/AI и «📎 загрузить файл» (фото сразу видно в макете). Видео: не на обложке, максимум 2.<br><b>Файлы держи в одной папке</b> — потом один раз дашь Claude путь к ней.</div>
      </div>
      <div class="group">
        <div class="gl">Конфиг</div>
        <textarea class="out" id="out" readonly></textarea>
        <button class="copy" id="copy">Скопировать конфиг</button>
      </div>
    </div>
    <div class="stagewrap">
      <div class="ec-stage" id="stage" data-theme="dark-editorial">
        <div class="filmstrip" id="film"></div>
      </div>
    </div>
  </div>

<script>
const THEMES = __THEMES__;
const FONTS = __FONTS__;
const REAL = __REAL_SLIDES__;   // real carousel slides when launched with --spec, else null
let state = { theme:'dark-editorial', font:'manrope', numbering:'counter', scope:'all',
              nslides:6, mode:'text', count:'0', manual:false,
              media:{}, defType:'photo', defSource:'own' };

function buildSlides(n){
  if(REAL && REAL.length) return REAL.slice();
  const arr = [{type:'cover', kicker:'тема: пример', title:'Заголовок\nи [[акцент]]', lead:'Подзаголовок в пару строк — задаёт тон.'}];
  const pool = [
    {type:'context', title:'Контекст\nодной мыслью', body:'Здесь раскрываем тему: пара коротких предложений.'},
    {type:'tip', title:'Главный\n[[совет]]', body:'Одна идея на слайд — заголовок и 2–3 предложения.'},
    {type:'quote', title:'Короткая\nцитата', author:'источник'},
  ];
  for(let k=0;k<n-2;k++){ const d=Object.assign({}, pool[k%pool.length]); if(d.type==='tip') d.kicker='шаг '+(k+1); arr.push(d); }
  arr.push({type:'cta', kicker:'финал', title:'Понравилось?', lead:'Сохрани карусель и попробуй завтра.'});
  return arr.slice(0, n);
}
function numberedSet(n, scope){
  let idx=[]; for(let i=1;i<=n;i++) idx.push(i);
  if(scope==='skip-cover') return idx.filter(i=>i!==1);
  if(scope==='middle') return idx.filter(i=>i!==1 && i!==n);
  return idx;
}

function fmt(s){
  s = (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  s = s.replace(/\[\[(.+?)\]\]/g, '<span class="accent">$1</span>');
  return s.replace(/\n/g,'<br>');
}
function autoSlots(c, n){
  if(c==='1') return [1];
  if(c==='2') return [1, Math.min(3,n)];
  if(c==='3') return [...new Set([1, Math.min(3,n), n-1])].filter(v=>v>=1 && v<=n).sort((a,b)=>a-b);
  return [];
}
function videoCount(except){ let c=0; for(const k in state.media){ if(+k!==except && state.media[k].type==='video') c++; } return c; }
function canVideo(n){ return n!==1 && videoCount(n) < 2; }   // never cover, max 2 videos
function applyAuto(){
  const idx = autoSlots(state.count, state.nslides); const m = {}; let vids = 0;
  idx.forEach(n=>{ let type = 'photo';
    if(state.defType==='video' && n!==1 && vids<2){ type='video'; vids++; }
    m[n] = { type, source: state.defSource }; });
  state.media = m;
}
function clampMedia(){ for(const k in state.media){ if(+k > state.nslides) delete state.media[+k]; } }
function slideHTML(def, i, disp, TT){
  const n = i+1;
  const m = state.media[n];
  const isMedia = !!m;
  const cls = ['slide'];
  if(def.type==='cta') cls.push('cta');
  if(isMedia) cls.push('media');
  let inner = '';
  if(isMedia) inner += '<div class="scrim"></div>';
  const dd = disp[n]; const dds = dd ? String(dd).padStart(2,'0') : '';
  if(state.numbering==='counter' && dd)
    inner += '<div class="num">'+dds+' / '+String(TT).padStart(2,'0')+'</div>';
  if(state.numbering==='ghost' && dd)
    inner += '<div class="big-index">'+dds+'</div>';
  if(def.kicker) inner += '<div class="kicker">'+fmt(def.kicker)+'</div>';
  if(def.type==='cover'){
    inner += '<div class="t-cover">'+fmt(def.title)+'</div>';
    inner += '<div class="divider"></div>';
    if(def.lead) inner += '<div class="lead">'+fmt(def.lead)+'</div>';
  } else if(def.type==='quote'){
    inner += '<h2 style="font-style:italic">«'+fmt(def.title)+'»</h2>';
    if(def.author) inner += '<div class="lead">'+fmt(def.author)+'</div>';
  } else if(def.type==='cta'){
    inner += '<div class="t-cover" style="font-size:84px">'+fmt(def.title)+'</div>';
    if(def.lead) inner += '<div class="lead">'+fmt(def.lead)+'</div>';
  } else {
    inner += '<h2>'+fmt(def.title)+'</h2>';
    if(def.body) inner += '<div class="body">'+fmt(def.body)+'</div>';
  }
  inner += '<div class="nick">@handle</div>';
  let bg = '';
  if(isMedia){
    if(m.preview) bg = ' style="background-image:url('+m.preview+');background-size:cover;background-position:center"';
    else bg = (m.type==='video')
      ? ' style="background-image:linear-gradient(135deg,#3a3f4a,#5b6270)"'
      : ' style="background-image:linear-gradient(135deg,#6f7785,#aab0bd)"';
  }
  return '<div class="'+cls.join(' ')+'"'+bg+'>'+inner+'</div>';
}
function renderFilm(){
  const film = document.getElementById('film');
  film.innerHTML = '';
  const N = state.nslides; const SLIDES = buildSlides(N);
  const set = numberedSet(N, state.scope); const disp = {}; set.forEach((x,k)=>disp[x]=k+1); const TT = set.length;
  SLIDES.forEach((def,i)=>{
    const n = i+1; const m = state.media[n];
    const cell = document.createElement('div'); cell.className = 'cell';
    const cap = document.createElement('div'); cap.className = 'cap';
    cap.textContent = 'слайд ' + n + (m ? '  · ' + (m.type==='video'?'видео':'фото') + ' · ' + (m.source==='ai'?'AI':'своё') : '');
    const t = document.createElement('div');
    t.className = 'thumb' + ((state.mode==='mix' && state.manual)?' pickable':'');
    let badges = '';
    if(m){ badges += '<div class="pcam">'+(m.type==='video'?'🎬':'📷')+'</div>';
           badges += '<div class="stag">'+(m.source==='ai'?'AI':'своё')+'</div>'; }
    t.innerHTML = slideHTML(def,i,disp,TT) + badges;
    if(state.mode==='mix' && state.manual){
      t.onclick = ()=>{
        if(state.media[n]) delete state.media[n];
        else state.media[n] = { type: (state.defType==='video' && canVideo(n))?'video':'photo', source: state.defSource };
        renderFilm(); renderOut();
      };
    }
    cell.appendChild(cap); cell.appendChild(t);
    if(state.mode==='mix' && m){
      const ctl = document.createElement('div'); ctl.className = 'mctl';
      ctl.innerHTML =
        '<button data-k="photo"'+(m.type==='photo'?' class="on"':'')+'>📷 фото</button>'+
        '<button data-k="video"'+(m.type==='video'?' class="on"':'')+'>🎬 видео</button>'+
        '<button data-k="own"'+(m.source==='own'?' class="on"':'')+'>своё</button>'+
        '<button data-k="ai"'+(m.source==='ai'?' class="on"':'')+'>AI</button>';
      ctl.querySelectorAll('button').forEach(bb=>{ bb.onclick=(e)=>{ e.stopPropagation(); const k=bb.dataset.k;
        if(k==='photo') state.media[n].type='photo';
        else if(k==='video'){ if(canVideo(n)) state.media[n].type='video'; }
        else if(k==='own'){ state.media[n].source='own'; }
        else if(k==='ai'){ state.media[n].source='ai'; if(!state.media[n].aiMode) state.media[n].aiMode='auto'; state.media[n].preview=null; }
        renderFilm(); renderOut(); }; });
      cell.appendChild(ctl);
      if(m.source==='ai'){
        const aim = document.createElement('div'); aim.className = 'mctl';
        aim.innerHTML =
          '<button data-a="auto"'+(((m.aiMode||'auto')==='auto')?' class="on"':'')+'>🧠 ИИ сам</button>'+
          '<button data-a="ref"'+((m.aiMode==='ref')?' class="on"':'')+'>🎯 по референсу</button>';
        aim.querySelectorAll('button').forEach(bb=>{ bb.onclick=(e)=>{ e.stopPropagation(); m.aiMode=bb.dataset.a; renderFilm(); renderOut(); }; });
        cell.appendChild(aim);
      }
      const needUpload = (m.source==='own') || (m.source==='ai' && m.aiMode==='ref');
      if(needUpload){
        const up = document.createElement('label'); up.className = 'upl';
        up.textContent = (m.source==='ai' ? '📎 референс стиля' : '📎 загрузить файл') + (m.file ? ' · ' + m.file : '');
        const inp = document.createElement('input'); inp.type='file'; inp.accept='image/*,video/*'; inp.style.display='none';
        inp.onchange = (e)=>{ const f=e.target.files[0]; if(!f) return; m.file=f.name;
          if(m.source==='own' && f.type.indexOf('image/')===0){ const r=new FileReader(); r.onload=()=>{ m.preview=r.result; renderFilm(); renderOut(); }; r.readAsDataURL(f); }
          else { m.preview=null; renderFilm(); renderOut(); } };
        up.appendChild(inp); cell.appendChild(up);
      } else if(m.source==='ai'){
        const h = document.createElement('div'); h.className='upl'; h.style.cursor='default'; h.style.borderStyle='solid';
        h.textContent='🧠 ИИ предложит концепт и стиль';
        cell.appendChild(h);
      }
    }
    film.appendChild(cell);
  });
}
function applyFont(){
  const f = FONTS.find(x=>x.id===state.font);
  const st = document.getElementById('stage');
  st.style.setProperty('--head-font', f.head);
  st.style.setProperty('--head-weight', f.weight);
  st.style.setProperty('--body-font', f.body);
}
function renderOut(){
  const media = state.mode==='mix'
    ? Object.keys(state.media).map(Number).sort((a,b)=>a-b).map(n=>{
        const M = state.media[n]; const e = {slide:n, type:M.type, source:M.source};
        if(M.source==='ai') e.aiMode = M.aiMode || 'auto';
        if(M.file) e.file = M.file; return e; })
    : [];
  const cfg = { theme: state.theme, font: state.font, numbering: state.numbering, numberScope: state.scope,
                slides: state.nslides, mode: state.mode, media };
  document.getElementById('out').value = JSON.stringify(cfg, null, 2);
}
function buildTiles(){
  const box = document.getElementById('tiles');
  THEMES.forEach(t=>{
    const el = document.createElement('div');
    el.className = 'tile' + (t.id===state.theme?' active':'');
    el.innerHTML = '<div class="sw" style="background:'+t.bg+'"><div class="dot" style="background:'+t.fg+'"></div></div><div class="tn">'+t.label+'</div>';
    el.onclick = ()=>{ state.theme=t.id; document.getElementById('stage').dataset.theme=t.id;
                       [...box.children].forEach(c=>c.classList.remove('active')); el.classList.add('active'); renderOut(); };
    box.appendChild(el);
  });
}
function buildFonts(){
  const box = document.getElementById('fbtns');
  FONTS.forEach(f=>{
    const el = document.createElement('button');
    el.className = 'fbtn' + (f.id===state.font?' active':'');
    el.innerHTML = f.label + '<div class="demo" style="font-family:'+f.head+';font-weight:'+f.weight+'">Заголовок</div>';
    el.onclick = ()=>{ state.font=f.id; applyFont();
                       [...box.children].forEach(c=>c.classList.remove('active')); el.classList.add('active'); renderOut(); };
    box.appendChild(el);
  });
}
function initControls(){
  document.querySelectorAll('#numbering button').forEach(b=>{
    b.onclick = ()=>{
      state.numbering = b.dataset.num;
      document.querySelectorAll('#numbering button').forEach(x=>x.classList.remove('active')); b.classList.add('active');
      renderFilm(); renderOut();
    };
  });
  document.querySelectorAll('#scope button').forEach(b=>{
    b.onclick = ()=>{
      state.scope = b.dataset.scope;
      document.querySelectorAll('#scope button').forEach(x=>x.classList.remove('active')); b.classList.add('active');
      renderFilm(); renderOut();
    };
  });
  document.querySelectorAll('#nslides button').forEach(b=>{
    b.onclick = ()=>{
      state.nslides = parseInt(b.dataset.n);
      document.querySelectorAll('#nslides button').forEach(x=>x.classList.remove('active')); b.classList.add('active');
      if(state.mode==='mix' && !state.manual) applyAuto();
      else clampMedia();
      renderFilm(); renderOut();
    };
  });
  document.querySelectorAll('#seg button').forEach(b=>{
    b.onclick = ()=>{
      state.mode = b.dataset.mode;
      document.querySelectorAll('#seg button').forEach(x=>x.classList.remove('active')); b.classList.add('active');
      document.getElementById('photogroup').style.display = state.mode==='mix' ? '' : 'none';
      if(state.mode==='text'){ state.media={}; }
      else { state.manual = (state.count==='manual'); if(!state.manual) applyAuto(); }
      renderFilm(); renderOut();
    };
  });
  document.querySelectorAll('#counts button').forEach(b=>{
    b.onclick = ()=>{
      state.count = b.dataset.c;
      document.querySelectorAll('#counts button').forEach(x=>x.classList.remove('active')); b.classList.add('active');
      state.manual = (state.count==='manual');
      if(!state.manual) applyAuto();
      renderFilm(); renderOut();
    };
  });
  document.querySelectorAll('#deftype button').forEach(b=>{
    b.onclick = ()=>{
      state.defType = b.dataset.t;
      document.querySelectorAll('#deftype button').forEach(x=>x.classList.remove('active')); b.classList.add('active');
      if(state.mode==='mix' && !state.manual) applyAuto();
      renderFilm(); renderOut();
    };
  });
  document.querySelectorAll('#defsource button').forEach(b=>{
    b.onclick = ()=>{
      state.defSource = b.dataset.s;
      document.querySelectorAll('#defsource button').forEach(x=>x.classList.remove('active')); b.classList.add('active');
      if(state.mode==='mix' && !state.manual) applyAuto();
      renderFilm(); renderOut();
    };
  });
  document.getElementById('copy').onclick = ()=>{
    const ta = document.getElementById('out'); ta.select();
    navigator.clipboard.writeText(ta.value).catch(()=>{});
    const btn = document.getElementById('copy'); btn.textContent='Скопировано ✓'; btn.classList.add('ok');
    setTimeout(()=>{ btn.textContent='Скопировать конфиг'; btn.classList.remove('ok'); }, 1500);
  };
}
if(REAL && REAL.length){
  state.nslides = REAL.length;
  const g = document.getElementById('nslides'); if(g && g.closest('.group')) g.closest('.group').style.display = 'none';
}
buildTiles(); buildFonts(); initControls(); applyFont(); renderFilm(); renderOut();
</script>
</body></html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--assets", default=None)
    ap.add_argument("--spec", default=None, help="optional spec.json — preview the REAL slide copy instead of the demo")
    args = ap.parse_args()
    import json
    script_dir = pathlib.Path(__file__).resolve().parent
    assets_dir = pathlib.Path(args.assets).resolve() if args.assets else (script_dir.parent / "assets")
    out = pathlib.Path(args.out).resolve() if args.out else (script_dir.parent / "configurator.html")

    real = "null"
    if args.spec:
        spec = json.loads(pathlib.Path(args.spec).read_text(encoding="utf-8"))
        keep = ("type", "kicker", "title", "lead", "body", "author")
        sl = [{k: s[k] for k in keep if s.get(k) is not None} for s in spec.get("slides", [])]
        real = json.dumps(sl, ensure_ascii=False)

    css = rescope((assets_dir / "styles.css").read_text(encoding="utf-8"))
    html = (TEMPLATE
            .replace("__THEME_CSS__", css)
            .replace("__THEMES__", json.dumps(THEMES, ensure_ascii=False))
            .replace("__FONTS__", json.dumps(FONTS, ensure_ascii=False))
            .replace("__REAL_SLIDES__", real))
    out.write_text(html, encoding="utf-8")
    print(f"configurator -> {out}" + (" (from your copy)" if args.spec else " (demo slides)"))


if __name__ == "__main__":
    main()
