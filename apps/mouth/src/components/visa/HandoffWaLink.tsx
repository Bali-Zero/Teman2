"use client";

export interface HandoffWaLinkProps {
  phone: string;
  nationality: string;
  purpose: string;
  durationMonths: number;
  budgetBand: string;
  reason: string;
}

export function HandoffWaLink({
  phone,
  nationality,
  purpose,
  durationMonths,
  budgetBand,
  reason,
}: HandoffWaLinkProps) {
  const normalisedPhone = phone.replace(/^\+/, "");
  const summary =
    `Hi Bali Zero, your wizard couldn't pick a visa for my case.\n\n` +
    `Nationality: ${nationality}\n` +
    `Purpose: ${purpose}\n` +
    `Duration: ${durationMonths} months\n` +
    `Budget: ${budgetBand}\n\n` +
    `Wizard note: ${reason}\n\n` +
    `Can you help me figure out the right visa?`;
  const href = `https://wa.me/${normalisedPhone}?text=${encodeURIComponent(summary)}`;

  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "var(--space-2, 0.5rem)",
        padding: "var(--space-3, 1rem) var(--space-4, 1.5rem)",
        borderRadius: "0.5rem",
        background: "#25D366",
        color: "#0a0a0a",
        fontFamily: "var(--font-serif, Georgia, serif)",
        fontSize: "1.05rem",
        textDecoration: "none",
        fontWeight: 500,
      }}
    >
      Start on WhatsApp →
    </a>
  );
}
