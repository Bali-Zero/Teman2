'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Bell, Check, CheckCheck, FileText, RefreshCw, AlertTriangle, MessageCircle } from 'lucide-react';
import { usePortalNotifications } from '@/hooks/usePortalNotifications';
import type { PortalNotification } from '@/lib/api/portal/portal.types';

function getNotificationIcon(type: string) {
  switch (type) {
    case 'document_verified':
    case 'document_uploaded':
      return <FileText className="w-4 h-4" />;
    case 'status_changed':
      return <RefreshCw className="w-4 h-4" />;
    case 'message_received':
      return <MessageCircle className="w-4 h-4" />;
    case 'deadline_approaching':
      return <AlertTriangle className="w-4 h-4" />;
    default:
      return <Bell className="w-4 h-4" />;
  }
}

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return '';
  const diff = Date.now() - new Date(dateStr).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export function PortalNotificationBadge({ count }: { count: number }) {
  if (count === 0) return null;
  return (
    <span
      className="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 rounded-full text-[10px] font-bold flex items-center justify-center"
      style={{ background: 'var(--bz-accent-warm)', color: '#0c0c0e' }}
    >
      {count > 99 ? '99+' : count}
    </span>
  );
}

export function PortalNotificationsList({
  notifications,
  onMarkRead,
  onMarkAllRead,
}: {
  notifications: PortalNotification[];
  onMarkRead: (id: number) => void;
  onMarkAllRead: () => void;
}) {
  const unread = notifications.filter((n) => !n.read);

  return (
    <div className="w-80 max-h-96 overflow-y-auto">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: 'rgba(255,255,255,0.05)' }}>
        <span className="text-sm font-semibold">Notifications</span>
        {unread.length > 0 && (
          <button
            onClick={onMarkAllRead}
            className="text-xs flex items-center gap-1 transition-opacity hover:opacity-80"
            style={{ color: 'var(--bz-accent-warm)' }}
          >
            <CheckCheck className="w-3 h-3" />
            Mark all read
          </button>
        )}
      </div>

      {/* List */}
      {notifications.length === 0 ? (
        <div className="px-4 py-8 text-center">
          <Bell className="w-8 h-8 mx-auto mb-2 opacity-20" style={{ color: 'var(--bz-text-2)' }} />
          <p className="text-xs" style={{ color: 'var(--bz-text-3)' }}>No notifications yet</p>
        </div>
      ) : (
        <div className="divide-y" style={{ borderColor: 'rgba(255,255,255,0.03)' }}>
          {notifications.map((notif) => (
            <div
              key={notif.id}
              className="px-4 py-3 flex items-start gap-3 transition-colors hover:bg-white/[0.02]"
              style={!notif.read ? { background: 'rgba(201,169,110,0.04)' } : {}}
            >
              <div
                className="p-1.5 rounded-md mt-0.5 flex-shrink-0"
                style={{ background: notif.read ? 'rgba(255,255,255,0.03)' : 'rgba(201,169,110,0.12)' }}
              >
                {React.cloneElement(getNotificationIcon(notif.type), {
                  style: { color: notif.read ? 'var(--bz-text-3)' : 'var(--bz-accent-warm)' },
                })}
              </div>
              <div className="flex-1 min-w-0">
                <p className={`text-xs ${notif.read ? '' : 'font-semibold'}`}>{notif.title}</p>
                {notif.body && (
                  <p className="text-xs mt-0.5 line-clamp-2" style={{ color: 'var(--bz-text-3)' }}>
                    {notif.body}
                  </p>
                )}
                <p className="text-[10px] mt-1" style={{ color: 'var(--bz-text-3)' }} suppressHydrationWarning>
                  {timeAgo(notif.created_at)}
                </p>
              </div>
              {!notif.read && (
                <button
                  onClick={() => onMarkRead(notif.id)}
                  className="p-1 rounded-md mt-0.5 flex-shrink-0 transition-opacity hover:opacity-80"
                  style={{ color: 'var(--bz-accent-warm)' }}
                  aria-label="Mark as read"
                >
                  <Check className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function PortalNotificationsPopover() {
  const { notifications, unreadCount, markRead, markAllRead } = usePortalNotifications();
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [isOpen]);

  // Close on Escape
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setIsOpen(false);
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [isOpen]);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 rounded-lg transition-colors hover:bg-white/[0.05]"
        aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ''}`}
      >
        <Bell className="w-5 h-5" style={{ color: 'var(--bz-text-2)' }} />
        <PortalNotificationBadge count={unreadCount} />
      </button>

      {isOpen && (
        <div
          className="absolute right-0 top-full mt-2 rounded-xl border shadow-2xl z-50 overflow-hidden"
          style={{
            background: 'rgba(24,24,28,0.95)',
            borderColor: 'rgba(255,255,255,0.08)',
            backdropFilter: 'blur(24px)',
          }}
        >
          <PortalNotificationsList
            notifications={notifications}
            onMarkRead={(id) => markRead(id)}
            onMarkAllRead={() => markAllRead()}
          />
        </div>
      )}
    </div>
  );
}
