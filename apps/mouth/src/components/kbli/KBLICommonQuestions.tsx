import { buildKbliFaq } from "@/lib/kbli-faq";
import type { KBLICode } from "@/lib/kbli-types";

/**
 * Visible counterpart of KBLIFaqJsonLd — both render from buildKbliFaq(),
 * so the FAQPage markup always has matching on-page content (Google
 * requires FAQ markup content to be visible on the page).
 */
export function KBLICommonQuestions({ code }: { code: KBLICode }) {
  const faq = buildKbliFaq(code);

  return (
    <section className="mt-8">
      <div className="flex items-center gap-4 py-2 mb-6">
        <div
          className="h-px flex-1"
          style={{ background: "var(--kbli-border)" }}
        />
        <span className="text-xs font-medium uppercase tracking-[0.15em] text-[var(--foreground-muted)]">
          Common Questions
        </span>
        <div
          className="h-px flex-1"
          style={{ background: "var(--kbli-border)" }}
        />
      </div>
      <div className="space-y-4">
        {faq.map((entry, i) => (
          <details
            key={entry.question}
            className="rounded-xl border border-[var(--border)] overflow-hidden"
            open={i === 0}
          >
            <summary
              className="cursor-pointer px-5 py-3.5 text-sm font-semibold text-[var(--foreground)] transition-colors hover:text-[var(--kbli-accent)]"
              style={{ background: "var(--kbli-bg-elevated)" }}
            >
              {entry.question}
            </summary>
            <div
              className="px-5 py-4 text-sm leading-relaxed text-[var(--foreground-secondary)]"
              style={{ background: "var(--kbli-bg-surface)" }}
            >
              {entry.answer}
            </div>
          </details>
        ))}
      </div>
    </section>
  );
}
