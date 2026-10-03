import type { Metadata } from "next";

export const metadata: Metadata = {
  alternates: {
    canonical: "https://balizero.com/cookies",
  },
  title: "Cookie Policy",
  robots: { index: false, follow: false },
};

export default function CookiePage() {
  return (
    <div
      className="max-w-3xl mx-auto px-6 md:px-10"
      style={{
        padding:
          "clamp(56px, 7vw, 96px) clamp(24px, 4vw, 40px) clamp(48px, 6vw, 80px)",
        fontVariantLigatures: "none",
      }}
    >
      <div
        className="text-[11px] font-semibold uppercase tracking-[0.28em] mb-4"
        style={{ color: "var(--text-tertiary)" }}
      >
        Legal · Last updated April 2026
      </div>

      <h1
        className="font-extrabold tracking-tight mb-10"
        style={{
          fontSize: "clamp(30px, 4.5vw, 52px)",
          lineHeight: 1.08,
          color: "var(--text-primary)",
        }}
      >
        Cookie Policy
      </h1>

      <div style={{ color: "var(--text-secondary)", maxWidth: "72ch" }}>
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
              <tr style={{ borderBottom: "1px solid var(--border-subtle)" }}>
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
                      "1px solid color-mix(in srgb, var(--border-subtle) 50%, transparent)",
                  }}
                >
                  <td
                    className="py-2.5 pr-4 font-mono text-[12px]"
                    style={{ color: "var(--r19-copper)" }}
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

        <section
          className="py-8"
          style={{ borderTop: "1px solid var(--border-subtle)" }}
        >
          <h2
            className="text-xl font-bold tracking-tight mb-3"
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
          className="mt-4 p-5 rounded-xl text-[13px]"
          style={{
            background:
              "color-mix(in srgb, var(--text-tertiary) 8%, transparent)",
            border: "1px solid var(--border-subtle)",
            color: "var(--text-tertiary)",
          }}
        >
          For questions, contact{" "}
          <a
            href="mailto:privacy@balizero.com"
            style={{ color: "var(--r19-copper)" }}
          >
            privacy@balizero.com
          </a>
          . See also our{" "}
          <a href="/privacy" style={{ color: "var(--r19-copper)" }}>
            Privacy Policy
          </a>
          .
        </div>
      </div>
    </div>
  );
}
