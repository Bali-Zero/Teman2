'use client';

import React from 'react';
import { PortalHeader } from '@/components/portal/PortalHeader';
import { PortalBottomNav } from '@/components/portal/PortalBottomNav';
import { ToastProvider } from '@/components/ui/toast';

export default function PortalLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ToastProvider>
      <div className="min-h-screen bg-neutral-50 dark:bg-neutral-950 text-neutral-900 dark:text-neutral-50 pb-20 md:pb-0">
        <PortalHeader />
        <main className="max-w-md mx-auto md:max-w-2xl lg:max-w-4xl px-4 py-6 md:py-8">
          {children}
        </main>
        <PortalBottomNav />
      </div>
    </ToastProvider>
  );
}