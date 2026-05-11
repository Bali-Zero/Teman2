import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TaxCompanyPilotWorkspace } from "./TaxCompanyPilotWorkspace";
import type { TaxCompanyPilotMap } from "@/lib/api/crm/crm.types";

const oceanMap: TaxCompanyPilotMap = {
  key: "ocean",
  primary_entry: "person",
  workspace_mode: "team_read_only",
  company: {
    name: "OCEAN CLOTHES AND SHOES PT",
    aliases: ["PT Ocean Clothes and Shoes"],
  },
  tax_member: {
    name: "DEA",
    workspace_branch: "TAX DEPARTMENT/Members/Dea",
    source_folder_url: "https://drive.google.com/drive/folders/dea",
  },
  drive_folders: {
    operational: "https://drive.google.com/drive/folders/ocean",
  },
  persons: [
    {
      name: "Natan Kleimonov",
      folder_url: "https://drive.google.com/drive/folders/natan",
      evidence: ["Passport"],
      role: null,
      role_confidence: "unconfirmed",
      relationship_confidence: "medium",
    },
  ],
  documents: [
    {
      name: "SPT 2025",
      group: "tax",
      evidence_url: "https://drive.google.com/drive/folders/tax",
      sensitivity: "company",
      confidence: "confirmed",
    },
  ],
  person_dossiers: [
    {
      person_name: "Natan Kleimonov",
      company_name: "OCEAN CLOTHES AND SHOES PT",
      headline: "Person to verify before opening OCEAN CLOTHES AND SHOES PT",
      tax_owner: "DEA",
      drive_folder_url: "https://drive.google.com/drive/folders/natan",
      document_groups: ["tax filings"],
      risk_flags: ["Company role needs human confirmation."],
      next_action: "Confirm the company role from registry documents.",
      relationship_confidence: "medium",
    },
  ],
  next_best_actions: [
    {
      owner: "setup",
      label: "Confirm company roles from company PDFs.",
      reason:
        "Needed before OCEAN CLOTHES AND SHOES PT can become a clean person-first workspace.",
      severity: "high",
    },
  ],
  business_story: [
    "Start from Natan Kleimonov, then open OCEAN CLOTHES AND SHOES PT only through the confirmed relationship.",
  ],
  duplicate_candidates: [
    {
      label: "Operational tax folder vs canonical-like company folder",
      urls: ["https://drive.google.com/drive/folders/ocean"],
      confidence: "medium",
    },
  ],
  gaps: [
    {
      code: "confirm_company_roles",
      label: "Confirm company roles from company PDFs.",
      severity: "high",
    },
  ],
  evidence_links: [
    {
      label: "Operational folder",
      url: "https://drive.google.com/drive/folders/ocean",
      kind: "folder",
    },
  ],
  ai_recap: ["Ocean has a DEA tax working folder."],
  read_only: true,
  confidence: "medium",
};

const bimalaMap: TaxCompanyPilotMap = {
  ...oceanMap,
  key: "bimala",
  company: {
    name: "BIMALA / Bimala Investments Bali PT",
    aliases: ["Bimala Investments Bali PT"],
  },
  tax_member: {
    name: "Dewa Ayu",
    workspace_branch: "TAX DEPARTMENT/Members/Dewa Ayu",
    source_folder_url: "https://drive.google.com/drive/folders/dewa",
  },
  persons: [
    {
      name: "Giulia Del Giudice",
      folder_url: "https://drive.google.com/drive/folders/giulia",
      evidence: ["ITAS E28A Investor"],
      role: null,
      role_confidence: "unconfirmed",
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
      name: "LKPM Periode 4 PDFs",
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
        "Confirmed person connected to BIMALA / Bimala Investments Bali PT",
      tax_owner: "Dewa Ayu",
      drive_folder_url: "https://drive.google.com/drive/folders/giulia",
      document_groups: ["investment reports"],
      risk_flags: ["Company role needs human confirmation."],
      next_action: "Confirm the company role from registry documents.",
      relationship_confidence: "confirmed",
    },
    {
      person_name: "Giorgia Emidio",
      company_name: "BIMALA / Bimala Investments Bali PT",
      headline:
        "Person to verify before opening BIMALA / Bimala Investments Bali PT",
      tax_owner: "Dewa Ayu",
      drive_folder_url: null,
      document_groups: ["investment reports"],
      risk_flags: ["Relationship needs human confirmation."],
      next_action:
        "Confirm the family or business relationship before nesting files.",
      relationship_confidence: "unconfirmed",
    },
  ],
  next_best_actions: [
    {
      owner: "tax",
      label: "Confirm child/person relationships before nesting child files.",
      reason:
        "Needed before BIMALA / Bimala Investments Bali PT can become a clean person-first workspace.",
      severity: "high",
    },
  ],
  business_story: [
    "Start from Giulia Del Giudice, then open BIMALA only through the confirmed relationship.",
  ],
  duplicate_candidates: [
    {
      label: "Bimala CRM company folder vs tax member working folder",
      urls: ["https://drive.google.com/drive/folders/bimala"],
      confidence: "medium",
    },
  ],
  gaps: [
    {
      code: "confirm_family_relationships",
      label: "Confirm child/person relationships before nesting child files.",
      severity: "high",
    },
  ],
  evidence_links: [
    {
      label: "Operational folder",
      url: "https://drive.google.com/drive/folders/bimala",
      kind: "folder",
    },
  ],
  ai_recap: ["Bimala is represented through Dewa Ayu's working folder."],
};

describe("TaxCompanyPilotWorkspace", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders company maps as business dossiers instead of technical audit panels", () => {
    render(<TaxCompanyPilotWorkspace maps={[oceanMap, bimalaMap]} />);

    expect(
      screen.getByText("Person-first intelligence desk"),
    ).toBeInTheDocument();
    expect(screen.getByText("Companies under review")).toBeInTheDocument();
    expect(screen.getAllByText("Open decisions")).toHaveLength(3);
    expect(screen.getAllByText("Tax owner")).toHaveLength(2);
    expect(screen.getAllByText("Person entry")).toHaveLength(2);
    expect(screen.getAllByText("Business story")).toHaveLength(2);
    expect(screen.getAllByText("Evidence story layer")).toHaveLength(2);
    expect(
      screen.getAllByText("Client portal: download approved documents only."),
    ).toHaveLength(2);
    expect(
      screen.getAllByText(
        "Team workspace: open Drive evidence and shortcuts from kita.",
      ),
    ).toHaveLength(2);
    expect(screen.getAllByText("Next best actions")).toHaveLength(2);
    expect(screen.getAllByText("Internal review")).toHaveLength(2);
    expect(screen.getAllByText("Key company records")).toHaveLength(2);
    expect(screen.getAllByText("Folder cleanup")).toHaveLength(2);

    expect(screen.getByText("OCEAN CLOTHES AND SHOES PT")).toBeInTheDocument();
    expect(
      screen.getByText("BIMALA / Bimala Investments Bali PT"),
    ).toBeInTheDocument();
    expect(screen.getByText("DEA")).toBeInTheDocument();
    expect(screen.getByText("Dewa Ayu")).toBeInTheDocument();
    expect(screen.getAllByText("Natan Kleimonov").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Giulia Del Giudice").length).toBeGreaterThan(
      0,
    );
    expect(screen.getAllByText("Giorgia Emidio").length).toBeGreaterThan(0);
    expect(
      screen.getAllByText("Confirm the company role from registry documents."),
    ).toHaveLength(4);
    expect(
      screen.getAllByText(
        "Confirm the family or business relationship before nesting files.",
      ).length,
    ).toBeGreaterThan(0);
    expect(screen.getByText("SPT 2025")).toBeInTheDocument();
    expect(screen.getByText("LKPM Periode 4 PDFs")).toBeInTheDocument();
    expect(
      screen.getAllByText("Confirm company roles from company PDFs."),
    ).toHaveLength(2);
    expect(
      screen.getByText(
        "Operational tax folder vs canonical-like company folder",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getAllByRole("link", {
        name: /open operational folder in drive/i,
      }),
    ).toHaveLength(2);
    expect(screen.queryByText("Evidence")).not.toBeInTheDocument();
    expect(screen.queryByText("Gaps")).not.toBeInTheDocument();
    expect(screen.queryByText("Duplicate Candidates")).not.toBeInTheDocument();
    expect(screen.queryByText("Read-only")).not.toBeInTheDocument();
    expect(screen.queryByText(/Confidence:/)).not.toBeInTheDocument();
    expect(screen.queryByText("Business recap")).not.toBeInTheDocument();
    expect(screen.queryByText("Client relationships")).not.toBeInTheDocument();
  });

  it("does not warn when company maps share the same backend key", () => {
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => undefined);

    render(
      <TaxCompanyPilotWorkspace
        maps={[oceanMap, { ...bimalaMap, key: oceanMap.key }]}
      />,
    );

    expect(
      screen.getByText("Person-first intelligence desk"),
    ).toBeInTheDocument();
    expect(consoleError.mock.calls.flat().join("\n")).not.toContain(
      "Encountered two children with the same key",
    );
  });
});
