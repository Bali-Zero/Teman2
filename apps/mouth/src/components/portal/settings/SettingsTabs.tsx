'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { AccountSettings } from './AccountSettings';
import { SecuritySettings } from './SecuritySettings';
import { NotificationSettings } from './NotificationSettings';
import { PrivacySettings } from './PrivacySettings';
import { LanguageSettings } from './LanguageSettings';

const TAB_IDS = ['account', 'security', 'notifications', 'privacy', 'language'] as const;
type TabId = (typeof TAB_IDS)[number];

const LABELS: Record<TabId, string> = {
  account: 'Account',
  security: 'Security',
  notifications: 'Notifications',
  privacy: 'Privacy',
  language: 'Language',
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
  const raw = sp?.get('tab') ?? 'account';
  const active: TabId = (TAB_IDS as readonly string[]).includes(raw) ? (raw as TabId) : 'account';

  const setTab = (t: string) => {
    const params = new URLSearchParams(sp?.toString() ?? '');
    params.set('tab', t);
    router.replace(`/portal/settings?${params.toString()}`);
  };

  return (
    <Tabs defaultValue="account" value={active} onValueChange={setTab}>
      <TabsList
        aria-label="Settings sections"
        role="tablist"
        className="flex flex-wrap gap-1 border-b border-white/10 mb-6"
      >
        {TAB_IDS.map((t) => (
          <TabsTrigger
            key={t}
            value={t}
            role="tab"
            aria-selected={active === t}
            className="px-4 py-2 text-sm text-[#c9a96e]/70 data-[state=active]:text-[#f0ece4] data-[state=active]:border-b-2 data-[state=active]:border-[#d4845a]"
          >
            {LABELS[t]}
          </TabsTrigger>
        ))}
      </TabsList>
      <TabsContent value="account" role="tabpanel">
        <AccountSettings />
      </TabsContent>
      <TabsContent value="security" role="tabpanel">
        <SecuritySettings />
      </TabsContent>
      <TabsContent value="notifications" role="tabpanel">
        <NotificationSettings />
      </TabsContent>
      <TabsContent value="privacy" role="tabpanel">
        <PrivacySettings />
      </TabsContent>
      <TabsContent value="language" role="tabpanel">
        <LanguageSettings />
      </TabsContent>
    </Tabs>
  );
}
