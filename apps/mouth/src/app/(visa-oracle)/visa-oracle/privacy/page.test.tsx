import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import VisaOraclePrivacyPage from "./page";

describe("Visa Oracle Privacy Policy V1", () => {
  it("publishes the approved durations, separate consent and ENFORCE gate", () => {
    render(<VisaOraclePrivacyPage />);

    expect(screen.getByText(/retained for 30 days/)).toBeInTheDocument();
    expect(screen.getByText(/retained for 24 hours/)).toBeInTheDocument();
    expect(screen.getByText(/retained for 90 days/)).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        name: "WhatsApp and CRM are separate choices",
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(
      "cannot enter ENFORCE mode",
    );
    expect(
      screen.getByRole("link", {
        name: "Send a request to privacy@balizero.com",
      }),
    ).toHaveAttribute("href", "mailto:privacy@balizero.com");
  });

  it("switches the complete notice to Bahasa Indonesia", async () => {
    const user = userEvent.setup();
    render(<VisaOraclePrivacyPage />);

    await user.click(
      screen.getByRole("button", { name: "Switch to Bahasa Indonesia" }),
    );

    expect(
      screen.getByRole("heading", { name: "Data Visa Oracle Anda" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        name: "WhatsApp dan CRM adalah pilihan terpisah",
      }),
    ).toBeInTheDocument();
    expect(document.documentElement.lang).toBe("id");
  });
});
