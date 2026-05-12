import { render, screen } from "@testing-library/react";
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
    reasons: ["Confirm current company tax standing before the next LKPM cycle."],
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

describe("BusinessStoryPanel", () => {
  it("renders a person-first business story with team Drive evidence and portal boundary", () => {
    render(
      <BusinessStoryPanel
        clientName="Giulia Del Giudice"
        companyNames={["Bimala Investments Bali PT"]}
        maps={[giuliaMap, unrelatedMap]}
        isLoading={false}
        error={null}
      />,
    );

    expect(screen.getByText("Client Story")).toBeInTheDocument();
    expect(
      screen.getByText("Person -> company -> tax -> documents -> next step"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("BIMALA / Bimala Investments Bali PT"),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("OCEAN CLOTHES AND SHOES PT"),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Giulia Del Giudice")).toBeInTheDocument();
    expect(screen.getByText("Tax owner: Dewa Ayu")).toBeInTheDocument();
    expect(screen.getByText("Needs a check")).toBeInTheDocument();
    expect(screen.getByText("76%")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Start from Giulia, then follow the Bimala company record, LKPM documents, and tax owner.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("LKPM Q1 2026")).toBeInTheDocument();
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
    expect(
      screen.getByRole("link", { name: /open lkpm q1 2026 evidence/i }),
    ).toHaveAttribute("href", "https://drive.google.com/drive/folders/lkpm");
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
      screen.getByText("No company linked yet"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Connect this person to a company, then the CRM can build the tax story.",
      ),
    ).toBeInTheDocument();
  });
});
