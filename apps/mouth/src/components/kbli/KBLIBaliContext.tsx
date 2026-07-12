import { MarkdownClient } from "@/components/kbli/MarkdownClient";

interface KBLIBaliContextProps {
  baliContext: string;
}

/**
 * Renders `baliContext` split on `\n---\n` into titled cards (gold-tier
 * editorial format: `**Title:** body`). Shared by the gold and non-gold
 * branches of /kbli/[code] — extracted verbatim from the gold layout so
 * both tiers get the same visual treatment. Degrades gracefully when the
 * text has no `---` separator (single untitled block, the common
 * non-gold shape) or no `**Title:**` prefix.
 */
export function KBLIBaliContext({ baliContext }: KBLIBaliContextProps) {
  return (
    <div className="space-y-5" style={{ maxWidth: "780px" }}>
      {baliContext.split(/\n---\n/).map((block, idx) => {
        const trimmed = block.trim();
        if (!trimmed) return null;

        const isMistakes = trimmed
          .toLowerCase()
          .includes("common client mistakes");
        const isNumbers =
          trimmed.toLowerCase().includes("governor") ||
          trimmed.toLowerCase().includes("numbers");
        const isReality =
          trimmed.toLowerCase().includes("reality") ||
          trimmed.toLowerCase().includes("market");

        const titleMatch = trimmed.match(/^\*\*([^*]+?):\*\*/);
        const cardTitle = titleMatch ? titleMatch[1] : null;
        const bodyText = cardTitle
          ? trimmed.replace(/^\*\*[^*]+?:\*\*\s*/, "")
          : trimmed;

        const accentColor = isMistakes
          ? "var(--kbli-pma-restricted)"
          : "var(--kbli-accent)";
        const blockIcon = isMistakes
          ? "⚠"
          : isNumbers
            ? "📊"
            : isReality
              ? "🏝"
              : "💡";
        const blockBg = isMistakes
          ? "rgba(232, 168, 73, 0.03)"
          : "rgba(212, 132, 90, 0.02)";

        return (
          <div
            key={idx}
            className="rounded-xl p-5"
            style={{
              background: blockBg,
              border: `1px solid ${isMistakes ? "rgba(232, 168, 73, 0.1)" : "var(--kbli-border)"}`,
            }}
          >
            {cardTitle && (
              <div className="mb-4 flex items-center gap-2.5">
                <span className="text-base">{blockIcon}</span>
                <span
                  className="text-sm font-bold tracking-wide"
                  style={{ color: accentColor }}
                >
                  {cardTitle}
                </span>
              </div>
            )}
            <div className="kbli-prose">
              <MarkdownClient>{bodyText}</MarkdownClient>
            </div>
          </div>
        );
      })}
    </div>
  );
}
