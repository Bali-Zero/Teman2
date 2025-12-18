"use client";

import React, { useState } from "react";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";

interface DashboardLayoutProps {
  children: React.ReactNode;
  title?: string;
}

export function DashboardLayout({ children, title }: DashboardLayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen bg-[var(--background)]">
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {/* Main content area - offset by sidebar width on desktop */}
      <div className="md:ml-64">
        <Header
          onMenuClick={() => setSidebarOpen(true)}
          title={title}
        />
        <main className="p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
