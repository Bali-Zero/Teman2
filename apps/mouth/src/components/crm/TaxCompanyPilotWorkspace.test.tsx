import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TaxCompanyPilotWorkspace } from "./TaxCompanyPilotWorkspace";
import type { TaxCompanyPilotMap } from "@/lib/api/crm/crm.types";

const oceanMap: TaxCompanyPilotMap = {
  key: "ocean",
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

    expect(screen.getByText("Business dossiers")).toBeInTheDocument();
    expect(screen.getByText("Companies under review")).toBeInTheDocument();
    expect(screen.getAllByText("Open decisions")).toHaveLength(3);
    expect(screen.getAllByText("Tax owner")).toHaveLength(2);
    expect(screen.getAllByText("Business recap")).toHaveLength(2);
    expect(screen.getAllByText("Client relationships")).toHaveLength(2);
    expect(screen.getAllByText("Key company records")).toHaveLength(2);
    expect(screen.getAllByText("Folder cleanup")).toHaveLength(2);

    expect(screen.getByText("OCEAN CLOTHES AND SHOES PT")).toBeInTheDocument();
    expect(
      screen.getByText("BIMALA / Bimala Investments Bali PT"),
    ).toBeInTheDocument();
    expect(screen.getByText("DEA")).toBeInTheDocument();
    expect(screen.getByText("Dewa Ayu")).toBeInTheDocument();
    expect(screen.getByText("Natan Kleimonov")).toBeInTheDocument();
    expect(screen.getByText("Giulia Del Giudice")).toBeInTheDocument();
    expect(screen.getByText("Giorgia Emidio")).toBeInTheDocument();
    expect(screen.getByText("SPT 2025")).toBeInTheDocument();
    expect(screen.getByText("LKPM Periode 4 PDFs")).toBeInTheDocument();
    expect(
      screen.getByText("Confirm company roles from company PDFs."),
    ).toBeInTheDocument();
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

    expect(screen.getByText("Business dossiers")).toBeInTheDocument();
    expect(consoleError.mock.calls.flat().join("\n")).not.toContain(
      "Encountered two children with the same key",
    );
  });
});
