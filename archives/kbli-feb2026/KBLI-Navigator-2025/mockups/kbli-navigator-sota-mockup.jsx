import { useState, useEffect, useRef } from "react";

// Lightweight inline icons (no lucide-react dependency issues)
const Icon = ({ d, size = 16, color = "currentColor", ...props }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke={color}
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    {...props}
  >
    {d}
  </svg>
);

const Icons = {
  search: (
    <>
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.35-4.35" />
    </>
  ),
  send: (
    <>
      <path d="m22 2-7 20-4-9-9-4Z" />
      <path d="M22 2 11 13" />
    </>
  ),
  chat: (
    <>
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </>
  ),
  db: (
    <>
      <ellipse cx="12" cy="5" rx="9" ry="3" />
      <path d="M3 5v14a9 3 0 0 0 18 0V5" />
      <path d="M3 12a9 3 0 0 0 18 0" />
    </>
  ),
  chart: (
    <>
      <path d="M3 3v18h18" />
      <path d="M18 17V9" />
      <path d="M13 17V5" />
      <path d="M8 17v-3" />
    </>
  ),
  star: (
    <>
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
    </>
  ),
  copy: (
    <>
      <rect width="14" height="14" x="8" y="8" rx="2" />
      <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" />
    </>
  ),
  globe: (
    <>
      <circle cx="12" cy="12" r="10" />
      <path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20" />
      <path d="M2 12h20" />
    </>
  ),
  shield: (
    <>
      <path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z" />
    </>
  ),
  alert: (
    <>
      <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3" />
      <path d="M12 9v4" />
      <path d="M12 17h.01" />
    </>
  ),
  check: (
    <>
      <path d="M20 6 9 17l-5-5" />
    </>
  ),
  down: (
    <>
      <path d="m6 9 6 6 6-6" />
    </>
  ),
  up: (
    <>
      <path d="m18 15-6-6-6 6" />
    </>
  ),
  right: (
    <>
      <path d="m9 18 6-6-6-6" />
    </>
  ),
  menu: (
    <>
      <line x1="4" x2="20" y1="12" y2="12" />
      <line x1="4" x2="20" y1="6" y2="6" />
      <line x1="4" x2="20" y1="18" y2="18" />
    </>
  ),
  x: (
    <>
      <path d="M18 6 6 18" />
      <path d="m6 6 12 12" />
    </>
  ),
  ext: (
    <>
      <path d="M15 3h6v6" />
      <path d="M10 14 21 3" />
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
    </>
  ),
  spark: (
    <>
      <path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.582a.5.5 0 0 1 0 .962L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z" />
    </>
  ),
  building: (
    <>
      <rect width="16" height="20" x="4" y="2" rx="2" />
      <path d="M9 22v-4h6v4" />
      <path d="M8 6h.01" />
      <path d="M16 6h.01" />
      <path d="M12 6h.01" />
      <path d="M12 10h.01" />
      <path d="M12 14h.01" />
      <path d="M16 10h.01" />
      <path d="M16 14h.01" />
      <path d="M8 10h.01" />
      <path d="M8 14h.01" />
    </>
  ),
  file: (
    <>
      <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" />
      <path d="M14 2v4a2 2 0 0 0 2 2h4" />
    </>
  ),
  briefcase: (
    <>
      <path d="M16 20V4a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
      <rect width="20" height="14" x="2" y="6" rx="2" />
    </>
  ),
  info: (
    <>
      <circle cx="12" cy="12" r="10" />
      <path d="M12 16v-4" />
      <path d="M12 8h.01" />
    </>
  ),
  zap: (
    <>
      <path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z" />
    </>
  ),
  factory: (
    <>
      <path d="M2 20a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V8l-7 5V8l-7 5V4a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2Z" />
      <path d="M17 18h1" />
      <path d="M12 18h1" />
      <path d="M7 18h1" />
    </>
  ),
  scale: (
    <>
      <path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z" />
      <path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z" />
      <path d="M7 21h10" />
      <path d="M12 3v18" />
      <path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2" />
    </>
  ),
};

const I = ({ name, size = 16, color = "currentColor" }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke={color}
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    {Icons[name]}
  </svg>
);

// Sector data with emoji instead of icons
const SECTORS = [
  {
    code: "A",
    name: "Agriculture, Forestry & Fishing",
    emoji: "🌾",
    count: 132,
    color: "#16a34a",
  },
  {
    code: "B",
    name: "Mining & Quarrying",
    emoji: "⛏️",
    count: 47,
    color: "#d97706",
  },
  {
    code: "C",
    name: "Manufacturing",
    emoji: "🏭",
    count: 477,
    color: "#2563eb",
  },
  {
    code: "D",
    name: "Electricity & Gas",
    emoji: "⚡",
    count: 18,
    color: "#7c3aed",
  },
  {
    code: "E",
    name: "Water & Waste Management",
    emoji: "💧",
    count: 24,
    color: "#0891b2",
  },
  { code: "F", name: "Construction", emoji: "🏗️", count: 62, color: "#ea580c" },
  {
    code: "G",
    name: "Trade & Repair",
    emoji: "🛒",
    count: 198,
    color: "#dc2626",
  },
  {
    code: "H",
    name: "Transport & Storage",
    emoji: "🚛",
    count: 89,
    color: "#4f46e5",
  },
  {
    code: "I",
    name: "Accommodation & Food",
    emoji: "🍽️",
    count: 56,
    color: "#be185d",
  },
  {
    code: "J",
    name: "Information & Communication",
    emoji: "💻",
    count: 74,
    color: "#0d9488",
  },
  {
    code: "K",
    name: "Financial Services",
    emoji: "💰",
    count: 68,
    color: "#b45309",
  },
  { code: "L", name: "Real Estate", emoji: "🏠", count: 12, color: "#6d28d9" },
  {
    code: "M",
    name: "Professional Services",
    emoji: "💼",
    count: 78,
    color: "#0369a1",
  },
  {
    code: "N",
    name: "Admin & Support",
    emoji: "👥",
    count: 54,
    color: "#9333ea",
  },
  {
    code: "O",
    name: "Government & Defense",
    emoji: "🏛️",
    count: 18,
    color: "#64748b",
  },
  { code: "P", name: "Education", emoji: "🎓", count: 42, color: "#059669" },
  {
    code: "Q",
    name: "Health & Social",
    emoji: "🏥",
    count: 36,
    color: "#e11d48",
  },
  {
    code: "R",
    name: "Arts & Recreation",
    emoji: "🎨",
    count: 32,
    color: "#c026d3",
  },
  {
    code: "S",
    name: "Other Services",
    emoji: "🔧",
    count: 48,
    color: "#475569",
  },
];

const MOCK_CODES = [
  {
    code: "62011",
    title: "Computer Programming Activities",
    sector: "J",
    risk: "Low",
    pma: "TERBUKA",
    pmaPercent: "100%",
    status: "MATCH_LANGSUNG",
    desc: "Custom software development, systems integration, mobile app development",
  },
  {
    code: "62012",
    title: "System Consultancy & Management",
    sector: "J",
    risk: "Low",
    pma: "TERBUKA",
    pmaPercent: "100%",
    status: "MATCH_LANGSUNG",
    desc: "IT consulting, systems design, ERP implementation services",
  },
  {
    code: "62021",
    title: "Information Technology Consultancy",
    sector: "J",
    risk: "Low",
    pma: "TERBUKA",
    pmaPercent: "100%",
    status: "CODICE_RINUMERATO",
    desc: "IT strategy consulting, digital transformation advisory",
  },
  {
    code: "56101",
    title: "Restaurant & Mobile Food Service",
    sector: "I",
    risk: "Medium",
    pma: "TERBATAS",
    pmaPercent: "67%",
    status: "MATCH_LANGSUNG",
    desc: "Full-service restaurants, cafes, food trucks, catering",
  },
  {
    code: "10710",
    title: "Bakery Products Manufacturing",
    sector: "C",
    risk: "Medium",
    pma: "TERBUKA",
    pmaPercent: "100%",
    status: "MATCH_LANGSUNG",
    desc: "Production of bread, cakes, pastries, and baked goods",
  },
  {
    code: "05101",
    title: "Coal Mining",
    sector: "B",
    risk: "High",
    pma: "TERBATAS",
    pmaPercent: "49%",
    status: "MATCH_LANGSUNG",
    desc: "Hard coal mining, open-pit and underground operations",
  },
];

const CHAT_DEMO = [
  {
    role: "user",
    text: "I want to start a software company in Bali as a foreigner. What KBLI code do I need?",
  },
  {
    role: "ai",
    text: "Great question! For a software company in Bali, here are the most relevant KBLI 2025 codes:\n\n62011 — Computer Programming Activities\n• Risk Level: 🟢 Low (NIB only, no additional permits)\n• Foreign Ownership: ✅ 100% allowed (TERBUKA)\n• Min. Investment: IDR 10 billion for PT PMA\n• Status: Direct Match from KBLI 2020\n\n62012 — System Consultancy & Management\n• Risk Level: 🟢 Low\n• Foreign Ownership: ✅ 100% allowed (TERBUKA)\n• Ideal for: IT consulting, systems integration\n\n⚠️ Important for Bali: Register your business address in a commercial zone (not residential). Bali has specific zoning regulations.\n\n➡️ Next Steps: Register through OSS at oss.go.id. You'll need passport, KITAS/KITAP, and proof of investment capital.\n\n📋 For a complete compliance analysis, contact 3Om Consulting: contact@3om.consulting",
  },
];

const SUGGESTIONS = [
  { emoji: "🏢", text: "Start a PT PMA company" },
  { emoji: "🔍", text: "Find my KBLI code" },
  { emoji: "🛡️", text: "Check foreign ownership limits" },
  { emoji: "📄", text: "What licenses do I need?" },
];

// --- BADGE COMPONENTS ---

function RiskBadge({ level }) {
  const c = {
    Low: { bg: "#dcfce7", fg: "#166534", dot: "#22c55e" },
    Medium: { bg: "#fef3c7", fg: "#92400e", dot: "#f59e0b" },
    High: { bg: "#fee2e2", fg: "#991b1b", dot: "#ef4444" },
  }[level] || { bg: "#f1f5f9", fg: "#475569", dot: "#94a3b8" };
  return (
    <span
      style={{
        background: c.bg,
        color: c.fg,
        fontSize: 11,
        fontWeight: 600,
        padding: "2px 8px",
        borderRadius: 99,
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
      }}
    >
      <span
        style={{ width: 6, height: 6, borderRadius: "50%", background: c.dot }}
      />
      {level}
    </span>
  );
}

function PmaBadge({ status, pct }) {
  const c = {
    TERBUKA: { bg: "#dcfce7", fg: "#166534", l: "Open" },
    TERBATAS: { bg: "#fef3c7", fg: "#92400e", l: "Restricted" },
    TERTUTUP: { bg: "#fee2e2", fg: "#991b1b", l: "Closed" },
  }[status] || { bg: "#f1f5f9", fg: "#475569", l: status };
  return (
    <span
      style={{
        background: c.bg,
        color: c.fg,
        fontSize: 11,
        fontWeight: 600,
        padding: "2px 8px",
        borderRadius: 99,
      }}
    >
      {c.l} {pct}
    </span>
  );
}

function StatusBadge({ status }) {
  const c = {
    MATCH_LANGSUNG: { bg: "#dcfce7", fg: "#166534", l: "Direct Match" },
    MATCH_CON_AGGREGAZIONE: { bg: "#dbeafe", fg: "#1e40af", l: "Aggregated" },
    CODICE_RINUMERATO: { bg: "#fef3c7", fg: "#92400e", l: "Renumbered" },
    BPS_ONLY: { bg: "#f3e8ff", fg: "#6b21a8", l: "Statistical Only" },
  }[status] || { bg: "#f1f5f9", fg: "#475569", l: status };
  return (
    <span
      style={{
        background: c.bg,
        color: c.fg,
        fontSize: 10,
        fontWeight: 600,
        padding: "2px 6px",
        borderRadius: 4,
      }}
    >
      {c.l}
    </span>
  );
}

// --- CHAT PANEL ---

function ChatPanel() {
  const [input, setInput] = useState("");
  const [msgs, setMsgs] = useState(CHAT_DEMO);
  const endRef = useRef(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs]);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        background: "#fafbfc",
      }}
    >
      <div
        style={{
          padding: "14px 16px",
          borderBottom: "1px solid #e2e8f0",
          background: "#fff",
          display: "flex",
          alignItems: "center",
          gap: 10,
        }}
      >
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: 8,
            background: "linear-gradient(135deg, #4f46e5, #7c3aed)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <I name="spark" size={16} color="#fff" />
        </div>
        <div>
          <div style={{ fontSize: 14, fontWeight: 700, color: "#0f172a" }}>
            KBLI AI Expert
          </div>
          <div
            style={{
              fontSize: 11,
              color: "#22c55e",
              display: "flex",
              alignItems: "center",
              gap: 4,
            }}
          >
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                background: "#22c55e",
                display: "inline-block",
              }}
            />
            Online
          </div>
        </div>
      </div>

      <div style={{ flex: 1, overflowY: "auto", padding: 14 }}>
        {msgs.map((m, i) => (
          <div
            key={i}
            style={{
              marginBottom: 12,
              display: "flex",
              flexDirection: "column",
              alignItems: m.role === "user" ? "flex-end" : "flex-start",
            }}
          >
            <div
              style={{
                maxWidth: "92%",
                padding: "11px 15px",
                whiteSpace: "pre-wrap",
                borderRadius:
                  m.role === "user"
                    ? "14px 14px 4px 14px"
                    : "14px 14px 14px 4px",
                background:
                  m.role === "user"
                    ? "linear-gradient(135deg, #4f46e5, #6366f1)"
                    : "#fff",
                color: m.role === "user" ? "#fff" : "#1e293b",
                fontSize: 13,
                lineHeight: 1.6,
                border: m.role === "user" ? "none" : "1px solid #f1f5f9",
                boxShadow:
                  m.role === "ai" ? "0 1px 3px rgba(0,0,0,0.05)" : "none",
              }}
            >
              {m.text}
            </div>
            {m.role === "ai" && (
              <div
                style={{
                  display: "flex",
                  gap: 10,
                  marginTop: 5,
                  paddingLeft: 4,
                }}
              >
                <button
                  style={{
                    fontSize: 11,
                    color: "#94a3b8",
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: 3,
                  }}
                >
                  <I name="copy" size={11} /> Copy
                </button>
                <button
                  style={{
                    fontSize: 11,
                    color: "#94a3b8",
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: 3,
                  }}
                >
                  <I name="star" size={11} /> Save
                </button>
              </div>
            )}
          </div>
        ))}
        <div ref={endRef} />
      </div>

      <div
        style={{
          padding: "10px 14px",
          borderTop: "1px solid #e2e8f0",
          background: "#fff",
        }}
      >
        <div style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about KBLI codes, licensing, PMA..."
            rows={1}
            style={{
              flex: 1,
              padding: "10px 14px",
              borderRadius: 12,
              border: "1px solid #e2e8f0",
              fontSize: 13,
              resize: "none",
              outline: "none",
              fontFamily: "inherit",
              background: "#f8fafc",
              boxSizing: "border-box",
            }}
            onFocus={(e) => {
              e.target.style.borderColor = "#818cf8";
            }}
            onBlur={(e) => {
              e.target.style.borderColor = "#e2e8f0";
            }}
          />
          <button
            style={{
              width: 40,
              height: 40,
              borderRadius: 12,
              border: "none",
              background: input.trim()
                ? "linear-gradient(135deg,#4f46e5,#7c3aed)"
                : "#e2e8f0",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <I
              name="send"
              size={16}
              color={input.trim() ? "#fff" : "#94a3b8"}
            />
          </button>
        </div>
        <div
          style={{
            fontSize: 10,
            color: "#94a3b8",
            marginTop: 5,
            textAlign: "center",
          }}
        >
          KBLI 2025 · BPS Regulation No. 7/2025 · Not legal advice
        </div>
      </div>
    </div>
  );
}

// --- CODE FINDER ---

function CodeFinderView() {
  const [search, setSearch] = useState("software development");
  const [expanded, setExpanded] = useState("62011");
  const [filter, setFilter] = useState("all");
  const filters = [
    { id: "all", l: "All Results" },
    { id: "open", l: "100% Foreign OK" },
    { id: "restricted", l: "Restricted FDI" },
    { id: "low", l: "Low Risk" },
  ];

  return (
    <div style={{ padding: "28px 32px", maxWidth: 960, margin: "0 auto" }}>
      <h2
        style={{
          fontSize: 22,
          fontWeight: 800,
          color: "#0f172a",
          margin: "0 0 4px",
          letterSpacing: "-0.02em",
        }}
      >
        Find Your KBLI Code
      </h2>
      <p style={{ fontSize: 13, color: "#64748b", margin: "0 0 16px" }}>
        Search 1,562 Indonesian business classification codes with AI-powered
        matching
      </p>

      <div style={{ position: "relative", marginBottom: 18 }}>
        <div style={{ position: "absolute", left: 16, top: 14 }}>
          <I name="search" size={18} color="#94a3b8" />
        </div>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder='Try: "software development", "62011", or "restoran"'
          style={{
            width: "100%",
            padding: "13px 80px 13px 44px",
            borderRadius: 12,
            border: "2px solid #e2e8f0",
            fontSize: 14,
            outline: "none",
            background: "#fff",
            fontFamily: "inherit",
            boxSizing: "border-box",
          }}
          onFocus={(e) => {
            e.target.style.borderColor = "#818cf8";
          }}
          onBlur={(e) => {
            e.target.style.borderColor = "#e2e8f0";
          }}
        />
        <span
          style={{
            position: "absolute",
            right: 12,
            top: 11,
            fontSize: 11,
            color: "#94a3b8",
            background: "#f1f5f9",
            padding: "3px 8px",
            borderRadius: 6,
            fontWeight: 600,
          }}
        >
          EN ↔ ID
        </span>
      </div>

      <div
        style={{
          display: "flex",
          gap: 6,
          marginBottom: 18,
          flexWrap: "wrap",
          alignItems: "center",
        }}
      >
        {filters.map((f) => (
          <button
            key={f.id}
            onClick={() => setFilter(f.id)}
            style={{
              padding: "6px 14px",
              borderRadius: 8,
              border: "1px solid",
              cursor: "pointer",
              borderColor: filter === f.id ? "#818cf8" : "#e2e8f0",
              background: filter === f.id ? "#eef2ff" : "#fff",
              color: filter === f.id ? "#4338ca" : "#64748b",
              fontSize: 12,
              fontWeight: 600,
            }}
          >
            {f.l}
          </button>
        ))}
        <span style={{ marginLeft: "auto", fontSize: 12, color: "#94a3b8" }}>
          Showing <strong style={{ color: "#334155" }}>6</strong> results
        </span>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {MOCK_CODES.map((c) => {
          const isExp = expanded === c.code;
          return (
            <div
              key={c.code}
              onClick={() => setExpanded(isExp ? null : c.code)}
              style={{
                border: `1.5px solid ${isExp ? "#818cf8" : "#e2e8f0"}`,
                borderRadius: 14,
                background: "#fff",
                cursor: "pointer",
                overflow: "hidden",
                transition: "all 0.2s",
                boxShadow: isExp
                  ? "0 4px 20px rgba(99,102,241,0.1)"
                  : "0 1px 3px rgba(0,0,0,0.04)",
              }}
            >
              <div
                style={{
                  padding: "13px 16px",
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  flexWrap: "wrap",
                }}
              >
                <div
                  style={{
                    minWidth: 60,
                    height: 34,
                    borderRadius: 8,
                    background: "#f8fafc",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 15,
                    fontWeight: 800,
                    color: "#4f46e5",
                    fontFamily: "monospace",
                    border: "1px solid #e2e8f0",
                  }}
                >
                  {c.code}
                </div>
                <div style={{ flex: 1, minWidth: 150 }}>
                  <div
                    style={{ fontSize: 14, fontWeight: 700, color: "#0f172a" }}
                  >
                    {c.title}
                  </div>
                  <div
                    style={{
                      fontSize: 12,
                      color: "#94a3b8",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {c.desc}
                  </div>
                </div>
                <div
                  style={{
                    display: "flex",
                    gap: 6,
                    alignItems: "center",
                    flexWrap: "wrap",
                  }}
                >
                  <RiskBadge level={c.risk} />
                  <PmaBadge status={c.pma} pct={c.pmaPercent} />
                  <I name={isExp ? "up" : "down"} size={16} color="#94a3b8" />
                </div>
              </div>

              {isExp && (
                <div
                  style={{
                    padding: "0 16px 16px",
                    borderTop: "1px solid #f1f5f9",
                    paddingTop: 14,
                  }}
                >
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns:
                        "repeat(auto-fit, minmax(160px, 1fr))",
                      gap: 10,
                      marginBottom: 12,
                    }}
                  >
                    <div
                      style={{
                        background: "#f8fafc",
                        borderRadius: 10,
                        padding: "10px 12px",
                      }}
                    >
                      <div
                        style={{
                          fontSize: 10,
                          fontWeight: 700,
                          color: "#94a3b8",
                          textTransform: "uppercase",
                          letterSpacing: "0.06em",
                          marginBottom: 5,
                        }}
                      >
                        Transition
                      </div>
                      <StatusBadge status={c.status} />
                      <div
                        style={{ fontSize: 11, color: "#64748b", marginTop: 4 }}
                      >
                        KBLI 2020 → 2025
                      </div>
                    </div>
                    <div
                      style={{
                        background: "#f8fafc",
                        borderRadius: 10,
                        padding: "10px 12px",
                      }}
                    >
                      <div
                        style={{
                          fontSize: 10,
                          fontWeight: 700,
                          color: "#94a3b8",
                          textTransform: "uppercase",
                          letterSpacing: "0.06em",
                          marginBottom: 5,
                        }}
                      >
                        OSS Licensing
                      </div>
                      <div
                        style={{
                          fontSize: 13,
                          fontWeight: 700,
                          color: "#0f172a",
                        }}
                      >
                        {c.risk === "Low"
                          ? "NIB Only"
                          : c.risk === "Medium"
                            ? "NIB + Permit"
                            : "Full Review"}
                      </div>
                      <div
                        style={{ fontSize: 11, color: "#64748b", marginTop: 4 }}
                      >
                        Risk-Based Approach
                      </div>
                    </div>
                    <div
                      style={{
                        background: "#f8fafc",
                        borderRadius: 10,
                        padding: "10px 12px",
                      }}
                    >
                      <div
                        style={{
                          fontSize: 10,
                          fontWeight: 700,
                          color: "#94a3b8",
                          textTransform: "uppercase",
                          letterSpacing: "0.06em",
                          marginBottom: 5,
                        }}
                      >
                        Min. Investment
                      </div>
                      <div
                        style={{
                          fontSize: 13,
                          fontWeight: 700,
                          color: "#0f172a",
                        }}
                      >
                        IDR 10B
                      </div>
                      <div
                        style={{ fontSize: 11, color: "#64748b", marginTop: 4 }}
                      >
                        For PT PMA entity
                      </div>
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: 8 }}>
                    <button
                      style={{
                        flex: 1,
                        padding: "10px",
                        borderRadius: 10,
                        border: "none",
                        background: "linear-gradient(135deg,#4f46e5,#6366f1)",
                        color: "#fff",
                        fontSize: 12,
                        fontWeight: 700,
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        gap: 6,
                      }}
                    >
                      <I name="chat" size={14} color="#fff" /> Ask AI About This
                      Code
                    </button>
                    <button
                      style={{
                        padding: "10px 16px",
                        borderRadius: 10,
                        border: "1.5px solid #e2e8f0",
                        background: "#fff",
                        color: "#334155",
                        fontSize: 12,
                        fontWeight: 600,
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                      }}
                    >
                      <I name="ext" size={14} /> OSS Portal
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// --- BROWSE SECTORS ---

function BrowseSectorsView() {
  return (
    <div style={{ padding: "28px 32px", maxWidth: 960, margin: "0 auto" }}>
      <h2
        style={{
          fontSize: 22,
          fontWeight: 800,
          color: "#0f172a",
          margin: "0 0 4px",
          letterSpacing: "-0.02em",
        }}
      >
        Browse by Sector
      </h2>
      <p style={{ fontSize: 13, color: "#64748b", margin: "0 0 20px" }}>
        22 sectors covering all economic activities in Indonesia (KBLI 2025)
      </p>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
          gap: 10,
        }}
      >
        {SECTORS.map((s) => (
          <button
            key={s.code}
            style={{
              padding: "12px 14px",
              borderRadius: 12,
              border: "1px solid #e2e8f0",
              background: "#fff",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 10,
              transition: "all 0.15s",
              textAlign: "left",
              width: "100%",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = s.color;
              e.currentTarget.style.boxShadow = `0 2px 12px ${s.color}22`;
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = "#e2e8f0";
              e.currentTarget.style.boxShadow = "none";
            }}
          >
            <span style={{ fontSize: 24 }}>{s.emoji}</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: "#0f172a" }}>
                {s.name}
              </div>
              <div style={{ fontSize: 11, color: "#94a3b8" }}>
                Section {s.code}
              </div>
            </div>
            <div
              style={{
                fontSize: 12,
                fontWeight: 700,
                color: s.color,
                background: `${s.color}18`,
                padding: "2px 8px",
                borderRadius: 6,
              }}
            >
              {s.count}
            </div>
            <I name="right" size={14} color="#cbd5e1" />
          </button>
        ))}
      </div>
    </div>
  );
}

// --- DASHBOARD ---

function DashboardView() {
  const stats = [
    {
      label: "Total KBLI Codes",
      value: "1,562",
      sub: "BPS Regulation No. 7/2025",
      icon: "db",
      color: "#4f46e5",
    },
    {
      label: "Open to Foreign Investment",
      value: "847",
      sub: "54% of all codes",
      icon: "globe",
      color: "#22c55e",
    },
    {
      label: "Restricted (Conditional)",
      value: "312",
      sub: "20% — requires DNI review",
      icon: "shield",
      color: "#f59e0b",
    },
    {
      label: "High Risk Activities",
      value: "189",
      sub: "Require additional permits",
      icon: "alert",
      color: "#ef4444",
    },
  ];

  const riskData = [
    { label: "Low Risk", count: 687, pct: 44, color: "#22c55e" },
    { label: "Medium Risk", count: 498, pct: 32, color: "#f59e0b" },
    { label: "High Risk", count: 189, pct: 12, color: "#ef4444" },
    { label: "Statistical Only", count: 188, pct: 12, color: "#a78bfa" },
  ];

  const statusData = [
    { label: "Direct Match", count: 1089, pct: 70, color: "#22c55e" },
    { label: "Aggregated", count: 218, pct: 14, color: "#3b82f6" },
    { label: "Renumbered", count: 81, pct: 5, color: "#f59e0b" },
    { label: "BPS Only", count: 174, pct: 11, color: "#a78bfa" },
  ];

  return (
    <div style={{ padding: "28px 32px", maxWidth: 1100, margin: "0 auto" }}>
      <h2
        style={{
          fontSize: 22,
          fontWeight: 800,
          color: "#0f172a",
          margin: "0 0 4px",
          letterSpacing: "-0.02em",
        }}
      >
        KBLI 2025 Dashboard
      </h2>
      <p style={{ fontSize: 13, color: "#64748b", margin: "0 0 22px" }}>
        Real-time analytics across 1,562 Indonesian business classification
        codes
      </p>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: 12,
          marginBottom: 24,
        }}
      >
        {stats.map((s, i) => (
          <div
            key={i}
            style={{
              padding: "16px 18px",
              borderRadius: 14,
              border: "1px solid #e2e8f0",
              background: "#fff",
            }}
          >
            <div
              style={{
                width: 34,
                height: 34,
                borderRadius: 10,
                background: `${s.color}14`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                marginBottom: 10,
              }}
            >
              <I name={s.icon} size={17} color={s.color} />
            </div>
            <div
              style={{
                fontSize: 26,
                fontWeight: 800,
                color: "#0f172a",
                letterSpacing: "-0.02em",
              }}
            >
              {s.value}
            </div>
            <div
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: "#64748b",
                marginTop: 2,
              }}
            >
              {s.label}
            </div>
            <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 3 }}>
              {s.sub}
            </div>
          </div>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
        {[
          { title: "Risk Level Distribution", data: riskData },
          { title: "KBLI 2020 → 2025 Transition", data: statusData },
        ].map((section, si) => (
          <div
            key={si}
            style={{
              padding: "18px 20px",
              borderRadius: 14,
              border: "1px solid #e2e8f0",
              background: "#fff",
            }}
          >
            <div
              style={{
                fontSize: 14,
                fontWeight: 700,
                color: "#0f172a",
                marginBottom: 14,
              }}
            >
              {section.title}
            </div>
            {section.data.map((r, i) => (
              <div key={i} style={{ marginBottom: 10 }}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    marginBottom: 4,
                  }}
                >
                  <span
                    style={{ fontSize: 12, fontWeight: 600, color: "#334155" }}
                  >
                    {r.label}
                  </span>
                  <span style={{ fontSize: 12, color: "#64748b" }}>
                    {r.count} ({r.pct}%)
                  </span>
                </div>
                <div
                  style={{
                    height: 8,
                    borderRadius: 4,
                    background: "#f1f5f9",
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      height: "100%",
                      width: `${r.pct}%`,
                      background: r.color,
                      borderRadius: 4,
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        ))}
      </div>

      <div
        style={{
          marginTop: 14,
          padding: "12px 16px",
          borderRadius: 12,
          background: "#f0f9ff",
          border: "1px solid #bae6fd",
          display: "flex",
          alignItems: "center",
          gap: 10,
        }}
      >
        <I name="info" size={18} color="#0284c7" />
        <div style={{ fontSize: 12, color: "#0c4a6e", lineHeight: 1.5 }}>
          <strong>Key insight:</strong> 54% of KBLI 2025 codes are fully open to
          foreign investment (TERBUKA). 70% had direct mapping from KBLI 2020.
        </div>
      </div>
    </div>
  );
}

// =====================================================================
// MAIN APP
// =====================================================================

export default function App() {
  const [view, setView] = useState("finder");
  const [chatOpen, setChatOpen] = useState(true);
  const [lang, setLang] = useState("en");

  const tabs = [
    { id: "finder", label: "Code Finder", icon: "search" },
    { id: "browse", label: "Browse Sectors", icon: "db" },
    { id: "dashboard", label: "Dashboard", icon: "chart" },
  ];

  return (
    <div
      style={{
        height: "100vh",
        display: "flex",
        flexDirection: "column",
        fontFamily: "Inter, -apple-system, system-ui, sans-serif",
        background: "#f8fafc",
        color: "#0f172a",
      }}
    >
      {/* TOP BAR */}
      <header
        style={{
          height: 54,
          display: "flex",
          alignItems: "center",
          padding: "0 18px",
          gap: 14,
          background: "#fff",
          borderBottom: "1px solid #e2e8f0",
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
          <div
            style={{
              width: 28,
              height: 28,
              borderRadius: 7,
              background: "linear-gradient(135deg,#4f46e5,#7c3aed)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <I name="scale" size={14} color="#fff" />
          </div>
          <span style={{ fontSize: 15, fontWeight: 800, color: "#0f172a" }}>
            KBLI 2025
          </span>
          <span style={{ fontSize: 15, fontWeight: 400, color: "#94a3b8" }}>
            Navigator Pro
          </span>
        </div>

        <nav
          style={{
            display: "flex",
            gap: 2,
            marginLeft: 20,
            background: "#f1f5f9",
            borderRadius: 10,
            padding: 3,
          }}
        >
          {tabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setView(t.id)}
              style={{
                padding: "7px 14px",
                borderRadius: 8,
                border: "none",
                cursor: "pointer",
                background: view === t.id ? "#fff" : "transparent",
                boxShadow:
                  view === t.id ? "0 1px 3px rgba(0,0,0,0.08)" : "none",
                color: view === t.id ? "#0f172a" : "#64748b",
                fontSize: 13,
                fontWeight: view === t.id ? 700 : 500,
                display: "flex",
                alignItems: "center",
                gap: 5,
              }}
            >
              <I name={t.icon} size={14} />
              {t.label}
            </button>
          ))}
        </nav>

        <div
          style={{
            marginLeft: "auto",
            display: "flex",
            alignItems: "center",
            gap: 10,
          }}
        >
          <div
            style={{
              display: "flex",
              borderRadius: 7,
              overflow: "hidden",
              border: "1px solid #e2e8f0",
            }}
          >
            {["EN", "ID"].map((l) => (
              <button
                key={l}
                onClick={() => setLang(l.toLowerCase())}
                style={{
                  padding: "4px 10px",
                  border: "none",
                  cursor: "pointer",
                  background: lang === l.toLowerCase() ? "#4f46e5" : "#fff",
                  color: lang === l.toLowerCase() ? "#fff" : "#64748b",
                  fontSize: 11,
                  fontWeight: 700,
                }}
              >
                {l}
              </button>
            ))}
          </div>

          <button
            onClick={() => setChatOpen(!chatOpen)}
            style={{
              padding: "6px 12px",
              borderRadius: 8,
              border: "none",
              cursor: "pointer",
              background: chatOpen
                ? "linear-gradient(135deg,#4f46e5,#7c3aed)"
                : "#f1f5f9",
              color: chatOpen ? "#fff" : "#64748b",
              fontSize: 12,
              fontWeight: 700,
              display: "flex",
              alignItems: "center",
              gap: 5,
            }}
          >
            <I name="chat" size={14} color={chatOpen ? "#fff" : "#64748b"} />
            AI Chat
          </button>

          <button
            style={{
              padding: "6px 14px",
              borderRadius: 8,
              border: "1.5px solid #e2e8f0",
              background: "#fff",
              color: "#334155",
              fontSize: 12,
              fontWeight: 600,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 5,
            }}
          >
            <I name="briefcase" size={14} /> Contact 3Om
          </button>
        </div>
      </header>

      {/* CONTENT */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {chatOpen && (
          <div
            style={{
              width: 360,
              flexShrink: 0,
              borderRight: "1px solid #e2e8f0",
            }}
          >
            <ChatPanel />
          </div>
        )}
        <main style={{ flex: 1, overflowY: "auto" }}>
          {view === "finder" && <CodeFinderView />}
          {view === "browse" && <BrowseSectorsView />}
          {view === "dashboard" && <DashboardView />}
        </main>
      </div>

      {/* FOOTER */}
      <footer
        style={{
          height: 34,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#fff",
          borderTop: "1px solid #e2e8f0",
          fontSize: 11,
          color: "#94a3b8",
          gap: 12,
          flexShrink: 0,
        }}
      >
        <span>
          Powered by <strong style={{ color: "#4f46e5" }}>balizero.com</strong>{" "}
          × 3Om Consulting
        </span>
        <span>·</span>
        <span>BPS Regulation No. 7/2025</span>
        <span>·</span>
        <span>Not legal advice</span>
      </footer>
    </div>
  );
}
