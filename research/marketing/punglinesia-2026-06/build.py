#!/usr/bin/env python3
"""PUNGLINESIA carousel — generate 6 brand-compliant 1080x1350 slide HTML files.

Bali Zero WR2 editorial carousel, news-flash archetype, 100% Bahasa Indonesia,
audience = Indonesian public. Hand-authored (NOT the autonomous WR2 generator)
because the topic is legally sensitive. Brand tokens from
~/.claude/skills/bali-zero-brand/tokens.json. NO Garuda (UU 24/2009 penghinaan
lambang negara). Render with chrome-headless-shell (see render.sh).
"""
import random
from pathlib import Path

OUT = Path(__file__).parent
LOGO = str(Path.home() / ".claude/skills/bali-zero-brand/assets/logo.png")

# --- corruption-veins SVG (deterministic, organic red branching) -------------
def veins(seed: int, n_main: int = 9) -> str:
    rng = random.Random(seed)
    paths = []
    for _ in range(n_main):
        # start from a random edge point
        edge = rng.choice(["t", "b", "l", "r"])
        if edge == "t":   x, y = rng.uniform(0, 1080), 0
        elif edge == "b": x, y = rng.uniform(0, 1080), 1350
        elif edge == "l": x, y = 0, rng.uniform(0, 1350)
        else:             x, y = 1080, rng.uniform(0, 1350)
        # walk toward center with jitter
        cx, cy = 540, 675
        pts = [(x, y)]
        steps = rng.randint(5, 9)
        for s in range(steps):
            t = (s + 1) / steps
            nx = x + (cx - x) * t + rng.uniform(-90, 90)
            ny = y + (cy - y) * t + rng.uniform(-90, 90)
            pts.append((nx, ny))
        d = "M " + " L ".join(f"{px:.0f} {py:.0f}" for px, py in pts)
        w = rng.choice([1.2, 1.6, 2.2, 3.0])
        op = rng.uniform(0.25, 0.7)
        paths.append(f'<path d="{d}" stroke="#C8102E" stroke-width="{w}" fill="none" opacity="{op:.2f}" stroke-linecap="round"/>')
        # small offshoots
        for _ in range(rng.randint(1, 3)):
            bi = rng.randint(1, len(pts) - 1)
            bx, by = pts[bi]
            ox = bx + rng.uniform(-140, 140)
            oy = by + rng.uniform(-140, 140)
            paths.append(f'<path d="M {bx:.0f} {by:.0f} L {ox:.0f} {oy:.0f}" stroke="#C8102E" stroke-width="1" fill="none" opacity="0.30" stroke-linecap="round"/>')
    return (
        '<svg class="veins" width="1080" height="1350" viewBox="0 0 1080 1350" '
        'xmlns="http://www.w3.org/2000/svg">'
        '<defs><filter id="g"><feGaussianBlur stdDeviation="2.2"/></filter></defs>'
        '<g filter="url(#g)">' + "".join(paths) + "</g>"
        '<g>' + "".join(paths) + "</g></svg>"
    )

# --- shared CSS --------------------------------------------------------------
CSS = """
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1080px;height:1350px;overflow:hidden;
  font-family:'Montserrat','Inter','Poppins',sans-serif;-webkit-font-smoothing:antialiased}
:root{--antracite:#2C2F38;--black:#000;--white:#fff;--muted:#9CA3AF;--yellow:#F4C430;--red:#C8102E}
.slide{position:relative;width:1080px;height:1350px;overflow:hidden}
.bg-black{background:#000}
.bg-antracite{background:#2C2F38}
.bg-dossier{background:radial-gradient(120% 90% at 50% 30%,#15171c 0%,#0a0b0e 70%,#000 100%)}
.veins{position:absolute;inset:0;z-index:1;mix-blend-mode:screen}
/* faint state-dossier stamps */
.dossier{position:absolute;inset:0;z-index:0;opacity:.05;color:#fff;overflow:hidden}
.dossier span{position:absolute;border:2px solid #fff;border-radius:4px;
  padding:8px 18px;font-weight:700;letter-spacing:.18em;font-size:22px;white-space:nowrap;text-transform:uppercase}
.dossier .line{border:none;height:1px;background:#fff;opacity:.5;padding:0}
.wrap{position:absolute;inset:0;z-index:3;display:flex;flex-direction:column;
  padding:80px 60px 150px 60px}
.center{align-items:center;justify-content:center;text-align:center}
.badge{position:absolute;top:40px;right:40px;z-index:4;background:var(--yellow);color:#000;
  font-family:'IBM Plex Mono',ui-monospace,monospace;font-size:18px;font-weight:700;
  padding:7px 13px;border-radius:4px;letter-spacing:.04em}
.logo{position:absolute;left:50%;bottom:48px;transform:translateX(-50%);z-index:4;
  width:66px;height:66px;background-image:url('LOGO_PATH');background-size:contain;
  background-repeat:no-repeat;background-position:center}
.dot{position:absolute;right:36px;bottom:36px;z-index:4;width:13px;height:13px;border-radius:50%;background:var(--yellow)}
/* type */
.wordmark{font-weight:800;letter-spacing:.01em;line-height:.96;font-size:138px}
.wordmark .r{color:var(--red)}
.wordmark .w{color:var(--white)}
.cover-sub{margin-top:34px;color:#fff;font-weight:800;font-size:38px;letter-spacing:.02em;line-height:1.15}
.cover-sub .y{color:var(--yellow)}
.h{font-weight:800;color:#fff;font-size:60px;line-height:1.04;letter-spacing:.02em;text-transform:uppercase;text-shadow:0 2px 10px rgba(0,0,0,.7)}
.h.yellow{color:var(--yellow)}
.divider{width:72px;height:5px;background:var(--yellow);margin:24px 0 36px}
.body{color:#fff;font-weight:700;font-size:33px;line-height:1.38;letter-spacing:0}
.body .y{color:var(--yellow)}
.body .r{color:var(--red)}
.spacer{flex:1}
/* recognition list */
.enum{display:flex;flex-direction:column;gap:22px;margin-top:8px}
.enum .it{border-left:4px solid var(--red);padding-left:22px;color:#fff;font-weight:800;
  font-size:40px;line-height:1.1;letter-spacing:.01em;text-transform:uppercase}
.punch{margin-top:48px;color:#fff;font-weight:700;font-size:34px;line-height:1.35}
.punch .y{color:var(--yellow)}
/* facts (evidence-carved) */
.facts{display:flex;flex-direction:column;gap:26px;margin-top:4px}
.fact{display:flex;gap:18px;align-items:flex-start}
.fact .m{color:var(--yellow);font-weight:800;font-size:26px;min-width:42px;line-height:1.2}
.fact .t{color:#fff;font-weight:700;font-size:30px;line-height:1.28;text-transform:uppercase;text-shadow:0 1px 6px rgba(0,0,0,.85)}
.take{margin-top:auto;border-top:2px solid rgba(244,196,48,.4);padding-top:18px}
.take .lab{color:var(--yellow);font-weight:700;font-size:15px;letter-spacing:.12em;text-transform:uppercase;margin-bottom:8px}
.take .tx{color:#fff;font-weight:800;font-size:30px;letter-spacing:.01em;text-transform:uppercase;line-height:1.1}
/* stat slide */
.stats{display:flex;flex-direction:column;gap:30px;margin-top:8px}
.stat{display:flex;flex-direction:column;gap:4px;border-left:4px solid var(--yellow);padding-left:22px}
.stat .num{color:var(--yellow);font-weight:800;font-size:64px;line-height:1;letter-spacing:.01em}
.stat .lab{color:rgba(255,255,255,.62);font-weight:700;font-size:24px;letter-spacing:.05em;text-transform:uppercase}
/* statement-bomb */
.statement{font-weight:800;font-size:60px;line-height:1.08;letter-spacing:.02em;color:#fff;
  text-transform:uppercase;text-align:center;max-width:900px}
.statement .y{color:var(--yellow)}
.cover-anchor{margin-top:24px;color:var(--yellow);font-family:'IBM Plex Mono',ui-monospace,monospace;font-weight:700;font-size:22px;letter-spacing:.05em}
.attr{position:absolute;left:60px;bottom:50px;z-index:4;color:var(--muted);font-weight:700;font-size:18px;letter-spacing:.03em}
.cover-img-bg{position:absolute;inset:0;z-index:0;background-image:url('cover-bg.png');background-size:cover;background-position:center;background-repeat:no-repeat}
.cover-sub-abs{position:absolute;left:60px;right:60px;top:730px;z-index:4;text-align:center;color:#fff;font-weight:800;font-size:37px;letter-spacing:.02em;line-height:1.15}
.cover-anchor-abs{position:absolute;left:60px;right:60px;bottom:150px;z-index:4;text-align:center;color:var(--yellow);font-family:'IBM Plex Mono',ui-monospace,monospace;font-weight:700;font-size:24px;letter-spacing:.05em}
""".replace("LOGO_PATH", LOGO)

DOSSIER = (
    '<div class="dossier">'
    '<span style="top:70px;left:60px;transform:rotate(-4deg)">RAHASIA</span>'
    '<span style="top:150px;right:70px;transform:rotate(3deg)">DOKUMEN NEGARA</span>'
    '<span style="bottom:300px;left:50px;transform:rotate(-2deg);border-radius:50%">UNTUK KEPENTINGAN DINAS</span>'
    '<span style="bottom:170px;right:80px;transform:rotate(2deg)">TERSANGKA</span>'
    '<hr class="line" style="top:430px;left:80px;width:380px">'
    '<hr class="line" style="top:520px;right:90px;width:300px">'
    '<hr class="line" style="bottom:520px;left:120px;width:340px">'
    '</div>'
)

def page(body: str, *, bg: str, veins_seed=None, dossier=False, badge=None,
         logo=True, dot=False, center=False) -> str:
    layers = ""
    if dossier:
        layers += DOSSIER
    if veins_seed is not None:
        layers += veins(veins_seed)
    badge_html = f'<div class="badge">{badge}</div>' if badge else ""
    logo_html = '<div class="logo"></div>' if logo else ""
    dot_html = '<div class="dot"></div>' if dot else ""
    wrap_cls = "wrap center" if center else "wrap"
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head>
<body><div class="slide {bg}">{layers}{badge_html}
<div class="{wrap_cls}">{body}</div>{dot_html}{logo_html}</div></body></html>"""

# ---------------------------------------------------------------------------
slides = {}

# S1 COVER
# S1 cover uses Antonello's original raster wordmark (cover_from_source.py),
# Garuda + 'BRIEF GRAFIS' cropped out, faded into the portrait canvas.
slides["slide1"] = (
    '<!doctype html><html><head><meta charset="utf-8"><style>' + CSS + '</style></head>'
    '<body><div class="slide bg-black">'
    '<div class="cover-img-bg"></div>'
    '<div class="badge">KPK &middot; 04.06.2026</div>'
    '<div class="cover-sub-abs">BUKAN OKNUM. INI PENYAKIT SISTEMIK.</div>'
    '<div class="cover-anchor-abs">17 TERSANGKA &middot; 48 JAM &middot; Rp 145,5 M</div>'
    '<div class="logo"></div>'
    '</div></body></html>')

# S2 RECOGNITION
slides["slide2"] = page(
    '<div class="h">KITA SEMUA<br>TAHU RASANYA</div>'
    '<div class="divider"></div>'
    '<div class="enum">'
    '<div class="it">Amplop di loket</div>'
    '<div class="it">&ldquo;Uang pelicin&rdquo; biar cepat</div>'
    '<div class="it">Calo menunggu di depan kantor</div>'
    '</div>'
    '<div class="punch">Pungli bukan berita baru buat kita &mdash; '
    'ia sudah jadi <span class="y">biaya hidup</span>.</div>'
    '<div class="spacer"></div>',
    bg="bg-antracite", dossier=True, dot=True)

# S3 FACTS (evidence-carved adapted)
slides["slide3"] = page(
    '<div class="h">REKAMAN KPK</div>'
    '<div class="divider"></div>'
    '<div class="facts">'
    '<div class="fact"><div class="m">&sect;1</div><div class="t">KPK menahan Wakil Menteri Imigrasi dan Pemasyarakatan Silmy Karim, ditetapkan tersangka</div></div>'
    '<div class="fact"><div class="m">&sect;2</div><div class="t">17 orang ditangkap dalam 48 jam (2&ndash;3 Juni 2026)</div></div>'
    '<div class="fact"><div class="m">&sect;3</div><div class="t">Dugaan pemerasan pengurusan izin tinggal WNA</div></div>'
    '<div class="fact"><div class="m">&sect;4</div><div class="t">Rp 145,5 miliar &middot; 2022&ndash;2026 &middot; sumber angka: KPK</div></div>'
    '</div>'
    '<div class="take"><div class="lab">Catatan kami</div>'
    '<div class="tx">Izin itu hak, bukan barang dagangan.</div></div>',
    bg="bg-dossier", dossier=True, dot=True)

# S4 SYSTEM (stat)
slides["slide4"] = page(
    '<div class="h">BUKAN<br>SATU OKNUM</div>'
    '<div class="divider"></div>'
    '<div class="stats">'
    '<div class="stat"><div class="num">Rp 145,5 M</div><div class="lab">dikumpulkan sistem &middot; 2022&ndash;2026</div></div>'
    '<div class="stat"><div class="num">~Rp 100 jt</div><div class="lab">per minggu &middot; bagian Karim (2023&ndash;2024, Dirjen)</div></div>'
    '<div class="stat"><div class="num">9 calo</div><div class="lab">swasta di dalam sistem</div></div>'
    '</div>'
    '<div class="punch">Ini bukan pegawai nakal &mdash; ini <span class="y">mesin</span> '
    'yang terlanjur dianggap wajar.</div>'
    '<div class="spacer"></div>'
    '<div class="attr">Sumber: KPK &middot; 4 Juni 2026</div>',
    bg="bg-antracite", dossier=True, dot=True)

# S5 BRIDGE
slides["slide5"] = page(
    '<div class="h">DUNIA<br>PERNAH LIHAT INI</div>'
    '<div class="divider"></div>'
    '<div class="body">Italia, 1992. Dimulai dari satu kasus, operasi '
    '<span class="y">&ldquo;Tangan Bersih&rdquo;</span> (Mani Pulite) mengubah '
    'sebuah negeri selamanya.<br><br>Di sana, mereka berhenti menyebutnya oknum.</div>'
    '<div class="punch" style="font-weight:800;font-size:38px">Setiap sistem bisa '
    '<span class="y">dibersihkan</span> &mdash; kalau berhenti dianggap wajar.</div>'
    '<div class="spacer"></div>',
    bg="bg-antracite", dossier=True, dot=True)

# S6 CLOSING statement-bomb
slides["slide6"] = page(
    '<div class="statement">PUNGLI BUKAN TAKDIR.<br>OBATNYA PUNYA NAMA: <span class="y">KPK</span>.</div>',
    bg="bg-black", veins_seed=23, dossier=False, logo=True, center=True)

for name, html in slides.items():
    (OUT / f"{name}.html").write_text(html, encoding="utf-8")
print(f"wrote {len(slides)} slides to {OUT}")
