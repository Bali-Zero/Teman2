import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ClientDocument } from "@/lib/api/crm/crm.types";
import { ImmigrationTab, isVisaFamilyDocument } from "./ImmigrationTab";

vi.mock("./AiSummaryCard", () => ({ AiSummaryCard: () => null }));

// Hoisted so the SAME `push` spy backs every `useRouter()` call across the
// file — a fresh `vi.fn()` per call (the round-2 shape) can never observe an
// argument, which is exactly what let a wrong navigation target through
// unpinned (R6-gate.md §4b, mutation k).
const { push } = vi.hoisted(() => ({ push: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

beforeEach(() => {
  push.mockClear();
});

// A few cases below freeze the clock (vi.setSystemTime) to pin exact-day
// boundaries. Always restore real time afterwards — a leaked fake clock
// would desync every other `Date.now()`-based fixture in this file.
afterEach(() => {
  vi.useRealTimers();
});

describe("isVisaFamilyDocument", () => {
  it("matches kitas, kitap, visa and e-visa document types", () => {
    for (const type of ["kitas", "KITAP", "visa c1", "e-visa", "evisa"]) {
      expect(isVisaFamilyDocument({ document_type: type })).toBe(true);
    }
  });

  it("matches VOA and its e-VOA spelling (GUILT: it is a visa document)", () => {
    for (const type of ["voa", "VOA", "e-voa", "evoa"]) {
      expect(isVisaFamilyDocument({ document_type: type })).toBe(true);
    }
  });

  it("does not match a non-visa document type (INNOCENCE)", () => {
    expect(isVisaFamilyDocument({ document_type: "passport" })).toBe(false);
    expect(isVisaFamilyDocument({ document_type: "working permit" })).toBe(
      false,
    );
  });
});

const baseDoc: ClientDocument = {
  id: 1,
  client_id: 1,
  document_type: "voa",
};

const renderTab = (documents: ClientDocument[]) =>
  render(
    <ImmigrationTab
      clientId={1}
      documents={documents}
      formatDate={(d) => d}
      onAddClick={vi.fn()}
      onEditClick={vi.fn()}
      onRefresh={vi.fn()}
    />,
  );

describe("ImmigrationTab — current permit panel vs visa history (R6 restyle)", () => {
  it("shows an unexpired VOA in the current-permit panel, not only in history (GUILT)", () => {
    const futureDate = new Date(Date.now() + 60 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      {
        ...baseDoc,
        id: 1,
        document_type: "voa",
        expiry_date: futureDate,
      },
    ]);

    expect(screen.getByText("Current permit")).toBeInTheDocument();
    expect(screen.queryByText("Visa history")).not.toBeInTheDocument();
  });

  it("shows an expired VOA only in the Visa history grid, not the permit panel (INNOCENCE)", () => {
    const pastDate = new Date(Date.now() - 60 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      {
        ...baseDoc,
        id: 2,
        document_type: "voa",
        expiry_date: pastDate,
      },
    ]);

    expect(screen.queryByText("Current permit")).not.toBeInTheDocument();
    expect(screen.getByText("Visa history")).toBeInTheDocument();
  });

  it("keeps an unexpired kitas as the current permit when a VOA is also present (existing precedence unchanged)", () => {
    const futureDate = new Date(Date.now() + 400 * 86400000)
      .toISOString()
      .slice(0, 10);
    const nearDate = new Date(Date.now() + 60 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      {
        ...baseDoc,
        id: 3,
        document_type: "kitas",
        expiry_date: futureDate,
      },
      {
        ...baseDoc,
        id: 4,
        document_type: "voa",
        expiry_date: nearDate,
      },
    ]);

    // Current permit picks the document with the furthest-out expiry first
    // (existing sort order: descending expiry) — unchanged by this fix.
    expect(screen.getAllByText("kitas")).toHaveLength(1);
    expect(screen.getByText("Visa history")).toBeInTheDocument();
    expect(screen.getAllByText("voa")).toHaveLength(1);
  });

  it("never classifies a non-visa document (e.g. passport-like) as a visa", () => {
    renderTab([
      {
        ...baseDoc,
        id: 5,
        document_type: "working permit",
        document_category: "immigration",
      },
    ]);

    expect(screen.queryByText("Current permit")).not.toBeInTheDocument();
    expect(screen.queryByText("Visa history")).not.toBeInTheDocument();
    expect(screen.getByText("Working Permit")).toBeInTheDocument();
  });

  it("renders the elapsed/expiry KPIs from real issue_date + expiry_date (no invented data)", () => {
    const issueDate = new Date(Date.now() - 20 * 86400000)
      .toISOString()
      .slice(0, 10);
    const expiryDate = new Date(Date.now() + 40 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      {
        ...baseDoc,
        id: 6,
        document_type: "kitas",
        issue_date: issueDate,
        expiry_date: expiryDate,
      },
    ]);

    expect(screen.getByText("Days on this permit")).toBeInTheDocument();
    expect(screen.getByText("Days to expiry")).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: /days elapsed/ }),
    ).toBeInTheDocument();
  });

  it("GUILT: omits the elapsed-days KPI and the validity track when issue_date is missing, rather than guessing it", () => {
    const futureDate = new Date(Date.now() + 60 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      {
        ...baseDoc,
        id: 7,
        document_type: "kitas",
        expiry_date: futureDate,
      },
    ]);

    expect(screen.getByText("Current permit")).toBeInTheDocument();
    expect(screen.queryByText("Days on this permit")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("img", { name: /days elapsed/ }),
    ).not.toBeInTheDocument();
    // The countdown itself does not need issue_date — only elapsed/total do.
    expect(screen.getByText("Days to expiry")).toBeInTheDocument();
  });

  it("Visa history shows a real document status when present, and a plain dash when it is not (no guessed status)", () => {
    const pastDate = new Date(Date.now() - 60 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      {
        ...baseDoc,
        id: 8,
        document_type: "kitas",
        expiry_date: pastDate,
        status: "verified",
      },
      {
        ...baseDoc,
        id: 9,
        document_type: "voa",
        expiry_date: pastDate,
      },
    ]);

    // R6c: the phone step (below 640px) relocates the same status node onto
    // the row's first cell too, so "verified" now renders twice — desktop
    // Status cell + phone block, jsdom evaluates no media queries.
    expect(screen.getAllByText("verified")).toHaveLength(2);
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });
});

describe("ImmigrationTab — Start Renewal CTA (R6 repair P0-1)", () => {
  it("GUILT: the permit panel shows Start Renewal for a kitas expiring in 45 days", () => {
    const soon = new Date(Date.now() + 45 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      { ...baseDoc, id: 20, document_type: "kitas", expiry_date: soon },
    ]);

    expect(
      screen.getByRole("button", { name: /start renewal/i }),
    ).toBeInTheDocument();
  });

  it("INNOCENCE: the permit panel shows no Start Renewal for a kitas expiring in 200 days", () => {
    const far = new Date(Date.now() + 200 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      { ...baseDoc, id: 21, document_type: "kitas", expiry_date: far },
    ]);

    expect(
      screen.queryByRole("button", { name: /start renewal/i }),
    ).not.toBeInTheDocument();
  });

  it("GUILT: an expired kitas in Visa history still offers Start Renewal", () => {
    const current = new Date(Date.now() + 400 * 86400000)
      .toISOString()
      .slice(0, 10);
    const expired = new Date(Date.now() - 10 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      { ...baseDoc, id: 22, document_type: "kitas", expiry_date: current },
      { ...baseDoc, id: 23, document_type: "kitas", expiry_date: expired },
    ]);

    expect(screen.getByText("Visa history")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /start renewal for kitas/i }),
    ).toBeInTheDocument();
  });

  it("BOUNDARY: shows Start Renewal at exactly 90 days out", () => {
    const now = new Date("2026-01-01T00:00:00.000Z");
    vi.setSystemTime(now);
    const expiryDate = new Date(now.getTime() + 90 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      { ...baseDoc, id: 24, document_type: "kitas", expiry_date: expiryDate },
    ]);

    expect(
      screen.getByRole("button", { name: /start renewal/i }),
    ).toBeInTheDocument();
  });

  it("BOUNDARY: hides Start Renewal at 91 days out — the threshold did not move", () => {
    const now = new Date("2026-01-01T00:00:00.000Z");
    vi.setSystemTime(now);
    const expiryDate = new Date(now.getTime() + 91 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      { ...baseDoc, id: 25, document_type: "kitas", expiry_date: expiryDate },
    ]);

    expect(
      screen.queryByRole("button", { name: /start renewal/i }),
    ).not.toBeInTheDocument();
  });
});

describe("ImmigrationTab — 'Days to expiry' never flips sign (R6 repair P0-2)", () => {
  it("GUILT: a permit expired 10 days ago (still in the 30-day grace) reads 'Days past expiry', never 'Days to expiry'", () => {
    const pastExpiry = new Date(Date.now() - 10 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      {
        ...baseDoc,
        id: 30,
        document_type: "kitas",
        expiry_date: pastExpiry,
      },
    ]);

    expect(screen.getByText("Current permit")).toBeInTheDocument();
    expect(screen.getByText("Days past expiry")).toBeInTheDocument();
    expect(screen.queryByText("Days to expiry")).not.toBeInTheDocument();
  });

  it("INNOCENCE: a permit expiring in 10 days still reads 'Days to expiry'", () => {
    const futureExpiry = new Date(Date.now() + 10 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      {
        ...baseDoc,
        id: 31,
        document_type: "kitas",
        expiry_date: futureExpiry,
      },
    ]);

    expect(screen.getByText("Days to expiry")).toBeInTheDocument();
    expect(screen.queryByText("Days past expiry")).not.toBeInTheDocument();
  });
});

describe("ImmigrationTab — 30-day grace boundary (R6 repair P1-6)", () => {
  it("BOUNDARY: a visa expired 29 days ago still shows in the permit panel (inside grace)", () => {
    const withinGrace = new Date(Date.now() - 29 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      { ...baseDoc, id: 40, document_type: "kitas", expiry_date: withinGrace },
    ]);

    expect(screen.getByText("Current permit")).toBeInTheDocument();
    expect(screen.queryByText("Visa history")).not.toBeInTheDocument();
  });

  it("BOUNDARY: a visa expired 31 days ago falls out of the panel and into Visa history", () => {
    const outsideGrace = new Date(Date.now() - 31 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      {
        ...baseDoc,
        id: 41,
        document_type: "kitas",
        expiry_date: outsideGrace,
      },
    ]);

    expect(screen.queryByText("Current permit")).not.toBeInTheDocument();
    expect(screen.getByText("Visa history")).toBeInTheDocument();
  });
});

/**
 * jsdom does not evaluate `@media` queries, so a plain `getByRole` cannot
 * see whether a control sits under the hover/focus-only `actions` slot
 * (`opacity-0 … [@media(hover:none)]:hidden`, `HairlineGrid.tsx:198-202`) —
 * on a touch device that slot is `display:none`. Walking the ancestor
 * chain and asserting neither class is present on any of it is the
 * structural proxy the re-audit asked for (§7 blocker 1).
 */
function assertReachableOnTouch(el: HTMLElement) {
  let node: HTMLElement | null = el;
  while (node) {
    expect(node.className).not.toMatch(/(?:^|\s)opacity-0(?:\s|$)/);
    expect(node.className).not.toMatch(/\[@media\(hover:none\)\]:hidden/);
    node = node.parentElement;
  }
}

describe("ImmigrationTab — Visa-history row controls are reachable on touch (R6 second repair, blocker 1)", () => {
  it("GUILT: Start Renewal and Download on a history row carry no hover/focus-only ancestor", () => {
    const currentDate = new Date(Date.now() + 500 * 86400000)
      .toISOString()
      .slice(0, 10);
    const renewDate = new Date(Date.now() - 5 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      { ...baseDoc, id: 70, document_type: "kitas", expiry_date: currentDate },
      {
        ...baseDoc,
        id: 71,
        document_type: "kitas",
        expiry_date: renewDate,
        google_drive_file_url:
          "https://drive.google.com/file/d/synthetic-fixture-id/view",
      },
    ]);

    assertReachableOnTouch(
      screen.getByRole("button", { name: /start renewal for kitas/i }),
    );
    assertReachableOnTouch(
      screen.getByRole("button", { name: /download kitas/i }),
    );
  });

  it("GUILT (round 3 — B1 inverts the round-2 pin): Edit and Remove on the same row also carry no hover/focus-only ancestor", () => {
    const currentDate = new Date(Date.now() + 500 * 86400000)
      .toISOString()
      .slice(0, 10);
    const historyDate = new Date(Date.now() - 5 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      { ...baseDoc, id: 72, document_type: "kitas", expiry_date: currentDate },
      { ...baseDoc, id: 73, document_type: "kitas", expiry_date: historyDate },
    ]);

    assertReachableOnTouch(screen.getByRole("button", { name: /edit kitas/i }));
    assertReachableOnTouch(
      screen.getByRole("button", { name: /remove kitas/i }),
    );
  });

  it("PIN (B1 — the defect that would have caught the missing column in round 1): every Visa-history row renders the same number of grid children as the head", () => {
    const currentDate = new Date(Date.now() + 500 * 86400000)
      .toISOString()
      .slice(0, 10);
    const withMember = new Date(Date.now() - 5 * 86400000)
      .toISOString()
      .slice(0, 10);
    const withoutMember = new Date(Date.now() - 15 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      { ...baseDoc, id: 74, document_type: "kitas", expiry_date: currentDate },
      {
        ...baseDoc,
        id: 75,
        document_type: "kitap",
        expiry_date: withMember,
        family_member_name: "Synthetic Dependent",
      },
      { ...baseDoc, id: 76, document_type: "visa", expiry_date: withoutMember },
    ]);

    const grid = document.querySelector(
      '[data-hgrid="immigration-visa-history"]',
    );
    expect(grid).not.toBeNull();
    const head = grid!.querySelector('[role="row"]');
    expect(head).not.toBeNull();
    const body = head!.nextElementSibling;
    expect(body).not.toBeNull();
    const rows = Array.from(body!.children);
    expect(rows.length).toBe(2); // withMember + withoutMember
    for (const row of rows) {
      expect(row.children.length).toBe(head!.children.length);
    }
  });

  it("PIN (R6b — the PR 6520 inert-collapse trap): the collapsed override carries as many tracks as non-collapse head cells, and the expanded template keeps all of them", () => {
    const currentDate = new Date(Date.now() + 500 * 86400000)
      .toISOString()
      .slice(0, 10);
    const historyDate = new Date(Date.now() - 5 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      { ...baseDoc, id: 80, document_type: "kitas", expiry_date: currentDate },
      { ...baseDoc, id: 81, document_type: "kitap", expiry_date: historyDate },
    ]);

    const grid = document.querySelector(
      '[data-hgrid="immigration-visa-history"]',
    );
    expect(grid).not.toBeNull();
    const head = grid!.querySelector('[role="row"]');
    expect(head).not.toBeNull();

    // `HairlineGrid`'s own `colsCollapsed` API only ever emits a `--cols`
    // media rule, and an inline `--cols` on the same element beats it
    // (PR 6520) — so the fix cannot rely on `--cols` at all below the
    // breakpoint. This pin fails if the fix goes back to relying on that
    // inert API: it requires a SEPARATE override that sets
    // `grid-template-columns` directly (the same technique DocumentsTab,
    // FamilyTab and ObligationsTable use), and checks its track count
    // against the DOM rather than trusting the prop.
    const overrideMatch = grid!.className.match(
      /\[&_\.grid\]:!grid-cols-\[([^\]]+)\]/,
    );
    expect(overrideMatch).not.toBeNull();
    const collapsedTracks = overrideMatch![1].split("_");

    const nonCollapseHeadCells = Array.from(head!.children).filter(
      (cell) => !cell.hasAttribute("data-collapse"),
    );
    // 4: Visa type, Status, Expires, Actions — "Issued" carries
    // `data-collapse` and leaves the flow below the breakpoint.
    expect(collapsedTracks.length).toBe(nonCollapseHeadCells.length);
    expect(collapsedTracks.length).toBe(4);

    const expandedTracks = grid!
      .getAttribute("style")!
      .match(/--cols:\s*([^;]+);/)![1]
      .trim()
      .split(/\s+/);
    expect(expandedTracks.length).toBe(head!.children.length);
    expect(expandedTracks.length).toBe(5);
  });
});

describe("ImmigrationTab — visa-history grid gets a phone step below 640px (R6c)", () => {
  it("PIN A: a max-sm override sized to the phone-visible head cells sits alongside the untouched R6b 1360 override", () => {
    const currentDate = new Date(Date.now() + 500 * 86400000)
      .toISOString()
      .slice(0, 10);
    const historyDate = new Date(Date.now() - 5 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      { ...baseDoc, id: 100, document_type: "kitas", expiry_date: currentDate },
      { ...baseDoc, id: 101, document_type: "kitap", expiry_date: historyDate },
    ]);

    const grid = document.querySelector(
      '[data-hgrid="immigration-visa-history"]',
    );
    expect(grid).not.toBeNull();
    const head = grid!.querySelector('[role="row"]');
    expect(head).not.toBeNull();

    const phoneVisibleHeadCells = Array.from(head!.children).filter(
      (cell) =>
        !cell.hasAttribute("data-collapse") &&
        !cell.className.includes("max-sm:hidden"),
    );
    // Visa type + the sr-only Actions head — Status and Expires leave below
    // 640px, same as Issued already does below 1360px.
    expect(phoneVisibleHeadCells.length).toBe(2);

    const phoneOverride = grid!.className.match(
      /max-sm:\[&_\.grid\]:!grid-cols-\[([^\]]+)\]/,
    );
    expect(phoneOverride).not.toBeNull();
    expect(phoneOverride![1].split("_").length).toBe(
      phoneVisibleHeadCells.length,
    );

    // R6b's 1360px override must stay green and unmodified in meaning: 4
    // tracks (Visa type, Status, Expires, Actions — Issued carries
    // data-collapse and already leaves the flow there).
    const desktopOverride = grid!.className.match(
      /max-\[1360px\]:\[&_\.grid\]:!grid-cols-\[([^\]]+)\]/,
    );
    expect(desktopOverride).not.toBeNull();
    expect(desktopOverride![1].split("_").length).toBe(4);
  });

  it("PIN B: every history row keeps 5 direct children, and its Status and Expires cells carry max-sm:hidden", () => {
    const currentDate = new Date(Date.now() + 500 * 86400000)
      .toISOString()
      .slice(0, 10);
    const historyDate1 = new Date(Date.now() - 5 * 86400000)
      .toISOString()
      .slice(0, 10);
    const historyDate2 = new Date(Date.now() - 15 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      { ...baseDoc, id: 102, document_type: "kitas", expiry_date: currentDate },
      {
        ...baseDoc,
        id: 103,
        document_type: "kitap",
        expiry_date: historyDate1,
      },
      { ...baseDoc, id: 104, document_type: "visa", expiry_date: historyDate2 },
    ]);

    const grid = document.querySelector(
      '[data-hgrid="immigration-visa-history"]',
    );
    const head = grid!.querySelector('[role="row"]');
    const body = head!.nextElementSibling;
    const rows = Array.from(body!.children) as HTMLElement[];
    expect(rows.length).toBe(2);

    for (const row of rows) {
      expect(row.children.length).toBe(head!.children.length);
      expect(row.children.length).toBe(5);
      const statusCell = row.children[1] as HTMLElement;
      const expiresCell = row.children[3] as HTMLElement;
      expect(statusCell.className).toContain("max-sm:hidden");
      expect(expiresCell.className).toContain("max-sm:hidden");
    }
  });

  it("PIN C: the phone block in the row's first cell carries the same status label (or —) and the exact Expires string, honouring the urgent class", () => {
    vi.setSystemTime(new Date("2026-01-01T00:00:00.000Z"));
    const currentDate = "2027-05-16"; // +500d, becomes the current permit
    const notUrgentDate = "2026-07-19"; // +200d, future but not the actualVisa
    const expiredDate = "2025-12-22"; // -10d

    renderTab([
      { ...baseDoc, id: 110, document_type: "kitas", expiry_date: currentDate },
      {
        ...baseDoc,
        id: 111,
        document_type: "kitap",
        expiry_date: notUrgentDate,
        status: "pending",
      },
      { ...baseDoc, id: 112, document_type: "voa", expiry_date: expiredDate },
    ]);

    const grid = document.querySelector(
      '[data-hgrid="immigration-visa-history"]',
    );
    const head = grid!.querySelector('[role="row"]');
    const body = head!.nextElementSibling;
    const rows = Array.from(body!.children) as HTMLElement[];
    expect(rows.length).toBe(2);

    for (const row of rows) {
      const wrapper = row.children[0] as HTMLElement;
      const phoneBlock = wrapper.querySelector(".sm\\:hidden") as HTMLElement;
      expect(phoneBlock).not.toBeNull();
      const desktopExpires = row.children[3] as HTMLElement;
      expect(phoneBlock.textContent).toContain(desktopExpires.textContent);
    }

    // The expired, status-less row (voa, id 112): dash where there is no
    // status, and the urgent warning class on the phone Expires line.
    const noStatusRow = rows.find((r) =>
      r.children[3].textContent?.includes("Expired 10d ago"),
    )!;
    const noStatusWrapper = noStatusRow.children[0] as HTMLElement;
    const noStatusPhoneBlock = noStatusWrapper.querySelector(
      ".sm\\:hidden",
    ) as HTMLElement;
    expect(noStatusPhoneBlock.textContent).toContain("—");
    const urgentLine = Array.from(
      noStatusPhoneBlock.querySelectorAll("span"),
    ).find((s) => s.textContent?.includes("Expired 10d ago"))!;
    expect(urgentLine.className).toContain("text-[var(--state-warning)]");

    // The kitap row (id 111) carries a real status: the phone block shows
    // the same tone/label, not a dash.
    const statusRow = rows.find(
      (r) => r.children[1].textContent === "pending",
    )!;
    const statusWrapper = statusRow.children[0] as HTMLElement;
    const statusPhoneBlock = statusWrapper.querySelector(
      ".sm\\:hidden",
    ) as HTMLElement;
    expect(statusPhoneBlock.textContent).toContain("pending");
  });
});

describe("ImmigrationTab — the six unpinned repairs from R6-reaudit.md §3 (M6-M11)", () => {
  it("GUILT: alert_color 'yellow' warns a history row's date cell even 300 days out (M6)", () => {
    vi.setSystemTime(new Date("2026-01-01T00:00:00.000Z"));
    const currentDate = "2027-05-16"; // +500d, becomes the current permit
    const yellowDate = "2026-10-28"; // +300d — date math alone would not warn
    renderTab([
      { ...baseDoc, id: 50, document_type: "kitas", expiry_date: currentDate },
      {
        ...baseDoc,
        id: 51,
        document_type: "kitap",
        expiry_date: yellowDate,
        alert_color: "yellow",
      },
    ]);

    // R6c: the phone step duplicates the same Expires string onto the row's
    // first cell — scope with getAllByText + an explicit length rather than
    // weakening the assertion.
    const expiryCells = screen.getAllByText(new RegExp(yellowDate));
    expect(expiryCells).toHaveLength(2);
    for (const cell of expiryCells) {
      expect(cell.className).toContain("text-[var(--state-warning)]");
    }
  });

  it("INNOCENCE: alert_color 'green' 300 days out stays a plain history date (M6)", () => {
    vi.setSystemTime(new Date("2026-01-01T00:00:00.000Z"));
    const currentDate = "2027-05-16"; // +500d
    const greenDate = "2026-10-28"; // +300d
    renderTab([
      { ...baseDoc, id: 52, document_type: "kitas", expiry_date: currentDate },
      {
        ...baseDoc,
        id: 53,
        document_type: "kitap",
        expiry_date: greenDate,
        alert_color: "green",
      },
    ]);

    // R6c: same duplication as the yellow case above.
    const expiryCells = screen.getAllByText(new RegExp(greenDate));
    expect(expiryCells).toHaveLength(2);
    for (const cell of expiryCells) {
      expect(cell.className).not.toContain("text-[var(--state-warning)]");
    }
  });

  it("PIN: formatDocType strips underscores on both the panel plaque and the history grid (M7)", () => {
    const currentDate = new Date(Date.now() + 500 * 86400000)
      .toISOString()
      .slice(0, 10);
    const historyDate = new Date(Date.now() - 5 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      {
        ...baseDoc,
        id: 54,
        document_type: "kitas_c317",
        expiry_date: currentDate,
      },
      {
        ...baseDoc,
        id: 55,
        document_type: "kitap_dependent",
        expiry_date: historyDate,
      },
    ]);

    expect(screen.getByText("kitas c317")).toBeInTheDocument();
    expect(screen.getByText("kitap dependent")).toBeInTheDocument();
  });

  it("PIN: an expired history row's date carries the expiry word, not just the date (M8)", () => {
    const currentDate = new Date(Date.now() + 500 * 86400000)
      .toISOString()
      .slice(0, 10);
    const expiredDate = new Date(Date.now() - 10 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      { ...baseDoc, id: 56, document_type: "kitas", expiry_date: currentDate },
      { ...baseDoc, id: 57, document_type: "kitap", expiry_date: expiredDate },
    ]);

    // R6c: same duplication — desktop Expires cell + phone block line.
    expect(screen.getAllByText(/Expired 10d ago/)).toHaveLength(2);
  });

  it("PIN: the current-permit panel shows the document's file_name (M9)", () => {
    const currentDate = new Date(Date.now() + 60 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      {
        ...baseDoc,
        id: 58,
        document_type: "kitas",
        expiry_date: currentDate,
        file_name: "synthetic-permit-scan.pdf",
      },
    ]);

    expect(screen.getByText("synthetic-permit-scan.pdf")).toBeInTheDocument();
  });

  it("PIN: the Visa history heading shows the real row count (M10)", () => {
    const currentDate = new Date(Date.now() + 500 * 86400000)
      .toISOString()
      .slice(0, 10);
    const h1 = new Date(Date.now() - 5 * 86400000).toISOString().slice(0, 10);
    const h2 = new Date(Date.now() - 15 * 86400000).toISOString().slice(0, 10);
    renderTab([
      { ...baseDoc, id: 59, document_type: "kitas", expiry_date: currentDate },
      { ...baseDoc, id: 60, document_type: "kitap", expiry_date: h1 },
      { ...baseDoc, id: 61, document_type: "visa", expiry_date: h2 },
    ]);

    expect(screen.getByText("Visa history")).toBeInTheDocument();
    expect(screen.getByText("(2)")).toBeInTheDocument();
  });

  it("PIN: family_member_name appears on a history row (M11)", () => {
    const currentDate = new Date(Date.now() + 500 * 86400000)
      .toISOString()
      .slice(0, 10);
    const historyDate = new Date(Date.now() - 5 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      { ...baseDoc, id: 62, document_type: "kitas", expiry_date: currentDate },
      {
        ...baseDoc,
        id: 63,
        document_type: "kitap",
        expiry_date: historyDate,
        family_member_name: "Synthetic Dependent",
      },
    ]);

    expect(screen.getByText(/Synthetic Dependent/)).toBeInTheDocument();
  });
});

describe("ImmigrationTab — days KPI numeral never carries a sign (R6 round 3, C1)", () => {
  it("PIN: the expiry KPI numeral renders the unsigned day count for a −10d fixture", () => {
    const pastExpiry = new Date(Date.now() - 10 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      { ...baseDoc, id: 80, document_type: "kitas", expiry_date: pastExpiry },
    ]);

    const caption = screen.getByText("Days past expiry");
    expect(caption.previousElementSibling?.textContent).toBe("10");
  });

  it("PIN: the elapsed-days KPI clamps to zero rather than a negative for a future issue_date", () => {
    const futureIssue = new Date(Date.now() + 5 * 86400000)
      .toISOString()
      .slice(0, 10);
    const expiry = new Date(Date.now() + 60 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      {
        ...baseDoc,
        id: 81,
        document_type: "kitas",
        issue_date: futureIssue,
        expiry_date: expiry,
      },
    ]);

    const caption = screen.getByText("Days on this permit");
    expect(caption.previousElementSibling?.textContent).toBe("00");
  });
});

describe("ImmigrationTab — Start Renewal navigates to the real target (R6 round 3, C2)", () => {
  it("PIN: the panel CTA calls router.push with the visa_renewal target for this client", () => {
    const soon = new Date(Date.now() + 45 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      { ...baseDoc, id: 90, document_type: "kitas", expiry_date: soon },
    ]);

    fireEvent.click(screen.getByRole("button", { name: /start renewal/i }));

    expect(push).toHaveBeenCalledWith(
      "/process/new?client_id=1&type=visa_renewal",
    );
  });

  it("PIN: a history row's CTA calls router.push with the same target", () => {
    const current = new Date(Date.now() + 400 * 86400000)
      .toISOString()
      .slice(0, 10);
    const expired = new Date(Date.now() - 10 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      { ...baseDoc, id: 91, document_type: "kitas", expiry_date: current },
      { ...baseDoc, id: 92, document_type: "kitas", expiry_date: expired },
    ]);

    fireEvent.click(
      screen.getByRole("button", { name: /start renewal for kitas/i }),
    );

    expect(push).toHaveBeenCalledWith(
      "/process/new?client_id=1&type=visa_renewal",
    );
  });
});

describe("ImmigrationTab — precise permit label (kita.balizero.com owner report: 'Permit: Visa' when the document is a KITAP)", () => {
  it("shows the backend-resolved permit_label instead of the raw generic document_type", () => {
    const futureDate = new Date(Date.now() + 60 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      {
        ...baseDoc,
        id: 200,
        document_type: "visa",
        expiry_date: futureDate,
        permit_family: "kitap",
        permit_label: "KITAP / ITAP — Permanent Stay Permit",
      },
    ]);

    expect(
      screen.getByText("KITAP / ITAP — Permanent Stay Permit"),
    ).toBeInTheDocument();
    expect(screen.queryByText("visa")).not.toBeInTheDocument();
  });

  it("GUILT: falls back to the raw document_type when the backend found no evidence for a family (never invents one)", () => {
    const futureDate = new Date(Date.now() + 60 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      {
        ...baseDoc,
        id: 201,
        document_type: "visa",
        expiry_date: futureDate,
        // no permit_label — backend had no evidence
      },
    ]);

    expect(screen.getByText("visa")).toBeInTheDocument();
  });

  it("shows the permit number and sponsor when the backend extracted them, and omits them when absent", () => {
    const futureDate = new Date(Date.now() + 60 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      {
        ...baseDoc,
        id: 202,
        document_type: "kitas",
        expiry_date: futureDate,
        permit_number: "TEST-0000",
        permit_sponsor: "Example Sponsor",
      },
    ]);

    expect(screen.getByText("TEST-0000")).toBeInTheDocument();
    expect(screen.getByText("Example Sponsor")).toBeInTheDocument();
  });

  it("GUILT: omits the permit-number and sponsor rows when the backend did not extract them", () => {
    const futureDate = new Date(Date.now() + 60 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      { ...baseDoc, id: 203, document_type: "kitas", expiry_date: futureDate },
    ]);

    expect(screen.queryByText("Permit no.")).not.toBeInTheDocument();
    expect(screen.queryByText("Sponsor")).not.toBeInTheDocument();
  });
});

describe("ImmigrationTab — MERP rides with the current permit, not 'Other' (owner report)", () => {
  it("GUILT: a document_type='MERP' companion document is NOT rendered in the Other section", () => {
    const futureDate = new Date(Date.now() + 60 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      { ...baseDoc, id: 210, document_type: "kitas", expiry_date: futureDate },
      {
        ...baseDoc,
        id: 211,
        document_type: "MERP",
        document_category: "immigration",
        permit_family: "merp",
      },
    ]);

    expect(screen.getByText("Current permit")).toBeInTheDocument();
    expect(screen.queryByText("Other")).not.toBeInTheDocument();
  });

  it("shows the MERP as a re-entry permit tied to the current permit card", () => {
    const futureDate = new Date(Date.now() + 60 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      { ...baseDoc, id: 212, document_type: "kitas", expiry_date: futureDate },
      {
        ...baseDoc,
        id: 213,
        document_type: "MERP",
        document_category: "immigration",
        permit_family: "merp",
        permit_label: "MERP — Multiple Exit Re-entry Permit",
      },
    ]);

    expect(
      screen.getByText("MERP — Multiple Exit Re-entry Permit"),
    ).toBeInTheDocument();
  });

  it("INNOCENCE: with no current permit, a MERP-only document still shows up under Other instead of disappearing", () => {
    renderTab([
      {
        ...baseDoc,
        id: 214,
        document_type: "MERP",
        document_category: "immigration",
        permit_family: "merp",
      },
    ]);

    expect(screen.queryByText("Current permit")).not.toBeInTheDocument();
    expect(screen.getByText("Other")).toBeInTheDocument();
  });
});

describe("ImmigrationTab — permit_family_label secondary line (owner correction: index leads, family is secondary)", () => {
  it("GUILT: shows the family label as a secondary line under the current-permit badge when it differs from the primary label", () => {
    const futureDate = new Date(Date.now() + 60 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      {
        ...baseDoc,
        id: 220,
        document_type: "visa",
        expiry_date: futureDate,
        permit_family: "kitas",
        permit_label: "E23 — Working KITAS",
        permit_family_label: "KITAS / ITAS — Limited Stay Permit",
      },
    ]);

    expect(screen.getByText("E23 — Working KITAS")).toBeInTheDocument();
    expect(
      screen.getByText("KITAS / ITAS — Limited Stay Permit"),
    ).toBeInTheDocument();
  });

  it("INNOCENCE: does not repeat the label when permit_family_label equals permit_label (no index was found)", () => {
    const futureDate = new Date(Date.now() + 60 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      {
        ...baseDoc,
        id: 221,
        document_type: "visa",
        expiry_date: futureDate,
        permit_family: "kitap",
        permit_label: "KITAP / ITAP — Permanent Stay Permit",
        permit_family_label: "KITAP / ITAP — Permanent Stay Permit",
      },
    ]);

    expect(
      screen.getAllByText("KITAP / ITAP — Permanent Stay Permit"),
    ).toHaveLength(1);
  });

  it("shows the family label in the visa-history row's secondary line when it differs from the primary label", () => {
    const futureDate = new Date(Date.now() + 400 * 86400000)
      .toISOString()
      .slice(0, 10);
    const pastDate = new Date(Date.now() - 60 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      {
        ...baseDoc,
        id: 222,
        document_type: "kitas",
        expiry_date: futureDate,
        permit_family: "kitas",
        permit_label: "KITAS / ITAS — Limited Stay Permit",
        permit_family_label: "KITAS / ITAS — Limited Stay Permit",
      },
      {
        ...baseDoc,
        id: 223,
        document_type: "visa",
        expiry_date: pastDate,
        permit_family: "itk",
        permit_label: "C31",
        permit_family_label: "ITK — Visit Stay Permit",
      },
    ]);

    expect(screen.getByText("Visa history")).toBeInTheDocument();
    expect(screen.getByText("C31")).toBeInTheDocument();
    expect(screen.getByText("ITK — Visit Stay Permit")).toBeInTheDocument();
  });
});

describe("ImmigrationTab — REWORK (independent gate, 2026-09-21)", () => {
  it("(a) GUILT: a document outside isVisaFamilyDocument (e.g. document_type='itk') still shows the resolved permit_label in the 'Other' card grid, not the raw document_type", () => {
    // 'itk' does not match isVisaFamilyDocument (no kitas/kitap/visa/voa
    // substring) so it lands in `otherDocs`, rendered by `renderDocCard` —
    // the prod bug: that card ignored permit_label entirely.
    renderTab([
      {
        ...baseDoc,
        id: 300,
        document_type: "itk",
        document_category: "immigration",
        permit_family: "itk",
        permit_label: "D12 — Pre-Investment (Multiple Entry)",
      },
    ]);

    expect(
      screen.getByText("D12 — Pre-Investment (Multiple Entry)"),
    ).toBeInTheDocument();
    expect(screen.queryByText("itk")).not.toBeInTheDocument();
  });

  it("(a) shows the family secondary line in the 'Other' card grid when it differs from the primary label", () => {
    renderTab([
      {
        ...baseDoc,
        id: 301,
        document_type: "itk",
        document_category: "immigration",
        permit_family: "itk",
        permit_label: "D12 — Pre-Investment (Multiple Entry)",
        permit_family_label: "ITK — Visit Stay Permit",
      },
    ]);

    expect(
      screen.getByText("D12 — Pre-Investment (Multiple Entry)"),
    ).toBeInTheDocument();
    expect(screen.getByText("ITK — Visit Stay Permit")).toBeInTheDocument();
  });

  it("(a) GUILT falls back to the raw document_type in the 'Other' grid when unresolved (never invents a label)", () => {
    renderTab([
      {
        ...baseDoc,
        id: 302,
        document_type: "itk",
        document_category: "immigration",
      },
    ]);
    expect(screen.getByText("itk")).toBeInTheDocument();
  });

  it("(b) does not apply text-transform:capitalize to a resolved permit_label in the current-permit badge", () => {
    const futureDate = new Date(Date.now() + 60 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      {
        ...baseDoc,
        id: 303,
        document_type: "visa",
        expiry_date: futureDate,
        permit_family: "kitas",
        permit_label:
          "E28D — Investor Visa Pendirian Cabang atau Anak Perusahaan Golden Visa",
      },
    ]);

    const badge = screen.getByText(
      "E28D — Investor Visa Pendirian Cabang atau Anak Perusahaan Golden Visa",
    );
    expect(badge.className).not.toMatch(/\bcapitalize\b/);
  });

  it("(b) GUILT: still applies capitalize to the raw document_type fallback in the current-permit badge", () => {
    const futureDate = new Date(Date.now() + 60 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      {
        ...baseDoc,
        id: 304,
        document_type: "voa",
        expiry_date: futureDate,
        // no permit_label — falls back to the raw document_type
      },
    ]);

    const badge = screen.getByText("voa");
    expect(badge.className).toMatch(/\bcapitalize\b/);
  });

  it("(b) does not apply text-transform:capitalize to a resolved permit_label in the 'Other' card grid", () => {
    renderTab([
      {
        ...baseDoc,
        id: 305,
        document_type: "itk",
        document_category: "immigration",
        permit_family: "itk",
        permit_label:
          "E28D — Investor Visa Pendirian Cabang atau Anak Perusahaan Golden Visa",
      },
    ]);

    const label = screen.getByText(
      "E28D — Investor Visa Pendirian Cabang atau Anak Perusahaan Golden Visa",
    );
    expect(label.className).not.toMatch(/\bcapitalize\b/);
  });

  it("(f) GUILT: a MERP document whose document_type is generic ('visa') never renders in BOTH the visa-history row and the MERP chip", () => {
    const futureDate = new Date(Date.now() + 400 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      {
        ...baseDoc,
        id: 310,
        document_type: "kitas",
        expiry_date: futureDate,
      },
      {
        ...baseDoc,
        id: 311,
        document_type: "visa",
        // No expiry_date on purpose: the MERP chip appends " · Exp ..."
        // whenever expiry_date is set, which would make the chip's own
        // text node no longer an EXACT match for the bare label and hide
        // a real double-render behind a text-matcher false negative.
        permit_family: "merp",
        permit_label: "MERP — Multiple Exit Re-entry Permit",
      },
    ]);

    expect(
      screen.getAllByText("MERP — Multiple Exit Re-entry Permit"),
    ).toHaveLength(1);
  });
});
