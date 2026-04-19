import { BZLogo } from "@balizero/core/components/BZLogo";

export function BrandEntrance() {
  return (
    <section className="text-center pt-28 pb-16 px-10">
      <div className="flex justify-center mb-6">
        <BZLogo variant="full" size={44} />
      </div>
      <p
        className="text-[15px] tracking-widest uppercase mb-10"
        style={{ color: "var(--text-tertiary)", fontWeight: 300 }}
      >
        Your business in Bali &nbsp;·&nbsp;{" "}
        <strong style={{ color: "var(--text-secondary)", fontWeight: 500 }}>
          Visa · Company · Tax · Property
        </strong>
      </p>
      <div className="flex justify-center gap-12 flex-wrap">
        <Stat n="5,000+" l="Clients Served" />
        <Stat n="Since 2019" l="Years of Excellence" />
        <Stat n="4" l="Expert Platforms" />
        <Stat n="100%" l="Legal Compliance" />
      </div>
    </section>
  );
}

function Stat({ n, l }: { n: string; l: string }) {
  return (
    <div className="text-center">
      <div
        className="text-[28px] font-extrabold leading-none"
        style={{
          background: "linear-gradient(135deg, var(--text-primary) 0%, var(--text-secondary) 100%)",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
          backgroundClip: "text",
        }}
      >
        {n}
      </div>
      <div
        className="text-[11px] uppercase tracking-wider mt-1"
        style={{ color: "var(--text-tertiary)" }}
      >
        {l}
      </div>
    </div>
  );
}
