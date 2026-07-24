import { SettingsTabs } from "@/components/portal/settings/SettingsTabs";

/**
 * Portal Settings shell.
 *
 * The page itself is a thin server component that renders the
 * URL-synced tab shell. Each tab is an independent client component
 * responsible for its own data loading (SWR hooks) and mutations, so
 * the shell stays cheap to render and does not coupling-bleed across
 * unrelated concerns.
 *
 * The existing `settings/notifications/` subroute remains live (not
 * deleted) as it may be linked from deep-linked notification emails.
 *
 * WS3 slice 7 (GARUDA Day Edition, 2026-07-24): masthead = copper rule +
 * Cormorant serif (--font-serif) in --tx-pure (was hardcoded #f0ece4
 * font-light — invisible on operative-light paper).
 */
export default function SettingsPage() {
  return (
    <main className="max-w-3xl mx-auto px-4 py-6">
      <section className="mb-6">
        <div
          aria-hidden="true"
          className="w-14 h-[3px] rounded-sm mb-4 bg-[var(--bz-copper)]"
        />
        <h1
          className="text-2xl font-semibold tracking-tight text-[var(--tx-pure)]"
          style={{ fontFamily: "var(--font-serif)" }}
        >
          Settings
        </h1>
      </section>
      <SettingsTabs />
    </main>
  );
}
