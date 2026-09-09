import "@testing-library/jest-dom/vitest";
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import VoaForm from "./voa-form";
import MatchForm from "./match-form";
import ClockForm from "./clock-form";
import { AppWizard, type WizardStep } from "./ui";
import {
  ClockResultView,
  MatchResultView,
  VisaResult,
  daysFromBaliToday,
} from "./results";
import { SecondHomeLanding } from "./secondhome/SecondHomeLanding";
import { SecondHomeLanguage } from "./secondhome/translations";
const push = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
beforeEach(() => {
  localStorage.clear();
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(Response.json({ available: false }, { status: 503 })),
  );
  push.mockClear();
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});
const next = () =>
  fireEvent.click(screen.getByRole("button", { name: "Continue" }));
describe("native public Visa journeys", () => {
  it("completes VOA preparation and never sends an eligibility POST", async () => {
    render(<VoaForm />);
    fireEvent.click(
      await screen.findByRole("button", { name: /Get a new Visa on Arrival/ }),
    );
    next();
    fireEvent.click(screen.getByRole("button", { name: "Tourism" }));
    next();
    fireEvent.change(screen.getByLabelText("Nationality"), {
      target: { value: "ITA" },
    });
    next();
    fireEvent.change(screen.getByLabelText("Entry date"), {
      target: { value: "2026-11-01" },
    });
    fireEvent.change(screen.getByLabelText("Passport expiry date"), {
      target: { value: "2030-11-01" },
    });
    fireEvent.click(
      screen.getByLabelText("Storage and deletion notice acknowledgement"),
    );
    fireEvent.click(screen.getByRole("button", { name: "Review my answers" }));
    expect(
      await screen.findByText(/No eligibility check submitted/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", {
        name: "Continue to the secure eligibility check",
      }),
    ).toHaveAttribute("href", "/legacy/visa/voa");
    expect(fetch).not.toHaveBeenCalled();
    expect(push).not.toHaveBeenCalled();
  });
  it("restores extension answers without losing its conditional expiry question", async () => {
    localStorage.setItem(
      "bz.garuda_voa.wizard",
      JSON.stringify({
        ts: Date.now(),
        idx: 3,
        values: {
          case_type: "extension",
          purpose: "tourism",
          trip: { nationality: "ITA" },
        },
      }),
    );
    render(<VoaForm />);
    await screen.findByRole("button", { name: /Extend a Visa/ });
    next();
    next();
    next();
    expect(
      screen.getByLabelText("Current Visa on Arrival expiry date"),
    ).toBeInTheDocument();
  });
  it("submits canonical Clock answers and navigates only to a valid reference", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      Response.json({ hash: "synthetic_clock" }),
    );
    render(<ClockForm />);
    fireEvent.change(screen.getByLabelText("Entry date"), {
      target: { value: "2026-08-01" },
    });
    fireEvent.change(screen.getByLabelText("Visa type"), {
      target: { value: "B1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Show my timeline" }));
    await waitFor(() =>
      expect(push).toHaveBeenCalledWith("/visa/clock/synthetic_clock"),
    );
    expect(JSON.parse(String(vi.mocked(fetch).mock.calls[0][1]?.body))).toEqual(
      { visa_type: "B1", entry_date: "2026-08-01", in_country_now: true },
    );
  });
  it("validates custom nationality and submits the real Match shape", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      Response.json({ hash: "synthetic_match" }),
    );
    render(<MatchForm />);
    fireEvent.change(await screen.findByLabelText("Nationality"), {
      target: { value: "OTHER" },
    });
    next();
    expect(screen.getByRole("alert")).toHaveTextContent("country code");
    fireEvent.change(screen.getByLabelText("Passport country code"), {
      target: { value: "ESP" },
    });
    next();
    fireEvent.click(
      screen.getByRole("button", {
        name: "Work remotely for a foreign employer",
      }),
    );
    next();
    fireEvent.change(screen.getByLabelText("Duration in months"), {
      target: { value: "12" },
    });
    next();
    fireEvent.click(screen.getByRole("button", { name: "Under IDR 50M" }));
    fireEvent.click(screen.getByRole("button", { name: "See my result" }));
    await waitFor(() =>
      expect(push).toHaveBeenCalledWith("/visa/match/synthetic_match"),
    );
    expect(JSON.parse(String(vi.mocked(fetch).mock.calls[0][1]?.body))).toEqual(
      {
        nationality: "ESP",
        purpose: "work_remote",
        duration_months: 12,
        budget_band: "under_50m",
      },
    );
  });
  it("blocks duplicate completion while the request is pending and tolerates blocked storage", async () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("blocked", "SecurityError");
    });
    let finish!: () => void;
    const onComplete = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          finish = resolve;
        }),
    );
    const steps: WizardStep[] = [
      { id: "one", title: "One", render: () => <p>Answer</p> },
    ];
    render(
      <AppWizard steps={steps} persistKey="test" onComplete={onComplete} />,
    );
    const button = await screen.findByRole("button", { name: "See my result" });
    fireEvent.click(button);
    fireEvent.click(button);
    expect(onComplete).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Checking…" })).toBeDisabled();
    finish();
    await screen.findByRole("button", { name: "See my result" });
  });
  it("shows a past recorded expiry without a false future countdown or reminder CTA", () => {
    render(
      <ClockResultView
        now={new Date("2026-09-09T01:00:00Z")}
        result={{
          hash: "synthetic",
          visa_type: "B1",
          entry_date: "2026-08-01",
          expiry_date: "2026-08-30",
          extensions_possible: 1,
          extension_days: 30,
          checkpoints: [],
        }}
      />,
    );
    expect(
      screen.getByText("10 days past the recorded expiry."),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Reminders and case discussion"),
    ).not.toBeInTheDocument();
    expect(
      daysFromBaliToday("2026-09-10", new Date("2026-09-09T16:30:00Z")),
    ).toBe(0);
  });
  it("preserves referral mode and hides unverified prices", () => {
    render(
      <MatchResultView
        result={{
          hash: "synthetic",
          recommended_visa: null,
          reason: "A specialist must review this purpose.",
          estimated_cost_idr: 12345678,
          cost_source: null,
          processing_days: null,
          pre_arrival_steps: [],
          alternatives: [],
          referral_mode: true,
          nationality: "ITA",
          purpose: "other",
          duration_months: 6,
          budget_band: "under_50m",
        }}
      />,
    );
    expect(
      screen.getByText("Your case needs a closer look."),
    ).toBeInTheDocument();
    expect(screen.queryByText(/12,345,678/)).not.toBeInTheDocument();
  });
  it("renders a recoverable saved-result error without inventing a result", async () => {
    vi.mocked(fetch).mockResolvedValue(
      Response.json({ error: "Preview not connected" }, { status: 503 }),
    );
    render(<VisaResult kind="clock" reference="synthetic_clock" />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Preview not connected",
    );
    expect(
      screen.getByRole("link", { name: "Open the existing result service" }),
    ).toHaveAttribute("href", "/legacy/visa/clock/synthetic_clock");
  });
  it.each(["en", "it", "id"] as const)(
    "keeps the complete Second Home guide and language links in %s",
    async (locale) => {
      render(
        <SecondHomeLanguage locale={locale}>
          <SecondHomeLanding />
        </SecondHomeLanguage>,
      );
      expect(screen.getByRole("heading", { level: 1 })).not.toHaveTextContent(
        "secondHome.",
      );
      expect(
        document.querySelectorAll("details").length,
      ).toBeGreaterThanOrEqual(5);
      expect(screen.getByRole("link", { name: "it" })).toHaveAttribute(
        "href",
        "/visa/second-home/it",
      );
      expect(
        document.querySelector('a[href="/visa/second-home/studio"]'),
      ).toBeTruthy();
      await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    },
  );
});
