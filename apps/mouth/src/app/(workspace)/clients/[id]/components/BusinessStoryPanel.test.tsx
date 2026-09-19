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

// Same shape as the pilot's real two-company dataset (a longer alias that
// CONTAINS a shorter one — "the alias list is itself the tell", per the R1
// audit §5.3): authored for a substring matcher, now read by an exact one
// after entity-level normalization. Persons/dossiers/stories are emptied so
// only the company path can produce a match.
const entityVarianceMap: TaxCompanyPilotMap = {
  ...giuliaMap,
  key: "entity-variance",
  company: {
    name: "Alpha Beta PT",
    aliases: ["PT Alpha B Group", "PT Alpha B"],
  },
  persons: [],
  person_dossiers: [],
  evidence_stories: [],
};

describe("BusinessStoryPanel", () => {
  it("renders the closed 'Case notes' section with the header subtitle, a one-paragraph summary, and no readiness percentage", () => {
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
    expect(
      screen.getByText("Person -> company -> tax -> documents -> next step"),
    ).toBeInTheDocument();
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
    expect(screen.queryByText("%", { exact: false })).not.toBeInTheDocument();
  });

  it("GUILT: opening the section shows the full per-company detail — company, relationship, backend readiness score as a plain number, tax owner, evidence link, and next actions — without attaching an unrelated map", async () => {
    const user = userEvent.setup();
    render(
      <BusinessStoryPanel
        clientName="Giulia Del Giudice"
        companyNames={["Bimala Investments Bali PT"]}
        maps={[giuliaMap, unrelatedMap]}
        isLoading={false}
        error={null}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Open" }));

    expect(
      screen.getByText("BIMALA / Bimala Investments Bali PT"),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("OCEAN CLOTHES AND SHOES PT"),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Giulia Del Giudice")).toBeInTheDocument();
    expect(screen.getByText("Tax owner: Dewa Ayu")).toBeInTheDocument();
    expect(screen.getByText("Needs a check")).toBeInTheDocument();
    // The backend's real readiness.score (76) renders as a plain number —
    // never with a "%" character, which would overstate it as measured.
    expect(screen.getByText("76")).toBeInTheDocument();
    expect(screen.queryByText(/76%/)).not.toBeInTheDocument();
    const section = screen.getByText("Case notes").closest("section");
    expect(section?.textContent).not.toMatch(/%/);
    expect(screen.getByText("LKPM Q1 2026")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /open lkpm q1 2026 evidence/i }),
    ).toHaveAttribute("href", "https://drive.google.com/drive/folders/lkpm");
    expect(
      screen.getAllByText(
        "Confirm current company tax standing before the next LKPM cycle.",
      ),
    ).toHaveLength(3);
    expect(
      screen.getByText(
        "Team can open Drive here. Clients only see approved downloads in the portal.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("What to do next")).toBeInTheDocument();
    expect(screen.getByText("tax")).toBeInTheDocument();
    expect(
      screen.getByText("Needed before the recap can be treated as current."),
    ).toBeInTheDocument();
    expect(screen.getByText("Reviewed Workspace AI")).toBeInTheDocument();
    expect(
      screen.getByText("Active PT PMA company profile confirmed."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Tax and LKPM files are present."),
    ).toBeInTheDocument();
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

  it("GUILT: legal-form spelling variance in the CRM's company_name still matches the pilot entity (R1 audit §5.3)", () => {
    // Each of these used to match only under the old bidirectional
    // SUBSTRING rule; a bare `===` after case-fold/whitespace-collapse (the
    // rejected PR's fix) drops every one of them. Entity-level
    // normalization — strip punctuation, parentheses, and legal-form
    // tokens as whole words — restores the match without reopening the
    // substring hole.
    const variants = [
      "Alpha Beta", // no PT token at all
      "PT Alpha Beta", // PT leading instead of trailing
      "Alpha Beta PT PMA", // extra legal-form token
      "PT. Alpha B", // punctuation after PT, matches an alias
      "Alpha Beta PT (Bali)", // parenthetical qualifier
      "Alpha B", // alias minus its PT token
    ];

    for (const companyName of variants) {
      const { unmount } = render(
        <BusinessStoryPanel
          clientName="Nobody Relevant"
          companyNames={[companyName]}
          maps={[entityVarianceMap]}
          isLoading={false}
          error={null}
        />,
      );
      expect(
        screen.getByRole("button", { name: "Open" }),
        `expected "${companyName}" to match the pilot entity`,
      ).toBeInTheDocument();
      unmount();
    }
  });

  it("INNOCENCE: 'PT Alpha' does not match 'PT Alpha Beta Indonesia' even after legal-form stripping", () => {
    const map: TaxCompanyPilotMap = {
      ...giuliaMap,
      key: "alpha-indonesia",
      company: { name: "PT Alpha Beta Indonesia", aliases: [] },
      persons: [],
      person_dossiers: [],
      evidence_stories: [],
    };
    render(
      <BusinessStoryPanel
        clientName="Nobody Relevant"
        companyNames={["PT Alpha"]}
        maps={[map]}
        isLoading={false}
        error={null}
      />,
    );
    expect(
      screen.getByText(
        "This person has a company, but the CRM has not read the documents yet.",
      ),
    ).toBeInTheDocument();
  });

  it("INNOCENCE: an empty string after stripping punctuation and legal-form tokens never matches anything", () => {
    const map: TaxCompanyPilotMap = {
      ...giuliaMap,
      key: "legal-form-only",
      company: { name: "PT PMA", aliases: [] },
      persons: [],
      person_dossiers: [],
      evidence_stories: [],
    };
    render(
      <BusinessStoryPanel
        clientName="Nobody Relevant"
        companyNames={["PT."]}
        maps={[map]}
        isLoading={false}
        error={null}
      />,
    );
    expect(
      screen.getByText(
        "This person has a company, but the CRM has not read the documents yet.",
      ),
    ).toBeInTheDocument();
  });

  it("INNOCENCE: a person name that merely contains another does not match (no substring rule on the person path)", () => {
    const map: TaxCompanyPilotMap = {
      ...giuliaMap,
      key: "person-substring",
      persons: [
        {
          name: "Jo Anne Somebody",
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
    render(
      <BusinessStoryPanel
        clientName="Jo Anne"
        companyNames={[]}
        maps={[map]}
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

  it("toggles aria-expanded and the Open/Close label on click, and aria-controls never dangles", async () => {
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
    const controlsId = toggle.getAttribute("aria-controls");
    expect(controlsId).toBeTruthy();
    // GUILT: on the pre-fix markup the id only existed on the open branch,
    // so this lookup returned null while the section was closed.
    expect(document.getElementById(controlsId as string)).toBeInTheDocument();

    await user.click(toggle);
    expect(screen.getByRole("button", { name: "Close" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    expect(document.getElementById(controlsId as string)).toBeInTheDocument();
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

    expect(screen.getByText("No company linked yet")).toBeInTheDocument();
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

  it("renders the error state with the restored heading", () => {
    render(
      <BusinessStoryPanel
        clientName="Giulia Del Giudice"
        companyNames={[]}
        maps={[]}
        isLoading={false}
        error={new Error("evidence layer down")}
      />,
    );

    expect(screen.getByText("Business story unavailable")).toBeInTheDocument();
    expect(
      screen.getByText(
        "The client profile is available, but the evidence layer did not load.",
      ),
    ).toBeInTheDocument();
  });
});
