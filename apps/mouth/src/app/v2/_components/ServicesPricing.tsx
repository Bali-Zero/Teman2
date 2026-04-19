import {
  IdCard,
  Building2,
  TrendingUp,
  MapPinned,
  MapPin,
  type LucideIcon,
} from "lucide-react";
import type { Funnel } from "@balizero/core/components/ThemeProvider";

interface Service {
  Icon: LucideIcon;
  funnel: Exclude<Funnel, null>;
  name: string;
  desc: string;
  price: string;
  per: string;
  loc: string;
}

const SERVICES: Service[] = [
  {
    Icon: IdCard,
    funnel: "visa",
    name: "Visa Processing",
    desc: "End-to-end visa application management. Tourist, business, KITAS, and retirement visas.",
    price: "$350",
    per: "/ visa",
    loc: "Seminyak, Bali",
  },
  {
    Icon: Building2,
    funnel: "kbli",
    name: "Company Setup",
    desc: "PT PMA, PT Lokal, CV establishment. Full legal setup from registration to NIB.",
    price: "$1,850",
    per: "/ company",
    loc: "Kuta, Bali",
  },
  {
    Icon: TrendingUp,
    funnel: "tax",
    name: "Tax & Accounting",
    desc: "Monthly reporting, annual SPT, VAT compliance. CoreTax integrated workflow.",
    price: "$220",
    per: "/ month",
    loc: "Denpasar, Bali",
  },
  {
    Icon: MapPinned,
    funnel: "property",
    name: "Property Due Diligence",
    desc: "Legal verification, zoning checks, land certificate review. Full property intelligence.",
    price: "$850",
    per: "/ report",
    loc: "Ubud, Bali",
  },
];

export function ServicesPricing() {
  return (
    <section
      className="py-10 px-10"
      style={{ background: "var(--surface-base)" }}
    >
      <div
        className="text-[11px] font-semibold uppercase tracking-widest mb-5"
        style={{ color: "var(--text-tertiary)" }}
      >
        Services &amp; Pricing
      </div>
      <div className="grid grid-cols-4 gap-4">
        {SERVICES.map((s) => (
          <div
            key={s.name}
            data-funnel={s.funnel}
            className="bz-glass bz-glass--strong p-4 flex items-center gap-4"
          >
            <div
              className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
              style={{
                background:
                  "color-mix(in srgb, var(--accent-funnel) 22%, transparent)",
                border:
                  "1px solid color-mix(in srgb, var(--accent-funnel) 45%, transparent)",
                color: "var(--accent-funnel-text)",
                backdropFilter: "blur(12px)",
                WebkitBackdropFilter: "blur(12px)",
              }}
            >
              <s.Icon size={18} strokeWidth={1.5} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-baseline justify-between gap-2 mb-0.5">
                <h4
                  className="text-[13px] font-bold tracking-tight truncate"
                  style={{ color: "var(--text-primary)" }}
                >
                  {s.name}
                </h4>
                <div
                  className="text-[16px] font-extrabold tracking-tight shrink-0"
                  style={{ color: "var(--text-primary)" }}
                >
                  {s.price}
                  <span
                    className="text-[10px] font-normal ml-0.5"
                    style={{ color: "var(--text-tertiary)" }}
                  >
                    {s.per}
                  </span>
                </div>
              </div>
              <div
                className="text-[10px] flex items-center gap-1"
                style={{ color: "var(--text-tertiary)" }}
              >
                <MapPin size={10} strokeWidth={1.8} />
                {s.loc}
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
