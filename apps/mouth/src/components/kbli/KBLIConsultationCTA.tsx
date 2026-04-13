import Link from "next/link";

const WHATSAPP_BASE = "https://wa.me/628213107363";

interface KBLIConsultationCTAProps {
  code: string;
  titleEn: string;
  pmaStatus: string;
}

export function KBLIConsultationCTA({
  code,
  titleEn,
  pmaStatus,
}: KBLIConsultationCTAProps) {
  const isPMAOpen = pmaStatus === "open" || pmaStatus === "restricted";
  const waText = encodeURIComponent(
    `Hello Bali Zero! I'm looking at KBLI ${code} (${titleEn}). I need help setting up my company. Can you guide me?`,
  );

  return (
    <section className="mt-12">
      <div
        className="rounded-2xl border p-6 sm:p-8"
        style={{
          background:
            "linear-gradient(135deg, rgba(212,132,90,0.08) 0%, rgba(30,30,35,0.95) 100%)",
          borderColor: "rgba(212,132,90,0.2)",
        }}
      >
        <div className="flex flex-col gap-6">
          {/* Header */}
          <div className="flex items-start gap-4">
            <div
              className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl text-2xl"
              style={{ backgroundColor: "rgba(212,132,90,0.15)" }}
            >
              {isPMAOpen ? "\u{1f3e2}" : "\u{1f4cb}"}
            </div>
            <div>
              <h2 className="text-lg font-bold text-[var(--kbli-text-primary)]">
                Ready to register this business?
              </h2>
              <p className="mt-1 text-sm text-[var(--kbli-text-muted)]">
                Bali Zero handles PT PMA setup, KBLI registration, NIB, and all
                licensing for KBLI {code}.
              </p>
            </div>
          </div>

          {/* Service cards */}
          <div className="grid gap-3 sm:grid-cols-2">
            {isPMAOpen && (
              <div
                className="rounded-xl border p-4"
                style={{
                  background: "rgba(255,255,255,0.03)",
                  borderColor: "rgba(255,255,255,0.06)",
                }}
              >
                <p className="text-xs font-medium uppercase tracking-wider text-[var(--kbli-text-muted)]">
                  PT PMA Setup
                </p>
                <p className="mt-1 text-xl font-bold text-[var(--kbli-text-primary)]">
                  IDR 20.000.000
                </p>
                <p className="mt-1 text-xs text-[var(--kbli-text-muted)]">
                  Company registration, KBLI, NIB, domicile
                </p>
              </div>
            )}
            <div
              className="rounded-xl border p-4"
              style={{
                background: "rgba(255,255,255,0.03)",
                borderColor: "rgba(255,255,255,0.06)",
              }}
            >
              <p className="text-xs font-medium uppercase tracking-wider text-[var(--kbli-text-muted)]">
                Virtual Office
              </p>
              <p className="mt-1 text-xl font-bold text-[var(--kbli-text-primary)]">
                IDR 5.000.000
              </p>
              <p className="mt-1 text-xs text-[var(--kbli-text-muted)]">
                Legal address for your PT PMA in Bali
              </p>
            </div>
          </div>

          {/* Trust + CTA */}
          <div className="flex flex-col items-start gap-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs text-[var(--kbli-text-muted)]">
              5,000+ companies registered since 2020
            </p>
            <a
              href={`${WHATSAPP_BASE}?text=${waText}`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-xl px-6 py-3 text-sm font-semibold text-white transition-opacity hover:opacity-90"
              style={{ backgroundColor: "#25d366" }}
            >
              <svg
                viewBox="0 0 24 24"
                className="h-4 w-4"
                fill="currentColor"
                aria-hidden="true"
              >
                <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
              </svg>
              Get started on WhatsApp
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}
