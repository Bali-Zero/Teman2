# Fresh-Opus gate 2 adversarial corpus for L12 (2026-09-25), kept verbatim as the
# acceptance corpus of the v3 spec (l12-v3-spec.md). Run from the repo root.
import sys
sys.path.insert(0,"scripts")
from kbli_dataset_lint import l12_full_ownership_claim as f
GATE1=[("I","Foreign investors are not granted full ownership of this company."),
("I","Foreign investors are never given full ownership of this company."),
("I","Since May 2026, full ownership is only possible for Indonesian citizens."),
("I","Only Indonesians can fully own this business."),
("G","Foreign investors can hold all of the shares in this company."),
("G","This company can be wholly-owned by foreign investors."),
("G","This company can be 100%-foreign-owned.")]
GUILT=[
"In May 2026, foreign investors could fully own this company.",
"Because Bali has no moratorium on this code, foreigners are allowed to fully own it.",
"Foreign investors are free to own all of the shares in this company.",
"Foreigners are able to hold 100% of the equity.",
"Overseas investors are entitled to full ownership of the business.",
"A foreign shareholder is given complete ownership under the current rules.",
"Foreign companies and their subsidiaries may hold the entire capital of this business.",
"Foreign investors can fully own this company, while Indonesian citizens must meet a separate reporting rule.",
"Foreign investors can fully own this company; only Indonesians may own the land.",
"100% foreign ownership is permitted for this activity in Bali.",
"Full foreign ownership is possible, since Bali imposes no moratorium on this code.",
"Starting 1 May 2026, a foreign PT PMA may be the sole owner of this business.",
"The company is permitted to be wholly foreign owned.",
"Foreign investors could own the business outright after registering with OSS.",
"Foreign investors may operate without any local partner.",
"In Bali, where there is no moratorium, foreign investors can hold all the shares.",
"Foreign investors can, since May 2026, fully own this company.",
"Foreign investors may, from May 2026, fully own this company.",
"Foreign investors, not Indonesian citizens, can fully own this company.",
"Non-Indonesian investors can fully own this company.",
"Foreign investors can fully own this company: the land title, however, goes only to Indonesian citizens.",
"Both foreign investors and Indonesian citizens can fully own this company.",
# probes of the void / subject route / predicate forms
"Foreign and Indonesian investors can fully own this company.",
"Foreign-owned PMA companies and Indonesian citizens can fully own this business.",
"Unlike Indonesian citizens, foreign individuals can fully own this company.",
"Unlike Indonesian citizens, a foreign PT PMA can fully own this company.",
"Investors who are not Indonesian citizens can fully own this company.",
"Foreign investors are now allowed to fully own this company.",
"Foreign investors can hold 100% of its shares.",
"Full ownership is available not only to Indonesian citizens but also to foreign investors.",
]
INNO=[
"Foreign investors cannot fully own this company in Bali.",
"Foreign investors are not allowed to hold all the shares.",
"Foreign investors are not able to own the whole company.",
"Foreign investors cannot, in Bali, fully own this company.",
"Foreign investors could not, under Perpres 49/2021, fully own this company.",
"Foreign investors may not be the sole owner of this business.",
"Only Indonesian nationals may hold the entire equity of this company.",
"Local investors can hold 100% of the shares.",
"Indonesians may own this company outright.",
"The business may be wholly owned by Indonesian shareholders.",
"Full ownership is permitted only for citizens of Indonesia.",
"Full ownership is possible only for Indonesian citizens, and foreigners are capped at 49%.",
"Indonesian citizens, rather than foreigners, are entitled to full ownership.",
"It is false that foreign investors can fully own this company.",
"There is no way for a foreign investor to fully own this company.",
"Could a foreign investor be the sole owner of this company?",
"Is full foreign ownership permitted for this code?",
"Full foreign ownership of this code ended in 2021.",
"Since late May, 100% foreign ownership has been closed to new applicants.",
"In May 2021 the government decided that full foreign ownership is not permitted.",
# probes: negated modal forms, month forms, clause-scoped subject
"Foreign investors can never fully own this company.",
"Foreign investors can no longer fully own this company.",
"Foreign investors may never hold all of the shares.",
"During May, full foreign ownership was suspended.",
"Last May, full foreign ownership was withdrawn for this code.",
"Foreigners are capped at 49%; only Indonesian citizens can fully own this business.",
"Foreign investors cannot fully own this company, but Indonesians can own it outright.",
"Only Indonesian citizens (see Perpres No. 10/2021) can fully own this company.",
]
def show(lbl,exp,s):
    got=f(s,49); flag=got is not None
    ok=(flag==(exp=="G"))
    print(f"{'ok ' if ok else 'MISS'} {lbl} exp={exp} flag={flag} :: {s}")
    return ok
print("== gate-1 defect sentences"); [show("g1",e,s) for e,s in GATE1]
print("== guilt"); [show("G%02d"%i,"G",s) for i,s in enumerate(GUILT,1)]
print("== innocence"); [show("I%02d"%i,"I",s) for i,s in enumerate(INNO,1)]
print("== maxa guards")
s="Foreign-owned PMA companies can fully own this business."
for m in (100,None,True,"special",False,49.0,0,99):
    print(repr(m), f(s,m) is not None)

# --- second probe round (c4b) ---
C4B = ["Foreign investors can hold all of its shares.",
"Foreign investors can hold all of the company's shares.",
"Throughout May, full foreign ownership was paused.",
"Every May, 100% foreign ownership is reviewed.",
"Foreign investors could never be the sole owner of this business.",
"Anyone who is not an Indonesian citizen can fully own this company.",
"Unlike Indonesian citizens, foreign buyers can fully own this company.",
"Foreign investors are also permitted to fully own this company.",
"Foreign investors will be allowed to fully own this company.",
"No foreign investor can fully own this company.",
"Full ownership is available to Indonesian citizens only.",
"This company can be wholly owned by Indonesian citizens or foreign investors.",
"Did you know foreign investors can fully own this company?",
"Foreign investors can fully own this company if the land title is registered only to Indonesian citizens.",
]
