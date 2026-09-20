// The inspector's copy line is the one string on this surface that TRAVELS:
// it is pasted into a client's email or chat, where nothing around it travels
// with it. Both fixtures below are the payloads the PRODUCTION inspect
// endpoint returned on 2026-09-20 (`inspect_kbli`), trimmed to the fields the
// line reads — not invented shapes.

import { describe, expect, it } from "vitest";
import type { KBLIDetail } from "@/lib/api/kbli.api";
import {
  buildInspectorCopyLine,
  getPmaBadge,
  getRiskBadge,
} from "./KBLIInspector";
import { summariseLicences } from "@/lib/kbli-licence-summary";

const retired = {
  pma_status: "NOT_VERIFIED",
  pma_max_asing: null,
  pma_verification_status: "declared_gap",
  pma_official_basis: null,
  pma_source_vintage: null,
  pma_cap_special: false,
  pma_cap_verified: false,
  code: "74100",
  title: "KBLI 74100 [KBLI 2020 — tidak ada dalam KBLI 2025]",
  description: "This code is not in the KBLI 2025 catalogue.",
  licensing_status: "NOT_IN_KBLI_2025",
  sector: "N/A",
  risk_profile: "Not applicable — code absent from KBLI 2025",
  licenses: [],
  related_requirements: {},
  related_codes: [],
} as unknown as KBLIDetail;

const live = {
  pma_status: "TERBUKA",
  pma_max_asing: 100,
  pma_verification_status: "located",
  pma_official_basis: "Perpres 10/2021 Pasal 3(1)(d) + 3(2)",
  pma_source_vintage: "2021-05-25",
  pma_cap_special: false,
  pma_cap_verified: true,
  code: "56101",
  title: "RESTAURANT (AKTIVITAS PENYEDIAAN MAKANAN DI BANGUNAN TETAP)",
  description: "Restaurant services in a permanent building.",
  licensing_status: "REGULATED",
  sector: "I.J-P",
  risk_profile: "Menengah Tinggi",
  licenses: [
    {
      type: "Restaurant License",
      scale: ["All"],
      risk_level: "Menengah Tinggi",
      sla: "N/A",
      requirements: [],
    },
    {
      type: "Sertifikat Standar",
      scale: ["All"],
      risk_level: "Menengah Tinggi",
      sla: "N/A",
      requirements: [],
    },
  ],
  related_requirements: {},
  related_codes: [],
} as unknown as KBLIDetail;

describe("buildInspectorCopyLine — a retired code travels as retired", () => {
  it("drops every segment that declines to answer and names the retirement", () => {
    const line = buildInspectorCopyLine(retired);

    expect(line).not.toContain("PMA:");
    expect(line).not.toContain("Risk:");
    expect(line).not.toContain("Licenses:");
    expect(line).not.toContain("Sector:");
    expect(line).not.toContain("[KBLI 2020");
    expect(line).not.toContain("Not listed in our data");
    // The code appears ONCE, not twice as it did when the title was pasted in.
    expect(line.match(/74100/g)).toHaveLength(1);
    expect(line).toContain("retired");
    expect(line).toContain("cannot be registered on OSS");
  });

  it("reads the structured status, never the title suffix (cicatrix #3)", () => {
    // A LIVE record whose title merely quotes the suffix must keep the normal
    // line: the verdict lives in `licensing_status`, and this is the mutation
    // a substring guard would fail.
    const impostor = {
      ...live,
      title: `${live.title} [KBLI 2020 — tidak ada dalam KBLI 2025]`,
    } as KBLIDetail;

    const line = buildInspectorCopyLine(impostor);
    expect(line).toContain("PMA:");
    expect(line).toContain("Risk:");
    expect(line).not.toContain("retired: this is a KBLI 2020 code");
  });
});

describe("innocence — a live code's line is byte-identical to the pre-cure one", () => {
  it("56101 keeps all five segments in the same order", () => {
    // The oracle is the expression this cure replaced, kept here deliberately:
    // it is what "unchanged" MEANS for the 1,555 codes that are not retired.
    const licList = summariseLicences(
      live.licenses.map((l) => l.type),
      live.licensing_status,
    );
    const legacy = `KBLI ${live.code} — ${live.title} | PMA: ${getPmaBadge(live).label} | Risk: ${getRiskBadge(live.risk_profile).label} | Licenses: ${licList} | Sector: ${live.sector}`;

    expect(buildInspectorCopyLine(live)).toBe(legacy);
  });
});
