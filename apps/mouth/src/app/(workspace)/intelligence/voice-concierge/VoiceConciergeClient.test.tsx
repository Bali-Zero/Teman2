import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { VoiceConciergeClient } from "./VoiceConciergeClient";

describe("VoiceConciergeClient", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          answer: "Start with the KBLI and zoning check.",
          intent: "company",
          risk_level: "medium",
          next_action: "collect_non_pii_context",
          quick_replies: ["Ask about KBLI", "Check zoning"],
          safety_note: "No PII.",
          mode: "demo",
          provider: "local-demo",
        }),
        { status: 200 },
      ),
    );
  });

  it("renders the voice concierge workbench", () => {
    render(<VoiceConciergeClient />);

    expect(
      screen.getByRole("heading", { name: "Voice Concierge" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });

  it("sends a typed turn and displays the structured response", async () => {
    const user = userEvent.setup();
    render(<VoiceConciergeClient />);

    await user.type(
      screen.getByLabelText("Concierge prompt"),
      "Can I open a cafe in Bali?",
    );
    await user.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(screen.getByText("Start with the KBLI and zoning check.")).toBeInTheDocument();
    });
    expect(screen.getByText("company")).toBeInTheDocument();
    expect(screen.getByText("collect_non_pii_context")).toBeInTheDocument();
    expect(screen.getByText("Ask about KBLI")).toBeInTheDocument();
    expect(global.fetch).toHaveBeenCalledWith(
      "/api/lab/voice-concierge",
      expect.objectContaining({ method: "POST" }),
    );
  });
});
