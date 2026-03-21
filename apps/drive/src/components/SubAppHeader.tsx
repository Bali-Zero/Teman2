// SubAppHeader.tsx — Warm Depth shell header for sub-apps (mail, calendar, drive, knowledge)
"use client";

import Link from "next/link";

interface SubAppHeaderProps {
  appName: string;
  userInitial?: string;
}

export function SubAppHeader({
  appName,
  userInitial = "Z",
}: SubAppHeaderProps) {
  return (
    <header
      className="h-[48px] flex items-center px-4 gap-3 border-b flex-shrink-0 sticky top-0 z-10"
      style={{
        background: "var(--bz-elevated, #131315)",
        borderColor: "var(--bz-border, rgba(255,255,255,0.055))",
      }}
    >
      {/* Logo + back to kita */}
      <Link
        href="https://kita.balizero.com"
        className="flex items-center gap-2 hover:opacity-80 transition-opacity"
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/static/balizero-logo-clean.png"
          alt="Bali Zero"
          className="w-[22px] h-[22px] rounded-full flex-shrink-0"
        />
      </Link>

      {/* Divider */}
      <span style={{ color: "var(--bz-text-3, #575350)", fontSize: 14 }}>
        /
      </span>

      {/* App name */}
      <span
        style={{
          fontSize: 13,
          fontWeight: 500,
          color: "var(--bz-text-1, #edeae4)",
        }}
      >
        {appName}
      </span>

      <div className="flex-1" />

      {/* User avatar */}
      <div
        className="w-[26px] h-[26px] rounded-[7px] flex items-center justify-center text-[10px] font-bold text-white flex-shrink-0 cursor-pointer hover:opacity-80 transition-opacity"
        style={{
          background: "linear-gradient(135deg, #c9a96e 0%, #d4845a 100%)",
        }}
      >
        {userInitial}
      </div>
    </header>
  );
}
