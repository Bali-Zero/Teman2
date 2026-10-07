import Foundation

// KBLIAnswerGate.swift — the deterministic post-generation gate (design §3, refuter P1-7/R2-6).
// Prompt instructions are not the only control: before display, every answer is checked against
// the SAME package that grounded it. Pure logic, zero LLM, zero process spawn.
//
// P2b CURE (2026-09-11, benchmark §4a): the first shipped version was a superscar-#3
// guard-OVER-match — it killed three classes of VERIFIED-TRUE answer, costing 3 of 8 structured
// questions on floors (ii) and (iii). The three carve-outs below (α/β/γ) are the cure. Each is
// deliberately narrow, each preserves the guilt case it was written around, and each has a
// guilt AND an innocence corpus in `Tests/gatetest` — because a guard that only has guilt tests
// is how the over-match shipped in the first place.

enum KBLIGateRejection: Equatable {
    /// A 5-digit code was cited that is not in the package that grounded the answer.
    case unknownCode(String)
    /// A `%` figure appeared with no exactly-one-figure clause to bind it to (spelled-out number,
    /// orphan marker, a multi-figure "…respectively" clause, or a figure with no code to bind to
    /// anywhere in the answer so far).
    case unverifiablePercentClaim(String)
    /// A %-figure was bound to a code, but the number does not match that code's `pma_max_asing`
    /// in the package.
    case percentCodeMismatch(code: String, claimed: Double, actual: Int)
    /// A %-figure was paired to a code the package marked `pma_conflict: true` — the ownership
    /// axis on that code must never be answered, regardless of the claimed number.
    case conflictRecordPercentClaim(code: String)
}

enum KBLIGateOutcome: Equatable {
    case pass(String)
    case rejected(KBLIGateRejection)
}

/// Everything the gate needs to know about the package that grounded the answer being checked —
/// captured at `KBLIContextPackageBuilder.build(...)` time and carried alongside the prompt so
/// verification never has to re-derive it (and can never silently drift from what was actually
/// sent).
struct KBLIGateContext {
    let includedCodes: Set<String>
    let capsByCode: [String: Int]
    let conflictCodes: Set<String>
    /// Codes the QUESTION named which the catalogue provably does NOT contain (α, below). Derived
    /// from the question by `KBLIContextPackageBuilder.absentQuestionCodes(from:knownIn:)` — never
    /// from the answer, so a model-invented code can never enter this set and buy itself an
    /// exemption.
    let absentCodes: Set<String>
    /// The %-figures the QUESTION itself named (δ, below) — "klien mau pegang 51% saham". Echoing
    /// the user's own premise back is not a claim ABOUT a record, so it must not consume the
    /// one-figure-per-clause budget. Derived from the question only, for the same reason as
    /// `absentCodes`: a figure the model invents can never enter this set.
    let questionFigures: Set<Double>

    init(includedCodes: Set<String>, capsByCode: [String: Int], conflictCodes: Set<String>,
         absentCodes: Set<String> = [], questionFigures: Set<Double> = []) {
        self.includedCodes = includedCodes
        self.capsByCode = capsByCode
        self.conflictCodes = conflictCodes
        self.absentCodes = absentCodes
        self.questionFigures = questionFigures
    }
}

enum KBLIAnswerGate {
    private static let codeRegex = try! NSRegularExpression(pattern: "\\b\\d{5}\\b")

    /// Matches a NUMBER immediately (optionally separated by whitespace) followed by a percent
    /// marker: `%`, fullwidth `％`, Arabic `٪`, or the words `percent` / `per cent` / `persen`
    /// (case-insensitive). The number group is the MAXIMAL atomic run of digits with an optional
    /// single decimal separator (`.` or `,`) — greedy by construction, so "49,0%" / "49.0%" parse
    /// as the number 49.0 and can never be mis-read as a trailing "0%" (design §3, R5-4).
    private static let percentClaimRegex = try! NSRegularExpression(
        pattern: "(\\d+(?:[.,]\\d+)?)\\s*(%|％|٪|percent\\b|per\\s*cent\\b|persen\\b)",
        options: [.caseInsensitive])

    /// ANY occurrence of a percent marker (symbol or word), used to detect "orphan" markers that
    /// were NOT captured by `percentClaimRegex` — i.e. a marker with no adjacent number, which is
    /// exactly the shape of a spelled-out claim ("forty-nine percent", "empat puluh sembilan
    /// persen"). Rejecting every orphan marker as unverifiable is a deliberately conservative
    /// superset of a full EN/ID number-word parser: it never UNDER-rejects (design §3: spelled-out
    /// forms "are rejected as unverifiable rather than skipped").
    private static let anyMarkerRegex = try! NSRegularExpression(
        pattern: "%|％|٪|percent\\b|per\\s*cent\\b|persen\\b", options: [.caseInsensitive])

    /// α — the absence lexicon. A code the question named and the catalogue does not contain may
    /// be CITED only inside a clause that explicitly states an absence. Kept to unambiguous
    /// negation/absence stems in ID and EN: every entry here must be a word that cannot appear in
    /// an affirmative factual claim about the code. (Deliberately NOT a general negation parser —
    /// a missing entry costs a false rejection, which is the safe direction; a loose entry would
    /// cost an under-match, which is not.)
    private static let absenceMarkers: [String] = [
        "tidak", "bukan", "belum", "tiada", "dihapus", "tidak terdaftar", "di luar",
        "does not", "do not", "doesn't", "not present", "not in", "not found", "not listed",
        "no data", "no record", "absent", "unavailable", "outside",
    ]

    /// Check a generated answer against the package that grounded it. NFKC-normalizes first
    /// (folds fullwidth `％` and similar compatibility variants into their canonical form before
    /// any parsing), then runs the code-citation check and the sentence-level %-pairing check.
    static func check(_ rawText: String, context: KBLIGateContext) -> KBLIGateOutcome {
        let text = rawText.precomposedStringWithCompatibilityMapping   // NFKC
        let clauses = sentences(of: text)

        // ── (a) every 5-digit code cited must be present in the package ────────────────────
        //
        // α CARVE-OUT (benchmark §4a, Q05 — 3/3 runs killed). Under the original rule it was
        // IMPOSSIBLE to correctly answer "68200 is not in the KBLI 2025 catalogue", because
        // saying so cites the code. A code is exempt only when BOTH hold: the question named it,
        // and the catalogue provably does not contain it (`absentCodes`), AND the clause citing
        // it states an absence. Everything a model invents on its own still fails closed here.
        for clause in clauses {
            for code in citedCodes(in: clause) {
                if context.includedCodes.contains(code) { continue }
                if context.absentCodes.contains(code), statesAbsence(clause) { continue }
                return .rejected(.unknownCode(code))
            }
        }

        // ── (b)/(c) clause-level % binding ─────────────────────────────────────────────────
        //
        // Still exactly ONE figure per clause: "…0% and 49%, respectively" remains unverifiable.
        // What changed is which CODES a figure may bind to:
        //   γ (Q13) — N codes in the clause, one figure: pass only if EVERY code carries the same
        //             verified cap equal to that figure. N == 1 is the original rule, unchanged.
        //   β (Q22) — ZERO codes in the clause: bind to the most recent verifiable code named in
        //             a PRECEDING clause of the same answer, so an exception sentence may repeat
        //             the cap it qualifies ("…may exceed 49% with ministerial approval").
        var carriedCode: String?
        for clause in clauses {
            let codes = citedCodes(in: clause)
            // The referent for a later code-less clause is this clause's last VERIFIABLE code.
            defer { if let last = codes.last(where: { context.capsByCode[$0] != nil }) { carriedCode = last } }

            let markers = anyMarkerRegex.numberOfMatches(in: clause, range: fullRange(clause))
            guard markers > 0 else { continue }   // no % claim in this clause at all

            let claims = percentClaims(in: clause)
            if claims.count != markers {
                // an orphan marker (spelled-out number, or a marker the numeric regex could not
                // bind to an adjacent digit run) — unverifiable by construction.
                return .rejected(.unverifiablePercentClaim(clause))
            }
            // δ (benchmark replay 2026-09-11, Q13 runs 1+3) — a clause may carry the user's OWN
            // figure alongside the verified cap that answers it: "quota massima 100%, quindi 51%
            // rientra nel limite". The 51 is the question's premise being echoed, not an
            // assertion about a record, so it does not consume the one-figure budget.
            //
            // The hole this must NOT open is "49222 mengizinkan 51%" — an assertion dressed as an
            // echo. So an echoed figure is discounted ONLY when a substantive figure remains in
            // the same clause to be verified; if every figure is an echo, they all stay in play
            // and are verified normally (that answer then rejects as a cap mismatch, as it must).
            var substantive = claims.filter { context.questionFigures.contains($0) == false }
            if substantive.isEmpty { substantive = claims }
            guard Set(substantive).count == 1 else {
                // two or more DISTINCT substantive figures in one clause — the pairing is
                // undefined regardless of how many codes are present ("…0% and 49%,
                // respectively" is exactly this shape).
                return .rejected(.unverifiablePercentClaim(clause))
            }
            let claimed = substantive[0]

            let bound: [String]
            if codes.isEmpty {
                if let carried = carriedCode {
                    bound = [carried]
                } else if let whole = uniformPackageCap(context) {
                    // A clause that speaks about the PACKAGE rather than about one record —
                    // "untuk lima KBLI yang tersedia, batasnya hingga 100%" (Q13 run 3, a correct
                    // answer the shipped gate killed). It is only verifiable when every record in
                    // the package agrees on the cap; a mixed package leaves the referent undefined
                    // and still rejects.
                    bound = [whole]
                } else {
                    // a figure with no code anywhere before it and no uniform package cap —
                    // nothing to verify against.
                    return .rejected(.unverifiablePercentClaim(clause))
                }
            } else {
                bound = codes
            }

            for code in bound {
                if context.conflictCodes.contains(code) {
                    return .rejected(.conflictRecordPercentClaim(code: code))
                }
                guard context.includedCodes.contains(code) else {
                    return .rejected(.unknownCode(code))
                }
                guard let actual = context.capsByCode[code] else {
                    return .rejected(.unverifiablePercentClaim(clause))
                }
                if claimed != Double(actual) {
                    return .rejected(.percentCodeMismatch(code: code, claimed: claimed, actual: actual))
                }
            }
        }

        return .pass(rawText)
    }

    // MARK: - helpers

    private static func fullRange(_ s: String) -> NSRange { NSRange(location: 0, length: (s as NSString).length) }

    /// Returns a representative code IFF every record in the package carries the same
    /// `pma_max_asing`, so a clause that quotes "the" cap without naming a record has exactly one
    /// thing it can mean. Nil on a mixed package (referent undefined → the clause rejects) and nil
    /// on an empty one.
    private static func uniformPackageCap(_ context: KBLIGateContext) -> String? {
        guard let first = context.capsByCode.first else { return nil }
        guard context.capsByCode.values.allSatisfy({ $0 == first.value }) else { return nil }
        guard context.conflictCodes.isDisjoint(with: context.capsByCode.keys) else { return nil }
        return first.key
    }

    /// δ helper: the %-figures a QUESTION names, for `KBLIGateContext.questionFigures`. Same
    /// grammar as the answer-side parser, so "51%" / "51 persen" / "51،0%" are read identically on
    /// both sides — an echo can only be recognised if it is parsed the same way it was written.
    static func figures(inQuestion text: String) -> Set<Double> {
        Set(percentClaims(in: text.precomposedStringWithCompatibilityMapping))
    }

    /// α predicate: does this clause explicitly state an absence? Case-insensitive substring over
    /// the absence lexicon — see `absenceMarkers` for why the list is intentionally short.
    private static func statesAbsence(_ clause: String) -> Bool {
        let lower = clause.lowercased()
        return absenceMarkers.contains { lower.contains($0) }
    }

    private static func citedCodes(in text: String) -> [String] {
        let ns = text as NSString
        return codeRegex.matches(in: text, range: NSRange(location: 0, length: ns.length))
            .map { ns.substring(with: $0.range) }
    }

    static func percentClaims(in text: String) -> [Double] {
        let ns = text as NSString
        var out: [Double] = []
        for m in percentClaimRegex.matches(in: text, range: NSRange(location: 0, length: ns.length)) {
            guard m.numberOfRanges >= 2 else { continue }
            let numStr = ns.substring(with: m.range(at: 1)).replacingOccurrences(of: ",", with: ".")
            if let v = Double(numStr) { out.append(v) }
        }
        return out
    }

    /// Splits on `.`, `!`, `?`, and newlines — a "clause" proxy for the design's sentence-level
    /// pairing rule. Deliberately simple and over-splitting is safe here: a real sentence broken
    /// into two clauses by this splitter still gets checked, just more strictly (one clause can
    /// no longer smuggle two codes past the other's figure).
    ///
    /// EXCEPT: a `.` flanked by a digit on both sides is a decimal separator, not a sentence
    /// boundary (measured bug: naive splitting cut "49.0%" into "49" and "0%", silently deleting
    /// the code+figure pairing in the SAME clause and mis-rejecting a correct claim as
    /// unverifiable — "49.0%" must parse identically to "49,0%", design §3 R5-4).
    private static func sentences(of text: String) -> [String] {
        var clauses: [String] = []
        var current = ""
        let chars = Array(text)
        for i in chars.indices {
            let c = chars[i]
            guard ".!?\n".contains(c) else { current.append(c); continue }
            let prevIsDigit = i > 0 && chars[i - 1].isNumber
            let nextIsDigit = i + 1 < chars.count && chars[i + 1].isNumber
            if c == "." && prevIsDigit && nextIsDigit {
                current.append(c)   // decimal point inside a number — not a boundary
                continue
            }
            if current.isEmpty == false { clauses.append(current) }
            current = ""
        }
        if current.isEmpty == false { clauses.append(current) }
        return clauses
    }
}
