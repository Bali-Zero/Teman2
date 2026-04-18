"use client";

import * as Tabs from "@radix-ui/react-tabs";
import { useRouter, useSearchParams } from "next/navigation";
import { AccountSettings } from "./AccountSettings";
import { SecuritySettings } from "./SecuritySettings";
import { NotificationSettings } from "./NotificationSettings";
import { PrivacySettings } from "./PrivacySettings";
import { LanguageSettings } from "./LanguageSettings";

const TAB_IDS = [
  "account",
  "security",
  "notifications",
  "privacy",
  "language",
] as const;
type TabId = (typeof TAB_IDS)[number];

const LABELS: Record<TabId, string> = {
  account: "Account",
  security: "Security",
  notifications: "Notifications",
  privacy: "Privacy",
  language: "Language",
};

/**
 * URL-synced tab shell for /portal/settings.
 *
 * The active tab lives in the `?tab=<id>` query param; unknown/missing values
 * fall back to "account". Navigation uses `router.replace` so the tab switch
 * does not pollute the browser history stack.
 */
export function SettingsTabs() {
  const router = useRouter();
  const sp = useSearchParams();
  const raw = sp?.get("tab") ?? "account";
  const active: TabId = (TAB_IDS as readonly string[]).includes(raw)
    ? (raw as TabId)
    : "account";

  const setTab = (t: string) => {
    const params = new URLSearchParams(sp?.toString() ?? "");
    params.set("tab", t);
    router.replace(`/portal/settings?${params.toString()}`);
  };

  return (
    <Tabs.Root value={active} onValueChange={setTab}>
      <Tabs.List
        aria-label="Settings sections"
        className="flex flex-wrap gap-1 border-b border-white/10 mb-6"
      >
        {TAB_IDS.map((t) => (
          <Tabs.Trigger
            key={t}
            value={t}
            className="px-4 py-2 text-sm text-[#c9a96e]/70 data-[state=active]:text-[#f0ece4] data-[state=active]:border-b-2 data-[state=active]:border-[#d4845a]"
          >
            {LABELS[t]}
          </Tabs.Trigger>
        ))}
      </Tabs.List>
      <Tabs.Content value="account">
        <AccountSettings />
      </Tabs.Content>
      <Tabs.Content value="security">
        <SecuritySettings />
      </Tabs.Content>
      <Tabs.Content value="notifications">
        <NotificationSettings />
      </Tabs.Content>
      <Tabs.Content value="privacy">
        <PrivacySettings />
      </Tabs.Content>
      <Tabs.Content value="language">
        <LanguageSettings />
      </Tabs.Content>
    </Tabs.Root>
  );
}
