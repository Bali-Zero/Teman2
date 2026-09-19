/** Family ledger behaviour — synthetic fixtures only, no client data. */
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FamilyTab } from "./FamilyTab";
import { api } from "@/lib/api";
import type { ClientDocument, FamilyMember } from "@/lib/api/crm/crm.types";

vi.mock("@/lib/api", () => ({
  api: { crm: { deleteFamilyMember: vi.fn() }, post: vi.fn() },
}));

vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }),
}));

// A vi.fn() wrapper (not a static factory) so individual tests can flip
// `ocrPolling` to true for one render via `mockReturnValueOnce`.
const { mockUseOcrPolling } = vi.hoisted(() => ({
  mockUseOcrPolling: vi.fn(() => ({
    ocrPolling: false,
    pollOcrStatus: vi.fn(),
  })),
}));

vi.mock("@/hooks/useOcrPolling", () => ({
  useOcrPolling: mockUseOcrPolling,
}));

const MEMBER: FamilyMember = {
  id: 1,
  client_id: 412,
  full_name: "Family Member A",
  relationship: "spouse",
  nationality: "Indonesian",
  current_visa_type: "D12",
  visa_expiry: "2027-09-15",
  visa_alert: "green",
} as FamilyMember;

const renderTab = (
  familyMembers: FamilyMember[] = [MEMBER],
  documents: ClientDocument[] = [],
) =>
  render(
    <FamilyTab
      clientId={412}
      familyMembers={familyMembers}
      documents={documents}
      formatDate={(date) => `formatted:${date}`}
      onAddClick={() => {}}
      onEditClick={() => {}}
      onRefresh={() => {}}
    />,
  );

afterEach(() => vi.useRealTimers());

describe("FamilyTab — r19 family ledger", () => {
  it("GUILT: the visa pill is sourced from visa_alert, not from the expiry date — the enum wins", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-19T12:00:00Z"));

    // The expiry is a decade out — date math would call this "Valid" — but
    // the server already flagged it expired, and that is what must render.
    renderTab([
      { ...MEMBER, visa_alert: "expired", visa_expiry: "2036-01-01" },
    ]);

    expect(screen.getByText("Expired")).toBeInTheDocument();
    expect(screen.queryByText("Valid")).not.toBeInTheDocument();
  });

  it("GUILT: a yellow visa_alert and a red visa_alert render different words", () => {
    renderTab([
      { ...MEMBER, id: 5, visa_alert: "yellow" },
      { ...MEMBER, id: 6, visa_alert: "red" },
    ]);

    expect(screen.getByText("Renewal recommended")).toBeInTheDocument();
    expect(screen.getByText("Expiring soon")).toBeInTheDocument();
  });

  it("GUILT: a yellow passport_alert and a red passport_alert render different words on the date cell when no expiry is known", () => {
    renderTab([
      {
        ...MEMBER,
        id: 5,
        passport_number: "X1111111",
        passport_expiry: undefined,
        passport_alert: "yellow",
      },
      {
        ...MEMBER,
        id: 6,
        passport_number: "X2222222",
        passport_expiry: undefined,
        passport_alert: "red",
      },
    ]);

    expect(screen.getByText(/Renewal recommended/)).toBeInTheDocument();
    expect(screen.getByText(/Expiring soon/)).toBeInTheDocument();
  });

  it("GUILT: passport_alert urgency shows the countdown wording on the date cell", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-19T12:00:00Z"));

    renderTab([
      {
        ...MEMBER,
        passport_number: "X1234567",
        passport_expiry: "2026-10-19",
        passport_alert: "red",
      },
    ]);

    expect(screen.getByText(/⏰ 30d left/)).toBeInTheDocument();
  });

  it("GUILT: a visa document with nothing extracted shows the OCR note and an em-dash, never the literal 'visa' as a type", () => {
    renderTab(
      [{ ...MEMBER, current_visa_type: undefined }],
      [
        {
          id: 20,
          client_id: 412,
          family_member_id: 1,
          document_type: "visa",
          google_drive_file_url:
            "https://drive.google.com/file/d/synthetic-visa/view",
        } as ClientDocument,
      ],
    );

    expect(
      screen.getByText("Document on file — upload to extract data via OCR"),
    ).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.queryByText("visa")).not.toBeInTheDocument();
  });

  it("GUILT: no row ever renders the copper 'you' tone", () => {
    const { container } = renderTab([
      { ...MEMBER, visa_alert: "expired" },
      { ...MEMBER, id: 2, visa_alert: "red" },
      { ...MEMBER, id: 3, visa_alert: undefined, current_visa_type: undefined },
    ]);

    expect(container.querySelector('[class*="--bz-copper-text"]')).toBeNull();
  });

  it("INNOCENCE: a member the server marks green renders the ok tone as 'Valid'", () => {
    renderTab([{ ...MEMBER, visa_alert: "green" }]);

    expect(screen.getByText("Valid")).toBeInTheDocument();
  });

  it("INNOCENCE: renders the r19 empty state when there are no family members", () => {
    renderTab([]);

    expect(screen.getByText("No family members on file.")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Add family member" }),
    ).toBeInTheDocument();
  });

  it("INNOCENCE: keeps each pre-existing member action reachable by accessible name", () => {
    renderTab(
      [MEMBER],
      [
        {
          id: 10,
          client_id: 412,
          family_member_id: 1,
          document_type: "passport",
          google_drive_file_url:
            "https://drive.google.com/file/d/synthetic-id/view",
        } as ClientDocument,
        {
          id: 11,
          client_id: 412,
          family_member_id: 1,
          document_type: "visa",
          google_drive_file_url:
            "https://drive.google.com/file/d/synthetic-visa/view",
        } as ClientDocument,
      ],
    );

    for (const name of [
      "Add family member",
      "Edit Family Member A",
      "Remove Family Member A",
      "Upload passport for Family Member A",
      "Upload visa for Family Member A",
      "View passport for Family Member A",
      "Download passport for Family Member A",
      "View visa for Family Member A",
      "Download visa for Family Member A",
    ]) {
      expect(screen.getByRole("button", { name })).toBeInTheDocument();
    }
  });

  it("GUILT: the passport urgency fallback threshold is exactly 180 days, with no alert to lean on", () => {
    vi.useFakeTimers();
    // "Now" at 00:00:00Z + date-only expiries (also midnight UTC) make
    // Math.ceil((expiry - now) / 86400000) land on an exact integer — no
    // half-day rounding to hide an off-by-one behind. 2026-09-19 + 180 days
    // = 2027-03-18 (day-of-year 262 + 180 = 442 = day 77 of 2027 = Mar 18);
    // +181 = Mar 19. Verified with `node -e` before writing this fixture.
    vi.setSystemTime(new Date("2026-09-19T00:00:00Z"));

    renderTab([
      // daysLeft === 180 exactly — must be urgent
      {
        ...MEMBER,
        id: 7,
        passport_number: "X1111111",
        passport_expiry: "2027-03-18",
        passport_alert: undefined,
      },
      // daysLeft === 181 exactly — must be quiet
      {
        ...MEMBER,
        id: 8,
        passport_number: "X2222222",
        passport_expiry: "2027-03-19",
        passport_alert: undefined,
      },
    ]);

    expect(screen.getByText(/Passport: ⏰ 180d left/)).toHaveAttribute(
      "style",
      "color: var(--state-warning);",
    );
    expect(screen.getByText(/Passport: ⏰ 181d left/)).toHaveAttribute(
      "style",
      "color: var(--tx-secondary);",
    );
  });

  it("GUILT: a passport more than a year out renders 'Nmo left' with the 30-day divisor", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-19T12:00:00Z"));

    renderTab([
      {
        ...MEMBER,
        id: 30,
        passport_number: "X3333333",
        passport_expiry: "2028-01-01",
        passport_alert: undefined,
      },
    ]);

    expect(screen.getByText(/Passport: 15mo left/)).toBeInTheDocument();
  });

  it("GUILT: a passport expiring on the current instant renders 'Expires today'", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-19T12:00:00Z"));

    renderTab([
      {
        ...MEMBER,
        id: 31,
        passport_number: "X4444444",
        passport_expiry: "2026-09-19",
        passport_alert: undefined,
      },
    ]);

    expect(screen.getByText(/Passport: Expires today/)).toBeInTheDocument();
  });

  it("GUILT: an already-expired passport renders 'Expired Nd ago'", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-19T12:00:00Z"));

    renderTab([
      {
        ...MEMBER,
        id: 32,
        passport_number: "X5555555",
        passport_expiry: "2026-09-14",
        passport_alert: undefined,
      },
    ]);

    expect(screen.getByText(/Passport: Expired 5d ago/)).toBeInTheDocument();
  });

  it("INNOCENCE: the delete control's title mirrors its accessible name (replaces the vanished OLD-TEST title assertion)", () => {
    renderTab([MEMBER]);

    expect(
      screen.getByRole("button", { name: "Remove Family Member A" }),
    ).toHaveAttribute("title", "Remove Family Member A");
  });

  it("INNOCENCE: the upload control announces the in-flight upload in its accessible name AND as a visible word next to the spinner", () => {
    vi.mocked(api.post).mockReturnValueOnce(new Promise(() => {}));

    renderTab([MEMBER]);

    const uploadButton = screen.getByRole("button", {
      name: "Upload passport for Family Member A",
    });
    const input = uploadButton.previousElementSibling as HTMLInputElement;
    const file = new File(["x"], "passport.jpg", { type: "image/jpeg" });
    fireEvent.change(input, { target: { files: [file] } });

    expect(
      screen.getByRole("button", {
        name: "Uploading passport for Family Member A",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("Uploading...")).toBeInTheDocument();
  });

  it("INNOCENCE: the upload control announces OCR polling in its accessible name AND as a visible word", () => {
    mockUseOcrPolling.mockReturnValueOnce({
      ocrPolling: true,
      pollOcrStatus: vi.fn(),
    });

    renderTab([MEMBER]);

    expect(
      screen.getByRole("button", {
        name: "OCR in corso for Family Member A",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("OCR in corso...")).toBeInTheDocument();
  });

  it("INNOCENCE: an idle upload control shows no status word — it stays icon-only", () => {
    renderTab([MEMBER]);

    expect(screen.queryByText("Uploading...")).not.toBeInTheDocument();
    expect(screen.queryByText("OCR in corso...")).not.toBeInTheDocument();
  });

  it("INNOCENCE: falls back to wait/No visa when a member has no visa data at all", () => {
    renderTab([
      {
        ...MEMBER,
        id: 4,
        full_name: "Family Member D",
        current_visa_type: undefined,
        visa_expiry: undefined,
        visa_alert: undefined,
      },
    ]);

    expect(screen.getByText("No visa")).toBeInTheDocument();
    expect(screen.queryByText(/formatted:undefined/)).not.toBeInTheDocument();
  });
});
