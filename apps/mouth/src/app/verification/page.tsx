"use client";

import { useState, useRef } from "react";
import { ChatHeader } from "@/components/chat/ChatHeader";
import { logger } from "@/lib/logger";

export default function VerificationPage() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isClockIn, setIsClockIn] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const userMenuRef = useRef<HTMLDivElement>(null);
  const avatarInputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="min-h-screen bg-[var(--background)] p-8">
      <h1 className="text-2xl font-bold mb-8 text-white">
        ChatHeader Accessibility Verification
      </h1>

      <div className="border border-[var(--border)] rounded-xl overflow-hidden bg-[var(--background-secondary)]">
        <ChatHeader
          isSidebarOpen={isSidebarOpen}
          onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)}
          isClockIn={isClockIn}
          isClockLoading={false}
          onToggleClock={() => setIsClockIn(!isClockIn)}
          messagesCount={5}
          isWsConnected={true}
          userName="Test User"
          userAvatar={null}
          showUserMenu={showUserMenu}
          onToggleUserMenu={() => setShowUserMenu(!showUserMenu)}
          userMenuRef={userMenuRef}
          avatarInputRef={avatarInputRef}
          onAvatarUpload={() => {}}
          onShowToast={(msg) => logger.info(msg)}
        />
      </div>

      <div className="mt-8 p-4 bg-[var(--background-elevated)] rounded-lg text-sm text-[var(--foreground-muted)]">
        <h2 className="font-semibold mb-2">Checklist:</h2>
        <ul className="list-disc pl-5 space-y-1">
          <li>
            Hover over the menu button: Should show "Open sidebar" tooltip.
          </li>
          <li>Hover over the clock button: Should show "Clock In" tooltip.</li>
          <li>
            Hover over the notification icon: Should show "Notifications"
            tooltip.
          </li>
          <li>Click the avatar: User menu should open.</li>
          <li>
            Inspect (Accessibility tab):
            <ul className="list-circle pl-5 mt-1">
              <li>
                Menu, Clock, Bell icons should have{" "}
                <code>aria-hidden="true"</code>.
              </li>
              <li>
                User menu button should have <code>aria-controls</code> pointing
                to the menu ID.
              </li>
              <li>
                User dropdown should have <code>role="menu"</code> and the
                corresponding <code>id</code>.
              </li>
            </ul>
          </li>
        </ul>
      </div>
    </div>
  );
}
