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

// JSX-specific guards (Button variant, icon-only aria-label) only make sense
// on ts/tsx; the colour/token guards (round-4 Q4) also walk .css so the CSS
// module cannot smuggle a literal or a banned alias past the scan.
const JSX_SOURCE_EXT = new Set([".ts", ".tsx"]);
const ALL_SOURCE_EXT = new Set([".ts", ".tsx", ".css"]);

function walkSourceFiles(dir: string, extSet: Set<string>): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      out.push(...walkSourceFiles(full, extSet));
      continue;
    }
    if (!entry.isFile()) continue;
    if (!extSet.has(extname(entry.name))) continue;
    if (entry.name.includes(".test.")) continue;
    if (full.includes(`${sep}__tests__${sep}`)) continue;
    out.push(full);
  }
  return out;
}

/** Strips `/* … *\/` block comments, and a `//` line comment ONLY when it
 * starts the line (optional leading whitespace, then `//`) — never a `//`
 * that appears mid-line. Round-4 Q5: the previous version stripped from ANY
 * `//` onward (guarded only against `://`), so a string literal that simply
 * CONTAINED `//` — e.g. `className="x // bg-[var(--bz-accent)]"` — had its
 * tail silently erased before the scan ever saw it, a bypass with no plant
 * required. Only stripping a line-leading `//` means a real trailing
 * comment is (safely) left in and scanned as if it were code — over-scan,
 * never under-scan, is the direction that cannot hide a real violation. */
function stripComments(src: string): string {
  return src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^[ \t]*\/\/.*$/gm, "");
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

const SOURCE_FILES = walkSourceFiles(DETAIL_DIR, JSX_SOURCE_EXT);
const ALL_SOURCE_FILES = walkSourceFiles(DETAIL_DIR, ALL_SOURCE_EXT);

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

// Round-4 Q7: the old check only asked "is there A variant prop, and is it
// not the literal string default" — which let `variant={someExpr}` through
// (an expression is not the literal "default", so `isDefaultLiteral` was
// false, and `hasVariant` was true) and let `variant="destructive"` through
// (present, non-default, but still a copper-adjacent shadcn fill this desk
// never wants). The allow-list below is closed: a Button's variant must be
// a STATIC string literal and must be one of exactly these four.
const VALID_STATIC_VARIANTS = new Set([
  "outline",
  "ghost",
  "secondary",
  "link",
]);

function staticVariantOf(tag: string): string | null {
  const m = tag.match(/variant\s*=\s*(["'`])([^"'`]*)\1/);
  return m ? m[2] : null;
}

describe("GLOB: no default-variant Button, static-literal variant only (R3a, tightened by round-4 Q7)", () => {
  it("every <Button ...> under [id]/** declares a static-literal variant from {outline, ghost, secondary, link}", () => {
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
          const variant = staticVariantOf(tag);
          if (!variant || !VALID_STATIC_VARIANTS.has(variant)) {
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
    expect(staticVariantOf(tag)).toBeNull();
  });

  it('GUILT: variant={cond ? "default" : "outline"} fails — a dynamic expression is not a static literal', () => {
    const fixture = '<Button variant={open ? "default" : "outline"}>';
    const tag = extractOpeningTag(fixture, 0);
    expect(staticVariantOf(tag)).toBeNull();
  });

  it('GUILT: variant="destructive" and variant="default" are both static literals, but neither is on the allow-list', () => {
    expect(
      VALID_STATIC_VARIANTS.has(
        staticVariantOf('<Button variant="destructive">')!,
      ),
    ).toBe(false);
    expect(
      VALID_STATIC_VARIANTS.has(staticVariantOf('<Button variant="default">')!),
    ).toBe(false);
  });

  it('INNOCENCE: variant="outline"/"ghost"/"secondary"/"link" are each accepted', () => {
    for (const v of ["outline", "ghost", "secondary", "link"]) {
      const tag = extractOpeningTag(`<Button variant="${v}" size="sm">`, 0);
      const variant = staticVariantOf(tag);
      expect(variant && VALID_STATIC_VARIANTS.has(variant)).toBe(true);
    }
  });
});

// Round-4 Q3: hue-parsing a literal to decide whether it "reads red" missed
// two whole classes of violation the review seats found on disk — an amber
// Tailwind utility (no literal at all to parse) and a template-built CSS
// var name (no colour token at all, just a string the guard couldn't see
// through). The blanket rule below is both stronger AND simpler: no raw
// colour literal of ANY hue is allowed under [id]/** — every colour must
// come from a named token — and no red/rose/orange/amber palette utility is
// allowed on any Tailwind colour-bearing prefix, regardless of what it is
// attached to. Round-4 Q4: this walk now includes `.css` (`ALL_SOURCE_FILES`).
const RAW_COLOR_LITERAL =
  /#[0-9a-fA-F]{3,4}\b|#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{8}\b|\b(?:rgba?|hsla?)\(/g;
const PALETTE_HUE_UTILITY =
  /\b(?:bg|text|border|from|via|to|ring|fill|stroke|outline|decoration|shadow|caret|divide|placeholder|accent)-(?:red|rose|orange|amber)-\d{2,3}\b/g;
const TEMPLATE_BUILT_VAR_NAME = /var\(--\$\{/g;

describe("GLOB: no red / no state-danger / no raw colour literal / no template-built var name (R3b, strengthened by round-4 Q3/Q4)", () => {
  it("no non-test file under [id]/** (ts/tsx/css) carries --state-danger, --bz-neon-purple, a raw colour literal, a red/rose/orange/amber palette utility, or a template-built CSS var name", () => {
    const offenders: string[] = [];
    for (const file of ALL_SOURCE_FILES) {
      const source = stripComments(readFileSync(file, "utf8"));
      const rel = file.replace(DETAIL_DIR, "");
      if (source.includes("--state-danger"))
        offenders.push(`${rel}: --state-danger`);
      if (source.includes("--bz-neon-purple"))
        offenders.push(`${rel}: --bz-neon-purple`);
      for (const m of source.matchAll(PALETTE_HUE_UTILITY))
        offenders.push(`${rel}: ${m[0]}`);
      for (const m of source.matchAll(RAW_COLOR_LITERAL))
        offenders.push(`${rel}: raw literal ${m[0]}`);
      for (const m of source.matchAll(TEMPLATE_BUILT_VAR_NAME))
        offenders.push(`${rel}: template-built var name (${m[0]}...)`);
    }
    expect(offenders, offenders.join("\n")).toEqual([]);
  });

  // These use String.prototype.match (never RegExp.prototype.test /
  // .toMatch on the shared module-level GLOBAL regex objects): a global
  // regex's `test()` advances `lastIndex` and leaves it advanced after a
  // MATCH, so calling `.toMatch(SAME_GLOBAL_REGEX)` across several
  // differently-sized fixture strings in sequence silently skips or
  // misses matches depending on call order. `String.prototype.match`
  // resets `lastIndex` to 0 both before and after running, so it is safe
  // to reuse the same exported pattern object here AND in the offender
  // scan above without cross-contamination.
  it("GUILT: a hex literal of ANY hue is caught, not just a red/copper one", () => {
    expect("color: #3b82f6;".match(RAW_COLOR_LITERAL)).not.toBeNull();
  });

  it("GUILT: an rgba()/hsla() literal of ANY hue is caught", () => {
    expect(
      'style={{ background: "rgba(59,130,246,0.12)" }}'.match(
        RAW_COLOR_LITERAL,
      ),
    ).not.toBeNull();
    expect(
      'style={{ background: "hsla(210,80%,50%,0.2)" }}'.match(
        RAW_COLOR_LITERAL,
      ),
    ).not.toBeNull();
  });

  it("GUILT: an amber/orange/rose/red Tailwind palette utility is caught on ANY listed prefix", () => {
    expect("text-amber-400".match(PALETTE_HUE_UTILITY)).not.toBeNull();
    expect("shadow-orange-500".match(PALETTE_HUE_UTILITY)).not.toBeNull();
    expect("from-rose-300".match(PALETTE_HUE_UTILITY)).not.toBeNull();
    expect("ring-red-600".match(PALETTE_HUE_UTILITY)).not.toBeNull();
  });

  it("GUILT: a template-built CSS var name is caught even with no colour literal in sight", () => {
    expect(
      "var(--${color}-500, #3b82f6)".match(TEMPLATE_BUILT_VAR_NAME),
    ).not.toBeNull();
  });

  it("INNOCENCE: emerald/blue/purple/indigo palette utilities are untouched — only red/rose/orange/amber are banned", () => {
    expect("text-emerald-400".match(PALETTE_HUE_UTILITY)).toBeNull();
    expect("text-blue-300".match(PALETTE_HUE_UTILITY)).toBeNull();
    expect("bg-purple-500/20".match(PALETTE_HUE_UTILITY)).toBeNull();
    expect("border-indigo-400/30".match(PALETTE_HUE_UTILITY)).toBeNull();
  });

  it("INNOCENCE: a named token (no literal, no template) trips neither check", () => {
    const line = 'style={{ color: "var(--state-warning)" }}';
    expect(line.match(RAW_COLOR_LITERAL)).toBeNull();
    expect(line.match(TEMPLATE_BUILT_VAR_NAME)).toBeNull();
  });

  it("GUILT: a // that does not start the line is left in by stripComments, so a bypass string still trips the scanner", () => {
    const fixture = 'className="x // bg-[var(--bz-accent)]"';
    expect(stripComments(fixture)).toContain("--bz-accent");
  });

  it("INNOCENCE: a real // comment that DOES start the line is stripped", () => {
    const fixture =
      "  // this prose mentions --bz-accent but is not code\nconst x = 1;";
    expect(stripComments(fixture)).not.toContain("--bz-accent");
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
    for (const file of ALL_SOURCE_FILES) {
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
// 3d. Destructive/icon-only controls announce themselves (round-4 Q6). The
// dedicated render proof lives in components/FamilyTab.test.tsx (the real,
// non-mocked component); this is the source-scan half — every <Button ...>
// or native <button ...> under [id]/** whose body renders a Trash2 or X
// icon must carry aria-label= on its OWN opening tag. Deliberately
// over-inclusive: a button with BOTH an icon and visible text (which
// already has an accessible name from the text) is still required to carry
// one — cheaper than teaching a source-text scan to tell "icon-only" apart
// from "icon-plus-text" apart, and never wrong to have both.
// ---------------------------------------------------------------------------

const ICON_OPENERS = ["<Button", "<button"];
const DESTRUCTIVE_ICONS = ["Trash2", "X"];

function findMatchingCloseTag(
  source: string,
  fromIdx: number,
  closeTagName: string,
): number {
  const idx = source.indexOf(closeTagName, fromIdx);
  return idx === -1 ? Math.min(source.length, fromIdx + 600) : idx;
}

describe("GLOB: destructive/icon-only controls carry an aria-label (Q6)", () => {
  it("every <Button>/<button> under [id]/** whose body renders a Trash2 or X icon has aria-label= on its own opening tag", () => {
    const offenders: string[] = [];
    for (const file of SOURCE_FILES) {
      const source = stripComments(readFileSync(file, "utf8"));
      const rel = file.replace(DETAIL_DIR, "");
      for (const opener of ICON_OPENERS) {
        const closeTagName = opener === "<Button" ? "</Button>" : "</button>";
        let idx = source.indexOf(opener);
        while (idx !== -1) {
          const after = source[idx + opener.length];
          if (after === undefined || /[\s/>]/.test(after)) {
            const tag = extractOpeningTag(source, idx);
            const bodyStart = idx + tag.length;
            const bodyEnd = findMatchingCloseTag(
              source,
              bodyStart,
              closeTagName,
            );
            const body = source.slice(bodyStart, bodyEnd);
            const hasDestructiveIcon = DESTRUCTIVE_ICONS.some((icon) =>
              new RegExp(`<${icon}[\\s/>]`).test(body),
            );
            if (hasDestructiveIcon && !/aria-label\s*=/.test(tag)) {
              offenders.push(
                `${rel}: ${tag.slice(0, 100).replace(/\s+/g, " ")}`,
              );
            }
          }
          idx = source.indexOf(opener, idx + opener.length);
        }
      }
    }
    expect(offenders, offenders.join("\n")).toEqual([]);
  });

  it("GUILT: an icon-only Trash2 button with no aria-label is what the pattern is built to catch", () => {
    const source =
      '<Button variant="ghost" size="icon" onClick={onDelete}>\n  <Trash2 className="w-4 h-4" />\n</Button>';
    const tag = extractOpeningTag(source, 0);
    const body = source.slice(tag.length, source.indexOf("</Button>"));
    expect(/<Trash2[\s/>]/.test(body)).toBe(true);
    expect(/aria-label\s*=/.test(tag)).toBe(false);
  });

  it("INNOCENCE: the same button WITH aria-label passes", () => {
    const source =
      '<Button variant="ghost" size="icon" onClick={onDelete} aria-label="Remove item">\n  <Trash2 className="w-4 h-4" />\n</Button>';
    const tag = extractOpeningTag(source, 0);
    expect(/aria-label\s*=/.test(tag)).toBe(true);
  });

  it("INNOCENCE: a button with neither icon carries no obligation", () => {
    const source =
      '<Button variant="outline" onClick={onSave}>\n  Save\n</Button>';
    const tag = extractOpeningTag(source, 0);
    const body = source.slice(tag.length, source.indexOf("</Button>"));
    expect(
      DESTRUCTIVE_ICONS.some((i) => new RegExp(`<${i}[\\s/>]`).test(body)),
    ).toBe(false);
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
