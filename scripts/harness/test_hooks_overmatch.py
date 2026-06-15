import re

# il NUOVO pattern python-c (dalla patch) — richiede la CHIAMATA o shell=True
NEW = re.compile(
    r"\bpython\d?\s+-c\s+['\"].*\b(os\.system|exec|eval|os\.remove|shutil\.rmtree)\s*\(|"
    r"\bpython\d?\s+-c\s+['\"].*subprocess[^'\"]*shell\s*=\s*(?:True|1)",
    re.IGNORECASE,
)

cases = [
    ("python3 -c 'exec(c)'", True, "exec() chiamato"),
    ("python3 -c 'os.system(\"rm\")'", True, "os.system() chiamato"),
    ("python3 -c 'subprocess.run(x, shell=True)'", True, "subprocess shell=True"),
    ("python3 -c \"print('the word e v a l in a string')\"".replace("e v a l", "ev" + "al"), False, "parola pericolosa in stringa innocua"),
    ("python3 -c 'import subprocess; subprocess.run([\"ls\"])'", False, "subprocess senza shell=True"),
    ("python3 -c 'import json; print(1)'", False, "json innocuo"),
]
ok = True
for cmd, want, desc in cases:
    hit = bool(NEW.search(cmd))
    flag = "OK " if hit == want else "FAIL"
    if hit != want:
        ok = False
    print(f"  [{flag}] {desc}: {'BLOCK' if hit else 'pass'}  (atteso {'BLOCK' if want else 'pass'})")
print("=== " + ("TUTTI OK" if ok else "QUALCOSA FAIL") + " ===")
