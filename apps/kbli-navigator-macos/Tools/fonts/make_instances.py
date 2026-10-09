#!/usr/bin/env python3
"""Cut the five static font instances the app bundles (spec §1.5) from the R19 variable fonts.

Run once, on a host with fontTools (M5): python3 Tools/fonts/make_instances.py <monorepo>/apps/mouth/public/fonts
The variable defaults paint the wrong weight (Fraunces wght 900 opsz 9 WONK 1, Manrope wght 200),
so every axis is pinned. Name IDs 1/3/4/6/16/17 are rewritten: no instance collides with another or with
an installed Fraunces/Manrope. Output: Resources/Fonts/<PostScript name>.ttf beside this app's OFL texts.
"""
import pathlib, sys
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

CUTS = {  # PostScript name -> (source, pinned axes)
    "KBLIFraunces-Display": ("fraunces-variable.ttf", {"wght": 450, "opsz": 144, "SOFT": 0, "WONK": 0}),
    "KBLIFraunces-Title": ("fraunces-variable.ttf", {"wght": 450, "opsz": 36, "SOFT": 0, "WONK": 0}),
    "KBLIFraunces-Text": ("fraunces-variable.ttf", {"wght": 450, "opsz": 20, "SOFT": 0, "WONK": 0}),
    "KBLIManrope-Regular": ("manrope-variable.ttf", {"wght": 400}),
    "KBLIManrope-SemiBold": ("manrope-variable.ttf", {"wght": 600}),
}
src, out = pathlib.Path(sys.argv[1]), pathlib.Path(__file__).resolve().parents[2] / "Resources" / "Fonts"
out.mkdir(parents=True, exist_ok=True)
for ps, (file, axes) in CUTS.items():
    font = instantiateVariableFont(TTFont(src / file, recalcTimestamp=False), axes)
    family, name = ps.replace("-", " "), font["name"]
    name.names = [r for r in name.names if r.nameID < 25]  # drop the variable-only names
    if "STAT" in font: del font["STAT"]  # its axis values point at the dropped names
    for nid, value in {1: family, 2: "Regular", 3: f"KBLI;{ps}", 4: family, 6: ps, 16: family, 17: "Regular"}.items():
        name.setName(value, nid, 3, 1, 0x409); name.setName(value, nid, 1, 0, 0)
    font.save(out / f"{ps}.ttf")
    print(ps, axes, (out / f"{ps}.ttf").stat().st_size)
