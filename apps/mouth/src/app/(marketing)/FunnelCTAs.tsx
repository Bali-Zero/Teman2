"use client";

const funnels = [
  {
    title: "Visa Oracle",
    description: "Find your best visa path in 60 seconds",
    href: "https://visa.balizero.com",
    accent: "#2E6FD4",
    accentGlow: "rgba(46, 111, 212, 0.15)",
    icon: (
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z" />
        <line x1="3" y1="6" x2="21" y2="6" />
        <path d="M16 10a4 4 0 0 1-8 0" />
      </svg>
    ),
  },
  {
    title: "KBLI Navigator",
    description: "Decode 1,563 Indonesian business codes",
    href: "/kbli",
    accent: "#d4845a",
    accentGlow: "rgba(212, 132, 90, 0.15)",
    icon: (
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <ellipse cx="12" cy="5" rx="9" ry="3" />
        <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
        <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
      </svg>
    ),
  },
  {
    title: "Tax & Compliance",
    description: "Personal and corporate tax services",
    href: "/contact?service=tax",
    accent: "#D4A853",
    accentGlow: "rgba(212, 168, 83, 0.15)",
    icon: (
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <rect x="4" y="2" width="16" height="20" rx="2" />
        <line x1="8" y1="6" x2="16" y2="6" />
        <line x1="8" y1="10" x2="16" y2="10" />
        <line x1="8" y1="14" x2="12" y2="14" />
      </svg>
    ),
  },
  {
    title: "Property",
    description: "Leasehold, freehold & investment guidance",
    href: "/property",
    accent: "#d4845a",
    accentGlow: "rgba(212, 132, 90, 0.15)",
    icon: (
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
        <polyline points="9 22 9 12 15 12 15 22" />
      </svg>
    ),
  },
];

function trackClick(funnel: string) {
  if (typeof window !== "undefined" && "gtag" in window) {
    (window as unknown as { gtag: (...args: unknown[]) => void }).gtag(
      "event",
      "funnel_cta_click",
      { funnel },
    );
  }
}

export function FunnelCTAs() {
  return (
    <section
      className="funnel-ctas"
      style={{
        maxWidth: "1200px",
        margin: "0 auto",
        padding: "48px 24px 32px",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "12px",
          marginBottom: "24px",
        }}
      >
        <div
          style={{
            width: "28px",
            height: "2px",
            background: "var(--gold, #D4A853)",
          }}
        />
        <h2
          style={{
            fontFamily: "'DM Serif Display', serif",
            fontSize: "20px",
            fontWeight: 400,
            color: "var(--cream, #F2EDE6)",
            letterSpacing: "0.02em",
          }}
        >
          Intelligence Tools
        </h2>
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))",
          gap: "16px",
        }}
      >
        {funnels.map((f) => (
          <a
            key={f.title}
            href={f.href}
            onClick={() => trackClick(f.title.toLowerCase().replace(/\s+/g, "-"))}
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "12px",
              padding: "20px",
              borderRadius: "14px",
              background: "rgba(6, 13, 20, 0.5)",
              border: "1px solid rgba(255, 255, 255, 0.06)",
              backdropFilter: "blur(12px)",
              textDecoration: "none",
              transition: "all 0.3s ease",
              cursor: "pointer",
            }}
            onMouseEnter={(e) => {
              const el = e.currentTarget;
              el.style.borderColor = `${f.accent}40`;
              el.style.boxShadow = `0 8px 32px ${f.accentGlow}`;
              el.style.transform = "translateY(-2px)";
            }}
            onMouseLeave={(e) => {
              const el = e.currentTarget;
              el.style.borderColor = "rgba(255, 255, 255, 0.06)";
              el.style.boxShadow = "none";
              el.style.transform = "translateY(0)";
            }}
          >
            <div
              style={{
                width: "44px",
                height: "44px",
                borderRadius: "10px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                background: `${f.accent}12`,
                color: f.accent,
              }}
            >
              {f.icon}
            </div>
            <div>
              <h3
                style={{
                  fontFamily: "'Inter', sans-serif",
                  fontSize: "15px",
                  fontWeight: 600,
                  color: "var(--cream, #F2EDE6)",
                  marginBottom: "4px",
                }}
              >
                {f.title}
              </h3>
              <p
                style={{
                  fontFamily: "'Inter', sans-serif",
                  fontSize: "13px",
                  fontWeight: 400,
                  color: "var(--w55, rgba(242, 237, 230, 0.55))",
                  lineHeight: 1.4,
                }}
              >
                {f.description}
              </p>
            </div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "4px",
                fontSize: "12px",
                fontWeight: 500,
                color: f.accent,
                marginTop: "auto",
              }}
            >
              Explore
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M5 12h14" />
                <path d="m12 5 7 7-7 7" />
              </svg>
            </div>
          </a>
        ))}
      </div>
    </section>
  );
}
