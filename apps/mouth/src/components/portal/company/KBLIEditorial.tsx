interface KBLIEditorialProps {
  kbliCode?: string;
  kbliDescription?: string;
}

export function KBLIEditorial({
  kbliCode,
  kbliDescription,
}: KBLIEditorialProps) {
  if (!kbliCode) return null;

  // Split comma-separated KBLI codes
  const codes = kbliCode.split(",").map((c) => c.trim());
  const descriptions = (kbliDescription || "").split(";").map((d) => d.trim());

  // KBLI code to English lookup (common ones)
  const kbliEnglish: Record<string, string> = {
    "68110": "Real Estate Activities \u2014 Own or Leased",
    "70209": "Other Management Consulting Activities",
    "56101": "Restaurant",
    "47111": "Retail Trade in Mini Markets",
    "46100": "Wholesale Trade on a Fee or Contract Basis",
    "62011": "Computer Programming Activities",
    "73100": "Advertising",
  };

  return (
    <div className="flex flex-col">
      {codes.map((code, i) => {
        const desc = descriptions[i] || descriptions[0] || "";
        const englishTitle = kbliEnglish[code];
        const isPrimary = i === 0;

        return (
          <div
            key={code}
            className={`py-6 grid grid-cols-[80px_1fr] gap-6 items-start ${
              i === 0 ? "pt-0" : ""
            } ${i < codes.length - 1 ? "border-b border-[var(--kbli-border)]" : ""}`}
          >
            {/* Code */}
            <span
              className="text-[28px] font-[800] tabular-nums tracking-[-0.03em] leading-none pt-1 opacity-60"
              style={{ color: "var(--kbli-accent)" }}
            >
              {code}
            </span>

            {/* Content */}
            <div>
              <div className="text-[15px] font-bold text-[var(--kbli-text-primary)] mb-1.5">
                {englishTitle || desc || `KBLI ${code}`}
              </div>
              {desc && (
                <div className="text-[13px] text-[var(--kbli-text-secondary)] leading-relaxed">
                  {desc}
                </div>
              )}
              <span
                className="inline-block mt-2 px-2 py-0.5 rounded-[var(--kbli-radius-sm)] text-[10px] font-semibold"
                style={{
                  background: isPrimary
                    ? "var(--kbli-accent-subtle)"
                    : "var(--kbli-zantara-bg)",
                  color: isPrimary
                    ? "var(--kbli-accent)"
                    : "var(--kbli-accent2)",
                }}
              >
                {isPrimary ? "Primary Activity" : "Secondary Activity"}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
