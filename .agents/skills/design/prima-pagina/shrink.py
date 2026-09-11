import sys,pathlib
from PIL import Image
d=pathlib.Path(sys.argv[1]); out=d/"shots_web"; out.mkdir(exist_ok=True)
tot=0
for f in sorted((d/"shots").glob("*.png")):
    im=Image.open(f).convert("RGB")
    w = 760 if f.stem.startswith("desktop") else 470
    if im.width>w: im=im.resize((w,round(im.height*w/im.width)), Image.LANCZOS)
    g=out/(f.stem+".jpg"); im.save(g,"JPEG",quality=78,optimize=True,progressive=True)
    tot+=g.stat().st_size
    print(f"{f.stem:<24} {im.width}x{im.height} {g.stat().st_size/1024:7.0f} KB")
print(f"TOTAL {tot/1024/1024:.2f} MB  (base64 inflates ~1.34x -> {tot*1.34/1024/1024:.2f} MB)")
