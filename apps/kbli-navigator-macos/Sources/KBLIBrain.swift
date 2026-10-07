import Foundation
import CryptoKit

// KBLIBrain.swift — the migration seam (design §4). ChatView asks ONE place "can I call a brain
// right now, and how" instead of branching on seat/variant logic inline.

/// Build-time constant flipping the chat flow between the new codex-backed brain and the legacy
/// OpenClaw runner. `OpenClawRunner.swift` stays COMPILED (design §4: "a dead dual path is
/// W84-class drift waiting to happen" — so it is made unreachable, not deleted) until the §8
/// benchmark gate passes and P2c deletes the legacy path for real. The criterion this window is
/// held to is UNREACHABILITY, not absence: the built bundle carries OpenClaw symbols next to the
/// codex runner's and that is correct — "no OpenClaw symbol" would be unsatisfiable by
/// construction and would push someone to delete a path to make a number green.
let useLegacyOpenClawBrain = false

/// BKPM enablement marker — the validator ONLY.
///
/// Until 2026-09-13 this was `static func isValid() -> Bool { false }`: fail-closed, correct as a
/// placeholder, and it meant the BKPM chat was off by construction on every machine including
/// ours. What replaces it keeps the fail-closed default and adds the one thing that makes a check
/// meaningful — an ISSUER THAT IS NOT THIS PROGRAM. The app embeds a public key and can verify a
/// marker; it holds no private key and therefore cannot mint one. The issuer is a separate
/// binary, `Tools/kbli-bkpm-provision`, built separately and never bundled; its private key lives
/// on the operator's disk at 0600 and is not in this repository.
///
/// The marker is bound to a stable machine identifier (a SHA-256 of the host UUID, so the file
/// discloses nothing about the machine), and a marker cut for another machine fails.
///
/// DECLARED GAP — EXPIRY. The marker carries `issued_at` and this validator does NOT check an
/// expiry, because a validity window is a business decision this window was told not to invent.
/// A marker is therefore valid until the issuer key is rotated. Recorded as a gap, not as a
/// feature.
enum KBLIBKPMMarker {
    /// The issuer's PUBLIC key (Ed25519, base64). Rotating the issuer key changes this literal —
    /// which is the intended cost: re-issuing markers is a deliberate act, not a silent one.
    static let issuerPublicKeyBase64 = "/ky2728qUPuJcgczqTncWsK0t3Adp3lrbQXH0JQGO7A="

    /// Where a marker is looked for. `KBLI_BKPM_MARKER_PATH` overrides it so the negative cases
    /// can actually be exercised by a test instead of being asserted in a comment.
    static var markerPath: String {
        if let override = ProcessInfo.processInfo.environment["KBLI_BKPM_MARKER_PATH"] {
            return override
        }
        return NSHomeDirectory() + "/Library/Application Support/KBLINavigator/bkpm-marker.json"
    }

    /// This machine's stable identity. Never the raw host UUID — a hash of it.
    static func currentMachineID() -> String? {
        var uuid = [UInt8](repeating: 0, count: 16)
        var ts = timespec(tv_sec: 0, tv_nsec: 0)
        guard gethostuuid(&uuid, &ts) == 0 else { return nil }
        return SHA256.hash(data: Data(uuid)).map { String(format: "%02x", $0) }.joined()
    }

    /// The exact bytes the issuer signed. Sorted keys, no whitespace — the signer and the
    /// verifier must agree byte-for-byte, and dictionary order is not a contract.
    private static func canonicalPayload(machineID: String, issuedAt: String) -> Data? {
        let obj: [String: String] = ["machine_id": machineID, "issued_at": issuedAt, "scope": "bkpm-chat"]
        return try? JSONSerialization.data(withJSONObject: obj, options: [.sortedKeys])
    }

    static func isValid() -> Bool {
        isValid(markerPath: markerPath, machineID: currentMachineID())
    }

    /// Fail-closed at every step: no file, unreadable file, malformed JSON, missing field, wrong
    /// machine, wrong scope, bad signature, or an unknown machine identity all return `false`.
    static func isValid(markerPath: String, machineID: String?) -> Bool {
        guard let machineID, machineID.isEmpty == false else { return false }
        guard let data = FileManager.default.contents(atPath: markerPath) else { return false }
        guard let obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else { return false }
        guard let claimedMachine = obj["machine_id"] as? String,
              let issuedAt = obj["issued_at"] as? String,
              let scope = obj["scope"] as? String,
              let sigB64 = obj["signature"] as? String else { return false }
        guard scope == "bkpm-chat" else { return false }
        guard claimedMachine == machineID else { return false }
        guard let sig = Data(base64Encoded: sigB64),
              let pubRaw = Data(base64Encoded: issuerPublicKeyBase64),
              let pub = try? Curve25519.Signing.PublicKey(rawRepresentation: pubRaw),
              let payload = canonicalPayload(machineID: claimedMachine, issuedAt: issuedAt) else { return false }
        return pub.isValidSignature(sig, for: payload)
    }
}

enum KBLIBrainAvailability: Equatable {
    case ready
    /// `reason` is an internal diagnostic tag ONLY — never shown to the user directly. The UI
    /// always renders the same fixed, host/vendor-free offline message (design §4) regardless of
    /// which reason fired; the tag exists for QA/debugging, not for display.
    case offline(reason: String)
}

enum KBLIBrain {
    /// design §4: BKPM is checked FIRST and is a hard gate, never OR'd with the seat probe — a
    /// valid seat must never substitute for a missing/wrong-machine marker.
    static func availability() -> KBLIBrainAvailability {
        availability(variant: AppVariant.current,
                     markerValid: KBLIBKPMMarker.isValid())
    }

    /// Injectable form — `AppVariant.current` reads `Bundle.main`, which a headless test binary
    /// cannot set, so the negatives required by the acceptance would otherwise be unexercisable.
    /// The seat probes below are the REAL ones: a test that stubbed them would prove nothing
    /// about the rule that matters here (marker first, seat never a substitute).
    static func availability(variant: AppVariant, markerValid: Bool) -> KBLIBrainAvailability {
        if variant == .bkpm {
            guard markerValid else { return .offline(reason: "bkpm-no-marker") }
        }
        guard let identity = KBLICodexAvailability.resolveIdentity() else {
            return .offline(reason: "codex-not-found")
        }
        guard KBLICodexAvailability.versionMatches(identity) else {
            return .offline(reason: "codex-version-mismatch")
        }
        guard KBLICodexAvailability.authFilePresent() else {
            return .offline(reason: "codex-not-logged-in")
        }
        return .ready
    }
}
