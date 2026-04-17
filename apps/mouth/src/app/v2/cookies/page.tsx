import type { Metadata } from "next";
import { NavShell } from "@balizero/core/components/NavShell";
import { BZLogo } from "@balizero/core/components/BZLogo";
import { Footer } from "../_components/Footer";

export const metadata: Metadata = {
  title: "Cookie Policy",
  robots: { index: false, follow: false },
};

export default function CookiePage() {
  return (
    <div
      style={{
        background: "var(--surface-base)",
        color: "var(--text-primary)",
        minHeight: "100vh",
      }}
    >
      <NavShell
        logo={<BZLogo variant="full" size={36} />}
        items={[{ label: "Home", href: "/v2" }]}
        actions={null}
      />

      <main className="max-w-3xl mx-auto px-6 md:px-10 pt-28 pb-20">
        <div
          className="text-[10px] font-semibold uppercase tracking-[0.2em] mb-4"
          style={{ color: "var(--text-tertiary)" }}
        >
          Legal · Last updated April 2026
        </div>

        <h1
          className="font-black tracking-tight mb-8"
          style={{ fontSize: "clamp(28px, 4vw, 44px)", lineHeight: 1.1 }}
        >
          Cookie Policy
        </h1>

        <div style={{ color: "var(--text-secondary)" }}>
          <p
            className="text-[15px] leading-relaxed mb-8 font-medium"
            style={{ color: "var(--text-primary)" }}
          >
            We use cookies to keep the site working and to understand how people
            use it. Here is what we set and why.
          </p>

          <div className="overflow-x-auto mb-8">
            <table
              className="w-full text-[13px]"
              style={{ borderCollapse: "collapse" }}
            >
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border-default)" }}>
                  <th
                    className="text-left py-3 pr-4 font-bold"
                    style={{ color: "var(--text-primary)" }}
                  >
                    Cookie
                  </th>
                  <th
                    className="text-left py-3 pr-4 font-bold"
                    style={{ color: "var(--text-primary)" }}
                  >
                    Type
                  </th>
                  <th
                    className="text-left py-3 pr-4 font-bold"
                    style={{ color: "var(--text-primary)" }}
                  >
                    Duration
                  </th>
                  <th
                    className="text-left py-3 font-bold"
                    style={{ color: "var(--text-primary)" }}
                  >
                    Purpose
                  </th>
                </tr>
              </thead>
              <tbody>
                {[
                  [
                    "nz_access_token",
                    "Essential",
                    "Session",
                    "SSO authentication across balizero.com subdomains",
                  ],
                  [
                    "theme",
                    "Essential",
                    "1 year",
                    "Stores light/dark mode preference",
                  ],
                  [
                    "_ga / _ga_*",
                    "Analytics",
                    "2 years",
                    "Google Analytics — page views, traffic sources (anonymized IP)",
                  ],
                  [
                    "_gid",
                    "Analytics",
                    "24 hours",
                    "Google Analytics — session identification",
                  ],
                ].map(([name, type, dur, purpose]) => (
                  <tr
                    key={name}
                    style={{
                      borderBottom:
                        "1px solid color-mix(in srgb, var(--border-default) 50%, transparent)",
                    }}
                  >
                    <td
                      className="py-2.5 pr-4 font-mono text-[12px]"
                      style={{ color: "var(--accent-funnel-text)" }}
                    >
                      {name}
                    </td>
                    <td className="py-2.5 pr-4">{type}</td>
                    <td className="py-2.5 pr-4">{dur}</td>
                    <td className="py-2.5">{purpose}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <section className="mb-8">
            <h2
              className="text-[18px] font-bold tracking-tight mb-3"
              style={{ color: "var(--text-primary)" }}
            >
              Managing cookies
            </h2>
            <p className="text-[14px] leading-relaxed">
              Essential cookies cannot be disabled without breaking login and
              preferences. Analytics cookies are loaded only after consent. You
              can revoke consent at any time by clearing cookies in your browser
              settings or contacting us.
            </p>
          </section>

          <div
            className="mt-12 p-5 rounded-xl text-[13px]"
            style={{
              background:
                "color-mix(in srgb, var(--text-tertiary) 8%, transparent)",
              border: "1px solid var(--border-default)",
              color: "var(--text-tertiary)",
            }}
          >
            For questions, contact{" "}
            <a
              href="mailto:privacy@balizero.com"
              style={{ color: "var(--accent-funnel-text)" }}
            >
              privacy@balizero.com
            </a>
            . See also our{" "}
            <a
              href="/v2/privacy"
              style={{ color: "var(--accent-funnel-text)" }}
            >
              Privacy Policy
            </a>
            .
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}
