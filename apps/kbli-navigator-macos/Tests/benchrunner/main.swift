import Foundation
import CryptoKit

// benchrunner — Tests/benchrunner/main.swift
//
// P2b benchmark harness for the KBLI Navigator Phase-2 codex chat brain (design doc
// research/operations/2026-08-19-kbli-navigator-phase2-codex-chat-design.md §8). Zero product
// changes: this file only ever CALLS the public/internal Sources/ API exactly the way
// Sources/Views/ChatView.swift's runTurn() does (see that function, ~L199-262) — nothing here
// is new production surface, and nothing under Sources/ is touched.
//
// Two subcommands:
//   run <corpus.json> <out.jsonl> [--runs N (default 3)] [--only Q1,Q2]
//   extract <answers.jsonl> <out.jsonl>
//
// Compile alongside the same Foundation-only, UI-free Sources/ set the existing
// packagetest/gatetest/codexrunnertest targets already compile: KBLIStore.swift, Models.swift,
// KBLIContextPackage.swift, KBLIAnswerGate.swift, KBLICodexRunner.swift.

// MARK: - Corpus / answer-file schemas

struct CorpusQuestion: Codable {
    let id: String
    let lang: String?
    let klass: String?
    let text: String
    enum CodingKeys: String, CodingKey {
        case id, lang, text
        case klass = "class"
    }
}

struct Corpus: Codable {
    let questions: [CorpusQuestion]
    // `meta` is deliberately NOT modeled — JSONDecoder ignores unrecognized top-level keys, and
    // the harness never needs anything from it.
}

struct AnswerLine: Codable {
    let qid: String
    let run: Int
    let raw_answer: String
}

// MARK: - Output line

struct GateTuple: Codable {
    let code: String
    let figure: Double
}

/// docs/gates/ROW-IDENTITY-CONTRACT.md §4 — what the builder served, by IDENTITY. `ordinal` is
/// the row's index in the record's canonical (physical) `per_skala` order; the array below is in
/// SERVED order, so the declaration names both the set and the order the model saw.
struct BenchServedRow: Codable {
    let ordinal: Int
    let skala_key: String
    // Required, non-optional: a Swift Optional that is nil would be OMITTED by the synthesized
    // encoder while Python writes an explicit null, and the scorer would have to guess which of
    // "the whole list" and "the runner forgot" it was looking at (contract §4).
    let persyaratan_served: Int
    let kewajiban_served: Int
}

struct BenchServedFields: Codable {
    let per_skala_rows_included: Int
    let per_skala_rows_total: Int
    let per_skala_rows_served: [BenchServedRow]
}

struct BenchLine: Codable {
    let qid: String
    let run: Int
    /// Contract §2 — the sha256 of the dataset this run READ. An ordinal is an index into a
    /// dataset, so without this stamp a record whose rows changed CONTENT but kept their length,
    /// order and skala_key would validate as EXACT on the scorer's side and the judge would be
    /// shown requirements the model never saw. The scorer drops the declaration of any row whose
    /// stamp is absent or is not the anchored value.
    let dataset_sha256: String?
    let lang: String?
    let klass: String?
    let package_codes: [String]?
    // What each served record actually carried. `package_codes` is code identity only, and the
    // scorer cannot tell a code served with its rows from one served as a bare anchor — so it
    // used to judge against the canonical rows for both (council round 4, codex-gpt-5.6-sol).
    let package_fields: [String: BenchServedFields]?
    let package_bytes: Int?
    let raw_answer: String?
    let gate_ok: Bool?
    let gate_reason: String?
    let tuples: [GateTuple]?
    let elapsed_s: Double?
    let error: String?
    /// Additive field, NOT in the original task spec's line shape — declared as a deviation in
    /// the implementation report. Distinguishes "the package never built" (narrowComparison /
    /// questionTooLong / schemaViolation — production never calls the runner in these cases, see
    /// ChatView.swift's switch over KBLIPackageOutcome) from "built, and the runner/gate ran".
    let package_outcome: String?

    enum CodingKeys: String, CodingKey {
        case qid, run, dataset_sha256, lang
        case klass = "class"
        case package_codes, package_fields, package_bytes, raw_answer, gate_ok, gate_reason, tuples, elapsed_s, error, package_outcome
    }
}

// MARK: - stderr helpers

func eprint(_ s: String) {
    FileHandle.standardError.write((s + "\n").data(using: .utf8)!)
}

func fail(_ s: String) -> Never {
    eprint("FATAL: \(s)")
    exit(1)
}

func writeLine<T: Encodable>(_ value: T, to handle: FileHandle, encoder: JSONEncoder) {
    guard let data = try? encoder.encode(value) else {
        eprint("WARN: failed to encode a JSONL line, skipping")
        return
    }
    handle.write(data)
    handle.write("\n".data(using: .utf8)!)
}

// MARK: - Dataset loading (KBLI_JSON env — same resolution as Tests/packagetest/main.swift)

/// Contract §2 — the sha256 of the dataset THIS process read, stamped on every answer row so the
/// scorer can refuse to read ordinals that index a different dataset. Computed once, from the
/// bytes actually loaded, never from a constant.
let datasetSHA256: String = {
    guard let path = ProcessInfo.processInfo.environment["KBLI_JSON"],
          let data = FileManager.default.contents(atPath: path) else { return "" }
    return SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
}()

func loadDataset() -> (KBLIStore, KBLIRawSchemaIndex) {
    guard let jsonPath = ProcessInfo.processInfo.environment["KBLI_JSON"] else {
        fail("set KBLI_JSON to the bundled dataset path (same convention as Tests/packagetest)")
    }
    guard let store = KBLIStore(jsonPath: jsonPath) else { fail("KBLIStore failed to load \(jsonPath)") }
    guard let schema = KBLIRawSchemaIndex(jsonPath: jsonPath) else { fail("KBLIRawSchemaIndex failed to load \(jsonPath)") }
    return (store, schema)
}

// MARK: - Gate verdict / rejection description

func gateVerdict(_ outcome: KBLIGateOutcome) -> (ok: Bool, reason: String?) {
    switch outcome {
    case .pass: return (true, nil)
    case .rejected(let r): return (false, describeRejection(r))
    }
}

func describeRejection(_ r: KBLIGateRejection) -> String {
    switch r {
    case .unknownCode(let c):
        return "unknownCode(\(c))"
    case .unverifiablePercentClaim(let clause):
        return "unverifiablePercentClaim(\(clause))"
    case .percentCodeMismatch(let code, let claimed, let actual):
        return "percentCodeMismatch(code:\(code),claimed:\(claimed),actual:\(actual))"
    case .conflictRecordPercentClaim(let code):
        return "conflictRecordPercentClaim(\(code))"
    }
}

func packageOutcomeTag(_ o: KBLIPackageOutcome) -> String {
    switch o {
    case .built: return "built"
    case .narrowComparison(let codes): return "narrowComparison:\(codes.joined(separator: ","))"
    case .questionTooLong(let n): return "questionTooLong:\(n)"
    case .schemaViolation(let s): return "schemaViolation:\(s)"
    }
}

// MARK: - Tuple extraction (harness-local, best-effort — logging field only)
//
// KBLIAnswerGate.check() (Sources/KBLIAnswerGate.swift) does NOT expose the code/percent tuples
// it parses internally — citedCodes/percentClaims/sentences are all `private`, and per the task
// spec Sources/ is not to be touched to expose them. This reimplements a best-effort version
// PURELY for the "tuples" logging field: it reuses the real production code-detection
// (KBLIContextPackageBuilder.extractCodes — internal, not private, already used by ChatView's
// history-anchor path) so a cited code only counts if it is a REAL known KBLI code, paired with a
// locally-reimplemented percent-number regex, one pairing per naive clause (split on '.!?\n' —
// NOT the gate's own decimal-aware splitter, so "49.0%" straddling a clause boundary can be
// missed here). This only affects the informational "tuples" field, never gate_ok/gate_reason,
// which come straight from the real KBLIAnswerGate.check() call.
let percentRegex = try! NSRegularExpression(
    pattern: "(\\d+(?:[.,]\\d+)?)\\s*(%|％|٪|percent\\b|per\\s*cent\\b|persen\\b)",
    options: [.caseInsensitive])

func extractTuples(from text: String, schema: KBLIRawSchemaIndex) -> [GateTuple] {
    var out: [GateTuple] = []
    let clauses = text.components(separatedBy: CharacterSet(charactersIn: ".!?\n"))
    for clause in clauses {
        guard clause.isEmpty == false else { continue }
        let codes = KBLIContextPackageBuilder.extractCodes(from: clause, knownIn: schema)
        guard codes.count == 1 else { continue }
        let ns = clause as NSString
        let matches = percentRegex.matches(in: clause, range: NSRange(location: 0, length: ns.length))
        guard matches.count == 1, let m = matches.first, m.numberOfRanges >= 2 else { continue }
        let numStr = ns.substring(with: m.range(at: 1)).replacingOccurrences(of: ",", with: ".")
        guard let v = Double(numStr) else { continue }
        out.append(GateTuple(code: codes[0], figure: v))
    }
    return out
}

// MARK: - run

func runRun(corpusPath: String, outPath: String, runs: Int, onlyIDs: Set<String>?) async {
    let (store, schema) = loadDataset()

    guard let corpusData = FileManager.default.contents(atPath: corpusPath) else {
        fail("cannot read corpus file at \(corpusPath)")
    }
    let corpus: Corpus
    do {
        corpus = try JSONDecoder().decode(Corpus.self, from: corpusData)
    } catch {
        fail("cannot parse corpus JSON at \(corpusPath): \(error)")
    }

    let questions: [CorpusQuestion]
    if let ids = onlyIDs {
        questions = corpus.questions.filter { ids.contains($0.id) }
    } else {
        questions = corpus.questions
    }
    if questions.isEmpty { fail("no questions to run (corpus empty, or --only matched nothing)") }

    FileManager.default.createFile(atPath: outPath, contents: nil)
    guard let outHandle = FileHandle(forWritingAtPath: outPath) else {
        fail("cannot open \(outPath) for writing")
    }
    defer { outHandle.closeFile() }
    let encoder = JSONEncoder()

    for q in questions {
        for runIdx in 1...runs {
            // (a) build the context package — NO current code card (cold chat), same call shape
            // as ChatView.swift's runTurn() (~L226-231), with currentCard: nil / history: []
            // per the harness spec (cold single-turn, no session history).
            // The builder DECLARES what it served (per_skala rows per code) instead of leaving
            // the scorer to assume the canonical slice — see KBLIContextPackageBuilder.FieldMap.
            let fieldMap = KBLIContextPackageBuilder.FieldMap()
            let outcome = KBLIContextPackageBuilder.build(
                question: q.text, currentCard: nil, history: [], store: store, schema: schema,
                fieldMap: fieldMap)
            let servedFields = fieldMap.perSkalaRowsByCode.reduce(into: [String: BenchServedFields]()) {
                let rows = (fieldMap.perSkalaRowsServedByCode[$1.key] ?? []).map {
                    BenchServedRow(ordinal: $0.ordinal, skala_key: $0.skalaKey,
                                   persyaratan_served: $0.persyaratanServed,
                                   kewajiban_served: $0.kewajibanServed)
                }
                $0[$1.key] = BenchServedFields(
                    per_skala_rows_included: $1.value,
                    per_skala_rows_total: fieldMap.perSkalaRowsTotalByCode[$1.key] ?? $1.value,
                    per_skala_rows_served: rows)
            }

            switch outcome {
            case .built(let prompt, let includedCodes, let capsByCode, let conflictCodes, let totalBytes):
                let start = Date()
                do {
                    // (b) invoke the runner exactly as production chat does — same type, same
                    // call, no argv/model override (KBLICodexRunner.buildArgv() pins the model).
                    let raw = try await KBLICodexRunner().run(prompt: prompt)
                    let elapsed = Date().timeIntervalSince(start)

                    // (c) apply the gate exactly as production does.
                    let ctx = KBLIGateContext(
                        includedCodes: includedCodes, capsByCode: capsByCode,
                        conflictCodes: conflictCodes,
                        absentCodes: KBLIContextPackageBuilder.absentQuestionCodes(from: q.text, knownIn: schema),
                        questionFigures: KBLIAnswerGate.figures(inQuestion: q.text))
                    let (ok, reason) = gateVerdict(KBLIAnswerGate.check(raw, context: ctx))
                    let tuples = extractTuples(from: raw, schema: schema)

                    let line = BenchLine(qid: q.id, run: runIdx, dataset_sha256: datasetSHA256, lang: q.lang, klass: q.klass,
                        package_codes: includedCodes.sorted(), package_fields: servedFields,
                        package_bytes: totalBytes,
                        raw_answer: raw, gate_ok: ok, gate_reason: reason, tuples: tuples,
                        elapsed_s: elapsed, error: nil, package_outcome: "built")
                    writeLine(line, to: outHandle, encoder: encoder)
                    eprint("[\(q.id) run \(runIdx)/\(runs)] ok \(String(format: "%.1f", elapsed))s")
                } catch {
                    // a runner error (auth death, timeout, ...) — record and CONTINUE, no retry.
                    let elapsed = Date().timeIntervalSince(start)
                    let msg = (error as? KBLICodexRunnerError)?.errorDescription ?? "\(error)"
                    let line = BenchLine(qid: q.id, run: runIdx, dataset_sha256: datasetSHA256, lang: q.lang, klass: q.klass,
                        package_codes: includedCodes.sorted(), package_fields: servedFields,
                        package_bytes: totalBytes,
                        raw_answer: nil, gate_ok: nil, gate_reason: nil, tuples: nil,
                        elapsed_s: elapsed, error: msg, package_outcome: "built")
                    writeLine(line, to: outHandle, encoder: encoder)
                    eprint("[\(q.id) run \(runIdx)/\(runs)] error \(msg)")
                }
            default:
                // production never calls the runner for a non-.built outcome (ChatView.swift's
                // switch shows a canned system message instead) — mirror that: no codex call.
                let tag = packageOutcomeTag(outcome)
                let line = BenchLine(qid: q.id, run: runIdx, dataset_sha256: datasetSHA256, lang: q.lang, klass: q.klass,
                    package_codes: [], package_fields: [:], package_bytes: nil,
                    raw_answer: nil, gate_ok: nil, gate_reason: nil, tuples: nil,
                    elapsed_s: nil, error: nil, package_outcome: tag)
                writeLine(line, to: outHandle, encoder: encoder)
                eprint("[\(q.id) run \(runIdx)/\(runs)] package-not-built (\(tag))")
            }
        }
    }
}

// MARK: - extract

/// Builds a "ground truth" gate context spanning every code CITED in an old-brain answer, by
/// reusing the real production builder (KBLIContextPackageBuilder.build) as an oracle: feeding
/// it batches of ≤maxExplicitCodes known codes as an explicit-code question reproduces the SAME
/// capsByCode/conflictCodes derivation ChatView's live package-scoped context would — with zero
/// reimplementation of the private per-record cap/conflict derivation logic inside
/// KBLIContextPackageBuilder.build(...) itself.
func buildGroundTruthContext(codes: [String], store: KBLIStore, schema: KBLIRawSchemaIndex) -> (KBLIGateContext, [String]) {
    var included = Set<String>()
    var caps: [String: Int] = [:]
    var conflicts = Set<String>()
    var anomalies: [String] = []
    var i = 0
    while i < codes.count {
        let chunk = Array(codes[i..<min(i + KBLIContextPackageBuilder.maxExplicitCodes, codes.count)])
        i += KBLIContextPackageBuilder.maxExplicitCodes
        let outcome = KBLIContextPackageBuilder.build(
            question: chunk.joined(separator: " "), currentCard: nil, history: [], store: store, schema: schema)
        if case .built(_, let inc, let cap, let conf, _) = outcome {
            included.formUnion(inc)
            for (k, v) in cap { caps[k] = v }
            conflicts.formUnion(conf)
        } else {
            anomalies.append(chunk.joined(separator: ","))
        }
    }
    return (KBLIGateContext(includedCodes: included, capsByCode: caps, conflictCodes: conflicts), anomalies)
}

func runExtract(answersPath: String, outPath: String) async {
    let (store, schema) = loadDataset()

    guard let data = FileManager.default.contents(atPath: answersPath),
          let text = String(data: data, encoding: .utf8) else {
        fail("cannot read answers file at \(answersPath)")
    }

    FileManager.default.createFile(atPath: outPath, contents: nil)
    guard let outHandle = FileHandle(forWritingAtPath: outPath) else {
        fail("cannot open \(outPath) for writing")
    }
    defer { outHandle.closeFile() }
    let encoder = JSONEncoder()
    let decoder = JSONDecoder()

    var n = 0
    for rawLine in text.split(separator: "\n", omittingEmptySubsequences: true) {
        guard let lineData = String(rawLine).data(using: .utf8) else { continue }
        let answer: AnswerLine
        do {
            answer = try decoder.decode(AnswerLine.self, from: lineData)
        } catch {
            eprint("WARN: skipping unparseable answers.jsonl line: \(error)")
            continue
        }
        n += 1

        // codes ACTUALLY cited in the answer, filtered to known real KBLI codes by the same
        // production extractor ChatView's history-anchor path uses.
        let citedKnown = KBLIContextPackageBuilder.extractCodes(from: answer.raw_answer, knownIn: schema)
        let (ctx, anomalies) = buildGroundTruthContext(codes: citedKnown, store: store, schema: schema)
        let (ok, reason) = gateVerdict(KBLIAnswerGate.check(answer.raw_answer, context: ctx))
        let tuples = extractTuples(from: answer.raw_answer, schema: schema)

        let line = BenchLine(qid: answer.qid, run: answer.run, dataset_sha256: nil, lang: nil, klass: nil,
            package_codes: nil, package_fields: nil, package_bytes: nil,
            raw_answer: answer.raw_answer, gate_ok: ok, gate_reason: reason, tuples: tuples,
            elapsed_s: nil,
            error: anomalies.isEmpty ? nil : "ground-truth-context-build-anomaly:\(anomalies.joined(separator: ";"))",
            package_outcome: nil)
        writeLine(line, to: outHandle, encoder: encoder)
        eprint("[\(answer.qid) run \(answer.run)] extracted (gate_ok=\(ok))")
    }
    if n == 0 { eprint("WARN: 0 lines extracted from \(answersPath)") }
}

// MARK: - entry point

func mainAsync() async {
    let arguments = CommandLine.arguments
    guard arguments.count >= 2 else {
        eprint("usage: benchrunner run <corpus.json> <out.jsonl> [--runs N] [--only Q1,Q2]")
        eprint("       benchrunner extract <answers.jsonl> <out.jsonl>")
        exit(2)
    }
    switch arguments[1] {
    case "run":
        guard arguments.count >= 4 else { fail("run requires <corpus.json> <out.jsonl>") }
        var runs = 3
        var onlyIDs: Set<String>? = nil
        var i = 4
        while i < arguments.count {
            switch arguments[i] {
            case "--runs":
                i += 1
                guard i < arguments.count, let n = Int(arguments[i]), n >= 1 else { fail("--runs requires a positive integer") }
                runs = n
            case "--only":
                i += 1
                guard i < arguments.count else { fail("--only requires a comma list") }
                onlyIDs = Set(arguments[i].split(separator: ",").map { $0.trimmingCharacters(in: .whitespaces) })
            default:
                fail("unknown argument: \(arguments[i])")
            }
            i += 1
        }
        await runRun(corpusPath: arguments[2], outPath: arguments[3], runs: runs, onlyIDs: onlyIDs)
    case "extract":
        guard arguments.count >= 4 else { fail("extract requires <answers.jsonl> <out.jsonl>") }
        await runExtract(answersPath: arguments[2], outPath: arguments[3])
    default:
        fail("unknown subcommand: \(arguments[1]) (want run|extract)")
    }
}

await mainAsync()
