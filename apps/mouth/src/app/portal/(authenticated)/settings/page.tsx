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
 */
export default function SettingsPage() {
  return (
    <main className="max-w-3xl mx-auto px-4 py-6">
      <h1 className="text-2xl font-light text-[#f0ece4] mb-6">Settings</h1>
      <SettingsTabs />
    </main>
  );
}
