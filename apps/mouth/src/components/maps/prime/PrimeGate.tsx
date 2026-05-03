"use client";
import { useState, type ReactNode } from "react";
import { useBrowserSupport } from "./hooks/useBrowserSupport";

export function PrimeGate({ children }: { children: ReactNode }) {
  const { supported, chromium, webgl2, loading } = useBrowserSupport();
  const [override, setOverride] = useState(false);

  if (loading) {
    return (
      <div
        data-testid="prime-gate-loading"
        className="h-screen w-screen bg-black flex items-center justify-center"
      >
        <div className="h-10 w-10 rounded-full border-2 border-[#d4845a] border-t-transparent animate-spin" />
      </div>
    );
  }

  if (supported || override) return <>{children}</>;

  const reason = !chromium
    ? "Prime requires a Chromium-based browser (Chrome, Edge, Brave, Arc)."
    : !webgl2
      ? "Prime requires WebGL2 support."
      : "Prime requires a supported browser configuration.";

  return (
    <div
      role="alert"
      className="h-screen w-screen bg-black text-white flex items-center justify-center p-6"
    >
      <div className="max-w-lg text-center space-y-6">
        <h1 className="text-2xl font-semibold">Prime requires Chrome/Edge</h1>
        <p className="text-white/70">{reason}</p>
        <p className="text-sm text-white/50">
          The 3D zoning map uses Google&apos;s <code>maps3d</code> API which is
          only reliable on Chromium browsers with WebGL2.
        </p>
        <div className="flex flex-col gap-3 items-center">
          <a
            href="https://www.google.com/chrome/"
            className="px-4 py-2 rounded-md bg-[#d4845a] text-black font-medium"
          >
            Get Chrome
          </a>
          <button
            type="button"
            onClick={() => setOverride(true)}
            className="text-xs text-white/40 underline hover:text-white/70"
          >
            Continue anyway
          </button>
        </div>
      </div>
    </div>
  );
}
