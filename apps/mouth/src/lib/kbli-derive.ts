/**
 * kbli-derive.ts — shared derivation helpers that bring the web card to parity with the native
 * KBLI Navigator app (Swift), 2026-06-28.
 *
 * Two PP 28/2025-grounded derivations the raw dataset does NOT carry directly, ported verbatim
 * from the Swift app so the web shows the same correct values:
 *
 *  1. licenseForRisk — when a scale's `perizinan` (licenseType) is empty (true on the ~1338
 *     array-form records where the legacy scalar was never filled), DERIVE the license from the
 *     risk tier. PP 28/2025 Pasal 124(4): "Tingkat Risiko menentukan jenis Perizinan Berusaha".
 *     The web previously fell back to a flat "NIB", which UNDERSTATED the requirement on the 937
 *     high-risk codes (Tinggi needs NIB + Izin, not bare NIB). Mirrors
 *     KBLIRegistryView.licenseForRisk.
 *
 *  2. formatTimeframe — render the jangka_waktu cleanly: "Otomatis" → "Instant", a bare day count
 *     ("3", "14") → "3 working days", an already-unit'd "5 Hari" → "5 working days" (strip the
 *     double unit), and the special-regime labels we just added ("Sesuai tahapan IUP (ESDM)",
 *     "Sesuai ketentuan OJK/BI") pass through verbatim. Mirrors PP28ScalePanel.formatJangkaWaktu.
 *
 * Keep these pure and dependency-free — both kbli-data.ts (client) and kbli-data.server.ts import
 * them, so the derivation lives in ONE place (the Swift bug was that each render site re-derived
 * differently; here we derive once in the transformer).
 */

/** License type derived from the risk tier when the explicit `perizinan` is empty (Pasal 124(4)). */
export function licenseForRisk(risk: string | null | undefined): string {
  const r = (risk || "").trim();
  // Tinggi → NIB + Izin (a verified permit on top of NIB). Menengah Tinggi / Menengah Rendah →
  // NIB + Sertifikat Standar. Rendah → NIB alone (instant). Unknown → NIB (safe minimum).
  if (r === "Tinggi") return "NIB + Izin";
  if (r === "Menengah Tinggi" || r === "Menengah Rendah")
    return "NIB + Sertifikat Standar";
  if (r === "Rendah") return "NIB";
  return "NIB";
}

/**
 * Resolve the license type for a scale: the explicit value if present, else derived from risk.
 *
 * IMPORTANT: in the real dataset `perizinan` is an ARRAY on ~99.5% of scales (the legacy
 * `string` type in kbli-types was a lie — it is a `string[]`, frequently empty `[]`), and a
 * bare `string` on the ~20 legacy records. Handle BOTH: join the distinct non-empty array
 * entries; fall back to the scalar; and when nothing is explicit (empty array / empty string),
 * derive from the risk tier. Mirrors the Swift app's permitText (scalar → array → derive).
 */
export function resolveLicenseType(
  perizinan: string | string[] | null | undefined,
  risk: string | null | undefined,
): string {
  if (Array.isArray(perizinan)) {
    const distinct = Array.from(
      new Set(perizinan.map((x) => (x || "").trim()).filter(Boolean)),
    );
    if (distinct.length > 0) return distinct.join(" · ");
    return licenseForRisk(risk);
  }
  const p = (perizinan || "").trim();
  if (p) return p;
  return licenseForRisk(risk);
}

const _BARE_DAYS = /^(\d{1,3})$/;
const _N_HARI = /^(\d{1,3})\s*[Hh]ari(?:\s*[Kk]erja)?$/;

/**
 * Format a raw jangka_waktu for display. Returns null when there is genuinely nothing to show
 * (empty / lone dash) — callers decide the placeholder. Never invents a value.
 */
export function formatTimeframe(raw: string | null | undefined): string | null {
  const s = (raw || "").trim();
  if (!s || s === "-" || s === "—") return null;
  if (s.toLowerCase() === "otomatis") return "Instant";
  const bare = _BARE_DAYS.exec(s);
  if (bare) return `${bare[1]} working days`;
  const hari = _N_HARI.exec(s);
  if (hari) return `${hari[1]} working days`;
  // special-regime labels ("Sesuai tahapan IUP (ESDM)", "Sesuai ketentuan OJK/BI") and any other
  // descriptive value pass through verbatim — they are already human-readable.
  return s;
}

/**
 * English label for a raw kategori_risiko value ("Tinggi", "Menengah Rendah",
 * ...). Same semantics as RiskBadge's parseRisk — check the compound
 * "menengah" forms BEFORE the bare ones. Returns null for unknown values:
 * a surface omitting the risk is honest, a surface inventing one is not.
 */
export function riskLabelEn(category?: string | null): string | null {
  if (!category) return null;
  const lower = category.toLowerCase();
  const menengah = lower.includes("menengah");
  if (menengah && lower.includes("tinggi")) return "Medium-High";
  if (menengah && lower.includes("rendah")) return "Medium-Low";
  if (lower.includes("tinggi")) return "High";
  if (lower.includes("rendah")) return "Low";
  return null;
}
