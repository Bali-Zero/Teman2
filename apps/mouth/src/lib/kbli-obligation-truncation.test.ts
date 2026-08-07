/**
 * A client must never read a cut-off legal duty as though it were complete.
 *
 * Guilt cases are the VERBATIM strings measured in the live stores on
 * 2026-08-05 — not invented examples. Innocence cases are the `"...; dan"`
 * enumeration items that Indonesian legal drafting produces on purpose (149 in
 * canonical): flagging one of those puts a false warning on correct data,
 * which is this defect with the sign reversed.
 */

import { describe, expect, it } from "vitest";

import {
  describeObligation,
  isSourceTruncated,
  TRUNCATION_HINT,
  TRUNCATION_NOTE,
} from "./kbli-obligation-truncation";

describe("isSourceTruncated — guilt, on strings the graph actually serves", () => {
  it("flags the string that sits on 35 codes, the widest-blast one", () => {
    expect(
      isSourceTruncated(
        "Memiliki bukti penyampaian wajib Data Industri tervalidasi setiap 6 (enam) bulan sekali sesuai peraturan perundang-undangan di bidang perindustrian dan",
      ),
    ).toBe(true);
  });

  it("flags the fisheries duty that names the report but not what is reported", () => {
    // "Report caught fish and ..." — trimming `dan` would understate the duty.
    expect(isSourceTruncated("Melaporkan ikan hasil tangkapan dan")).toBe(true);
  });

  it("flags a fragment that begins mid-sentence with a full stop", () => {
    expect(isSourceTruncated(". Produk yang")).toBe(true);
  });

  it("flags a duty cut off on a bare preposition", () => {
    expect(
      isSourceTruncated(
        "Melaksanakan ketentuan dalam peraturan perundang-undangan di",
      ),
    ).toBe(true);
  });

  it("flags a duty cut off on a bare relative pronoun", () => {
    expect(isSourceTruncated("Menerapkan teknik budi daya yang")).toBe(true);
  });

  it("is case-insensitive and tolerant of trailing whitespace", () => {
    expect(isSourceTruncated("Laporan kegiatan usaha (LKU) DAN  ")).toBe(true);
  });
});

describe("isSourceTruncated — innocence, the cases that must stay unmarked", () => {
  it("does NOT flag an enumerated list item ending '; dan'", () => {
    // 149 of these exist in canonical. They are item N of `a. ...; b. ...; dan`
    expect(
      isSourceTruncated(
        "Memberikan kemudahan bagi petugas baik pusat maupun daerah pada saat melakukan pengawasan, pembinaan dan evaluasi; dan",
      ),
    ).toBe(false);
  });

  it("does NOT flag a list item that also contains 'yang' mid-sentence", () => {
    // The list-style test must win over the dangling test, not merely coexist.
    expect(
      isSourceTruncated(
        "Membayar pendapatan negara atas komoditas yang ditambang; dan",
      ),
    ).toBe(false);
  });

  it("does NOT flag a complete duty that merely CONTAINS the trigger words", () => {
    expect(
      isSourceTruncated(
        "Menerapkan sistem jaminan mutu dan keamanan hasil perikanan di seluruh rantai produksi",
      ),
    ).toBe(false);
  });

  it("does NOT flag a word that merely ENDS in the trigger letters", () => {
    // Word-boundary, not substring — cicatrix family #3. Measured: a substring
    // implementation would falsely flag 17 distinct COMPLETE duties.
    expect(isSourceTruncated("Menjaga kelestarian badan")).toBe(false);
  });

  it("does NOT flag the Hajj duties that genuinely end in 'Arab Saudi'", () => {
    // The sharpest real case, and it is on 79122 — the Umrah/Hajj code. A
    // substring match on `di` would tell those clients that a COMPLETE legal
    // duty is cut off. Both strings verbatim from canonical.
    expect(
      isSourceTruncated(
        "Memberangkatkan dan memulangkan Jemaah Umroh sesuai dengan masa berlaku visa umroh di Arab Saudi",
      ),
    ).toBe(false);
    expect(
      isSourceTruncated(
        "Melaporkan jumlah jemaah haji khusus yang akan dibadalhajikan sebelum pelaksanaan wukuf kepada petugas penyelenggaraan ibadah haji di Arab Saudi",
      ),
    ).toBe(false);
  });

  it("DECLARED LIMIT — a word cut in half is invisible to a conjunction test", () => {
    // These two ARE truncated ("periodi[k]", "pedoman budi [daya]") and this
    // detector does not catch them: it finds sentences cut at a word boundary,
    // never a word cut through the middle. Catching those needs a lexicon, not
    // a regex. Pinned so the gap is a known false-negative rather than an
    // unexamined one — the fail-safe direction (a missing warning, never a
    // false one). Both strings verbatim from canonical.
    expect(
      isSourceTruncated(
        "Memiliki dokumen hasil kalibrasi peralatan quality control secara periodik atau hasil uji laboratorium independen atas produk yang dihasilkan secara periodi",
      ),
    ).toBe(false);
    expect(isSourceTruncated("Melakukan budi daya sesuai pedoman budi")).toBe(
      false,
    );
  });

  it("does NOT flag a duty ending in a preposition we measured at zero", () => {
    // `untuk`/`serta`/`dari` matched 0 strings in both stores, so they are not
    // guarded; a duty ending in one of them must not be silently marked.
    expect(isSourceTruncated("Menyediakan fasilitas untuk")).toBe(false);
  });

  it("treats empty and missing input as not-truncated, never as a warning", () => {
    expect(isSourceTruncated("")).toBe(false);
    expect(isSourceTruncated("   ")).toBe(false);
    expect(isSourceTruncated(null)).toBe(false);
    expect(isSourceTruncated(undefined)).toBe(false);
  });
});

describe("describeObligation", () => {
  it("returns the source text UNALTERED — the dangling word is never trimmed", () => {
    const raw = "Melaporkan ikan hasil tangkapan dan";
    const out = describeObligation(raw);
    expect(out.text).toBe(raw);
    expect(out.text.endsWith("dan")).toBe(true);
    expect(out.truncated).toBe(true);
  });

  it("passes a complete duty through unflagged", () => {
    const raw = "Memiliki Nomor Induk Berusaha (NIB)";
    expect(describeObligation(raw)).toEqual({ text: raw, truncated: false });
  });

  it("trims surrounding whitespace without touching the sentence", () => {
    expect(describeObligation("  Laporan kegiatan usaha (LKU) dan  ")).toEqual({
      text: "Laporan kegiatan usaha (LKU) dan",
      truncated: true,
    });
  });

  it("survives a null obligation without throwing", () => {
    expect(describeObligation(null)).toEqual({ text: "", truncated: false });
  });
});

describe("the copy shown to a client", () => {
  it("names the source as the thing that is incomplete, not our data", () => {
    expect(TRUNCATION_NOTE).toContain("source");
  });

  it("tells the reader what to DO — a warning they cannot act on is noise", () => {
    expect(TRUNCATION_HINT).toMatch(/oss\.go\.id|Bali Zero/);
  });
});
