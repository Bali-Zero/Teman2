"use client";

interface WhatsAppIconProps {
  size?: number;
  strokeWidth?: number;
  color?: string;
  fill?: string;
  fillOpacity?: number;
}

const MessageCircle = ({
  size = 20,
  strokeWidth = 2,
  color = "currentColor",
  fill = "none",
  fillOpacity = 0,
  ...props
}: WhatsAppIconProps) => (
  <svg
    viewBox="0 0 24 24"
    width={size}
    height={size}
    fill={fill}
    fillOpacity={fillOpacity}
    stroke={color}
    strokeWidth={strokeWidth}
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
    {...props}
  >
    <path d="M21 11.5a8.5 8.5 0 0 0-16.1 5.06L3 21l4.69-1.64A8.5 8.5 0 1 0 21 11.5" />
    <path d="m9 9 6 3-2 1.5-1 3.5 1.5-1 2 1.5" />
  </svg>
);

/**
 * Persistent WhatsApp contact FAB — pill-shaped with label.
 * Fixed bottom-left. Always visible on every page/route.
 */
export function WhatsAppFAB({
  phone = "6282230102328",
  message = "Hi Bali Zero, I would like to get in touch.",
}: {
  phone?: string;
  message?: string;
}) {
  const href = `https://wa.me/${phone}?text=${encodeURIComponent(message)}`;
  // role="complementary" + aria-label so the FAB is announced as its own
  // landmark, satisfying axe `region` (no orphan content outside landmarks).
  return (
    <aside aria-label="Direct contact" className="contents">
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        aria-label="Chat with us on WhatsApp"
        className="fab-whatsapp fixed z-[500] flex items-center gap-3 rounded-full transition-all hover:-translate-y-1 hover:scale-[1.03] group"
        style={{
          background: "linear-gradient(135deg, #25D366 0%, #128C7E 100%)",
          boxShadow:
            "0 8px 32px rgba(37, 211, 102, 0.45), inset 0 1px 0 rgba(255,255,255,0.2)",
          border: "1px solid rgba(255,255,255,0.18)",
        }}
      >
        {/* Icon disc */}
        <span
          className="flex items-center justify-center rounded-full shrink-0 relative"
          style={{
            width: 40,
            height: 40,
            background: "rgba(255,255,255,0.22)",
          }}
        >
          <MessageCircle
            size={22}
            strokeWidth={2.2}
            color="#ffffff"
            fill="#ffffff"
            fillOpacity={0.15}
          />
          {/* Online pulse */}
          <span
            className="absolute rounded-full"
            style={{
              top: -2,
              right: -2,
              width: 14,
              height: 14,
              background: "#ffffff",
              border: "2px solid #128C7E",
            }}
          />
        </span>

        <span className="fab-label flex flex-col items-start leading-none">
          <span
            className="font-bold"
            style={{
              color: "#ffffff",
              fontSize: 13,
              letterSpacing: "0.02em",
            }}
          >
            Chat with us
          </span>
          <span
            className="mt-1"
            style={{
              color: "rgba(255,255,255,0.85)",
              fontSize: 10,
              fontWeight: 500,
              letterSpacing: "0.05em",
              textTransform: "uppercase",
            }}
          >
            WhatsApp · Reply &lt; 5 min
          </span>
        </span>
      </a>
    </aside>
  );
}
