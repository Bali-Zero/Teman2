interface ZohoConnectBannerProps {
  onConnect: () => void;
  isConnecting: boolean;
}

export function ZohoConnectBanner({
  onConnect,
  isConnecting,
}: ZohoConnectBannerProps) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-6 p-8">
      <div className="w-20 h-20 rounded-2xl bg-[var(--accent)]/10 flex items-center justify-center">
        <svg
          className="w-10 h-10 text-[var(--accent)]"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
          />
        </svg>
      </div>
      <div className="text-center">
        <h2 className="text-xl font-semibold text-[var(--foreground)] mb-2">
          Connect your Zoho Mail
        </h2>
        <p className="text-sm text-[var(--foreground-muted)] max-w-xs">
          Connect your Zoho Mail account to read, send, and manage emails
          directly from this dashboard.
        </p>
      </div>
      <button
        onClick={onConnect}
        disabled={isConnecting}
        className="px-6 py-3 bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
      >
        {isConnecting ? (
          <>
            <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            Connecting...
          </>
        ) : (
          "Connect to Zoho Mail"
        )}
      </button>
    </div>
  );
}
