import base64, pathlib, sys
d = pathlib.Path(sys.argv[1]); shots = d/"shots_web"
SHOTS = [
 ("phone-day", "Giorno · telefono",
  "390×844. Il primo schermo: fotografia, titolo, e la domanda. Nessun form, nessuna email."),
 ("phone-day-answered", "Giorno · la risposta",
  "«Fino a 30 giorni» → B1. La risposta arriva prima del nome. È l'unico segnale di fiducia che un imitatore non sa falsificare, perché richiede di sapere la risposta."),
 ("phone-night", "Notte · terra neutra",
  "Ground OKLCH L 19,0%, croma 0,016: grigio caldo, non nero. Distanza di tinta terra→accento 32°."),
 ("phone-night-answered", "Notte · seconda domanda",
  "«Un anno o più» apre la domanda sul motivo; poi E33G, con la soglia pubblicata di 60.000 USD l'anno."),
 ("phone-oxblood", "Notte · campo rosso",
  "La polarità alternativa della Q10, ancora aperta: il rosso smette di essere accento e diventa la terra."),
 ("desktop-day", "Giorno · desktop",
  "1280×900. La colonna di lettura resta a 680px — la misura non cresce con lo schermo — ma i sei volti escono in una banda a piena larghezza."),
 ("desktop-night", "Notte · desktop",
  "Stesso documento, stessa banda, tema scelto dal visitatore e non dalla pagina."),
 ("diagnostic-greyscale", "Diagnostica · scala di grigi",
  "Nessun significato passa dalla sola tinta: il rosso è l'unico accento e non porta mai un'informazione da solo."),
 ("diagnostic-sunlight", "Diagnostica · pieno sole",
  "Contrasto 0,62 · luminosità 1,22 — un telefono tenuto fuori a mezzogiorno, che è dove questa pagina si legge davvero."),
]
cards=[]
for name,title,note in SHOTS:
    f = shots/f"{name}.jpg"
    b64 = base64.b64encode(f.read_bytes()).decode()
    kb = f.stat().st_size/1024
    cards.append(f"""  <figure>
    <figcaption><b>{title}</b><span>{note}</span></figcaption>
    <img src="data:image/jpeg;base64,{b64}" alt="{title}">
    <p class="meta">{name} · {kb:,.0f} KB · reso a 2×</p>
  </figure>""")
html = """<title>Front Page States</title>
<style>
:root{--ground:#FCFAF8;--surface:#FFF;--ink:#17120F;--muted:#574E49;--faint:#7A6F69;
  --rule:#E9E3DC}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --ground:#161311;--surface:#211E1C;--ink:#EEEAE7;--muted:#B5B0AC;--faint:#95908C;
  --rule:#2E2B29}}
:root[data-theme="dark"]{--ground:#161311;--surface:#211E1C;--ink:#EEEAE7;--muted:#B5B0AC;
  --faint:#95908C;--rule:#2E2B29}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);
  font:15px/1.5 "Public Sans","Helvetica Neue",Arial,sans-serif}
header{max-width:1180px;margin:0 auto;padding:46px 20px 6px}
h1{margin:0 0 12px;font-size:31px;font-weight:800;letter-spacing:-.022em;text-wrap:balance}
header p{margin:0 0 10px;max-width:66ch;color:var(--muted);text-wrap:pretty}
main{max-width:1180px;margin:0 auto;padding:26px 20px 76px;
  display:grid;gap:32px;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));
  align-items:start}
figure{margin:0;background:var(--surface);border:1px solid var(--rule)}
figcaption{padding:13px 15px;border-bottom:1px solid var(--rule);display:flex;
  flex-direction:column;gap:4px}
figcaption b{font-size:15px}
figcaption span{color:var(--muted);font-size:13.5px;text-wrap:pretty}
img{display:block;width:100%;height:auto}
.meta{margin:0;padding:10px 15px;border-top:1px solid var(--rule);
  color:var(--faint);font-size:12.5px;font-variant-numeric:tabular-nums}
</style>
<header>
  <h1>Front page, nove stati</h1>
  <p>Screenshot a piena pagina della stessa sorgente, resi a 2× su Chromium headless.
     Il tema non è un interruttore decorativo: giorno, notte-neutra e notte-rossa sono tre
     palette definite a token, e la pagina pubblicata sceglie da sé quella del visitatore.</p>
  <p>Gli stati «risposta» esistono perché lo scatto di un elemento interattivo vuoto mostra
     la cornice e non il prodotto. Gli ultimi due non sono design: sono sonde — una toglie
     il colore, l'altra simula il sole.</p>
</header>
<main>
""" + "\n".join(cards) + "\n</main>\n"
(d/"gallery.html").write_text(html)
print("gallery.html %.2f MB" % (len(html.encode())/1024/1024))
