/**
 * K3b — /clients/[id] desk grammar (SAETTA-R19K window K3).
 *
 * Mocking follows `../ClientDetailClient.test.tsx` (same component, the
 * pre-existing file already has the full mock surface for every child tab
 * and modal) — this file adds the masthead/status/DOM-order/stamp/copper
 * checks the K3b spec asks for, without re-deriving anything K3a already
 * settled: `clientStatusTone` and `viewerIsNext` are imported from the row
 * model, not recomputed here.
 *
 * Fixtures are synthetic only — `Client 0412`, `client412@example.test`,
 * `staff@example.test`, `member-a@example.test` — never a real name, phone,
 * passport number or email (K3b spec §1).
 */
import { readdirSync, readFileSync } from "node:fs";
import { extname, join, sep } from "node:path";
import React from "react";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "@/lib/api";
import type { ClientProfile } from "@/lib/api/crm/crm.types";
import { clientStatusTone, viewerIsNext } from "../../client-row-model";

const {
  mockUpdateClient,
  mockSetClientCache,
  mockInvalidateClient,
  mockUseClientDetail,
  mockGetUserProfile,
  stableTimeline,
  stableSearchParams,
} = vi.hoisted(() => ({
  mockUpdateClient: vi.fn(),
  mockSetClientCache: vi.fn(),
  mockInvalidateClient: vi.fn(),
  mockUseClientDetail: vi.fn(),
  mockGetUserProfile: vi.fn(),
  stableTimeline: [],
  stableSearchParams: { get: vi.fn(() => null) },
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "412" }),
  useRouter: () => ({
    back: vi.fn(),
    push: vi.fn(),
    replace: vi.fn(),
  }),
  useSearchParams: () => stableSearchParams,
}));

vi.mock("@/lib/api", () => ({
  api: {
    getProfile: vi.fn().mockResolvedValue({
      email: "staff@example.test",
    }),
    getUserProfile: (...args: unknown[]) =>
      (mockGetUserProfile as (...a: unknown[]) => unknown)(...args),
    crm: {
      updateClient: mockUpdateClient,
      createInteraction: vi.fn(),
    },
  },
}));

vi.mock("@/hooks/useClientDetail", () => ({
  useClientDetail: mockUseClientDetail,
  useClientTimeline: () => ({ data: stableTimeline }),
  useDocumentCategories: () => ({ data: [] }),
  useClientBusinessStory: () => ({
    data: [],
    error: null,
    isLoading: false,
  }),
  useInvalidateClient: () => mockInvalidateClient,
  useSetClientCache: () => mockSetClientCache,
}));

vi.mock("@/hooks/useTeamMembers", () => ({
  useTeamMemberOptions: () => ({ options: [] }),
}));

vi.mock("@/lib/logger", () => ({
  logger: { error: vi.fn(), info: vi.fn(), warn: vi.fn(), debug: vi.fn() },
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("../components/OverviewTab", () => ({
  OverviewTab: () => <div data-testid="OverviewTab" />,
}));
vi.mock("../components/DocumentsTab", () => ({
  DocumentsTab: () => <div data-testid="DocumentsTab" />,
}));
vi.mock("../components/ProcessTab", () => ({
  ProcessTab: () => <div data-testid="ProcessTab" />,
}));
vi.mock("../components/FamilyTab", () => ({
  FamilyTab: () => <div data-testid="FamilyTab" />,
}));
vi.mock("../components/ImmigrationTab", () => ({
  ImmigrationTab: () => <div data-testid="ImmigrationTab" />,
}));
vi.mock("../components/CompanyTab", () => ({
  CompanyTab: () => <div data-testid="CompanyTab" />,
}));
vi.mock("../components/TaxTab", () => ({
  TaxTab: () => <div data-testid="TaxTab" />,
}));
vi.mock("../components/TimelineTab", () => ({
  TimelineTab: () => <div data-testid="TimelineTab" />,
}));
vi.mock("../components/WaTimelineTab", () => ({
  WaTimelineTab: () => <div data-testid="WaTimelineTab" />,
}));
vi.mock("../components/PortalMessages", () => ({
  PortalMessages: () => <div data-testid="PortalMessages" />,
}));
vi.mock("../components/BusinessStoryPanel", () => ({
  BusinessStoryPanel: () => <div data-testid="BusinessStoryPanel" />,
}));
vi.mock("../components/modals/EditClientModal", () => ({
  EditClientModal: () => null,
}));
vi.mock("../components/modals/AddFamilyMemberModal", () => ({
  AddFamilyMemberModal: () => null,
}));
vi.mock("../components/modals/EditFamilyMemberModal", () => ({
  EditFamilyMemberModal: () => null,
}));
vi.mock("../components/modals/AddDocumentModal", () => ({
  AddDocumentModal: () => null,
}));
vi.mock("../components/modals/EditDocumentModal", () => ({
  EditDocumentModal: () => null,
}));

// ---------------------------------------------------------------------------
// Fixtures — synthetic only
// ---------------------------------------------------------------------------

const VIEWER_EMAIL = "staff@example.test";
const OTHER_MEMBER = "member-a@example.test";

function makeProfile(
  overrides: {
    status?: "lead" | "active" | "completed" | "lost" | "inactive";
    assignedTo?: string;
    activePracticesCount?: number;
    companyName?: string;
  } = {},
): ClientProfile {
  const {
    status = "active",
    assignedTo,
    activePracticesCount = 0,
    companyName,
  } = overrides;
  return {
    client: {
      id: 412,
      uuid: "uuid-412",
      full_name: "Client 0412",
      email: "client412@example.test",
      status,
      client_type: "individual",
      assigned_to: assignedTo,
      company_name: companyName,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    },
    family_members: [],
    documents: [],
    expiry_alerts: [],
    practices: Array.from({ length: activePracticesCount }, (_, i) => ({
      id: 9000 + i,
      status: "on_process",
      practice_type_code: "SYNTHETIC",
      practice_type_name: "Synthetic Process",
    })),
    company_links: [],
    stats: {
      family_count: 0,
      documents_count: 0,
      practices_count: activePracticesCount,
      expired_count: 0,
      red_alerts: 0,
      yellow_alerts: 0,
    },
  };
}

function renderClient(profile: ClientProfile) {
  mockUseClientDetail.mockReturnValue({
    data: profile,
    isLoading: false,
    error: null,
  });
  return import("../ClientDetailClient").then(({ ClientDetailClient }) =>
    render(<ClientDetailClient taxConsultants={[]} />),
  );
}

// The file-based checks are located from the working directory, same
// pattern as `clients/__tests__/clients-desk.test.tsx` and
// `garuda-voa/r19.test.tsx` (`import.meta.url` is not a file URL here).
const DETAIL_DIR = join(
  process.cwd(),
  "src",
  "app",
  "(workspace)",
  "clients",
  "[id]",
);

beforeEach(() => {
  vi.clearAllMocks();
  mockGetUserProfile.mockReturnValue({ email: VIEWER_EMAIL });
  mockInvalidateClient.mockResolvedValue(undefined);
  mockUpdateClient.mockResolvedValue({});
});

// ---------------------------------------------------------------------------
// 1. Masthead — reference eyebrow, computed subtitle
// ---------------------------------------------------------------------------

describe("masthead", () => {
  it("renders the zero-padded reference eyebrow from client.id", async () => {
    await renderClient(makeProfile());
    expect(screen.getByText("CLIENT · #0412")).toBeInTheDocument();
  });

  it("appends the company name to the eyebrow only when the field is set", async () => {
    await renderClient(makeProfile({ companyName: "PT Contoh Abadi" }));
    expect(
      screen.getByText("CLIENT · #0412 · PT Contoh Abadi"),
    ).toBeInTheDocument();
  });

  it("GUILT: a fixture with no active practices renders NO subtitle sentence", async () => {
    // A regex on the expected WORDING (e.g. /processes are moving/) would
    // pass even if the subtitle were mutated to some OTHER always-on
    // string — this caught exactly that when mutation-tested. The
    // structural check below does not: Masthead renders `sentence ? <p>…
    // : null` as the title's very next sibling, so "no subtitle" is "the
    // <h1> has no next element" regardless of what text a bug might put
    // there instead.
    await renderClient(makeProfile({ activePracticesCount: 0 }));
    const heading = screen.getByRole("heading", {
      level: 1,
      name: "Client 0412",
    });
    expect(heading.nextElementSibling).toBeNull();
  });

  it("INNOCENCE: active practices produce a sentence, singular and plural both", async () => {
    await renderClient(makeProfile({ activePracticesCount: 1 }));
    expect(screen.getByText(/^1 process is moving\.$/)).toBeInTheDocument();
    cleanup();

    await renderClient(makeProfile({ activePracticesCount: 3 }));
    expect(screen.getByText(/^3 processes are moving\.$/)).toBeInTheDocument();
  });

  it("adds the ownership clause only when the viewer is next, never a count it cannot prove", async () => {
    await renderClient(
      makeProfile({
        activePracticesCount: 3,
        assignedTo: VIEWER_EMAIL,
        status: "active",
      }),
    );
    await waitFor(() => {
      expect(
        screen.getByText(
          "3 processes are moving; this record needs your action.",
        ),
      ).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// 2. Status → tone, everywhere
// ---------------------------------------------------------------------------

describe("status tone", () => {
  it("lost and inactive are NOT the same tone as completed", () => {
    expect(clientStatusTone("lost")).not.toBe(clientStatusTone("completed"));
    expect(clientStatusTone("inactive")).not.toBe(
      clientStatusTone("completed"),
    );
    expect(clientStatusTone("lost")).toBe(clientStatusTone("inactive"));
  });

  it("the status trigger's colour is wired from clientStatusTone, not a second map", async () => {
    await renderClient(makeProfile({ status: "completed" }));
    const completedTrigger = screen.getByRole("button", {
      name: "Change client status",
    });
    expect(completedTrigger.className).toContain("state-success");
    cleanup();

    await renderClient(makeProfile({ status: "lost" }));
    const lostTrigger = screen.getByRole("button", {
      name: "Change client status",
    });
    expect(lostTrigger.className).toContain("tx-secondary");
    expect(lostTrigger.className).not.toContain("state-success");
  });

  it("every status option in the menu is a real StatePill (aria-pressed button), one per status", async () => {
    const user = userEvent.setup();
    await renderClient(makeProfile({ status: "active" }));

    await user.click(
      screen.getByRole("button", { name: "Change client status" }),
    );

    const options = ["lead", "active", "completed", "lost", "inactive"].map(
      (s) => screen.getByRole("button", { name: s }),
    );
    expect(options).toHaveLength(5);
    options.forEach((opt) => expect(opt).toHaveAttribute("aria-pressed"));
    expect(screen.getByRole("button", { name: "active" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: "lost" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });
});

// ---------------------------------------------------------------------------
// 3. GLOB guards (K3b C6-round-3 / R3). Round 2's list-based guards let R1/R2
// (ClientDetailClient.tsx L492/L867) slip through because they were not on
// the list. These walk the WHOLE [id]/** tree (readdirSync recursive) so a
// future file is covered automatically, and strip comments first (so a
// docstring mentioning a token does not trip the guard, and so a token
// hidden inside a `//` comment does not silently pass it either).
// ---------------------------------------------------------------------------

const NON_TEST_SOURCE_EXT = new Set([".ts", ".tsx"]);

function walkSourceFiles(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      out.push(...walkSourceFiles(full));
      continue;
    }
    if (!entry.isFile()) continue;
    if (!NON_TEST_SOURCE_EXT.has(extname(entry.name))) continue;
    if (entry.name.includes(".test.")) continue;
    if (full.includes(`${sep}__tests__${sep}`)) continue;
    out.push(full);
  }
  return out;
}

/** Strips `/* … *\/` block comments and `//` line comments — but NOT `://`
 * (so `https://wa.me/...` inside a template literal is left intact). Good
 * enough for TSX source; this file has no `//` inside a string that isn't
 * part of a URL. */
function stripComments(src: string): string {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|[^:])\/\/.*$/gm, "$1");
}

/** Extracts one JSX opening tag starting at `startIdx` (which must point at
 * `<`), tracking `{}` depth and string state so a `>` inside an attribute
 * expression (e.g. `onClick={() => a > b}`) or a string is never mistaken
 * for the tag's own close. */
function extractOpeningTag(src: string, startIdx: number): string {
  let i = startIdx;
  let depth = 0;
  let inString: string | null = null;
  while (i < src.length) {
    const c = src[i];
    if (inString) {
      if (c === "\\") {
        i += 2;
        continue;
      }
      if (c === inString) inString = null;
      i++;
      continue;
    }
    if (c === '"' || c === "'" || c === "`") {
      inString = c;
      i++;
      continue;
    }
    if (c === "{") {
      depth++;
      i++;
      continue;
    }
    if (c === "}") {
      depth--;
      i++;
      continue;
    }
    if (depth === 0 && c === ">") {
      return src.slice(startIdx, i + 1);
    }
    i++;
  }
  return src.slice(startIdx, Math.min(src.length, startIdx + 500));
}

function parseColor(token: string): { r: number; g: number; b: number } | null {
  let m = token.match(/rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)/);
  if (m) return { r: +m[1], g: +m[2], b: +m[3] };
  m = token.match(/^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b/);
  if (m) {
    let hex = m[1];
    if (hex.length === 3)
      hex = hex
        .split("")
        .map((c) => c + c)
        .join("");
    const num = parseInt(hex, 16);
    return { r: (num >> 16) & 255, g: (num >> 8) & 255, b: num & 255 };
  }
  return null;
}

/** Red AND copper both live in the same warm hue band (copper measures
 * H≈11°, memory 2026-09-14 / this window's own browser capture) — a single
 * hue check catches a raw literal standing in for either, which is the
 * whole point: a guard reading only `--bz-copper` text misses a hex that
 * resolves to the identical colour. */
function isRedOrCopperHue(c: { r: number; g: number; b: number }): boolean {
  const r = c.r / 255,
    g = c.g / 255,
    b = c.b / 255;
  const max = Math.max(r, g, b),
    min = Math.min(r, g, b);
  const l = (max + min) / 2;
  if (max === min) return false;
  const d = max - min;
  const s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
  let h: number;
  switch (max) {
    case r:
      h = ((g - b) / d + (g < b ? 6 : 0)) * 60;
      break;
    case g:
      h = ((b - r) / d + 2) * 60;
      break;
    default:
      h = ((r - g) / d + 4) * 60;
  }
  const hueDist = Math.min(Math.abs(h - 0), 360 - Math.abs(h - 0));
  return hueDist <= 20 && s * 100 > 35;
}

const SOURCE_FILES = walkSourceFiles(DETAIL_DIR);

describe("GLOB: active tab is ink, not ownership (K3b C1)", () => {
  it("the .tabActive rule carries no copper/accent var and paints ink", () => {
    const css = readFileSync(
      join(DETAIL_DIR, "client-detail-desk.module.css"),
      "utf8",
    );
    const match = css.match(/\.tabActive\s*{([^}]*)}/);
    expect(match, ".tabActive block not found").toBeTruthy();
    const block = match![1];
    expect(block, ".tabActive still references copper/accent").not.toMatch(
      /--bz-copper|--bz-accent/,
    );
    expect(block, ".tabActive does not use the ink token").toMatch(/--tx-pure/);
  });
});

describe("GLOB: no default-variant Button (R3a)", () => {
  it("every <Button ...> under [id]/** declares an explicit, non-default variant", () => {
    const offenders: string[] = [];
    for (const file of SOURCE_FILES) {
      const source = stripComments(readFileSync(file, "utf8"));
      let idx = source.indexOf("<Button");
      while (idx !== -1) {
        // Only a JSX tag boundary (`<Button` followed by whitespace, `>` or
        // `/`), not e.g. `<ButtonGroup`.
        const after = source[idx + 7];
        if (after === undefined || /[\s/>]/.test(after)) {
          const tag = extractOpeningTag(source, idx);
          const hasVariant = /variant\s*=/.test(tag);
          const isDefaultLiteral = /["'`]default["'`]/.test(tag);
          if (!hasVariant || isDefaultLiteral) {
            offenders.push(
              `${file.replace(DETAIL_DIR, "")}: ${tag.slice(0, 120).replace(/\s+/g, " ")}`,
            );
          }
        }
        idx = source.indexOf("<Button", idx + 7);
      }
    }
    expect(offenders, offenders.join("\n")).toEqual([]);
  });

  it("GUILT: a <Button> with no variant prop at all is what the pattern is built to catch", () => {
    const fixture = '<Button\n  size="sm"\n  onClick={handleSend}\n>';
    const tag = extractOpeningTag(fixture, 0);
    expect(/variant\s*=/.test(tag)).toBe(false);
  });

  it('GUILT: variant={cond ? "default" : "outline"} is caught by the literal-default check even though variant= IS present', () => {
    const fixture = '<Button variant={open ? "default" : "outline"}>';
    const tag = extractOpeningTag(fixture, 0);
    expect(/variant\s*=/.test(tag)).toBe(true);
    expect(/["'`]default["'`]/.test(tag)).toBe(true);
  });
});

describe("GLOB: no red / no state-danger / no raw red-or-copper literal (R3b)", () => {
  it("no file under [id]/** carries --state-danger, --bz-neon-purple, a red-N utility, or a raw red/copper rgba()/hex", () => {
    const offenders: string[] = [];
    for (const file of SOURCE_FILES) {
      const source = stripComments(readFileSync(file, "utf8"));
      const rel = file.replace(DETAIL_DIR, "");
      if (source.includes("--state-danger"))
        offenders.push(`${rel}: --state-danger`);
      if (source.includes("--bz-neon-purple"))
        offenders.push(`${rel}: --bz-neon-purple`);
      const redUtil = source.match(/\b(?:bg|text|border)-red-\d/);
      if (redUtil) offenders.push(`${rel}: ${redUtil[0]}`);
      const colorTokens =
        source.match(/(?:rgba?\([^)]*\)|#[0-9a-fA-F]{3,6}\b)/g) || [];
      for (const tok of colorTokens) {
        const c = parseColor(tok);
        if (c && isRedOrCopperHue(c)) offenders.push(`${rel}: raw ${tok}`);
      }
    }
    expect(offenders, offenders.join("\n")).toEqual([]);
  });

  it("GUILT: a raw copper hex literal is caught by the hue check even with no token name at all", () => {
    const c = parseColor("#a44b36");
    expect(c).toBeTruthy();
    expect(isRedOrCopperHue(c!)).toBe(true);
  });

  it("GUILT: a raw danger-red rgba() is caught the same way", () => {
    const c = parseColor("rgba(239,68,68,0.10)");
    expect(c).toBeTruthy();
    expect(isRedOrCopperHue(c!)).toBe(true);
  });

  it("INNOCENCE: an unrelated blue does not trip the hue check", () => {
    const c = parseColor("rgba(59,130,246,0.12)");
    expect(c).toBeTruthy();
    expect(isRedOrCopperHue(c!)).toBe(false);
  });
});

describe("GLOB: copper only by an explicit, verified allow-list (R3c)", () => {
  // Each entry names the file (relative to DETAIL_DIR) and a UNIQUE
  // substring of the actual gated line. If the substring stops matching
  // (the line moved or was rewritten) the entry is stale and the test
  // fails loudly instead of silently exempting whatever replaced it.
  //
  // This list is EMPTY: within [id]/** there is no line that spells
  // --bz-accent/--bz-copper/--bz-copper-text/--accent literally and is
  // ownership-gated. The one real gated mark is
  // `<Stamp tone="copper" owned={needsViewerAction} />` — it names the r19
  // primitive and the predicate, never the CSS var (the var lives inside
  // `components/workspace/r19/Stamp.tsx`, which this window does not
  // touch and this walk does not scan).
  const ALLOW_LIST: { file: string; snippet: string }[] = [];

  it("every allow-list entry still matches its file verbatim (stale entries must not silently exempt)", () => {
    for (const { file, snippet } of ALLOW_LIST) {
      const source = readFileSync(join(DETAIL_DIR, file), "utf8");
      expect(
        source,
        `allow-list entry for ${file} no longer matches: "${snippet}"`,
      ).toContain(snippet);
    }
  });

  it("--bz-accent/--bz-copper/--bz-copper-text/--accent occur ONLY at allow-listed lines", () => {
    // `(?!-)` on the bare --accent branch is load-bearing: without it this
    // over-matches the PREFIX of a distinct, legitimate token like
    // `--accent-whatsapp` (WhatsApp brand green) or `--accent-foreground`
    // (scar family #3 — guard on the entity, never a substring).
    const tokenPattern =
      /--bz-accent\b|--bz-copper(?:-text)?\b|--accent(?!-)\b/g;
    const offenders: string[] = [];
    for (const file of SOURCE_FILES) {
      const rel = file.replace(DETAIL_DIR, "").replace(/^[\\/]/, "");
      const allowed = ALLOW_LIST.filter((e) => e.file === rel);
      const source = stripComments(readFileSync(file, "utf8"));
      const lines = source.split("\n");
      lines.forEach((line, i) => {
        if (!tokenPattern.test(line)) return;
        tokenPattern.lastIndex = 0;
        if (allowed.some((e) => line.includes(e.snippet))) return;
        offenders.push(`${rel}:${i + 1}: ${line.trim().slice(0, 120)}`);
      });
    }
    expect(offenders, offenders.join("\n")).toEqual([]);
  });

  it("GUILT: an --bz-accent hover border planted in a fixture string is caught by the same pattern", () => {
    const fixture = 'hover:border-[var(--bz-accent)]/50"';
    expect(fixture).toMatch(/--bz-accent\b/);
  });

  it("INNOCENCE: --accent-whatsapp/--accent-foreground are distinct tokens and do not trip the bare --accent check", () => {
    const tokenPattern =
      /--bz-accent\b|--bz-copper(?:-text)?\b|--accent(?!-)\b/;
    expect("text-[var(--accent-whatsapp)]").not.toMatch(tokenPattern);
    expect("var(--accent-foreground)").not.toMatch(tokenPattern);
    expect("var(--accent)").toMatch(tokenPattern);
  });

  it("INNOCENCE: the owned Stamp call site carries the ownership predicate, never the literal copper token", () => {
    const source = readFileSync(
      join(DETAIL_DIR, "ClientDetailClient.tsx"),
      "utf8",
    );
    expect(source).toMatch(
      /<Stamp tone="copper" owned={needsViewerAction} \/>/,
    );
    expect(source).not.toMatch(/--bz-copper\b/);
    expect(source).not.toMatch(/--bz-accent\b/);
  });
});

// ---------------------------------------------------------------------------
// 3d. Sticky tab bar (K3b C4) — stays reachable while a long tab scrolls
// ---------------------------------------------------------------------------

describe("sticky tab bar", () => {
  it("the tab bar is sticky under the header, on an opaque page background", () => {
    const css = readFileSync(
      join(DETAIL_DIR, "client-detail-desk.module.css"),
      "utf8",
    );
    const match = css.match(/\.tabBar\s*{([^}]*)}/);
    expect(match, ".tabBar block not found").toBeTruthy();
    const block = match![1];
    expect(block, "tabBar is not position: sticky").toMatch(
      /position:\s*sticky/,
    );
    expect(block, "tabBar top is not pinned to the header height").toMatch(
      /top:\s*var\(--bz-header-height/,
    );
    expect(block, "tabBar has no opaque background").toMatch(
      /background:\s*var\(--bz-base\)/,
    );
  });

  it("no ancestor inside this module sets overflow — only the tab bar's own horizontal scroll may (sticky needs the viewport as scroll container, concept.md §6)", () => {
    const css = readFileSync(
      join(DETAIL_DIR, "client-detail-desk.module.css"),
      "utf8",
    );
    // Strip comments first — the module's own docstring narrates the
    // overflow law in prose ("Sticky heads fail if any ancestor gains
    // overflow…"), which would otherwise false-positive this check.
    const withoutComments = css.replace(/\/\*[\s\S]*?\*\//g, "");
    const withoutTabBarRule = withoutComments.replace(/\.tabBar\s*{[^}]*}/, "");
    expect(withoutTabBarRule).not.toMatch(/overflow/);
  });
});

// ---------------------------------------------------------------------------
// 4. "Where it stands" is first in the DOM
// ---------------------------------------------------------------------------

describe("DOM order", () => {
  it("the status column precedes the tab bar in document order", async () => {
    await renderClient(makeProfile({ activePracticesCount: 1 }));
    const statusColumn = screen.getByTestId("status-column");
    const tabBar = screen.getByTestId("tab-bar");
    // DOCUMENT_POSITION_FOLLOWING (4): tabBar comes AFTER statusColumn.
    // jsdom applies no layout/CSS, so this is honestly a DOM-order check —
    // the visual "moved right on desktop" is the CSS module's `order`,
    // proven by inspection, not by a jsdom assertion that would always pass.
    expect(
      statusColumn.compareDocumentPosition(tabBar) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// 5. Stamp binds to a timestamp, and to nothing else
// ---------------------------------------------------------------------------

describe("stamp", () => {
  it("Client has no review timestamp field, so no forest 'Reviewed' stamp ever renders", async () => {
    await renderClient(
      makeProfile({ status: "active", assignedTo: VIEWER_EMAIL }),
    );
    expect(screen.queryByText(/Reviewed/)).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 6. Copper — derived ownership only
// ---------------------------------------------------------------------------

describe("copper ownership", () => {
  it("a client assigned to the viewer and non-terminal shows the copper mark", async () => {
    const owned = makeProfile({ status: "active", assignedTo: VIEWER_EMAIL });
    expect(viewerIsNext(owned.client, VIEWER_EMAIL)).toBe(true);

    await renderClient(owned);
    await waitFor(() => {
      expect(screen.getByText("Needs you")).toBeInTheDocument();
    });
  });

  it("the SAME client completed does not (DISPOSITION F15)", async () => {
    const terminal = makeProfile({
      status: "completed",
      assignedTo: VIEWER_EMAIL,
    });
    expect(viewerIsNext(terminal.client, VIEWER_EMAIL)).toBe(false);

    await renderClient(terminal);
    await waitFor(() => {
      expect(mockGetUserProfile).toHaveBeenCalled();
    });
    expect(screen.queryByText("Needs you")).not.toBeInTheDocument();
  });

  it("a client assigned to someone else never shows the viewer's copper mark", async () => {
    await renderClient(
      makeProfile({ status: "active", assignedTo: OTHER_MEMBER }),
    );
    await waitFor(() => {
      expect(mockGetUserProfile).toHaveBeenCalled();
    });
    expect(screen.queryByText("Needs you")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 7. Viewer email — sync cache first, one async fallback, silent failure
//    (round-3 R5: the cache-only read used to leave the viewer permanently
//    "unknown" whenever `getUserProfile()` missed, even though a fresh
//    `getProfile()` call would have found it.)
// ---------------------------------------------------------------------------

describe("viewer email — async fallback on a cache miss (R5)", () => {
  it("cache miss + getProfile resolves: the copper mark renders from the async email", async () => {
    mockGetUserProfile.mockReturnValue(null);
    vi.mocked(api.getProfile).mockResolvedValueOnce({
      email: VIEWER_EMAIL,
    } as Awaited<ReturnType<typeof api.getProfile>>);

    await renderClient(
      makeProfile({ status: "active", assignedTo: VIEWER_EMAIL }),
    );

    await waitFor(() => {
      expect(screen.getByText("Needs you")).toBeInTheDocument();
    });
  });

  it("cache miss + getProfile rejects: no throw, viewer stays unknown, no copper mark", async () => {
    mockGetUserProfile.mockReturnValue(null);
    vi.mocked(api.getProfile).mockRejectedValueOnce(new Error("network down"));

    await renderClient(
      makeProfile({ status: "active", assignedTo: VIEWER_EMAIL }),
    );

    await waitFor(() => {
      expect(api.getProfile).toHaveBeenCalled();
    });
    expect(screen.queryByText("Needs you")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 8. Status trigger — a real disclosure control (round-3 R6)
// ---------------------------------------------------------------------------

describe("status trigger button — disclosure semantics (R6)", () => {
  it("is type=button, announces menu popup, and aria-expanded flips with the menu", async () => {
    const user = userEvent.setup();
    await renderClient(
      makeProfile({ status: "active", assignedTo: VIEWER_EMAIL }),
    );

    const trigger = screen.getByRole("button", {
      name: "Change client status",
    });
    expect(trigger).toHaveAttribute("type", "button");
    expect(trigger).toHaveAttribute("aria-haspopup", "menu");
    expect(trigger).toHaveAttribute("aria-expanded", "false");

    await user.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");

    await user.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "false");
  });
});
