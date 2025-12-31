'use client';

import React from 'react';
import { Mail, ExternalLink, Shield, CheckCircle2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ZohoConnectBannerProps {
  onConnect: () => void;
  isConnecting?: boolean;
}

export function ZohoConnectBanner({ onConnect, isConnecting }: ZohoConnectBannerProps) {
  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="max-w-md w-full mx-auto p-8 rounded-2xl border border-[var(--border)] bg-[var(--background-secondary)]">
        {/* Icon */}
        <div className="flex justify-center mb-6">
          <div className="w-16 h-16 rounded-2xl bg-[var(--accent)]/10 flex items-center justify-center">
            <Mail className="w-8 h-8 text-[var(--accent)]" />
          </div>
        </div>

        {/* Title */}
        <h2 className="text-xl font-semibold text-[var(--foreground)] text-center mb-2">
          Connect Your Email
        </h2>
        <p className="text-sm text-[var(--foreground-muted)] text-center mb-6">
          Link your Zoho Mail account to manage emails directly from Zantara
        </p>

        {/* Features */}
        <div className="space-y-3 mb-6">
          <div className="flex items-center gap-3 text-sm text-[var(--foreground-muted)]">
            <CheckCircle2 className="w-4 h-4 text-[var(--success)]" />
            <span>Read, send, and reply to emails</span>
          </div>
          <div className="flex items-center gap-3 text-sm text-[var(--foreground-muted)]">
            <CheckCircle2 className="w-4 h-4 text-[var(--success)]" />
            <span>Access all folders and attachments</span>
          </div>
          <div className="flex items-center gap-3 text-sm text-[var(--foreground-muted)]">
            <CheckCircle2 className="w-4 h-4 text-[var(--success)]" />
            <span>Search across your inbox</span>
          </div>
        </div>

        {/* Connect Button */}
        <button
          onClick={onConnect}
          disabled={isConnecting}
          className={cn(
            'w-full py-3 px-4 rounded-lg font-medium transition-all flex items-center justify-center gap-2',
            'bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white',
            'disabled:opacity-50 disabled:cursor-not-allowed'
          )}
        >
          {isConnecting ? (
            <>
              <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Connecting...
            </>
          ) : (
            <>
              <ExternalLink className="w-4 h-4" />
              Connect Zoho Mail
            </>
          )}
        </button>

        {/* Security Note */}
        <div className="mt-4 flex items-center justify-center gap-2 text-xs text-[var(--foreground-muted)]">
          <Shield className="w-3 h-3" />
          <span>Secure OAuth 2.0 connection</span>
        </div>
      </div>
    </div>
  );
}
