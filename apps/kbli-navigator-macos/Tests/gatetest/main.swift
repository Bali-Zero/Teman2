import Foundation

func ck(_ c: Bool, _ m: String) { if c { print("  ✅ \(m)") } else { print("  ❌ FAIL: \(m)"); exit(1) } }

// The exact multi-record bypass from the design doc (§3 post-generation gate): package
// {51101→49, 79122→0}, answer "79122 allows 49%" — 49 exists in the package but NOT on 79122.
let ctx = KBLIGateContext(includedCodes: ["51101", "79122"], capsByCode: ["51101": 49, "79122": 0], conflictCodes: [])

print("Innocence — correct single claims pass:")
switch KBLIAnswerGate.check("79122 has a 0% foreign ownership cap.", context: ctx) {
case .pass: print("  ✅ correct claim (79122=0%) passes")
default: ck(false, "correct claim (79122=0%) should pass")
}
switch KBLIAnswerGate.check("51101 allows 49% foreign ownership.", context: ctx) {
case .pass: print("  ✅ correct claim (51101=49%) passes")
default: ck(false, "correct claim (51101=49%) should pass")
}
switch KBLIAnswerGate.check("The navigator does not carry that fact.", context: ctx) {
case .pass: print("  ✅ a plain abstention with no code/percent at all passes")
default: ck(false, "abstention with no claims should pass")
}

print("Guilt — the exact cross-record bypass (design §3):")
switch KBLIAnswerGate.check("79122 allows 49%.", context: ctx) {
case .rejected(.percentCodeMismatch(let code, let claimed, let actual)):
    ck(code == "79122" && claimed == 49.0 && actual == 0, "79122/49% rejected as percentCodeMismatch(79122, 49.0, actual=0)")
default: ck(false, "79122 allows 49% MUST be rejected (got pass or wrong rejection)")
}

print("Guilt — unknown code cited:")
switch KBLIAnswerGate.check("KBLI 99999 is open.", context: ctx) {
case .rejected(.unknownCode(let c)): ck(c == "99999", "unknown code 99999 rejected")
default: ck(false, "citing a code outside the package must reject")
}

print("Guilt — numeric percent surface forms (all parse to 49.0 against 51101's real cap):")
for phrase in ["51101 allows 49%.", "51101 allows 49 percent.", "51101 allows 49 persen.",
               "51101 allows 49,0%.", "51101 allows 49.0%.", "51101 allows 49％.", "51101 allows 49٪."] {
    switch KBLIAnswerGate.check(phrase, context: ctx) {
    case .pass: print("  ✅ '\(phrase)' parses to 49.0 and passes (matches 51101's real cap)")
    default: ck(false, "'\(phrase)' should parse as 49.0% and pass")
    }
}

print("Guilt — the '49,0%%' trap must be 49.0, never a trailing 0%:")
// If a buggy parser read "49,0%" as "0%" it would compare against 51101's cap (49) and reject.
// The correct parse (49.0) must PASS.
switch KBLIAnswerGate.check("51101 allows 49,0%.", context: ctx) {
case .pass: print("  ✅ '49,0%' parsed as the maximal atomic number 49.0, not a trailing 0%")
default: ck(false, "'49,0%' must parse as 49.0, never as a trailing 0%")
}

print("Guilt — spelled-out numbers rejected as unverifiable (orphan marker, no adjacent digits):")
for phrase in ["51101 allows forty-nine percent.", "51101 mengizinkan empat puluh sembilan persen."] {
    switch KBLIAnswerGate.check(phrase, context: ctx) {
    case .rejected(.unverifiablePercentClaim): print("  ✅ '\(phrase)' rejected as unverifiable")
    default: ck(false, "'\(phrase)' (spelled-out number) must reject as unverifiable")
    }
}

print("Guilt — multi-code / multi-figure clause ('…respectively') is unverifiable:")
switch KBLIAnswerGate.check("51101 and 79122 allow 49% and 0%, respectively.", context: ctx) {
case .rejected(.unverifiablePercentClaim): print("  ✅ multi-code/multi-figure clause rejected")
default: ck(false, "a clause with 2 codes and 2 figures must reject as unverifiable pairing")
}

print("Guilt — pma_conflict record: ANY percent claim on it rejects, even a 'correct'-looking one:")
let conflictCtx = KBLIGateContext(includedCodes: ["50111"], capsByCode: [:], conflictCodes: ["50111"])
switch KBLIAnswerGate.check("50111 allows 49% foreign ownership.", context: conflictCtx) {
case .rejected(.conflictRecordPercentClaim(let c)): ck(c == "50111", "50111 (pma_conflict) rejects any % claim, even one matching the raw dataset number")
default: ck(false, "a % claim on a pma_conflict record must always reject")
}

// ═════════════════════════════════════════════════════════════════════════════════════════
// P2b CURE (benchmark §4a) — the three over-match carve-outs. Every rule gets a GUILT case
// (the thing the rule exists to stop, which must still be stopped) and an INNOCENCE case (the
// verified-true answer the shipped gate was killing). The shipped gate had only guilt tests;
// that is exactly how it went out over-matching.
// ═════════════════════════════════════════════════════════════════════════════════════════

// α — a code the QUESTION named that the catalogue provably does not contain (Q05: 68200).
let absentCtx = KBLIGateContext(includedCodes: ["68111"], capsByCode: ["68111": 100],
                                conflictCodes: [], absentCodes: ["68200"])

print("α innocence — an absence statement about a question-named absent code passes:")
for phrase in ["Navigator tidak membawa data untuk KBLI 68200.",
               "68200 tidak terdaftar dalam katalog KBLI 2025.",
               "The catalogue does not contain 68200.",
               "68200 is not listed in the 2025 catalogue."] {
    switch KBLIAnswerGate.check(phrase, context: absentCtx) {
    case .pass: print("  ✅ '\(phrase)' passes")
    default: ck(false, "α: '\(phrase)' is the EXPECTED answer and must pass")
    }
}
switch KBLIAnswerGate.check("68111 adalah 100%. 68200 tidak ada dalam katalog.", context: absentCtx) {
case .pass: print("  ✅ a correct claim plus an absence statement passes together")
default: ck(false, "α: correct claim + absence statement must pass")
}

print("α guilt — the carve-out must NOT launder anything else:")
switch KBLIAnswerGate.check("68200 adalah kode untuk real estate.", context: absentCtx) {
case .rejected(.unknownCode(let c)): ck(c == "68200", "α: an AFFIRMATIVE claim about an absent code still rejects")
default: ck(false, "α: an affirmative claim about 68200 must reject — no absence marker in the clause")
}
switch KBLIAnswerGate.check("68200 tidak ada. 68200 memiliki batas 49%.", context: absentCtx) {
case .rejected: print("  ✅ α: the marker in clause 1 does not license the affirmative clause 2")
default: ck(false, "α: an absence marker must not carry across clause boundaries")
}
switch KBLIAnswerGate.check("99999 tidak ada dalam katalog.", context: absentCtx) {
case .rejected(.unknownCode(let c)): ck(c == "99999", "α: a code the MODEL invented is not in absentCodes and still rejects")
default: ck(false, "α: only codes the QUESTION named may use the carve-out")
}
// The α carve-out licenses the CITATION only. The %-binding stage runs afterwards against
// `includedCodes`, which an absent code is by definition not in — so a figure attached to it
// rejects as `unknownCode`, not as `unverifiablePercentClaim`. Either way, no figure can ever
// ride an absence statement into a served answer.
switch KBLIAnswerGate.check("68200 tidak ada, batasnya 49%.", context: absentCtx) {
case .rejected(.unknownCode(let c)): ck(c == "68200", "α: no figure may ever be attached to an absent code")
default: ck(false, "α: a % figure bound to an absent code must reject (it is not in includedCodes)")
}

// β — an exception clause repeating the cap it qualifies (Q22: 25200, cap 49).
let excCtx = KBLIGateContext(includedCodes: ["25200", "51101"], capsByCode: ["25200": 49, "51101": 49],
                             conflictCodes: [])

print("β innocence — an exception sentence may repeat its own code's verified cap:")
switch KBLIAnswerGate.check(
    "KBLI 25200 dibatasi 49% untuk asing. Namun dapat melebihi 49% dengan persetujuan Menteri Pertahanan.",
    context: excCtx) {
case .pass: print("  ✅ Q22's exact shape (cap sentence + exception sentence) passes")
default: ck(false, "β: the Q22 exception shape must pass — both figures are the same verified cap")
}

print("β guilt — carry-forward verifies, it does not wave through:")
switch KBLIAnswerGate.check("KBLI 25200 dibatasi 49%. Dengan izin bisa sampai 100%.", context: excCtx) {
case .rejected(.percentCodeMismatch(let c, let claimed, let actual)):
    ck(c == "25200" && claimed == 100.0 && actual == 49, "β: a code-less clause quoting a DIFFERENT figure rejects as mismatch")
default: ck(false, "β: 100% carried onto a 49%-capped code must reject")
}
// A leading code-less figure has nothing to bind to — but only on a package whose caps DISAGREE.
// (On a uniform package the δ package-level rule below gives it exactly one possible referent,
// which is the point of that rule; `excCtx` is uniform at 49, so this case needs a mixed one.)
let mixedLeadCtx = KBLIGateContext(includedCodes: ["25200", "68111"], capsByCode: ["25200": 49, "68111": 100],
                                   conflictCodes: [])
switch KBLIAnswerGate.check("Batas kepemilikan asing adalah 49%.", context: mixedLeadCtx) {
case .rejected(.unverifiablePercentClaim): print("  ✅ β: a figure with NO code before it, on a mixed package, still rejects")
default: ck(false, "β: a leading code-less figure on a mixed package has no referent and must reject")
}

// γ — a multi-code clause where every code shares the same verified cap (Q13).
let sharedCtx = KBLIGateContext(includedCodes: ["51101", "51102", "68111", "79122"],
                                capsByCode: ["51101": 100, "51102": 100, "68111": 100, "79122": 0],
                                conflictCodes: [])

print("γ innocence — N codes, one figure, all sharing that verified cap:")
switch KBLIAnswerGate.check("KBLI 51101, 51102, dan 68111 semuanya terbuka hingga 100%.", context: sharedCtx) {
case .pass: print("  ✅ three codes sharing cap 100 with one figure passes")
default: ck(false, "γ: a fully checkable multi-code clause must pass")
}

print("γ guilt — one dissenting cap in the clause kills it:")
switch KBLIAnswerGate.check("KBLI 51101, 51102, dan 79122 semuanya terbuka hingga 100%.", context: sharedCtx) {
case .rejected(.percentCodeMismatch(let c, _, let actual)):
    ck(c == "79122" && actual == 0, "γ: 79122 (cap 0) in a '100%' clause rejects as mismatch")
default: ck(false, "γ: a clause is only verified when EVERY code in it carries the quoted figure")
}
switch KBLIAnswerGate.check("KBLI 51101 dan 51102 adalah 100% dan 49%.", context: sharedCtx) {
case .rejected(.unverifiablePercentClaim): print("  ✅ γ: two figures in one clause remain unverifiable")
default: ck(false, "γ: the multi-FIGURE rule must survive the multi-CODE carve-out")
}

// δ — the user's own figure echoed beside the verified cap that answers it (Q13 runs 1+3).
let echoCtx = KBLIGateContext(includedCodes: ["49222", "63900"], capsByCode: ["49222": 100, "63900": 100],
                              conflictCodes: [], questionFigures: [51.0])

print("δ innocence — an echoed question figure does not consume the one-figure budget:")
switch KBLIAnswerGate.check("KBLI 49222: quota estera massima 100%, quindi 51% rientra nel limite.", context: echoCtx) {
case .pass: print("  ✅ verified cap + echoed premise in one clause passes")
default: ck(false, "δ: '100%, quindi 51%' must pass — 100 is the verified cap, 51 is the question's own figure")
}
switch KBLIAnswerGate.check("Untuk KBLI yang tersedia, batasnya hingga 100%, jadi 51% berada dalam batas.", context: echoCtx) {
case .pass: print("  ✅ a package-level clause passes when every package record shares the cap")
default: ck(false, "δ: a code-less package-level clause must pass on a uniform package")
}

print("δ guilt — an echo alone does not verify itself:")
switch KBLIAnswerGate.check("KBLI 63900 mengizinkan 51%.", context: echoCtx) {
case .rejected(.percentCodeMismatch(let c, let claimed, let actual)):
    ck(c == "63900" && claimed == 51.0 && actual == 100, "δ: a clause whose ONLY figure is the echo is still verified as a claim")
default: ck(false, "δ: '63900 allows 51%' asserts a cap of 51 on a cap-100 record and must reject")
}
let mixedCtx = KBLIGateContext(includedCodes: ["49222", "79122"], capsByCode: ["49222": 100, "79122": 0],
                               conflictCodes: [], questionFigures: [51.0])
switch KBLIAnswerGate.check("Batasnya hingga 100%, jadi 51% berada dalam batas.", context: mixedCtx) {
case .rejected(.unverifiablePercentClaim): print("  ✅ δ: on a MIXED package the package-level referent is undefined and rejects")
default: ck(false, "δ: a package-level clause must reject when the package's caps disagree")
}

print("Regression — the original design §3 bypass is still blocked after all four carve-outs:")
switch KBLIAnswerGate.check("79122 allows 49%.", context: ctx) {
case .rejected(.percentCodeMismatch): print("  ✅ cross-record bypass still rejected")
default: ck(false, "the original bypass must remain blocked")
}

print("ALL GATE TESTS PASSED")
