import Foundation

/// Builds the local "FONTI" (sources) block that gets injected into Zantara's prompt, so the
/// answer is grounded on the real KBLI dataset — NLM-style: the bot answers only from these,
/// never invents a code or a Bali status (the system-prompt enforces the rest).
struct Grounding {
    let store: KBLIStore

    /// Compose the prompt sent to OpenClaw: a FONTI block (retrieved locally) + the user question.
    func prompt(userMessage: String, focusCode: KBLI?) -> String {
        let sources = self.sources(forQuery: userMessage, code: focusCode)
        return """
        FONTI (rispondi SOLO da queste; cita il codice; se non c'è, dillo — non inventare):
        \(sources)

        DOMANDA: \(userMessage)
        """
    }

    /// Retrieve the relevant KBLI records (the focus code if any, plus top search hits) and
    /// render them as a compact, citable sources block.
    func sources(forQuery query: String, code: KBLI?) -> String {
        var picked: [KBLI] = []
        if let c = code { picked.append(c) }
        for k in store.search(query).rows.prefix(4) where picked.contains(where: { $0.kode == k.kode }) == false {
            picked.append(k)
        }
        if picked.isEmpty { return "(nessuna fonte KBLI trovata per questa query)" }
        return picked.prefix(5).map(Self.render).joined(separator: "\n\n")
    }

    /// One KBLI record as a sources entry.
    private static func render(_ k: KBLI) -> String {
        var lines = ["KBLI \(k.kode) — \(k.judul)"]
        if let pma = k.pmaStatus, pma.isEmpty == false { lines.append("PMA nazionale: \(pma)") }
        if let l4 = k.l4Bali {
            lines.append("Stato Bali: \(l4.status)\(l4.blocked ? " (BLOCCATO)" : "")")
            if let r = l4.reason, r.isEmpty == false { lines.append("Motivo: \(r)") }
            if let m = l4.moratorium, let eff = m.effective {
                lines.append("Moratoria: eff. \(eff)\(m.source.map { " — \($0)" } ?? "")")
            }
        }
        if k.uraian.isEmpty == false {
            let u = k.uraian.replacingOccurrences(of: "\n", with: " ")
            lines.append("Descrizione: \(u.prefix(300))")
        }
        return lines.joined(separator: "\n")
    }
}
