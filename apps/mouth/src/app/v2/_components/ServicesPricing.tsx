interface Service {
  icon: string;
  name: string;
  desc: string;
  price: string;
  per: string;
  loc: string;
}

const SERVICES: Service[] = [
  {
    icon: "🛂",
    name: "Visa Processing",
    desc: "End-to-end visa application management. Tourist, business, KITAS, and retirement visas.",
    price: "$350",
    per: "/ visa",
    loc: "Seminyak, Bali",
  },
  {
    icon: "🏢",
    name: "Company Setup",
    desc: "PT PMA, PT Lokal, CV establishment. Full legal setup from registration to NIB.",
    price: "$1,850",
    per: "/ company",
    loc: "Kuta, Bali",
  },
  {
    icon: "📊",
    name: "Tax & Accounting",
    desc: "Monthly reporting, annual SPT, VAT compliance. CoreTax integrated workflow.",
    price: "$220",
    per: "/ month",
    loc: "Denpasar, Bali",
  },
  {
    icon: "🏡",
    name: "Property Due Diligence",
    desc: "Legal verification, zoning checks, land certificate review. Full property intelligence.",
    price: "$850",
    per: "/ report",
    loc: "Ubud, Bali",
  },
];

export function ServicesPricing() {
  return (
    <section className="py-20 px-10" style={{ background: "var(--surface-base)" }}>
      <div
        className="text-[11px] font-semibold uppercase tracking-widest mb-10"
        style={{ color: "var(--text-tertiary)" }}
      >
        Services & Pricing
      </div>
      <div className="grid grid-cols-4 gap-4">
        {SERVICES.map((s) => (
          <div
            key={s.name}
            className="rounded-2xl p-7 transition-all hover:-translate-y-0.5"
            style={{
              background: "var(--surface-raised)",
              border: "1px solid var(--border-default)",
            }}
          >
            <div
              className="w-11 h-11 rounded-xl mb-4 flex items-center justify-center text-[22px]"
              style={{ background: "color-mix(in srgb, var(--accent-zantara) 10%, transparent)" }}
            >
              {s.icon}
            </div>
            <h4
              className="text-[16px] font-bold tracking-tight mb-1.5"
              style={{ color: "var(--text-primary)" }}
            >
              {s.name}
            </h4>
            <p className="text-xs leading-relaxed mb-4" style={{ color: "var(--text-tertiary)" }}>
              {s.desc}
            </p>
            <div
              className="text-[22px] font-extrabold tracking-tight"
              style={{ color: "var(--text-primary)" }}
            >
              {s.price}{" "}
              <span className="text-xs font-normal" style={{ color: "var(--text-tertiary)" }}>
                {s.per}
              </span>
            </div>
            <div className="text-[11px] mt-1" style={{ color: "var(--text-tertiary)" }}>
              📍 {s.loc}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
