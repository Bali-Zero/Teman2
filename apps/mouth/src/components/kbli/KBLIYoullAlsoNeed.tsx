import Link from "next/link";
import { getCode } from "@/lib/kbli-data";

interface KBLIYoullAlsoNeedProps {
  text: string;
}

const BULLET_LINE_RE = /^-\s+(.*)$/;
// Leading `**`/`*` wrapping is optional on both sides of the code — the
// prevailing dataset format is bold-markdown ("**47111**", "**47111** —
// desc"), but plain "47111 — desc" bullets exist too. Anchored at the start
// of `content` so prose that merely *contains* a 5-digit number (not at the
// front of the bullet) never matches — see innocence tests.
const LEADING_CODE_RE = /^\*{0,2}(\d{5})\*{0,2}\s*(?:—|-|:)?\s*(.*)$/;

/**
 * Parses `youllAlsoNeed` markdown-ish bullets ("- 12345 — description",
 * "- **12345**", "- **12345** — description") into styled rows. When a row
 * starts with a 5-digit KBLI code that exists in the dataset, it links to
 * /kbli/<code>; otherwise the code (or full line) renders as plain text.
 * Lines that don't match the "- " bullet shape pass through unparsed so the
 * section degrades gracefully on free-form text.
 */
export function KBLIYoullAlsoNeed({ text }: KBLIYoullAlsoNeedProps) {
  const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);

  return (
    <ul className="space-y-2">
      {lines.map((line, idx) => {
        const bulletMatch = line.match(BULLET_LINE_RE);
        const content = bulletMatch ? bulletMatch[1] : line;
        const codeMatch = content.match(LEADING_CODE_RE);

        if (codeMatch) {
          const [, code, rest] = codeMatch;
          const exists = !!getCode(code);
          return (
            <li key={idx} className="flex items-baseline gap-2.5 text-sm">
              {exists ? (
                <Link
                  href={`/kbli/${code}`}
                  className="shrink-0 font-mono font-bold text-[var(--kbli-accent)] hover:text-[var(--kbli-accent-hover)]"
                >
                  {code}
                </Link>
              ) : (
                <span className="shrink-0 font-mono font-bold text-[var(--foreground-secondary)]">
                  {code}
                </span>
              )}
              {rest && (
                <span className="text-[var(--foreground-secondary)]">
                  {rest}
                </span>
              )}
            </li>
          );
        }

        return (
          <li
            key={idx}
            className="text-sm text-[var(--foreground-secondary)]"
          >
            {content}
          </li>
        );
      })}
    </ul>
  );
}
