#!/usr/bin/env python3
"""
build.py — turn a carousel spec (JSON) into a self-contained carousel.html
plus a render_manifest.json that tells render.py which slides are images
and which are video composites.

Usage:
    python build.py <spec.json> [--out <build_dir>] [--assets <skill_assets_dir>]

Defaults:
    --out     <spec_dir>/build
    --assets  <this_script>/../assets

See references/spec_schema.md for the full spec format.
"""
import argparse, html, json, pathlib, shutil, sys

PRESETS = {"dark-editorial", "light", "warm-film", "bold-gradient",
           "crimson", "pink-lime", "blush", "magenta-noir", "burgundy"}

# Optional font-pair override (spec.font). Overrides the theme's heading/body font.
FONT_PAIRS = {
    "manrope":   {"--head-font": "'Manrope', sans-serif",   "--head-weight": "800", "--body-font": "'Manrope', sans-serif"},
    "fraunces":  {"--head-font": "'Fraunces', serif",       "--head-weight": "600", "--body-font": "'Manrope', sans-serif"},
    "unbounded": {"--head-font": "'Unbounded', sans-serif", "--head-weight": "800", "--body-font": "'Manrope', sans-serif"},
    "archivo":   {"--head-font": "'Archivo', sans-serif",   "--head-weight": "900", "--body-font": "'Manrope', sans-serif"},
}


def esc(s):
    return html.escape(str(s), quote=False)


def fmt(s):
    """Escape, then enable \\n -> <br> and [[word]] -> accent span."""
    if s is None:
        return ""
    out = esc(s).replace("\n", "<br>")
    while "[[" in out and "]]" in out:
        a = out.index("[["); b = out.index("]]", a)
        inner = out[a + 2:b]
        out = out[:a] + f'<span class="accent">{inner}</span>' + out[b + 2:]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--out", default=None)
    ap.add_argument("--assets", default=None)
    args = ap.parse_args()

    spec_path = pathlib.Path(args.spec).resolve()
    spec_dir = spec_path.parent
    spec = json.loads(spec_path.read_text(encoding="utf-8"))

    script_dir = pathlib.Path(__file__).resolve().parent
    assets_dir = pathlib.Path(args.assets).resolve() if args.assets else (script_dir.parent / "assets")
    out_dir = pathlib.Path(args.out).resolve() if args.out else (spec_dir / "build")
    (out_dir / "assets").mkdir(parents=True, exist_ok=True)

    nick = spec.get("nick", "")
    slides = spec["slides"]
    total = len(slides)

    # ---- theme ----
    theme = spec.get("theme", "dark-editorial")
    custom_style = ""
    body_class = ""
    extra_fonts = ""
    if isinstance(theme, dict):
        base = theme.get("base", "dark-editorial")
        data_theme = base
        body_class = "ec-custom"
        decls = "".join(f"{k}:{v};" for k, v in theme.get("vars", {}).items())
        custom_style = f"\n<style>body.ec-custom{{{decls}}}</style>"
        for f in theme.get("fonts", []):
            extra_fonts += f'\n<link rel="stylesheet" href="{f}">'
    else:
        data_theme = theme if theme in PRESETS else "dark-editorial"

    # ---- font pair (optional override of the theme's fonts) ----
    font = spec.get("font")
    if font in FONT_PAIRS:
        fdecls = "".join(f"{k}:{v};" for k, v in FONT_PAIRS[font].items())
        body_class = (body_class + " ec-font").strip()
        custom_style += f"\n<style>body.ec-font{{{fdecls}}}</style>"

    # ---- numbering style: counter (small NN/TT) | ghost (big transparent number) | none ----
    numbering = spec.get("numbering", "counter")
    if numbering not in ("counter", "ghost", "none"):
        numbering = "counter"

    # ---- numbering scope: which slides carry a number, and where the count starts ----
    #   all        → 1..N (cover = 1, last numbered)
    #   skip-cover → cover unnumbered; 2nd slide = 1
    #   middle     → cover and last slide unnumbered
    number_scope = spec.get("numberScope", "all")
    if number_scope not in ("all", "skip-cover", "middle"):
        number_scope = "all"
    if number_scope == "skip-cover":
        numbered = [n for n in range(1, total + 1) if n != 1]
    elif number_scope == "middle":
        numbered = [n for n in range(1, total + 1) if n not in (1, total)]
    else:
        numbered = list(range(1, total + 1))
    num_display = {n: pos + 1 for pos, n in enumerate(numbered)}  # slide index -> shown number
    num_total = len(numbered)                                      # denominator for "DD / TT"

    styles = (assets_dir / "styles.css").read_text(encoding="utf-8")

    media_counter = [0]

    def copy_media(src):
        """Copy a referenced media file into build/assets with a safe name."""
        p = (spec_dir / src) if not pathlib.Path(src).is_absolute() else pathlib.Path(src)
        p = p.resolve()
        if not p.exists():
            print(f"  WARNING: media not found: {p}", file=sys.stderr)
        ext = p.suffix.lower() or ".bin"
        name = f"media{media_counter[0]}{ext}"
        media_counter[0] += 1
        try:
            shutil.copy(p, out_dir / "assets" / name)
        except Exception as e:
            print(f"  WARNING: could not copy {p}: {e}", file=sys.stderr)
        return f"assets/{name}"

    def load_visual(vid):
        f = assets_dir / "visuals" / f"{vid}.svg"
        if f.exists():
            return f.read_text(encoding="utf-8")
        print(f"  WARNING: visual '{vid}' not found in {assets_dir/'visuals'}", file=sys.stderr)
        return ""

    slide_html = []
    manifest = []

    for i, s in enumerate(slides, start=1):
        sid = f"s{i}"
        stype = s.get("type", "context")
        bg = s.get("background") or {"kind": "none"}
        kind = bg.get("kind", "none")
        classes = ["slide"]
        style_attr = ""
        scrim = ""
        video_rel = None

        if kind == "photo":
            classes.append("media")
            rel = copy_media(bg["src"])
            style_attr = f" style=\"background-image:url('{rel}')\""
            scrim = '<div class="scrim"></div>'
        elif kind == "video":
            classes += ["media", "video-bg"]
            video_rel = copy_media(bg["src"])
            scrim = '<div class="scrim"></div>'
        elif kind == "preset":
            classes += ["bg-preset", f"preset-{bg.get('name','spotlight')}"]

        is_vtip = (stype == "tip" and s.get("visual") and kind not in ("photo", "video"))
        _dd = num_display.get(i)
        num = (f'<div class="num">{_dd:02d} / {num_total:02d}</div>'
               if numbering == "counter" and _dd else "")
        ghost_html = (f'<div class="big-index">{_dd:02d}</div>'
                      if numbering == "ghost" and _dd and not is_vtip else "")
        nick_html = f'<div class="nick">{esc(nick)}</div>' if nick else ""
        kicker = f'<div class="kicker">{fmt(s["kicker"])}</div>' if s.get("kicker") else ""

        inner = ""
        if stype == "cover":
            inner += num + ghost_html + kicker
            inner += f'<h1>{fmt(s.get("title",""))}</h1>'
            if s.get("lead"):
                inner += '<div class="divider"></div>'
                inner += f'<div class="lead">{fmt(s["lead"])}</div>'
            inner += nick_html

        elif stype == "context":
            inner += num + ghost_html + kicker
            inner += f'<h2>{fmt(s.get("title",""))}</h2>'
            if s.get("body"):
                inner += f'<div class="body">{fmt(s["body"])}</div>'
            inner += nick_html

        elif stype == "tip":
            visual = s.get("visual")
            if visual and kind not in ("photo", "video"):
                classes.append("withvis")
                inner += num
                inner += '<div class="vis-row"><div class="vis-text">'
                inner += kicker
                inner += f'<h2>{fmt(s.get("title",""))}</h2>'
                if s.get("body"):
                    inner += f'<div class="body">{fmt(s["body"])}</div>'
                inner += '</div><div class="vis-art">' + load_visual(visual) + '</div></div>'
                inner += nick_html
            else:
                inner += num + ghost_html
                inner += kicker
                inner += f'<h2>{fmt(s.get("title",""))}</h2>'
                if s.get("body"):
                    inner += f'<div class="body">{fmt(s["body"])}</div>'
                inner += nick_html

        elif stype == "quote":
            inner += num + ghost_html
            inner += f'<h2 style="font-style:italic;max-width:840px">«{fmt(s.get("title",""))}»</h2>'
            if s.get("author"):
                inner += f'<div class="lead">— {fmt(s["author"])}</div>'
            inner += nick_html

        elif stype == "cta":
            classes.append("cta")
            inner += num + ghost_html + kicker
            inner += f'<h2>{fmt(s.get("title",""))}</h2>'
            if s.get("lead"):
                inner += f'<div class="lead">{fmt(s["lead"])}</div>'
            inner += nick_html
        else:
            inner += num + f'<h2>{fmt(s.get("title",""))}</h2>' + nick_html

        cls = " ".join(classes)
        slide_html.append(f'<div class="{cls}" id="{sid}"{style_attr}>{scrim}{inner}</div>')

        name = f'{i:02d}_{stype}'
        manifest.append({
            "id": sid, "index": i, "name": name,
            "mode": "video" if kind == "video" else "image",
            "video": video_rel,
        })

    page = f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="UTF-8">{extra_fonts}
<style>
{styles}
</style>{custom_style}
</head>
<body class="{body_class}" data-theme="{data_theme}">
{chr(10).join(slide_html)}
</body></html>"""

    (out_dir / "carousel.html").write_text(page, encoding="utf-8")
    (out_dir / "render_manifest.json").write_text(
        json.dumps({"size": spec.get("size", [1080, 1350]), "slides": manifest},
                   ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"built {total} slides -> {out_dir/'carousel.html'}")
    vids = [m for m in manifest if m["mode"] == "video"]
    if vids:
        print(f"  {len(vids)} video slide(s): " + ", ".join(m["name"] for m in vids))


if __name__ == "__main__":
    main()
