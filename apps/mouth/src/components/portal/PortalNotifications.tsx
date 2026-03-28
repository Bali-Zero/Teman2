'use client';

/**
 * PortalNotifications Component
 *
 * Visualizza notifiche e alert del portale clienti
 */

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  Bell,
  AlertTriangle,
  FileText,
  MessageSquare,
  Calendar,
  CheckCircle2,
  X,
  ChevronRight,
  ExternalLink,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { usePortalNotifications } from '@/hooks/usePortal';
import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';

interface PortalNotificationsProps {
  variant?: 'popover' | 'sidebar' | 'inline';
  maxItems?: number;
}

const ICONS = {
  visa: Calendar,
  document: FileText,
  tax: AlertTriangle,
  message: MessageSquare,
  action: CheckCircle2,
};

const SEVERITY_STYLES = {
  info: {
    bg: 'bg-blue-500/10',
    border: 'border-blue-500/20',
    text: 'text-blue-400',
    icon: 'text-blue-400',
  },
  warning: {
    bg: 'bg-yellow-500/10',
    border: 'border-yellow-500/20',
    text: 'text-yellow-400',
    icon: 'text-yellow-400',
  },
  critical: {
    bg: 'bg-red-500/10',
    border: 'border-red-500/20',
    text: 'text-red-400',
    icon: 'text-red-400',
  },
};

function NotificationItem({
  notification,
  onDismiss,
}: {
  notification: {
    id: string;
    type: string;
    title: string;
    message: string;
    severity: 'info' | 'warning' | 'critical';
    href?: string;
    createdAt: string;
  };
  onDismiss?: (id: string) => void;
}) {
  const router = useRouter();
  const Icon = ICONS[notification.type as keyof typeof ICONS] || Bell;
  const styles = SEVERITY_STYLES[notification.severity];

  const handleClick = () => {
    if (notification.href) {
      router.push(notification.href);
    }
  };

  return (
    <div
      className={cn(
        'relative p-3 rounded-lg border transition-colors',
        styles.bg,
        styles.border,
        notification.href && 'cursor-pointer hover:bg-opacity-20',
        'group'
      )}
      onClick={handleClick}
    >
      <div className="flex gap-3">
        <div className={cn('mt-0.5', styles.icon)}>
          <Icon className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <p className={cn('font-medium text-sm', styles.text)}>{notification.title}</p>
          <p className="text-sm text-gray-400 mt-0.5 line-clamp-2">{notification.message}</p>
        </div>
        {notification.href && (
          <ChevronRight className="w-4 h-4 text-gray-500 opacity-0 group-hover:opacity-100 transition-opacity" />
        )}
      </div>
      {onDismiss && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDismiss(notification.id);
          }}
          aria-label="Dismiss notification"
          className="absolute top-2 right-2 p-1 text-gray-500 hover:text-gray-300 opacity-0 group-hover:opacity-100 transition-opacity"
        >
          <X className="w-3 h-3" />
        </button>
      )}
    </div>
  );
}

/**
 * Popover notifications (header)
 */
export function PortalNotificationsPopover() {
  const [open, setOpen] = useState(false);
  const { notifications, unreadCount, criticalCount } = usePortalNotifications();
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  const visibleNotifications = notifications.filter((n) => !dismissed.has(n.id)).slice(0, 5);

  const handleDismiss = (id: string) => {
    setDismissed((prev) => new Set(prev).add(id));
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          aria-label={unreadCount > 0 ? `Notifications (${unreadCount} unread)` : 'Notifications'}
          className="relative p-2 text-[var(--foreground-muted)] hover:text-[var(--foreground)] transition-colors"
        >
          <Bell className="w-5 h-5" />
          {unreadCount > 0 && (
            <span
              className={cn(
                'absolute top-1 right-1 w-4 h-4 text-[10px] font-medium rounded-full flex items-center justify-center',
                criticalCount > 0 ? 'bg-red-500 text-white' : 'bg-[var(--accent)] text-white'
              )}
            >
              {unreadCount > 9 ? '9+' : unreadCount}
            </span>
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-80 p-0 bg-[#1a1a1a] border-gray-800" align="end">
        <div className="p-3 border-b border-gray-800">
          <div className="flex items-center justify-between">
            <h3 className="font-medium text-[var(--foreground)]">Notifications</h3>
            {criticalCount > 0 && (
              <span className="text-xs px-2 py-0.5 bg-red-500/20 text-red-400 rounded-full">
                {criticalCount} urgent
              </span>
            )}
          </div>
        </div>
        <div className="max-h-[400px] overflow-y-auto">
          {visibleNotifications.length === 0 ? (
            <div className="p-8 text-center text-gray-500">
              <Bell className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">No new notifications</p>
            </div>
          ) : (
            <div className="p-3 space-y-2">
              {visibleNotifications.map((notification) => (
                <NotificationItem
                  key={notification.id}
                  notification={notification}
                  onDismiss={handleDismiss}
                />
              ))}
            </div>
          )}
        </div>
        {notifications.length > 5 && (
          <div className="p-3 border-t border-gray-800">
            <Button
              variant="ghost"
              className="w-full text-sm text-[var(--foreground-muted)]"
              onClick={() => {
                setOpen(false);
                // Navigate to notifications page if exists
              }}
            >
              View all notifications
            </Button>
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}

/**
 * Inline notifications list
 */
export function PortalNotificationsList({ maxItems = 5 }: { maxItems?: number }) {
  const { notifications, criticalCount, warningCount } = usePortalNotifications();

  if (notifications.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        <CheckCircle2 className="w-12 h-12 mx-auto mb-2 opacity-50" />
        <p>No pending notifications</p>
        <p className="text-sm text-gray-600 mt-1">You're all caught up!</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        {criticalCount > 0 && (
          <span className="text-xs px-2 py-1 bg-red-500/20 text-red-400 rounded-full">
            {criticalCount} Critical
          </span>
        )}
        {warningCount > 0 && (
          <span className="text-xs px-2 py-1 bg-yellow-500/20 text-yellow-400 rounded-full">
            {warningCount} Warning
          </span>
        )}
      </div>

      <div className="space-y-2">
        {notifications.slice(0, maxItems).map((notification) => (
          <NotificationItem key={notification.id} notification={notification} />
        ))}
      </div>

      {notifications.length > maxItems && (
        <p className="text-center text-sm text-gray-500">
          +{notifications.length - maxItems} more notifications
        </p>
      )}
    </div>
  );
}

/**
 * Compact notification badge
 */
export function PortalNotificationBadge({ onClick }: { onClick?: () => void }) {
  const { unreadCount, criticalCount } = usePortalNotifications();

  if (unreadCount === 0) return null;

  return (
    <button
      onClick={onClick}
      aria-label={`Notifications (${unreadCount} unread)`}
      className={cn(
        'fixed bottom-20 right-4 md:hidden z-50',
        'w-12 h-12 rounded-full shadow-lg flex items-center justify-center',
        'transition-transform hover:scale-105',
        criticalCount > 0 ? 'bg-red-500' : 'bg-[var(--accent)]'
      )}
    >
      <Bell className="w-5 h-5 text-white" />
      <span className="absolute -top-1 -right-1 w-5 h-5 bg-white text-black text-xs font-bold rounded-full flex items-center justify-center">
        {unreadCount > 9 ? '9+' : unreadCount}
      </span>
    </button>
  );
}
