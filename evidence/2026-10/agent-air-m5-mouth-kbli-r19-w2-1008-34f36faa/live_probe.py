import importlib.util,json,pathlib,sys,os
R=pathlib.Path(sys.argv[1]);BASE=sys.argv[2];OUT=pathlib.Path(sys.argv[3]);SHOTS=pathlib.Path(os.path.expanduser("~/BATTAGLIA-20261008/PREVIEW-kbli-nav-design/w2"))
def load(n):
    sp=importlib.util.spec_from_file_location(n,R/f".claude/skills/design/strumenti/{n}.py");m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
M=load("measure");D=load("defects")
PAGES=["/kbli","/kbli/55203","/kbli/51101","/kbli/56101","/kbli-explorer"]
from playwright.sync_api import sync_playwright
res={"contrast":{}, "shots":[]}
with sync_playwright() as pw:
    b=pw.chromium.launch(executable_path=M.CHROME)
    for path in PAGES:
        slug=path.strip("/").replace("/","-")
        for v,(w,h) in M.VIEWPORTS.items():
            for t,(scheme,forced) in M.THEMES.items():
                ctx=b.new_context(viewport={"width":w,"height":h},color_scheme=scheme,device_scale_factor=1)
                pg=ctx.new_page();pg.goto(BASE+path,wait_until="load",timeout=180000);pg.wait_for_timeout(300)
                if forced:pg.evaluate("t=>document.documentElement.setAttribute('data-theme',t)",forced)
                pg.wait_for_timeout(1500)
                r=pg.evaluate(M.PROBE_JS);pg.wait_for_timeout(400);r=pg.evaluate(M.PROBE_JS)
                f=r["contrast_failures"]
                res["contrast"][f"{path} {v}/{t}"]={"failures":len(f),"min_ratio":min([x["ratio"] for x in f],default=None),"worst":sorted(f,key=lambda x:x["ratio"])[:3],"unmeasurable_over_image":len(r["unmeasurable_over_image"]),"horizontal_scroll":r["horizontal_scroll"]}
                fn=f"{slug}-{v}-{t}.png";pg.screenshot(path=str(SHOTS/fn),full_page=True);res["shots"].append(fn)
                ctx.close()
    calib=R/".claude/skills/design/strumenti/controlli-di-calibrazione"
    pg=b.new_page(viewport={"width":390,"height":844});ctl={}
    for n in("innocent","guilty"):
        pg.goto((calib/f"defects-{n}.html").resolve().as_uri(),wait_until="load");pg.wait_for_timeout(400);ctl[n]=pg.evaluate(D.PROBE_JS)
    seats={}
    for path in PAGES:
        pg.goto(BASE+path,wait_until="load",timeout=180000);pg.wait_for_timeout(1500);seats[path]=pg.evaluate(D.PROBE_JS)
    inn={c:ctl["innocent"].get(c,[]) for c in D.CLASSES if ctl["innocent"].get(c)}
    sil=[c for c in D.CLASSES if not ctl["guilty"].get(c)]
    res["defects"]={"innocence":"CLEAN" if not inn else "NOISY "+json.dumps(inn),"guilt":"ALL FIRE" if not sil else "SILENT ON "+",".join(sil),
      "trusted":not inn and not sil,"findings":{p:{c:len(s[c]) for c in D.CLASSES if s[c]} for p,s in seats.items()},"detail":{p:{c:s[c][:3] for c in D.CLASSES if s[c]} for p,s in seats.items()}}
    b.close()
OUT.write_text(json.dumps(res,indent=1))
bad=[(k,v["failures"],v["min_ratio"]) for k,v in res["contrast"].items() if v["failures"]]
print("contrast states with failures:",len(bad),"of",len(res["contrast"]));
for x in bad:print(" ",x)
print("defects:",res["defects"]["innocence"],"|",res["defects"]["guilt"],"| trusted:",res["defects"]["trusted"]);print(json.dumps(res["defects"]["findings"]))
