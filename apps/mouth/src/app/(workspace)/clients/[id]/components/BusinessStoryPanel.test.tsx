import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { BusinessStoryPanel } from "./BusinessStoryPanel";
import type { TaxCompanyPilotMap } from "@/lib/api/crm/crm.types";

const giuliaMap: TaxCompanyPilotMap = {
  key: "bimala",
  primary_entry: "person",
  workspace_mode: "team_read_only",
  company: {
    name: "BIMALA / Bimala Investments Bali PT",
    aliases: ["Bimala Investments Bali PT"],
  },
  tax_member: {
    name: "Dewa Ayu",
    workspace_branch: "TAX DEPARTMENT/Members/Dewa Ayu",
    source_folder_url: "https://drive.google.com/drive/folders/dewa",
  },
  drive_folders: {
    operational: "https://drive.google.com/drive/folders/bimala",
  },
  persons: [
    {
      name: "Giulia Del Giudice",
      folder_url: "https://drive.google.com/drive/folders/giulia",
      evidence: ["ITAS E28A Investor"],
      role: "Shareholder",
      role_confidence: "confirmed",
      relationship_confidence: "confirmed",
    },
    {
      name: "Giorgia Emidio",
      folder_url: null,
      evidence: ["Child evisa file"],
      role: null,
      role_confidence: "unconfirmed",
      relationship_confidence: "unconfirmed",
    },
  ],
  documents: [
    {
      name: "LKPM Q1 2026",
      group: "lkpm",
      evidence_url: "https://drive.google.com/drive/folders/lkpm",
      sensitivity: "company",
      confidence: "confirmed",
    },
  ],
  person_dossiers: [
    {
      person_name: "Giulia Del Giudice",
      company_name: "BIMALA / Bimala Investments Bali PT",
      headline:
        "Giulia Del Giudice is the person entry point for Bimala Investments Bali PT.",
      tax_owner: "Dewa Ayu",
      drive_folder_url: "https://drive.google.com/drive/folders/giulia",
      document_groups: ["Investment reports", "Company registry"],
      risk_flags: [],
      next_action:
        "Confirm current company tax standing before the next LKPM cycle.",
      relationship_confidence: "confirmed",
    },
  ],
  evidence_stories: [
    {
      person_name: "Giulia Del Giudice",
      company_name: "BIMALA / Bimala Investments Bali PT",
      tax_owner: "Dewa Ayu",
      recap:
        "Start from Giulia, then follow the Bimala company record, LKPM evidence, and tax owner.",
      relationship_path: [
        "Giulia Del Giudice",
        "BIMALA / Bimala Investments Bali PT",
        "Tax: Dewa Ayu",
      ],
      evidence_items: [
        {
          label: "Document",
          detail: "LKPM Q1 2026 is classified as lkpm.",
          source_label: "LKPM Q1 2026",
          source_url: "https://drive.google.com/drive/folders/lkpm",
          source_kind: "folder",
          audience: "team",
          confidence: "confirmed",
        },
      ],
      next_action:
        "Confirm current company tax standing before the next LKPM cycle.",
      portal_rule: "Client portal: download approved documents only.",
      team_rule: "Team workspace: open Drive evidence and shortcuts from kita.",
      confidence: "confirmed",
    },
  ],
  next_best_actions: [
    {
      owner: "tax",
      label: "Confirm current company tax standing before the next LKPM cycle.",
      reason: "Needed before the recap can be treated as current.",
      severity: "medium",
    },
  ],
  readiness: {
    status: "needs_review",
    score: 76,
    label: "Needs review",
    reasons: [
      "Confirm current company tax standing before the next LKPM cycle.",
    ],
  },
  business_story: [
    "Bimala is visible through a person-first path, not a company-only archive.",
  ],
  duplicate_candidates: [],
  gaps: [],
  evidence_links: [
    {
      label: "Bimala working folder",
      url: "https://drive.google.com/drive/folders/bimala",
      kind: "folder",
    },
  ],
  ai_recap: ["Bimala has LKPM and company evidence."],
  workspace_ai: {
    provider: "notebooklm",
    notebook_id: "notebook_bimala",
    note_id: "note_bimala",
    source_file_ids: ["drive_profile"],
    facts: [
      {
        category: "identity",
        label: "Company profile",
        detail: "Active PT PMA company profile confirmed.",
        source_file_ids: ["drive_profile"],
        confidence: "confirmed",
      },
      {
        category: "compliance",
        label: "Tax trail",
        detail: "Tax and LKPM files are present.",
        source_file_ids: ["drive_profile"],
        confidence: "confirmed",
      },
    ],
    approved_by: "team@balizero.com",
    approved_at: "2026-05-12T15:50:00Z",
    created_at: "2026-05-12T15:45:00Z",
  },
  read_only: true,
  confidence: "confirmed",
};

const unrelatedMap: TaxCompanyPilotMap = {
  ...giuliaMap,
  key: "ocean",
  company: {
    name: "OCEAN CLOTHES AND SHOES PT",
    aliases: ["PT Ocean"],
  },
  persons: [
    {
      name: "Natan Kleimonov",
      folder_url: null,
      evidence: ["Passport"],
      role: null,
      role_confidence: "medium",
      relationship_confidence: "medium",
    },
  ],
  person_dossiers: [],
  evidence_stories: [],
};

// Same company family as `giuliaMap`, but a DIFFERENT company: "PT Synthetic
// Alpha Beta" merely CONTAINS "PT Synthetic Alpha" as a substring. The old
// bidirectional substring match attached this map's story to a client whose
// only company link is "PT Synthetic Alpha" (portal audit wrong-client risk).
const alphaBetaMap: TaxCompanyPilotMap = {
  ...giuliaMap,
  key: "alpha-beta",
  company: {
    name: "PT Synthetic Alpha Beta",
    aliases: [],
  },
  persons: [
    {
      name: "Synthetic Beta Person",
      folder_url: null,
      evidence: [],
      role: null,
      role_confidence: "unconfirmed",
      relationship_confidence: "unconfirmed",
    },
  ],
  person_dossiers: [],
  evidence_stories: [],
};

// The exact same company as `alphaBetaMap`'s target, spelled with different
// case and doubled internal whitespace — must still match after
// normalization (trim + case-fold + whitespace collapse).
const alphaMap: TaxCompanyPilotMap = {
  ...giuliaMap,
  key: "alpha",
  company: {
    name: "pt   synthetic alpha",
    aliases: [],
  },
  persons: [
    {
      name: "Synthetic Alpha Person",
      folder_url: null,
      evidence: [],
      role: null,
      role_confidence: "unconfirmed",
      relationship_confidence: "unconfirmed",
    },
  ],
  person_dossiers: [],
  evidence_stories: [],
};

describe("BusinessStoryPanel", () => {
  it("renders the closed 'Case notes' section with a one-paragraph summary and no readiness percentage", () => {
    render(
      <BusinessStoryPanel
        clientName="Giulia Del Giudice"
        companyNames={["Bimala Investments Bali PT"]}
        maps={[giuliaMap, unrelatedMap]}
        isLoading={false}
        error={null}
      />,
    );

    expect(screen.getByText("Case notes")).toBeInTheDocument();
    const toggle = screen.getByRole("button", { name: "Open" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(
      screen.getByText(
        "Start from Giulia, then follow the Bimala company record, LKPM documents, and tax owner.",
      ),
    ).toBeInTheDocument();
    // Closed state shows only the summary paragraph — the fuller per-company
    // detail (and its evidence links) is not in the DOM yet.
    expect(
      screen.queryByText("BIMALA / Bimala Investments Bali PT"),
    ).not.toBeInTheDocument();
  });

  it("GUILT: opening the section never renders a readiness percentage, even for a map whose fixture used to show one", async () => {
    const user = userEvent.setup();
    render(
      <BusinessStoryPanel
        clientName="Giulia Del Giudice"
        companyNames={["Bimala Investments Bali PT"]}
        maps={[giuliaMap]}
        isLoading={false}
        error={null}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Open" }));

    expect(
      screen.getByText("BIMALA / Bimala Investments Bali PT"),
    ).toBeInTheDocument();
    expect(screen.getByText("Needs a check")).toBeInTheDocument();
    expect(screen.queryByText(/76%/)).not.toBeInTheDocument();
    expect(screen.queryByText("%", { exact: false })).not.toBeInTheDocument();
    const section = screen.getByText("Case notes").closest("section");
    expect(section?.textContent).not.toMatch(/%/);
  });

  it("GUILT: a story for 'PT Synthetic Alpha Beta' is NOT attached to a client whose company is 'PT Synthetic Alpha'", () => {
    render(
      <BusinessStoryPanel
        clientName="Someone Else"
        companyNames={["PT Synthetic Alpha"]}
        maps={[alphaBetaMap]}
        isLoading={false}
        error={null}
      />,
    );

    // No company matched → the empty-story state, not a case-notes summary.
    expect(
      screen.getByText(
        "This person has a company, but the CRM has not read the documents yet.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Open" }),
    ).not.toBeInTheDocument();
  });

  it("INNOCENCE: an exact company match survives case-folding and whitespace collapse", async () => {
    const user = userEvent.setup();
    render(
      <BusinessStoryPanel
        clientName="Someone Else"
        companyNames={["PT Synthetic Alpha"]}
        maps={[alphaMap]}
        isLoading={false}
        error={null}
      />,
    );

    const toggle = screen.getByRole("button", { name: "Open" });
    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    // Testing-library's default text matcher collapses whitespace itself,
    // so the fixture's doubled internal space reads back as single-spaced.
    expect(screen.getByText("pt synthetic alpha")).toBeInTheDocument();
  });

  it("toggles aria-expanded and the Open/Close label on click", async () => {
    const user = userEvent.setup();
    render(
      <BusinessStoryPanel
        clientName="Giulia Del Giudice"
        companyNames={["Bimala Investments Bali PT"]}
        maps={[giuliaMap]}
        isLoading={false}
        error={null}
      />,
    );

    const toggle = screen.getByRole("button", { name: "Open" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    await user.click(toggle);
    expect(screen.getByRole("button", { name: "Close" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
  });

  it("shows an operating gap when no company story is linked yet", () => {
    render(
      <BusinessStoryPanel
        clientName="Unlinked Person"
        companyNames={[]}
        maps={[]}
        isLoading={false}
        error={null}
      />,
    );

    expect(
      screen.getByText(
        "Connect this person to a company, then the CRM can build the tax story.",
      ),
    ).toBeInTheDocument();
  });

  it("renders the loading state without crashing", () => {
    render(
      <BusinessStoryPanel
        clientName="Giulia Del Giudice"
        companyNames={[]}
        maps={[]}
        isLoading={true}
        error={null}
      />,
    );

    expect(screen.getByText("Case notes")).toBeInTheDocument();
    expect(screen.getByText("Loading business story")).toBeInTheDocument();
  });
});
