import { MarkdownClient } from "@/components/kbli/MarkdownClient";
import type { KBLIEditorialContent } from "@/lib/kbli-types";

/**
 * LOOP-2 magazine layer — renders intel_2026.editorial as the article the code
 * page leads with: display headline, standfirst dek, "By the numbers" sidebar
 * card, editorial body, pull-quote. Server component, no client JS of its own.
 * Content arrives only through scripts/kbli_apply_editorials.py gates, so this
 * component renders it verbatim (markdown body via MarkdownClient).
 */
export function KBLIEditorial({ editorial }: { editorial: KBLIEditorialContent }) {
  return (
    <article className="relative">
      <header className="mb-8" style={{ maxWidth: "820px" }}>
        <h2
          className="mb-4 font-bold leading-tight"
          style={{ fontSize: "clamp(1.6rem, 3.2vw, 2.4rem)", letterSpacing: "-0.02em" }}
        >
          {editorial.headline}
        </h2>
        <p
          className="leading-relaxed"
          style={{ fontSize: "1.125rem", color: "var(--kbli-text-secondary)" }}
        >
          {editorial.standfirst}
        </p>
      </header>

      {editorial.byTheNumbers && editorial.byTheNumbers.length > 0 && (
        <aside
          className="mb-8 rounded-2xl p-6 lg:float-right lg:ml-8 lg:w-72"
          style={{
            background: "rgba(212, 132, 90, 0.04)",
            border: "1px solid var(--kbli-border)",
          }}
        >
          <div
            className="mb-4 text-xs font-bold uppercase tracking-widest"
            style={{ color: "var(--kbli-accent)" }}
          >
            By the numbers
          </div>
          <dl className="space-y-4">
            {editorial.byTheNumbers.map((n) => (
              <div key={n.label}>
                <dt
                  className="text-xs uppercase tracking-wide"
                  style={{ color: "var(--kbli-text-secondary)" }}
                >
                  {n.label}
                </dt>
                <dd className="mt-0.5 text-sm font-semibold">{n.value}</dd>
              </div>
            ))}
          </dl>
        </aside>
      )}

      <div className="kbli-prose" style={{ maxWidth: "720px" }}>
        <MarkdownClient withKbliLinks>{editorial.body}</MarkdownClient>
      </div>

      {editorial.pullQuote && (
        <blockquote
          className="my-10 border-l-2 pl-6 text-xl font-medium leading-snug lg:clear-right"
          style={{
            borderColor: "var(--kbli-accent)",
            color: "var(--kbli-text-primary)",
            maxWidth: "640px",
          }}
        >
          {editorial.pullQuote}
        </blockquote>
      )}
    </article>
  );
}
