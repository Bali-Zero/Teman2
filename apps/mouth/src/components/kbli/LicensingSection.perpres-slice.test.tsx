// Perpres slice-disclosure frame — 10 general BROADER-adjudicated codes (12
// BROADER-adjudicated minus 20235/30303, excluded as adjacent-not-contained
// — see ADJACENT_NOT_CONTAINED in perpres_slice_disclosure_relation.py) plus
// 30111's two hand-authored rows and 30113's one render "100% open" correctly
// for the WHOLE code while a narrower bidang usaha inside them carries a
// Perpres 10/2021 (as amended by 49/2021) Lampiran III foreign-cap condition.
// A real render, using REAL codes from the live artifact via kbli-data.ts
// (not synthetic overrides) — the strongest available proof the disclosure
// actually reaches the rendered DOM.

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { getCode } from "@/lib/kbli-data";
import { LicensingSection } from "./LicensingSection";

describe("LicensingSection perpres slice-disclosure frame", () => {
  it("13133 (batik cap, cap 0) renders the domestic-capital sentence with the annex's own bidang usaha text", () => {
    const kbli = getCode("13133");
    expect(kbli?.perpresSlice).toHaveLength(1);
    if (!kbli) throw new Error("13133 missing from kbli-data.ts");

    render(<LicensingSection kbli={kbli} gold={null} />);

    expect(
      screen.getByText(
        /One activity inside this code is foreign-capital restricted/,
      ),
    ).toBeInTheDocument();
    expect(screen.getByText(/Industri batik cap/)).toBeInTheDocument();
    expect(
      screen.getByText(
        /is reserved for domestic capital under Perpres 10\/2021/,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Everything else in this code is open as shown/),
    ).toBeInTheDocument();
  });

  it("26513 (radar, cap 49) renders the 49% sentence and its condition", () => {
    const kbli = getCode("26513");
    expect(kbli?.perpresSlice).toHaveLength(1);
    expect(kbli?.perpresSlice?.[0].condition).toBe(
      "may exceed 49% with Menteri Pertahanan approval",
    );
    if (!kbli) throw new Error("26513 missing from kbli-data.ts");

    render(<LicensingSection kbli={kbli} gold={null} />);

    expect(
      screen.getByText(
        /is capped at 49% foreign ownership under Perpres 10\/2021/,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/may exceed 49% with Menteri Pertahanan approval/),
    ).toBeInTheDocument();
  });

  it("30111 renders BOTH rows (warship 49% + Pinisi/Cadik 0%) as separate paragraphs", () => {
    const kbli = getCode("30111");
    expect(kbli?.perpresSlice).toHaveLength(2);
    if (!kbli) throw new Error("30111 missing from kbli-data.ts");

    render(<LicensingSection kbli={kbli} gold={null} />);

    expect(screen.getByText(/Industri kapal perang/)).toBeInTheDocument();
    expect(screen.getByText(/Pinisi, Cadik/)).toBeInTheDocument();
    // Both a 0% and a 49% sentence must be present on the page.
    expect(
      screen.getByText(
        /is reserved for domestic capital under Perpres 10\/2021/,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /is capped at 49% foreign ownership under Perpres 10\/2021/,
      ),
    ).toBeInTheDocument();
  });

  it("30111 renders the 'everything else is open' closer exactly ONCE, not once per row", () => {
    // The Pinisi/Cadik row (0%, no condition) is NOT open — a per-row
    // "the rest is open" sentence repeated after the warship row would be
    // false. One shared closer after every row has had its say.
    const kbli = getCode("30111");
    if (!kbli) throw new Error("30111 missing from kbli-data.ts");

    render(<LicensingSection kbli={kbli} gold={null} />);

    expect(
      screen.getAllByText(/Everything else in this code is open as shown/),
    ).toHaveLength(1);
  });

  it("58130 (press, cap 0 WITH a phased condition) renders the condition, never the absolute closure sentence", () => {
    // guilt: a condition-bearing cap-0 row must NOT get the unqualified
    // "no foreign equity in that slice" claim — false for the expansion
    // phase (0% at establishment; 49% via capital market for expansion).
    const kbli = getCode("58130");
    expect(kbli?.perpresSlice).toHaveLength(1);
    expect(kbli?.perpresSlice?.[0].foreignCapPct).toBe(0);
    expect(kbli?.perpresSlice?.[0].condition).toBe(
      "0% at establishment; 49% via capital market for expansion",
    );
    if (!kbli) throw new Error("58130 missing from kbli-data.ts");

    render(<LicensingSection kbli={kbli} gold={null} />);

    expect(
      screen.getByText(
        /is reserved for domestic capital at establishment under Perpres 10\/2021 \(as amended\) — 0% at establishment; 49% via capital market for expansion\./,
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText(/no foreign equity in that slice/)).toBeNull();
  });

  it("innocence: 13133 (cap 0, condition null) still renders the absolute closure sentence", () => {
    const kbli = getCode("13133");
    expect(kbli?.perpresSlice?.[0].condition).toBeNull();
    if (!kbli) throw new Error("13133 missing from kbli-data.ts");

    render(<LicensingSection kbli={kbli} gold={null} />);

    expect(
      screen.getByText(/no foreign equity in that slice/),
    ).toBeInTheDocument();
  });

  it("innocence: a non-affected code (56101) renders no slice-disclosure frame", () => {
    const kbli = getCode("56101");
    expect(kbli?.perpresSlice).toBeUndefined();
    if (!kbli) throw new Error("56101 missing from kbli-data.ts");

    render(<LicensingSection kbli={kbli} gold={null} />);

    expect(screen.queryByText(/foreign-capital restricted/)).toBeNull();
    expect(
      screen.queryByText(/is reserved for domestic capital under Perpres/),
    ).toBeNull();
    expect(
      screen.queryByText(/is capped at 49% foreign ownership under Perpres/),
    ).toBeNull();
  });

  it("innocence: the frame is independent of the Bali-block frame — a non-Bali-blocked code still renders it", () => {
    // 13133 carries no baliL4 block; proves the frame's own condition does
    // not silently require baliBlocked to be true or false in a way that
    // would hide it on a normal open code.
    const kbli = getCode("13133");
    if (!kbli) throw new Error("13133 missing from kbli-data.ts");
    expect(kbli.baliL4?.blocked).toBeFalsy();

    render(<LicensingSection kbli={kbli} gold={null} />);

    expect(
      screen.getByText(
        /One activity inside this code is foreign-capital restricted/,
      ),
    ).toBeInTheDocument();
  });
});
