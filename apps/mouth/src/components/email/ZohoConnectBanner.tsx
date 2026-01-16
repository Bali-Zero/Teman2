/**
 * Zoho Connect Banner (Stub)
 *
 * This is a stub implementation to prevent build errors.
 */

interface ZohoConnectBannerProps {
  onConnect: () => void;
  isConnecting: boolean;
}

export function ZohoConnectBanner({ onConnect, isConnecting }: ZohoConnectBannerProps) {
  return (
    <div className="flex items-center justify-center p-8">
      <button
        onClick={onConnect}
        disabled={isConnecting}
        className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
      >
        {isConnecting ? 'Connecting...' : 'Connect to Zoho Mail'}
      </button>
    </div>
  );
}
