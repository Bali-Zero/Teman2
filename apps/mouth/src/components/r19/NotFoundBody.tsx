import Link from "next/link";

// One 404 body for the whole R19 surface: `(blog)/not-found.tsx` and the
// root `app/not-found.tsx` both render this inside a (possibly `force`d)
// R19Presentation, so a broken link always lands on the same paper-and-copper
// page instead of the two dark, pre-R19 designs it replaces.
const LINKS = [
  { href: "/", label: "Home" },
  { href: "/services", label: "Services" },
  { href: "/news", label: "News" },
  { href: "/contact", label: "Contact" },
];

export function NotFoundBody() {
  return (
    <div
      className="max-w-3xl mx-auto px-6 md:px-10"
      style={{
        padding:
          "clamp(56px, 7vw, 96px) clamp(24px, 4vw, 40px) clamp(48px, 6vw, 80px)",
      }}
    >
      <div
        className="text-[11px] font-semibold uppercase tracking-[0.28em] mb-4"
        style={{ color: "var(--r19-copper)" }}
      >
        404
      </div>
      <h1
        className="tracking-tight mb-4"
        style={{
          fontSize: "clamp(30px, 4.5vw, 52px)",
          lineHeight: 1.08,
          color: "var(--text-primary)",
        }}
      >
        This page doesn&apos;t exist
      </h1>
      <p
        className="mb-10"
        style={{
          fontSize: "16px",
          lineHeight: 1.6,
          color: "var(--text-secondary)",
          maxWidth: "60ch",
        }}
      >
        The link may be broken, or the page may have moved.
      </p>
      <div
        style={{
          borderTop: "1px solid var(--r19-line)",
          paddingTop: "24px",
        }}
      >
        <ul
          className="flex flex-wrap gap-x-6 gap-y-2"
          style={{ listStyle: "none", padding: 0, margin: 0 }}
        >
          {LINKS.map((link) => (
            <li key={link.href}>
              <Link
                href={link.href}
                className="underline"
                style={{ color: "var(--r19-copper)" }}
              >
                {link.label}
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
