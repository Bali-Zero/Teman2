import { cleanup, render, screen, within, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getServiceDossier } from "../../content/service-dossiers";
import { ServiceCatalog } from "./ServiceCatalog";

const names = ["B1 Visa on Arrival (VOA)", "B1 Visa on Arrival — Extension (+30 days)"];
const dossiers = names.map(getServiceDossier);
const groups = dossiers.map((dossier, index) => ({ title: "Group " + (index + 1), description: "Services for review", services: [dossier] }));
beforeEach(() => { Element.prototype.scrollIntoView = vi.fn(); window.history.replaceState(null, "", "/"); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("service catalog decision support", () => {
  it("searches descriptions, reopens matching groups and restores the full collection", async () => {
    const user = userEvent.setup();
    const { container } = render(<ServiceCatalog title="Immigration" groups={groups} />);
    const secondGroup = container.querySelector<HTMLDetailsElement>("#catalog-2")!;
    secondGroup.open = false;
    await user.type(screen.getByRole("searchbox"), "already in Indonesia");
    expect(secondGroup.open).toBe(true);
    expect(container.querySelector("#" + dossiers[0].id)).not.toBeVisible();
    expect(container.querySelector("#" + dossiers[1].id)).toBeVisible();
    expect(screen.getByText("1 of 2 services")).toBeVisible();
    await user.clear(screen.getByRole("searchbox"));
    await user.type(screen.getByRole("searchbox"), "no-such-service");
    expect(screen.getByRole("heading", { name: "No matching services." })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Clear search" }));
    for (const dossier of dossiers) expect(container.querySelector("#" + dossier.id)).toBeVisible();
  });

  it("compares actual differences without changing quote context and returns keyboard focus", async () => {
    const user = userEvent.setup();
    const { container } = render(<ServiceCatalog title="Immigration" groups={groups} />);
    const quote = screen.getByRole("link", { name: "Request a quote for " + names[1] }).getAttribute("href");
    await user.click(screen.getByRole("checkbox", { name: "Compare " + names[0] }));
    expect(screen.getByRole("button", { name: "Compare selected (1)" })).toBeDisabled();
    await user.click(screen.getByRole("checkbox", { name: "Compare " + names[1] }));
    await user.click(screen.getByRole("button", { name: "Compare selected (2)" }));
    expect(screen.getByRole("heading", { name: "Two services, side by side." })).toHaveFocus();
    const comparison = screen.getByRole("table", { name: "Selected service comparison" });
    for (const dossier of dossiers) expect(within(comparison).getByText(dossier.distinction)).toBeVisible();
    expect(screen.getByRole("link", { name: "Request a quote for " + names[1] })).toHaveAttribute("href", quote);
    await user.click(screen.getByRole("button", { name: "Return to selected services ↑" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Compare selected (2)" })).toHaveFocus());
    const row = container.querySelector("#" + dossiers[1].id)!;
    const summary = within(row as HTMLElement).getByText("Scope & preparation");
    await user.click(summary); // Native keyboard activation is verified in the browser.
    expect(row.querySelector("details")!.open).toBe(true);
    await user.click(within(row as HTMLElement).getByRole("button", { name: "Close dossier & return to service ↑" }));
    expect(row.querySelector("details")!.open).toBe(false);
    expect(summary).toHaveFocus();
  });

  it("reveals an anchored service after a filter hid its closed group", async () => {
    const user = userEvent.setup();
    const { container } = render(<ServiceCatalog title="Immigration" groups={groups} />);
    await user.type(screen.getByRole("searchbox"), "no-match");
    container.querySelector<HTMLDetailsElement>("#catalog-2")!.open = false;
    window.location.hash = dossiers[1].id;
    await waitFor(() => expect(screen.getByRole("searchbox")).toHaveValue(""));
    expect(container.querySelector<HTMLDetailsElement>("#catalog-2")!.open).toBe(true);
    expect(container.querySelector("#" + dossiers[1].id)).toBeVisible();
  });
});
