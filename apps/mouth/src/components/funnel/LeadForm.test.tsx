import * as React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { LeadForm } from "./LeadForm";

vi.mock("@/lib/analytics", () => ({
  trackEvent: vi.fn(),
  trackLeadCreated: vi.fn(),
}));

import { trackEvent, trackLeadCreated } from "@/lib/analytics";

describe("LeadForm", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    global.fetch = vi.fn(() =>
      Promise.resolve({ ok: true, status: 200 } as Response),
    );
  });

  function fill(values: {
    name?: string;
    email?: string;
    phone?: string;
    service?: string;
    message?: string;
  }) {
    if (values.name !== undefined) {
      fireEvent.change(screen.getByLabelText(/full name/i), {
        target: { value: values.name },
      });
    }
    if (values.email !== undefined) {
      fireEvent.change(screen.getByLabelText(/email/i), {
        target: { value: values.email },
      });
    }
    if (values.phone !== undefined) {
      fireEvent.change(screen.getByLabelText(/phone/i), {
        target: { value: values.phone },
      });
    }
    if (values.service !== undefined) {
      fireEvent.change(screen.getByLabelText(/^service$/i), {
        target: { value: values.service },
      });
    }
    if (values.message !== undefined) {
      fireEvent.change(screen.getByLabelText(/how can we help/i), {
        target: { value: values.message },
      });
    }
  }

  it("tracks lead_form_start on first field change", () => {
    render(<LeadForm source="unit-test" />);
    fill({ name: "A" });
    expect(trackEvent).toHaveBeenCalledWith("lead_form_start", {
      source: "unit-test",
    });
  });

  it("surfaces validation errors without submitting", async () => {
    render(<LeadForm source="unit-test" />);
    fireEvent.submit(screen.getByRole("form", { name: /lead capture form/i }));
    await waitFor(() => {
      expect(screen.getByText(/please enter your full name/i)).toBeInTheDocument();
    });
    expect(global.fetch).not.toHaveBeenCalled();
    expect(trackEvent).toHaveBeenCalledWith(
      "lead_form_error",
      expect.objectContaining({ source: "unit-test", reason: "validation" }),
    );
  });

  it("submits valid payload and fires trackLeadCreated", async () => {
    render(<LeadForm source="unit-test" />);
    fill({
      name: "Jane Doe",
      email: "jane@example.com",
      service: "visa",
      message: "Please help me move to Bali.",
    });
    fireEvent.submit(screen.getByRole("form", { name: /lead capture form/i }));
    await waitFor(() => {
      expect(trackLeadCreated).toHaveBeenCalledWith("unit-test");
    });
    expect(global.fetch).toHaveBeenCalledTimes(1);
    const [, init] = (global.fetch as unknown as ReturnType<typeof vi.fn>).mock
      .calls[0];
    const body = JSON.parse(init.body);
    expect(body).toMatchObject({
      source: "unit-test",
      name: "Jane Doe",
      email: "jane@example.com",
      service: "visa",
    });
  });

  it("shows an error banner on network failure", async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({ ok: false, status: 500 } as Response),
    );
    render(<LeadForm source="unit-test" />);
    fill({
      name: "Jane Doe",
      email: "jane@example.com",
      service: "visa",
      message: "Please help me move to Bali.",
    });
    fireEvent.submit(screen.getByRole("form", { name: /lead capture form/i }));
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/try again/i);
    });
  });
});
