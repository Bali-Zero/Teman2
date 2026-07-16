import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { KBLIYoullAlsoNeed } from "./KBLIYoullAlsoNeed";

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    className,
  }: {
    children: React.ReactNode;
    href: string;
    className?: string;
  }) => (
    <a href={href} className={className}>
      {children}
    </a>
  ),
}));

// Mirrors getCode()'s existence check the component calls per code — only
// codes in this set resolve to a link, everything else falls back to a
// plain (unlinked) span, same as a real KBLI code missing from the dataset.
const EXISTING_CODES = new Set(["01310", "01131", "56303", "47111"]);

vi.mock("@/lib/kbli-data", () => ({
  getCode: (code: string) =>
    EXISTING_CODES.has(code) ? { code } : undefined,
}));

describe("KBLIYoullAlsoNeed", () => {
  // Guilt: the real bullet formats found in a census of
  // apps/mouth/data/kbli-gold-all.json's `youllAlsoNeed` field — bold-only
  // ("- **CODE**", the dominant format, 871/1404 bullets), bold-with-desc
  // ("- **CODE** — desc", 264/1404), and plain-with-desc using either an
  // em-dash or a hyphen separator (268/1404 em-dash; hyphen kept for
  // backward compat with the pre-fix regex).
  describe("guilt — real bullet formats get their code linked", () => {
    it("links a bold-only code (- **CODE**)", () => {
      render(<KBLIYoullAlsoNeed text="- **01310**" />);
      const link = screen.getByRole("link", { name: "01310" });
      expect(link).toHaveAttribute("href", "/kbli/01310");
    });

    it("links a bold code followed by an em-dash description (- **CODE** — desc)", () => {
      render(
        <KBLIYoullAlsoNeed text="- **01131** — Related business activity" />,
      );
      const link = screen.getByRole("link", { name: "01131" });
      expect(link).toHaveAttribute("href", "/kbli/01131");
      expect(
        screen.getByText("Related business activity"),
      ).toBeInTheDocument();
    });

    it("links a plain code followed by an em-dash description (- CODE — desc)", () => {
      render(
        <KBLIYoullAlsoNeed text="- 56303 — If you run a tasting room or chocolate café" />,
      );
      const link = screen.getByRole("link", { name: "56303" });
      expect(link).toHaveAttribute("href", "/kbli/56303");
      expect(
        screen.getByText("If you run a tasting room or chocolate café"),
      ).toBeInTheDocument();
    });

    it("links a plain code followed by a hyphen description (- CODE - desc)", () => {
      render(
        <KBLIYoullAlsoNeed text="- 47111 - Retail sale in non-specialized stores" />,
      );
      const link = screen.getByRole("link", { name: "47111" });
      expect(link).toHaveAttribute("href", "/kbli/47111");
      expect(
        screen.getByText("Retail sale in non-specialized stores"),
      ).toBeInTheDocument();
    });

    it("renders a multi-bullet list (the shape every youllAlsoNeed entry actually uses) independently per line", () => {
      render(
        <KBLIYoullAlsoNeed text={"- **01310**\n- **01401**\n- **46201**"} />,
      );
      expect(screen.getByRole("link", { name: "01310" })).toHaveAttribute(
        "href",
        "/kbli/01310",
      );
      // 01401 / 46201 aren't in EXISTING_CODES, so they degrade to a plain
      // span (existence-check behavior below) rather than a link — still
      // correctly detected and unmangled.
      expect(screen.getByText("01401")).toBeInTheDocument();
      expect(screen.getByText("46201")).toBeInTheDocument();
      expect(screen.getAllByRole("link")).toHaveLength(1);
    });
  });

  // Preserve existing behavior: a well-formed code that doesn't exist in the
  // dataset must still render (as plain text, not a link) — the fix only
  // touches detection, never the existence-gated link/span choice.
  describe("existence check preserved — a detected code absent from the dataset stays a plain span", () => {
    it("renders a bold code that doesn't exist as plain text with no stray markdown", () => {
      render(<KBLIYoullAlsoNeed text="- **99999**" />);
      expect(screen.queryByRole("link")).not.toBeInTheDocument();
      expect(screen.getByText("99999")).toBeInTheDocument();
      expect(screen.queryByText(/\*/)).not.toBeInTheDocument();
    });
  });

  // Innocence: guard family #3 discipline — detection must anchor on the
  // code being at the FRONT of the bullet content, never match a bare
  // 5-digit number appearing anywhere in prose.
  describe("innocence — a 5-digit number that isn't a leading bullet code is never mangled", () => {
    it("leaves a bullet whose content doesn't start with a code fully intact, including an embedded number", () => {
      render(
        <KBLIYoullAlsoNeed text="- OJK legal counsel — WAJIB — see POJK 12345 for details" />,
      );
      expect(screen.queryByRole("link")).not.toBeInTheDocument();
      expect(
        screen.getByText(
          "OJK legal counsel — WAJIB — see POJK 12345 for details",
        ),
      ).toBeInTheDocument();
    });

    it("passes non-bulleted free text through unparsed even when it contains a 5-digit number", () => {
      render(
        <KBLIYoullAlsoNeed text="Search the KBLI Navigator using code 01234 as example." />,
      );
      expect(screen.queryByRole("link")).not.toBeInTheDocument();
      expect(
        screen.getByText(
          "Search the KBLI Navigator using code 01234 as example.",
        ),
      ).toBeInTheDocument();
    });
  });
});
