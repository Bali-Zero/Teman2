import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { translate, type I18nKey } from "../_lib/i18n";
import { OracleShell } from "./OracleShell";

// R2 (owner decision 2026-10-11): the retirement-age notice, driven through
// the real shell. Three actions — Continue answers, Second Home and Change
// my answers are navigation and record nothing.

async function reachNotice(birth: string): Promise<void> {
  fireEvent.click(await screen.findByRole("button", { name: /^start$/i }));
  fireEvent.click(
    await screen.findByRole("button", { name: /planning ahead/i }),
  );
  await screen.findByRole("heading", {
    name: /do you currently hold a limited or permanent stay permit/i,
  });
  fireEvent.click(await screen.findByRole("button", { name: /^no$/i }));
  fireEvent.change(await screen.findByRole("combobox"), {
    target: { value: "US" },
  });
  fireEvent.click(screen.getByRole("button", { name: /^add country$/i }));
  fireEvent.click(screen.getByRole("button", { name: /^continue$/i }));
  const birthDate =
    document.querySelector<HTMLInputElement>('input[type="date"]');
  expect(birthDate).not.toBeNull();
  fireEvent.change(birthDate!, { target: { value: birth } });
  fireEvent.click(screen.getByRole("button", { name: /see my options/i }));
  fireEvent.click(await screen.findByRole("button", { name: /^retirement/i }));
  fireEvent.click(
    await screen.findByRole("button", { name: /one main purpose/i }),
  );
}

const NOTICE = translate("en", "q.retirement_age_notice" as I18nKey);

describe("OracleShell · the retirement-age notice", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    window.localStorage.clear();
    vi.stubEnv("NEXT_PUBLIC_VISA_ORACLE_MODE", "ENGINE");
  });
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("shows the three actions and a concrete 55th-birthday date for a visitor under 55", async () => {
    render(<OracleShell />);
    await reachNotice("1990-01-01");

    expect(
      await screen.findByRole("heading", { name: NOTICE }),
    ).toBeInTheDocument();
    expect(screen.getByText(/You turn 55 on 1 January 2045\./)).toBeTruthy();
    expect(screen.queryByText(/{{date}}/)).toBeNull();
    for (const key of [
      "q.retirement_age_notice.opt.continue",
      "q.retirement_age_notice.opt.second_home",
      "q.retirement_age_notice.opt.change",
    ]) {
      expect(
        screen.getByRole("button", { name: translate("en", key as I18nKey) }),
      ).toBeInTheDocument();
    }
  });

  it("Continue goes on to the unchanged retirement branch", async () => {
    render(<OracleShell />);
    await reachNotice("1990-01-01");
    fireEvent.click(
      await screen.findByRole("button", {
        name: translate("en", "q.retirement_age_notice.opt.continue"),
      }),
    );
    expect(
      await screen.findByRole("heading", {
        name: translate("en", "q.retirement_basis" as I18nKey),
      }),
    ).toBeInTheDocument();
  });

  it("Look at Second Home re-routes without claiming eligibility", async () => {
    render(<OracleShell />);
    await reachNotice("1990-01-01");
    fireEvent.click(
      await screen.findByRole("button", {
        name: translate("en", "q.retirement_age_notice.opt.second_home"),
      }),
    );
    expect(
      await screen.findByRole("heading", {
        name: translate("en", "q.trip_scope" as I18nKey),
      }),
    ).toBeInTheDocument();
    expect(screen.queryByText(NOTICE)).toBeNull();
  });

  it("Change my answers reopens the date of birth", async () => {
    render(<OracleShell />);
    await reachNotice("1990-01-01");
    fireEvent.click(
      await screen.findByRole("button", {
        name: translate("en", "q.retirement_age_notice.opt.change"),
      }),
    );
    expect(
      await screen.findByRole("heading", {
        name: translate("en", "q.birth_date" as I18nKey),
      }),
    ).toBeInTheDocument();
  });

  it("a visitor aged 55 or more never sees it", async () => {
    render(<OracleShell />);
    await reachNotice("1950-01-01");
    expect(
      await screen.findByRole("heading", {
        name: translate("en", "q.retirement_basis" as I18nKey),
      }),
    ).toBeInTheDocument();
    expect(screen.queryByText(NOTICE)).toBeNull();
  });
});
