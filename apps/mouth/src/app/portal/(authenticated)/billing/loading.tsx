export default function BillingLoading() {
  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <section>
        <div
          className="h-7 w-40 rounded animate-pulse"
          style={{ background: "var(--bz-border)" }}
        />
        <div
          className="h-4 w-64 rounded mt-2 animate-pulse"
          style={{ background: "var(--bz-border)", opacity: 0.5 }}
        />
      </section>
      <div className="grid grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="rounded-xl border p-4 h-24 animate-pulse"
            style={{
              background: "rgba(30,30,35,0.7)",
              borderColor: "rgba(255,255,255,0.05)",
            }}
          />
        ))}
      </div>
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="rounded-lg border p-4 h-20 animate-pulse"
            style={{
              background: "rgba(30,30,35,0.7)",
              borderColor: "rgba(255,255,255,0.05)",
            }}
          />
        ))}
      </div>
    </div>
  );
}
