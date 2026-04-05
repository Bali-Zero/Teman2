import type { VisaRecommendation } from "@/lib/visa-oracle/types";

const CATEGORY_LABELS: Record<string, string> = {
  single_entry_visas: "Single Entry",
  multiple_entry_visas: "Multiple Entry",
  visa_extensions: "Extension",
  kitas_permits: "KITAS Permit",
  kitap_permits: "KITAP Permit",
};

interface VisaCardProps {
  visa: VisaRecommendation;
  rank: number;
  onAskQuestion: () => void;
}

export function VisaCard({ visa, rank, onAskQuestion }: VisaCardProps) {
  const isBestMatch = rank === 1;
  const categoryLabel = CATEGORY_LABELS[visa.category] ?? visa.category;

  return (
    <div
      className="flex flex-col gap-4 p-6 rounded-xl"
      style={{
        backgroundColor: "var(--bz-elevated)",
        border: isBestMatch
          ? "1px solid var(--bz-accent)"
          : "1px solid rgba(255,255,255,0.08)",
      }}
    >
      {/* Badge + name */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <span
            className="text-xs font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full self-start"
            style={{
              backgroundColor: isBestMatch
                ? "var(--bz-accent)"
                : "rgba(255,255,255,0.08)",
              color: isBestMatch ? "#fff" : "var(--tx-secondary)",
            }}
          >
            {isBestMatch ? "Best match" : `Option ${rank}`}
          </span>
          <h3 className="text-lg font-bold mt-1">{visa.visa_name}</h3>
        </div>
      </div>

      {/* Category */}
      <p
        className="text-sm font-medium"
        style={{ color: "var(--tx-secondary)" }}
      >
        {categoryLabel}
      </p>

      {/* Price */}
      <div className="flex items-baseline gap-2">
        <span
          className="text-2xl font-bold"
          style={{ color: "var(--bz-accent)" }}
        >
          {visa.price}
        </span>
        <span className="text-xs" style={{ color: "var(--tx-secondary)" }}>
          Bali Zero fee
        </span>
      </div>

      {/* Details */}
      <div
        className="flex flex-col gap-1 text-sm"
        style={{ color: "var(--tx-secondary)" }}
      >
        <span>Duration: {visa.duration}</span>
        <span>Validity: {visa.validity}</span>
        {visa.notes && (
          <p
            className="text-xs mt-1 leading-relaxed"
            style={{ color: "var(--tx-secondary)" }}
          >
            {visa.notes}
          </p>
        )}
      </div>

      {/* CTA */}
      <button
        onClick={onAskQuestion}
        className="mt-2 px-4 py-2 rounded-lg text-sm font-semibold transition-opacity hover:opacity-80 active:opacity-70"
        style={{
          border: "1px solid var(--bz-accent)",
          color: "var(--bz-accent)",
        }}
      >
        Ask a question about this visa
      </button>
    </div>
  );
}
