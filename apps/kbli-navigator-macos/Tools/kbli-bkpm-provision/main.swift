import Foundation
import CryptoKit

// kbli-bkpm-provision — the BKPM enablement marker ISSUER.
//
// It is a separate program, built separately, and it is NOT part of any app bundle. That is the
// whole point of it existing: a check that grants itself does not check anything. The app holds
// only the PUBLIC key and can therefore verify a marker but never mint one; the private key
// lives on the operator's disk at 0600 and never enters this repository.
//
//   keygen <private-key-path>          create an issuer keypair; writes the private key 0600 and
//                                      prints ONLY the public key (base64) on stdout
//   machine-id                          print this machine's stable identifier (the value a
//                                      marker is bound to)
//   issue <private-key-path> <out.json> [--machine-id <id>]
//                                      sign a marker for this machine (or for the id given)
//
// The marker deliberately carries NO expiry: expiry was ruled out of scope for this increment
// and is recorded as a declared gap rather than invented here.

func eprint(_ s: String) { FileHandle.standardError.write((s + "\n").data(using: .utf8)!) }
func fail(_ s: String) -> Never { eprint("FATAL: \(s)"); exit(1) }

/// The machine identity a marker is bound to: a hash of the host UUID, never the UUID itself, so
/// a marker file lying around discloses nothing about the machine it was cut for.
func machineID() -> String {
    var uuid = [UInt8](repeating: 0, count: 16)
    var ts = timespec(tv_sec: 0, tv_nsec: 0)
    guard gethostuuid(&uuid, &ts) == 0 else { fail("gethostuuid failed") }
    let digest = SHA256.hash(data: Data(uuid))
    return digest.map { String(format: "%02x", $0) }.joined()
}

func canonicalPayload(machineID: String, issuedAt: String) -> Data {
    // Sorted keys, no whitespace: the signer and the verifier must agree byte-for-byte, and a
    // dictionary's iteration order is not a contract.
    let obj: [String: String] = ["machine_id": machineID, "issued_at": issuedAt, "scope": "bkpm-chat"]
    return try! JSONSerialization.data(withJSONObject: obj, options: [.sortedKeys])
}

let args = CommandLine.arguments
guard args.count >= 2 else {
    eprint("usage: kbli-bkpm-provision keygen <private-key-path>")
    eprint("       kbli-bkpm-provision machine-id")
    eprint("       kbli-bkpm-provision issue <private-key-path> <out.json> [--machine-id <id>]")
    exit(2)
}

switch args[1] {
case "keygen":
    guard args.count >= 3 else { fail("keygen requires <private-key-path>") }
    let path = args[2]
    if FileManager.default.fileExists(atPath: path) {
        fail("refusing to overwrite an existing issuer key at \(path)")
    }
    let key = Curve25519.Signing.PrivateKey()
    let dir = (path as NSString).deletingLastPathComponent
    try? FileManager.default.createDirectory(atPath: dir, withIntermediateDirectories: true)
    let raw = key.rawRepresentation
    guard FileManager.default.createFile(atPath: path, contents: raw,
                                         attributes: [.posixPermissions: 0o600]) else {
        fail("cannot write the issuer key")
    }
    // stdout carries the PUBLIC key only. The private key never leaves the file above.
    print(key.publicKey.rawRepresentation.base64EncodedString())

case "machine-id":
    print(machineID())

case "issue":
    guard args.count >= 4 else { fail("issue requires <private-key-path> <out.json>") }
    var target = machineID()
    var i = 4
    while i < args.count {
        if args[i] == "--machine-id", i + 1 < args.count { target = args[i + 1]; i += 1 }
        else { fail("unknown argument: \(args[i])") }
        i += 1
    }
    guard let raw = FileManager.default.contents(atPath: args[2]),
          let key = try? Curve25519.Signing.PrivateKey(rawRepresentation: raw) else {
        fail("cannot read an issuer key at \(args[2])")
    }
    let fmt = ISO8601DateFormatter()
    fmt.formatOptions = [.withInternetDateTime]
    let issuedAt = fmt.string(from: Date())
    let payload = canonicalPayload(machineID: target, issuedAt: issuedAt)
    guard let sig = try? key.signature(for: payload) else { fail("signing failed") }
    let marker: [String: Any] = [
        "machine_id": target,
        "issued_at": issuedAt,
        "scope": "bkpm-chat",
        "signature": sig.base64EncodedString(),
    ]
    let data = try! JSONSerialization.data(withJSONObject: marker, options: [.sortedKeys, .prettyPrinted])
    let dir = (args[3] as NSString).deletingLastPathComponent
    try? FileManager.default.createDirectory(atPath: dir, withIntermediateDirectories: true)
    guard FileManager.default.createFile(atPath: args[3], contents: data,
                                         attributes: [.posixPermissions: 0o600]) else {
        fail("cannot write the marker")
    }
    eprint("issued a bkpm-chat marker for machine \(target.prefix(12))… → \(args[3])")

default:
    fail("unknown subcommand: \(args[1])")
}
