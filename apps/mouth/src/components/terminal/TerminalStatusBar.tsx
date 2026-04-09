/**
 * TerminalStatusBar — fixed 40px top bar for the terminal view.
 *
 * Layout:
 *   [ Zantara logo  Terminal ]  [ current model · session id ]  [ dot · role · N tok ]
 *
 * The connection dot reflects the gateway state reported by `isGatewayConfigured`:
 *   - green  → local gateway ready
 *   - yellow → cloud fallback in use
 *   - red    → offline (navigator.onLine = false)
 */

"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { isGatewayConfigured } from "@/lib/gateway";

interface TerminalStatusBarProps {
  model?: string;
  role?: string;
  tokenCount?: number;
  sessionId?: string;
}

type ConnectionState = "gateway" | "cloud" | "offline";

export function TerminalStatusBar({
  model,
  role,
  tokenCount,
  sessionId,
}: TerminalStatusBarProps) {
  const [connection, setConnection] = useState<ConnectionState>("cloud");

  useEffect(() => {
    const resolve = () => {
      if (typeof navigator !== "undefined" && !navigator.onLine) {
        setConnection("offline");
        return;
      }
      setConnection(isGatewayConfigured() ? "gateway" : "cloud");
    };
    resolve();
    if (typeof window !== "undefined") {
      window.addEventListener("online", resolve);
      window.addEventListener("offline", resolve);
      // Listen to localStorage changes (gateway token updates in another tab).
      window.addEventListener("storage", resolve);
      return () => {
        window.removeEventListener("online", resolve);
        window.removeEventListener("offline", resolve);
        window.removeEventListener("storage", resolve);
      };
    }
    return undefined;
  }, []);

  // Green when connected (cloud or gateway), red when offline.
  const dotColour =
    connection === "offline"
      ? "bg-[var(--bz-red)] shadow-[0_0_8px_rgba(217,95,90,0.6)]"
      : "bg-[var(--bz-green)] shadow-[0_0_8px_rgba(77,184,122,0.6)]";

  const dotLabel =
    connection === "gateway"
      ? "local gateway"
      : connection === "cloud"
        ? "cloud"
        : "offline";

  return (
    <div
      className="h-10 flex items-center gap-3 px-4 md:px-6 border-b border-white/10 bg-[var(--bz-base)]/95 backdrop-blur-md font-mono text-[11px] text-white/70"
      role="toolbar"
      aria-label="Terminal status bar"
    >
      {/* Left — logo + label */}
      <div className="flex items-center gap-2 flex-shrink-0">
        <Image
          src="/assets/logo/zantara-lotus.png"
          alt="Zantara"
          width={18}
          height={18}
          className="w-[18px] h-[18px] rounded-sm"
        />
        <span className="font-semibold text-white/90 uppercase tracking-[0.5px]">
          Zantara
        </span>
        <span className="text-white/30">·</span>
        <span className="text-[var(--bz-accent)] uppercase tracking-[0.5px]">
          terminal
        </span>
      </div>

      {/* Center — model + session */}
      <div className="flex-1 flex items-center justify-center gap-2 min-w-0 text-white/50">
        {model ? (
          <span className="truncate">
            <span className="text-white/30">model:</span>{" "}
            <span className="text-white/80">{model}</span>
          </span>
        ) : (
          <span className="text-white/30">model: —</span>
        )}
        {sessionId && (
          <>
            <span className="text-white/20 hidden md:inline">·</span>
            <span className="hidden md:inline truncate max-w-[200px]">
              <span className="text-white/30">session:</span>{" "}
              <span className="text-white/70">{sessionId}</span>
            </span>
          </>
        )}
      </div>

      {/* Right — connection dot + role + tokens */}
      <div className="flex items-center gap-2 flex-shrink-0">
        <span
          className={`w-2 h-2 rounded-full ${dotColour}`}
          aria-label={`Connection: ${dotLabel}`}
          title={dotLabel}
        />
        <span className="hidden md:inline text-white/40 uppercase tracking-[0.5px]">
          {dotLabel}
        </span>
        {role && (
          <>
            <span className="text-white/20">·</span>
            <span className="text-white/60 uppercase tracking-[0.5px]">
              {role}
            </span>
          </>
        )}
        {tokenCount !== undefined && (
          <>
            <span className="text-white/20">·</span>
            <span className="tabular-nums text-white/60">{tokenCount} tok</span>
          </>
        )}
      </div>
    </div>
  );
}
