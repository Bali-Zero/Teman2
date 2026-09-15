/**
 * FamilyTab — round-4 Q6 render proof.
 *
 * client-detail-desk.test.tsx's GLOB guards prove the SOURCE never has an
 * icon-only Trash2/X control without an aria-label; this file proves that
 * promise survives rendering — the delete-member control actually carries
 * an accessible name in the DOM, on a real (non-mocked) FamilyTab.
 *
 * Fixture is synthetic only: "Family Member A", no real name/passport/email
 * (K3b spec §1 / CLAUDE.md builder contract #4).
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { FamilyTab } from "./FamilyTab";
import type { FamilyMember } from "@/lib/api/crm/crm.types";

vi.mock("@/lib/api", () => ({
  api: {
    crm: {
      deleteFamilyMember: vi.fn(),
      getClientAiSummary: vi
        .fn()
        .mockResolvedValue({ status: "not_generated" }),
    },
    post: vi.fn(),
  },
}));

vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }),
}));

vi.mock("@/lib/logger", () => ({
  logger: { error: vi.fn(), info: vi.fn(), warn: vi.fn(), debug: vi.fn() },
}));

vi.mock("@/hooks/useOcrPolling", () => ({
  useOcrPolling: () => ({ ocrPolling: false, pollOcrStatus: vi.fn() }),
}));

const MEMBER: FamilyMember = {
  id: 1,
  full_name: "Family Member A",
  relationship: "spouse",
} as FamilyMember;

describe("FamilyTab — delete-member control (round-4 Q6)", () => {
  it("the icon-only delete control renders with a real aria-label naming the action and target", () => {
    render(
      <FamilyTab
        clientId={412}
        familyMembers={[MEMBER]}
        documents={[]}
        formatDate={(d) => d}
        onAddClick={() => {}}
        onEditClick={() => {}}
        onRefresh={() => {}}
      />,
    );
    const deleteButton = screen.getByRole("button", {
      name: "Remove family member",
    });
    expect(deleteButton).toBeInTheDocument();
    expect(deleteButton).toHaveAttribute("title", "Remove family member");
  });
});
