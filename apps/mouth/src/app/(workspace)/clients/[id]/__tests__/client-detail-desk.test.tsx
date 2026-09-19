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
import * as ts from "typescript";
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
vi.mock("../components/ActivityTab", () => ({
  ActivityTab: () => <div data-testid="ActivityTab" />,
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

// ---------------------------------------------------------------------------
// Round-7 — Codex R4 blocked the hand-written scanners a SECOND time:
//   (a) a regex literal like `/"/` earlier in a file has no notion of
//       "this quote is inside a regex, not a string" in a char-by-char
//       scanner that just toggles `inString` on every `"`/`'`/`` ` `` it
//       sees — so `/"/`'s quote desynchronises the parity, and a LATER
//       genuine string's `/* bg-red-500 *\/`-shaped substring gets stripped
//       as if it were a real comment.
//   (b) `variant\s*=` (even with the round-5 lookbehind) matches the TEXT
//       of a DIFFERENT attribute's string value — `title='variant="outline"'`
//       counts as "has a variant" to a scanner that cannot tell "this quote
//       character is inside an unrelated attribute's value" from "this is
//       the real `variant=` prop".
// Patching the regex a third time is a fix of a fix (CLAUDE.md builder
// contract §1: a fix-of-a-fix stops at depth 1). Both bugs are the SAME
// root cause — a hand-rolled scanner re-deriving what a real parser already
// knows for free — so the surface changes instead: every non-test .ts/.tsx
// under [id]/** is parsed with the TypeScript compiler API
// (`ts.createSourceFile`) and walked as a real AST. A RegularExpressionLiteral
// is its own token kind, never a string boundary — bug (a) is structurally
// impossible. A JSX attribute's NAME and its STRING VALUE are distinct AST
// nodes — bug (b) is structurally impossible: `title`'s string value is
// never mistaken for a `variant` attribute because the scan only ever reads
// the `.name` of an actual `JsxAttribute`, never greps attribute values for
// the substring "variant=". `.css` files have no regex literals (CSS syntax
// has none), so they keep a plain regex comment-strip for `/* … */` — that
// half of the old approach was never the bug and needs no AST.
// ---------------------------------------------------------------------------

/** Parses a REAL file's contents with the compiler API, using TSX mode for
 * `.tsx` (JSX-bearing) files and plain TS mode for `.ts` (constants/types/
 * utils, no JSX) files — the same distinction `JSX_SOURCE_EXT` already
 * draws for which files even get scanned for JSX. */
function parseSourceFile(filePath: string, source: string): ts.SourceFile {
  const scriptKind = filePath.endsWith(".tsx")
    ? ts.ScriptKind.TSX
    : ts.ScriptKind.TS;
  return ts.createSourceFile(
    filePath,
    source,
    ts.ScriptTarget.Latest,
    /* setParentNodes */ true,
    scriptKind,
  );
}

/** Parses a small in-test fixture STRING (guilt/innocence cases, never a
 * real file) — always TSX mode, since every fixture in this suite is a JSX
 * snippet. TypeScript's parser recovers gracefully from an intentionally
 * incomplete fragment (e.g. an opening tag with no matching close), so the
 * exact fixture strings this suite already had keep working unchanged. */
function parseFixture(source: string): ts.SourceFile {
  return ts.createSourceFile(
    "fixture.tsx",
    source,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  );
}

function lineOf(sf: ts.SourceFile, node: ts.Node): number {
  return ts.getLineAndCharacterOfPosition(sf, node.getStart(sf)).line + 1;
}

/** The static, literal `variant="…"` value of a Button-shaped opening tag —
 * `null` for anything else (missing, a dynamic expression, or a DIFFERENT
 * attribute like `data-variant`/`title` that merely contains the text
 * "variant="). Reads the JsxAttribute node named exactly `variant`, never a
 * text scan over the tag's source. */
function getStaticVariant(
  node: ts.JsxOpeningElement | ts.JsxSelfClosingElement,
  sf: ts.SourceFile,
): string | null {
  // A spread can supply `variant` at runtime whatever the literal says, so a
  // Button carrying one has no provable static variant (Codex R5).
  if (node.attributes.properties.some((p) => ts.isJsxSpreadAttribute(p))) {
    return null;
  }
  const variantAttr = node.attributes.properties.find(
    (p): p is ts.JsxAttribute =>
      ts.isJsxAttribute(p) && p.name.getText(sf) === "variant",
  );
  if (
    !variantAttr ||
    !variantAttr.initializer ||
    !ts.isStringLiteral(variantAttr.initializer)
  ) {
    return null;
  }
  return variantAttr.initializer.text;
}

/** Fixture-only convenience: parses a JSX snippet and returns the static
 * variant of its first opening/self-closing element (mirrors the old
 * `staticVariantOf(extractOpeningTag(fixture, 0))` two-step for every
 * existing guilt/innocence test, now as one AST call). */
function variantOfFixture(source: string): string | null {
  const sf = parseFixture(source);
  let found: ts.JsxOpeningElement | ts.JsxSelfClosingElement | null = null;
  function visit(node: ts.Node) {
    if (found) return;
    if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
      found = node;
      return;
    }
    ts.forEachChild(node, visit);
  }
  visit(sf);
  return found ? getStaticVariant(found, sf) : null;
}

/** Every `<Button ...>` in `sf` that lacks a static-literal variant from the
 * allow-list. `label` is the offender-report prefix (a relative file path
 * for a real file, or `"fixture"` for a guilt/innocence test). */
function findButtonVariantOffenses(sf: ts.SourceFile, label: string): string[] {
  const offenders: string[] = [];
  function visit(node: ts.Node) {
    if (
      (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) &&
      node.tagName.getText(sf) === "Button"
    ) {
      const variant = getStaticVariant(node, sf);
      if (!variant || !VALID_STATIC_VARIANTS.has(variant)) {
        offenders.push(
          `${label}:${lineOf(sf, node)}: ${node.getText(sf).slice(0, 120).replace(/\s+/g, " ")}`,
        );
      }
    }
    ts.forEachChild(node, visit);
  }
  visit(sf);
  return offenders;
}

/** True when `node` (or anything nested under it, JSX-expression-wrapped or
 * not) renders a `<Trash2 .../>`/`<X .../>`-shaped element. */
function hasDestructiveIconDescendant(
  node: ts.Node,
  sf: ts.SourceFile,
): boolean {
  if (ts.isJsxSelfClosingElement(node) || ts.isJsxOpeningElement(node)) {
    const name = node.tagName.getText(sf);
    if (name === "Trash2" || name === "X") return true;
  }
  let found = false;
  ts.forEachChild(node, (c) => {
    if (!found && hasDestructiveIconDescendant(c, sf)) found = true;
  });
  return found;
}

/** Every `<Button>`/`<button>` in `sf` whose children render a destructive
 * icon but whose OWN opening tag carries no `aria-label`. Self-closing
 * Buttons can never fail this (no children, so no icon can be inside). */
function findIconOnlyAriaLabelOffenses(
  sf: ts.SourceFile,
  label: string,
): string[] {
  const offenders: string[] = [];
  function visit(node: ts.Node) {
    if (ts.isJsxElement(node)) {
      const tagName = node.openingElement.tagName.getText(sf);
      if (tagName === "Button" || tagName === "button") {
        const hasIcon = node.children.some((c) =>
          hasDestructiveIconDescendant(c, sf),
        );
        if (hasIcon) {
          const hasAriaLabel = node.openingElement.attributes.properties.some(
            (p) => ts.isJsxAttribute(p) && p.name.getText(sf) === "aria-label",
          );
          if (!hasAriaLabel) {
            offenders.push(
              `${label}:${lineOf(sf, node.openingElement)}: ${node.openingElement
                .getText(sf)
                .slice(0, 100)
                .replace(/\s+/g, " ")}`,
            );
          }
        }
      }
    }
    ts.forEachChild(node, visit);
  }
  visit(sf);
  return offenders;
}

type TextHit = { line: number; text: string };

/** Collects the COOKED text of every node kind that can carry a colour
 * literal, a Tailwind utility name or a CSS var alias as DATA rather than
 * syntax: StringLiteral, NoSubstitutionTemplateLiteral, the head/middle/tail
 * literal chunks of a TemplateExpression, and JsxText. A comment is not a
 * node at all (excluded for free — there is no stripping step to fool), and
 * a RegularExpressionLiteral is its own token kind the walk never descends
 * into as if it were string content. */
function collectColorText(sf: ts.SourceFile): TextHit[] {
  const hits: TextHit[] = [];
  function push(node: ts.Node, text: string) {
    hits.push({ line: lineOf(sf, node), text });
  }
  function visit(node: ts.Node) {
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) {
      push(node, node.text);
    } else if (node.kind === ts.SyntaxKind.JsxText) {
      push(node, node.getText(sf));
    } else if (ts.isTemplateExpression(node)) {
      push(node.head, node.head.text);
      for (const span of node.templateSpans)
        push(span.literal, span.literal.text);
    }
    ts.forEachChild(node, visit);
  }
  visit(sf);
  return hits;
}

/** Structural replacement for the old `TEMPLATE_BUILT_VAR_NAME` regex
 * (`/var\(--\$\{/g`, matched against raw source text): true for any
 * TemplateExpression literal chunk that immediately precedes an
 * interpolation (its head, or a TemplateMiddle — never the final Tail,
 * which precedes no further `${…}`) and ends in `var(--` — i.e. the CSS
 * var's NAME itself, not just a value inside it, is template-built. */
function templateBuiltVarNameHits(sf: ts.SourceFile): TextHit[] {
  const hits: TextHit[] = [];
  function visit(node: ts.Node) {
    if (ts.isTemplateExpression(node)) {
      const parts = [node.head, ...node.templateSpans.map((s) => s.literal)];
      parts.forEach((lit, idx) => {
        if (idx === parts.length - 1) return; // the Tail precedes no `${`
        // `var(--state-${tone})` builds the name as surely as `var(--${x})`
        // does, and can land on --state-danger (Codex R5).
        if (/var\(--[\w-]*$/.test(lit.text)) {
          hits.push({ line: lineOf(sf, lit), text: lit.text });
        }
      });
    }
    ts.forEachChild(node, visit);
  }
  visit(sf);
  return hits;
}

/** Colour/token offenders for one REAL or FIXTURE .ts/.tsx source, via the
 * AST text collectors above — the same RAW_COLOR_LITERAL/PALETTE_HUE_UTILITY
 * patterns as before, now run against cooked node text instead of a
 * comment-stripped raw-text scan. */
function colorOffensesForTsSource(sf: ts.SourceFile, label: string): string[] {
  const offenders: string[] = [];
  for (const { line, text } of collectColorText(sf)) {
    if (text.includes("--state-danger"))
      offenders.push(`${label}:${line}: --state-danger`);
    if (text.includes("--bz-neon-purple"))
      offenders.push(`${label}:${line}: --bz-neon-purple`);
    for (const m of text.matchAll(PALETTE_HUE_UTILITY))
      offenders.push(`${label}:${line}: ${m[0]}`);
    for (const m of text.matchAll(RAW_COLOR_LITERAL))
      offenders.push(`${label}:${line}: raw literal ${m[0]}`);
  }
  for (const { line, text } of templateBuiltVarNameHits(sf)) {
    offenders.push(`${label}:${line}: template-built var name (${text}...)`);
  }
  return offenders;
}

/** Colour/token offenders for a `.css` source — CSS has no regex literals,
 * so a plain `/* … *\/` regex strip is safe (unlike the JS/TSX case, there
 * is no string-vs-regex ambiguity to get wrong), then the same text
 * assertions run on the whole remaining text (CSS has no AST here — a bare
 * `color: var(--state-danger)` is not inside any string node to collect). */
function colorOffensesForCssSource(source: string, label: string): string[] {
  const offenders: string[] = [];
  const stripped = source.replace(/\/\*[\s\S]*?\*\//g, "");
  if (stripped.includes("--state-danger"))
    offenders.push(`${label}: --state-danger`);
  if (stripped.includes("--bz-neon-purple"))
    offenders.push(`${label}: --bz-neon-purple`);
  for (const m of stripped.matchAll(PALETTE_HUE_UTILITY))
    offenders.push(`${label}: ${m[0]}`);
  for (const m of stripped.matchAll(RAW_COLOR_LITERAL))
    offenders.push(`${label}: raw literal ${m[0]}`);
  return offenders;
}

const COPPER_TOKEN_PATTERN =
  /--bz-accent\b|--bz-copper(?:-text)?\b|--accent(?!-)\b/g;

/** Copper-alias offenders for one REAL .ts/.tsx source, via the same
 * AST text collector — checked against the (file-scoped) allow-list. */
function copperOffensesForTsSource(
  sf: ts.SourceFile,
  label: string,
  allowed: { snippet: string }[],
): string[] {
  const offenders: string[] = [];
  for (const { line, text } of collectColorText(sf)) {
    if (!text.match(COPPER_TOKEN_PATTERN)) continue;
    if (allowed.some((e) => text.includes(e.snippet))) continue;
    offenders.push(`${label}:${line}: ${text.slice(0, 120)}`);
  }
  return offenders;
}

/** Copper-alias offenders for a `.css` source — line-based, same allow-list
 * contract, comments stripped with the plain (CSS-safe) block-comment regex. */
function copperOffensesForCssSource(
  source: string,
  label: string,
  allowed: { snippet: string }[],
): string[] {
  const offenders: string[] = [];
  const stripped = source.replace(/\/\*[\s\S]*?\*\//g, "");
  stripped.split("\n").forEach((line, i) => {
    if (!line.match(COPPER_TOKEN_PATTERN)) return;
    if (allowed.some((e) => line.includes(e.snippet))) return;
    offenders.push(`${label}:${i + 1}: ${line.trim().slice(0, 120)}`);
  });
  return offenders;
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

describe("GLOB: no default-variant Button, static-literal variant only (R3a, tightened by round-4 Q7, AST-based round-7)", () => {
  it("every <Button ...> under [id]/** declares a static-literal variant from {outline, ghost, secondary, link}", () => {
    const offenders: string[] = [];
    for (const file of SOURCE_FILES) {
      const rel = file.replace(DETAIL_DIR, "");
      const sf = parseSourceFile(file, readFileSync(file, "utf8"));
      offenders.push(...findButtonVariantOffenses(sf, rel));
    }
    expect(offenders, offenders.join("\n")).toEqual([]);
  });

  it("GUILT: a <Button> with no variant prop at all is what the pattern is built to catch", () => {
    expect(
      variantOfFixture('<Button size="sm" onClick={handleSend}>Send</Button>'),
    ).toBeNull();
  });

  it('GUILT: variant={cond ? "default" : "outline"} fails — a dynamic expression is not a static literal', () => {
    expect(
      variantOfFixture(
        '<Button variant={open ? "default" : "outline"}>Go</Button>',
      ),
    ).toBeNull();
  });

  it('GUILT: variant="destructive" and variant="default" are both static literals, but neither is on the allow-list', () => {
    expect(
      VALID_STATIC_VARIANTS.has(
        variantOfFixture('<Button variant="destructive">Go</Button>')!,
      ),
    ).toBe(false);
    expect(
      VALID_STATIC_VARIANTS.has(
        variantOfFixture('<Button variant="default">Go</Button>')!,
      ),
    ).toBe(false);
  });

  it('INNOCENCE: variant="outline"/"ghost"/"secondary"/"link" are each accepted', () => {
    for (const v of ["outline", "ghost", "secondary", "link"]) {
      const variant = variantOfFixture(
        `<Button variant="${v}" size="sm">Go</Button>`,
      );
      expect(variant && VALID_STATIC_VARIANTS.has(variant)).toBe(true);
    }
  });

  it('GUILT (round-5 M3): data-variant="outline" is a DIFFERENT prop and must not be read as a real variant', () => {
    expect(
      variantOfFixture('<Button data-variant="outline">Go</Button>'),
    ).toBeNull();
  });

  it('INNOCENCE (round-5 M3): a real variant="outline" still matches even with a data-variant on the same tag', () => {
    expect(
      variantOfFixture(
        '<Button data-variant="outline" variant="ghost">Go</Button>',
      ),
    ).toBe("ghost");
  });

  it("GUILT (round-7 Codex R4): title='variant=\"outline\"' is a DIFFERENT attribute's STRING VALUE, not a real variant prop — a text scan over the tag's source cannot tell those apart, an AST walk over actual JsxAttribute nodes can", () => {
    const sf = parseFixture(`<Button title='variant="outline"'>Go</Button>`);
    const offenders = findButtonVariantOffenses(sf, "fixture");
    expect(offenders.length).toBe(1);
    expect(
      variantOfFixture(`<Button title='variant="outline"'>Go</Button>`),
    ).toBeNull();
  });

  it('GUILT (Codex R5): a spread after variant="outline" can override it at runtime, so the Button fails', () => {
    const sf = parseFixture(
      `<Button variant="outline" {...buttonProps}>Go</Button>`,
    );
    expect(findButtonVariantOffenses(sf, "fixture").length).toBe(1);
  });

  it('INNOCENCE (round-7 Codex R4): a real variant="outline" still passes even sitting next to that title', () => {
    const sf = parseFixture(
      `<Button title='variant="outline"' variant="outline">Go</Button>`,
    );
    expect(findButtonVariantOffenses(sf, "fixture")).toEqual([]);
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
// Round-5 M4: case-insensitive (`RGB(1 2 3)` read the same as `rgb(...)`),
// and covers the modern CSS colour functions too — `hwb()`/`lab()`/`lch()`/
// `oklab()`/`oklch()`/`color()` are just as raw and un-token-able as
// `rgba()`, and none of them were in the old alternation.
const RAW_COLOR_LITERAL =
  /#[0-9a-fA-F]{3,4}\b|#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{8}\b|\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\(/gi;
const PALETTE_HUE_UTILITY =
  /\b(?:bg|text|border|from|via|to|ring|fill|stroke|outline|decoration|shadow|caret|divide|placeholder|accent)-(?:red|rose|orange|amber)-\d{2,3}\b/g;

describe("GLOB: no red / no state-danger / no raw colour literal / no template-built var name (R3b, strengthened by round-4 Q3/Q4, AST-based round-7)", () => {
  it("no non-test file under [id]/** (ts/tsx/css) carries --state-danger, --bz-neon-purple, a raw colour literal, a red/rose/orange/amber palette utility, or a template-built CSS var name", () => {
    const offenders: string[] = [];
    for (const file of ALL_SOURCE_FILES) {
      const rel = file.replace(DETAIL_DIR, "");
      const raw = readFileSync(file, "utf8");
      if (file.endsWith(".css")) {
        offenders.push(...colorOffensesForCssSource(raw, rel));
      } else {
        offenders.push(
          ...colorOffensesForTsSource(parseSourceFile(file, raw), rel),
        );
      }
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

  it("GUILT (round-5 M4): an UPPERCASE colour function is caught the same as lowercase", () => {
    expect("background: RGB(1 2 3);".match(RAW_COLOR_LITERAL)).not.toBeNull();
  });

  it("GUILT (round-5 M4): a modern CSS colour function (oklch/hwb/lab/lch/oklab/color) is caught", () => {
    expect("color: oklch(0.6 0.2 30);".match(RAW_COLOR_LITERAL)).not.toBeNull();
    expect("color: hwb(30 20% 10%);".match(RAW_COLOR_LITERAL)).not.toBeNull();
    expect("color: lab(50% 40 20);".match(RAW_COLOR_LITERAL)).not.toBeNull();
    expect("color: lch(50% 60 30);".match(RAW_COLOR_LITERAL)).not.toBeNull();
    expect(
      "color: oklab(0.5 0.1 0.05);".match(RAW_COLOR_LITERAL),
    ).not.toBeNull();
    expect(
      "color: color(display-p3 1 0 0);".match(RAW_COLOR_LITERAL),
    ).not.toBeNull();
  });

  it("GUILT: an amber/orange/rose/red Tailwind palette utility is caught on ANY listed prefix", () => {
    expect("text-amber-400".match(PALETTE_HUE_UTILITY)).not.toBeNull();
    expect("shadow-orange-500".match(PALETTE_HUE_UTILITY)).not.toBeNull();
    expect("from-rose-300".match(PALETTE_HUE_UTILITY)).not.toBeNull();
    expect("ring-red-600".match(PALETTE_HUE_UTILITY)).not.toBeNull();
  });

  it("GUILT: a template-built CSS var name is caught even with no colour literal in sight (now a structural AST check on the TemplateExpression head, round-7)", () => {
    const sf = parseFixture("const style = `var(--${color}-500)`;");
    expect(templateBuiltVarNameHits(sf)).not.toEqual([]);
  });

  it("GUILT (Codex R5): a PARTIALLY template-built var name like var(--state-${tone}) is caught too", () => {
    const sf = parseFixture("const style = `var(--state-${tone})`;");
    expect(templateBuiltVarNameHits(sf)).not.toEqual([]);
  });

  it("INNOCENCE (Codex R5): interpolating a VALUE inside a complete var name is not a built name", () => {
    const sf = parseFixture(
      "const style = `color-mix(in srgb, var(--tx-pure) ${pct}%, transparent)`;",
    );
    expect(templateBuiltVarNameHits(sf)).toEqual([]);
  });

  it("GUILT (round-7): the raw literal riding along in the SAME template's tail is still caught by the general text collector", () => {
    const sf = parseFixture("const style = `var(--${color}-500, #3b82f6)`;");
    expect(
      colorOffensesForTsSource(sf, "fixture").some((o) =>
        o.includes("#3b82f6"),
      ),
    ).toBe(true);
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
    const sf = parseFixture('const style = "var(--state-warning)";');
    expect(templateBuiltVarNameHits(sf)).toEqual([]);
  });

  it("GUILT (round-7): a regex literal like /\"/ earlier in the same file must not desynchronise string tracking — the old char-scanner treated its quote as a string delimiter and stripped a LATER genuine string's comment-shaped content; an AST has no such state to desync (Codex R4, replaces the round-5 M2 stripComments-specific fixture)", () => {
    const fixtureSrc =
      'const q = /"/;\nfunction Comp() {\n  return <div className="x /* bg-red-500 */">hi</div>;\n}';
    const sf = parseFixture(fixtureSrc);
    const offenders = colorOffensesForTsSource(sf, "fixture");
    expect(offenders.some((o) => o.includes("bg-red-500"))).toBe(true);
  });

  it("GUILT: a bypass string containing a `//`-shaped or `/* */`-shaped substring is STILL a plain string literal to the parser, never a comment — its content is collected and scanned like any other string", () => {
    const sf = parseFixture('<div className="x // bg-[var(--bz-accent)]" />');
    const hits = collectColorText(sf);
    expect(hits.some((h) => h.text.includes("--bz-accent"))).toBe(true);
  });

  it("INNOCENCE: a real // comment mentioning --bz-accent produces NO node at all — comments are not nodes, so there is nothing to collect or to fool", () => {
    const sf = parseFixture(
      "  // this prose mentions --bz-accent but is not code\nconst x = 1;",
    );
    const hits = collectColorText(sf);
    expect(hits.some((h) => h.text.includes("--bz-accent"))).toBe(false);
  });

  it("INNOCENCE: a real block comment mentioning bg-red-500 produces NO node at all either", () => {
    const sf = parseFixture(
      "/* this prose mentions bg-red-500 but is not code */\nconst x = 1;",
    );
    const hits = collectColorText(sf);
    expect(hits.some((h) => h.text.includes("bg-red-500"))).toBe(false);
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
    // `COPPER_TOKEN_PATTERN` (module scope, round-7) carries the same
    // `(?!-)` on the bare --accent branch — load-bearing: without it this
    // over-matches the PREFIX of a distinct, legitimate token like
    // `--accent-whatsapp` (WhatsApp brand green) or `--accent-foreground`
    // (scar family #3 — guard on the entity, never a substring).
    const offenders: string[] = [];
    for (const file of ALL_SOURCE_FILES) {
      const rel = file.replace(DETAIL_DIR, "").replace(/^[\\/]/, "");
      const allowed = ALLOW_LIST.filter((e) => e.file === rel);
      const raw = readFileSync(file, "utf8");
      if (file.endsWith(".css")) {
        offenders.push(...copperOffensesForCssSource(raw, rel, allowed));
      } else {
        offenders.push(
          ...copperOffensesForTsSource(
            parseSourceFile(file, raw),
            rel,
            allowed,
          ),
        );
      }
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

describe("GLOB: destructive/icon-only controls carry an aria-label (Q6, AST-based round-7)", () => {
  it("every <Button>/<button> under [id]/** whose body renders a Trash2 or X icon has aria-label= on its own opening tag", () => {
    const offenders: string[] = [];
    for (const file of SOURCE_FILES) {
      const rel = file.replace(DETAIL_DIR, "");
      const sf = parseSourceFile(file, readFileSync(file, "utf8"));
      offenders.push(...findIconOnlyAriaLabelOffenses(sf, rel));
    }
    expect(offenders, offenders.join("\n")).toEqual([]);
  });

  it("GUILT: an icon-only Trash2 button with no aria-label is what the pattern is built to catch", () => {
    const sf = parseFixture(
      '<Button variant="ghost" size="icon" onClick={onDelete}>\n  <Trash2 className="w-4 h-4" />\n</Button>',
    );
    expect(findIconOnlyAriaLabelOffenses(sf, "fixture")).not.toEqual([]);
  });

  it("INNOCENCE: the same button WITH aria-label passes", () => {
    const sf = parseFixture(
      '<Button variant="ghost" size="icon" onClick={onDelete} aria-label="Remove item">\n  <Trash2 className="w-4 h-4" />\n</Button>',
    );
    expect(findIconOnlyAriaLabelOffenses(sf, "fixture")).toEqual([]);
  });

  it("INNOCENCE: a button with neither icon carries no obligation", () => {
    const sf = parseFixture(
      '<Button variant="outline" onClick={onSave}>\n  Save\n</Button>',
    );
    expect(findIconOnlyAriaLabelOffenses(sf, "fixture")).toEqual([]);
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

// ---------------------------------------------------------------------------
// 9. Tax tab year selector — no page-level overflow at 390 (round-6)
// ---------------------------------------------------------------------------
//
// Round 6: with the Log panel open and the Tax tab active, YearSelector's row
// of 5 unwrapped year buttons pushed document.documentElement.scrollWidth
// past the 390px mandate (measured 443-448 vs clientWidth 390) — the flex
// row had no wrap allowance, so flexbox's default content-based min-width
// kept every button on one unbroken line and the header row's `justify-
// between` had nowhere to give. The cure is layout-only (flex-wrap on both
// the YearSelector wrapper and its button row, plus a flex-col -> sm:flex-
// row stack on the "Tax Overview" header row) — no colour, copy or handler
// changed. This pin reads TaxTab.tsx's raw source (same idiom as the
// `.tabActive`/`.tabBar` CSS-block checks above, applied to a .tsx source
// block instead of a .css rule) so a future edit that drops the wrap
// allowance goes red here before it ever reaches a browser capture.
describe("GLOB: YearSelector row wraps instead of overflowing at 390 (round-6)", () => {
  const taxTabSource = readFileSync(
    join(DETAIL_DIR, "components", "TaxTab.tsx"),
    "utf8",
  );

  it("the year-button row allows wrapping, not a forced single line", () => {
    const rowMatch = taxTabSource.match(
      /<div className="flex flex-wrap gap-1">\s*{years\.map/,
    );
    expect(
      rowMatch,
      "YearSelector's button row lost flex-wrap — it will force all 5 years onto one unbroken line and overflow at 390",
    ).toBeTruthy();
  });

  it("the YearSelector's own wrapper allows wrapping ahead of the Year: label", () => {
    const wrapMatch = taxTabSource.match(
      /<div className="flex items-center gap-2 flex-wrap">\s*<span className="text-sm text-\[var\(--bz-text-2\)\]">Year:/,
    );
    expect(
      wrapMatch,
      "YearSelector's outer wrapper lost flex-wrap ahead of the 'Year:' label",
    ).toBeTruthy();
  });

  it("the Tax Overview header row stacks below sm instead of forcing one row", () => {
    const headerMatch = taxTabSource.match(
      /<div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">/,
    );
    expect(
      headerMatch,
      "Tax Overview header row lost its flex-col -> sm:flex-row stacking allowance",
    ).toBeTruthy();
  });
});
