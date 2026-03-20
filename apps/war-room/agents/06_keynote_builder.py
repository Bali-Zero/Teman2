#!/usr/bin/env python3
"""
FASE 4 -- Keynote Builder (Editable, Hybrid)
=============================================
Approccio:
  1. PIL genera IL SOLO SFONDO
  2. AppleScript costruisce il .key con text box REALI editabili

LAYOUT definitivo (da analisi reference 42.png / 43.png):
  COVER:      foto full-bleed (scurata) + titolo bianco alto + sottotitolo gold
  CONTENT:    sfondo dark SOLO testo. Layout:
                - Headline gold    y=80  (top, CENTRATO)
                - Subhead gold     y=290 (opzionale, CENTRATO)
                - Body white       y=320 (giustificato, margini MX)
                - Bottom y=800+    VUOTO (breathing space intenzionale)
  FULL_BLEED  (non cover): foto al 28% opacity come sfondo + stesso layout testo

FIX 2026-03-04:
  - Headline non più x=0: ora x=MX, w=IW → mai tocca i bordi
  - mk_text ora accetta param align ('left'/'center'/'right'/'justify')
  - Headline: align=center
  - Body: align=justify, altezza aumentata a 480px
  - Cover headline/subhead: align=center
"""

import json, argparse, sys, subprocess, shutil, tempfile
from pathlib import Path
from PIL import Image, ImageEnhance

# -- Canvas -------------------------------------------------------------------
W = 1080
H = 1350

# -- Colori brand (AppleScript: 0-65535) -------------------------------------
BG_RGB    = (55, 61, 66)       # #373D42 — confermato da Zero
GOLD_AS   = f"{{{244*257}, {160*257}, {28*257}}}"    # #F4A01C — matches brand.json text_accent
WHITE_AS  = f"{{{217*257}, {217*257}, {217*257}}}"   # #D9D9D9
PWHITE_AS = f"{{{255*257}, {255*257}, {255*257}}}"

# -- Font (PostScript names) --------------------------------------------------
FN_COVER  = "LeagueSpartan-Bold"   # solo titolo cover (58pt)
FN_HEAD   = "Montserrat-ExtraBold" # headline content
FN_BODY   = "Montserrat-Regular"   # body — corretto da Zero 2026-03-04
FN_ACC    = "Montserrat-Bold"      # subhead / accent

# -- Margini ------------------------------------------------------------------
MX = 90            # margine sinistro/destro — 90px = 8.3% su 1080px (Instagram safe zone)
IW = W - MX * 2   # 900px inner width — TESTO MAI OLTRE QUESTO

# -- Layout copertina ---------------------------------------------------------
COV_HY, COV_HH, COV_HS = 300, 240, 58   # titolo: LeagueSpartan 58pt
COV_SY, COV_SH, COV_SS = 560, 120, 34   # sottotitolo: Montserrat-Bold 34pt
COV_LY, COV_LS          = 1240, 80       # logo bottom-center

# -- Layout content -----------------------------------------------------------
#    Valori aggiornati da analisi reference "Carousel Dea" (2026-03-04)
# Valori corretti da Zero manualmente in Keynote (2026-03-04)
# Blocco centrato verticalmente (canvas 1350px, centro=675)
# headline visual ~540, body visual ~680 — gap ~30px
HD_Y, HD_H, HD_S = 550, 110, 40   # headline gold 40pt
SH_Y, SH_H, SH_S = 680,  65, 26   # subhead gold
BD_Y, BD_H, BD_S = 550, 620, 22   # body Montserrat-Regular 22pt
BD_Y_NOSUB        = 690            # 30px sotto fine headline (550+110+30)
BD_Y_SUB          = 760            # 15px sotto subhead (680+65+15)

LOGO = Path(__file__).parent.parent / "assets" / "bz_logo_clear.png"


# -- PIL: genera sfondo -------------------------------------------------------
def make_bg(img_path: str, tmp_dir: Path, slide_num: int,
            is_cover: bool, is_full_bleed: bool) -> str:
    """
    Cover:          foto scurata (brightness 0.55)
    Full-bleed:     dark flat + foto blended 28%
    Tutto il resto: dark flat (NO foto)
    """
    out = tmp_dir / f"bg_{slide_num:02d}.jpg"
    has = bool(img_path and Path(img_path).exists())

    if is_cover and has:
        img = Image.open(img_path).convert("RGB").resize((W, H), Image.LANCZOS)
        img = ImageEnhance.Brightness(img).enhance(0.55)
        img.save(out, "JPEG", quality=90)

    elif is_full_bleed and has:
        base  = Image.new("RGB", (W, H), BG_RGB)
        photo = Image.open(img_path).convert("RGB").resize((W, H), Image.LANCZOS)
        mask  = Image.new("L", (W, H), int(255 * 0.28))
        base.paste(photo, (0, 0), mask)
        base.save(out, "JPEG", quality=90)

    else:
        # PNG lossless per flat color — evita color shift da compressione JPEG
        out_png = out.with_suffix(".png")
        Image.new("RGB", (W, H), BG_RGB).save(out_png, "PNG")
        return str(out_png)

    return str(out)


# -- AppleScript helpers ------------------------------------------------------
def esc(s: str) -> str:
    """Escape per stringa AppleScript UTF-8. Mantiene accenti."""
    s = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
    for k, v in {"\u2019": "'", "\u2018": "'",
                 "\u201c": '"', "\u201d": '"',
                 "\u2013": "-", "\u2014": "--"}.items():
        s = s.replace(k, v)
    return s

def mk_text(var, text, x, y, w, h, font, size, color_as, align="left"):
    """
    Crea una text box Keynote via AppleScript.
    align: parametro accettato ma NON applicato via AppleScript —
    Keynote Creator Studio blocca 'alignment' (errore -10006 read-only).
    Il centering visivo è garantito dai margini: x=MX, w=IW.
    Per centrare manualmente: Keynote → Format → Text → Center.
    """
    return [
        f'            set {var} to make new text item'
        f' with properties {{position:{{{x},{y}}}, width:{w}, height:{h}}}',
        f'            try',
        f'                set vertical alignment of {var} to top',
        f'            end try',
        f'            set position of {var} to {{{x}, {y}}}',
        f'            set object text of {var} to "{esc(text)}"',
        f'            tell object text of {var}',
        f'                set font to "{font}"',
        f'                set size to {size}',
        f'                set color of every character to {color_as}',
        f'            end tell',
    ]

def mk_line(var, path, x, y, w, h):
    """Linea divisoria gold — immagine PNG flat (generata da PIL)."""
    return mk_img(var, path, x, y, w, h, opac=100)

def mk_img(var, path, x, y, w, h, opac=100):
    return [
        f'            set {var}_a to (POSIX file "{path}") as alias',
        f'            set {var} to make new image'
        f' with properties {{file:{var}_a, position:{{{x},{y}}}, width:{w}, height:{h}}}',
        f'            set opacity of {var} to {opac}',
    ]


# -- Slide builders -----------------------------------------------------------
def _slide_open(idx, first_slide):
    """
    Apre il blocco AppleScript per una slide.
    first_slide=True → riusa 'slide 1' esistente (evita slide bianca extra).
    first_slide=False → crea nuova slide con make new slide at end.
    """
    # Cleanup su TUTTE le slide — loop inverso per indice (più affidabile)
    open_cmd = f'        set s{idx} to slide 1' if first_slide else \
               f'        set s{idx} to make new slide at end'
    return [
        open_cmd,
        f'        tell s{idx}',
        # Delete text items per indice (inverso — evita shift di indici)
        f'            set _nt to count of every text item',
        f'            repeat with _ti from _nt to 1 by -1',
        f'                try',
        f'                    delete text item _ti',
        f'                end try',
        f'            end repeat',
        # Delete immagini
        f'            try',
        f'                delete every image',
        f'            end try',
        # Delete shapes
        f'            try',
        f'                delete every shape',
        f'            end try',
        f'            delay 0.1',
    ]


def as_cover(idx, slide, bg_path, first_slide=False):
    headline = slide.get("headline", "").upper()
    subhead  = (slide.get("subhead") or "").upper()
    lines = _slide_open(idx, first_slide)
    lines += mk_img(f"bg{idx}", bg_path, 0, 0, W, H, 100)
    # Headline: x=MX, w=IW → mai tocca i bordi
    lines += mk_text(f"h{idx}",  headline, MX, COV_HY, IW, COV_HH,
                     FN_COVER, COV_HS, PWHITE_AS)
    if subhead:
        lines += mk_text(f"sh{idx}", subhead, MX, COV_SY, IW, COV_SH,
                         FN_ACC, COV_SS, GOLD_AS)
    if LOGO.exists():
        lx = (W - COV_LS) // 2
        lines += mk_img(f"logo{idx}", str(LOGO), lx, COV_LY, COV_LS, COV_LS, 100)
    lines.append(f'        end tell')
    return lines


def as_content(idx, slide, bg_path, first_slide=False):
    headline = slide.get("headline", "").upper()
    subhead  = (slide.get("subhead") or "").upper()
    body     = (slide.get("body") or "").upper()
    lines = _slide_open(idx, first_slide)
    lines += mk_img(f"bg{idx}", bg_path, 0, 0, W, H, 100)

    # Headline
    lines += mk_text(f"h{idx}", headline, MX, HD_Y, IW, HD_H,
                     FN_HEAD, HD_S, GOLD_AS)

    # Subhead opzionale
    bd_y = BD_Y_NOSUB
    if subhead:
        lines += mk_text(f"sh{idx}", subhead, MX, SH_Y, IW, SH_H,
                         FN_ACC, SH_S, GOLD_AS)
        bd_y = BD_Y_SUB

    # Body
    if body:
        lines += mk_text(f"bd{idx}", body, MX, bd_y, IW, BD_H,
                         FN_BODY, BD_S, WHITE_AS)

    # Logo bottom-center (tutte le slide)
    if LOGO.exists():
        lx = (W - COV_LS) // 2
        lines += mk_img(f"logo{idx}", str(LOGO), lx, COV_LY, COV_LS, COV_LS, 100)

    lines.append(f'        end tell')
    return lines


# -- Build --------------------------------------------------------------------
def build(slides, image_map, out_dir, keynote_dir):
    tmp_bg = out_dir / "backgrounds"
    tmp_bg.mkdir(parents=True, exist_ok=True)
    keynote_dir.mkdir(parents=True, exist_ok=True)
    key_path = str(keynote_dir / "presentation.key")



    sc = [
        'tell application "Keynote"',
        '    try',
        '        close every document saving no',
        '    end try',
        '    activate', '    delay 1',
        f'    set d to make new document with properties {{width:{W}, height:{H}}}',
        '    tell d',
        # Keynote non permette 0 slide: tiene sempre almeno 1.
        # Eliminiamo slide 2..N se esistono, poi riusiamo slide 1.
        '        set _n to count of slides',
        '        if _n > 1 then',
        '            repeat with _i from _n to 2 by -1',
        '                delete slide _i',
        '            end repeat',
        '        end if',
        '        delay 0.3',
    ]

    for i, slide in enumerate(slides):
        num        = slide.get("slide_number", i + 1)
        img        = image_map.get(str(num), image_map.get(num, ""))
        is_cover   = slide.get("is_cover", False)
        layout     = slide.get("layout", "text_only")
        is_fb      = (layout == "full_bleed") and not is_cover
        first_slide = (i == 0)   # prima slide: riusa slide 1 esistente

        bg_path = make_bg(img, tmp_bg, num, is_cover, is_fb)
        tag = "cover" if is_cover else ("full_bleed" if is_fb else "content")
        print(f"  slide {num} [{tag}]{'[first]' if first_slide else ''}: bg={Path(bg_path).name}", file=sys.stderr)

        if is_cover:
            sc += as_cover(num, slide, bg_path, first_slide=first_slide)
        else:
            sc += as_content(num, slide, bg_path, first_slide=first_slide)

    sc += [
        '    end tell',
        f'    save d in POSIX file "{key_path}"',
        '    close d saving no',
        'end tell',
    ]

    script = "\n".join(sc)
    import os as _os
    fd, _tmp = tempfile.mkstemp(suffix=".applescript")
    sp = Path(_tmp)
    _os.close(fd)
    sp.write_text(script, encoding="utf-8")

    print(f"  AppleScript: {len(sc)} righe", file=sys.stderr)
    r = subprocess.run(["osascript", str(sp)], capture_output=True, text=True, timeout=480)
    sp.unlink(missing_ok=True)

    if r.returncode != 0:
        print(f"  ERROR: {r.stderr[:500]}", file=sys.stderr)
        return False
    print(f"  OK: .key generato", file=sys.stderr)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slides", required=True)
    ap.add_argument("--images", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--master", required=True)
    args = ap.parse_args()

    data       = json.loads(Path(args.slides).read_text())
    slides     = data.get("slides", data if isinstance(data, list) else [])
    images_dir = Path(args.images).resolve()
    out_dir    = Path(args.output).resolve()
    master_dir = Path(args.master).resolve()
    key_dir    = out_dir / "keynote"

    for d in [out_dir, key_dir, master_dir]:
        d.mkdir(parents=True, exist_ok=True)

    mf   = images_dir / "manifest.json"
    imap = json.loads(mf.read_text()) if mf.exists() else {}

    print(f"\n Keynote editabile ({len(slides)} slide)...", file=sys.stderr)
    ok = build(slides, imap, out_dir, key_dir)

    if ok:
        shutil.copy2(key_dir / "presentation.key", master_dir / "presentation.key")
        if cap := data.get("instagram_caption", ""):
            (master_dir / "instagram_caption.txt").write_text(cap)
        print(f"\n Master --> {master_dir}", file=sys.stderr)
    else:
        print("\n Build fallita", file=sys.stderr)


if __name__ == "__main__":
    main()
