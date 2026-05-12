"use client";

import { useState, useEffect } from "react";

// Map of tool keys to their internal URL paths
const TOOL_URL_MAP = {
  "tax-calendar": "/tax-calendar",
  "kbli-explorer": "/kbli",
  "visa-match": "/visa/match",
} as const;

// Map of tool keys to their human-readable display labels
const TOOL_LABEL_MAP = {
  "tax-calendar": "Tax Calendar",
  "kbli-explorer": "KBLI Explorer",
  "visa-match": "Visa Match",
} as const;

type ToolKey = keyof typeof TOOL_URL_MAP;

interface ArticleToolEmbedProps {
  tool: ToolKey;
}

// Height thresholds for responsive iframe sizing
const DESKTOP_HEIGHT = 520;
const MOBILE_HEIGHT = 420;
const MOBILE_BREAKPOINT = 768;

export function ArticleToolEmbed({ tool }: ArticleToolEmbedProps) {
  const [isLoaded, setIsLoaded] = useState(false);
  const [iframeHeight, setIframeHeight] = useState(DESKTOP_HEIGHT);

  const toolUrl = TOOL_URL_MAP[tool];
  const toolLabel = TOOL_LABEL_MAP[tool];

  // Detect mobile on mount and on resize to set responsive iframe height
  useEffect(() => {
    function updateHeight() {
      setIframeHeight(
        window.innerWidth < MOBILE_BREAKPOINT ? MOBILE_HEIGHT : DESKTOP_HEIGHT,
      );
    }

    updateHeight();
    window.addEventListener("resize", updateHeight);
    return () => window.removeEventListener("resize", updateHeight);
  }, []);

  return (
    <div className="my-8 overflow-hidden rounded-xl border border-white/10 bg-white/5">
      {/* Tool header bar — label + category badge */}
      <div className="flex items-center gap-3 border-b border-white/10 bg-white/5 px-4 py-3">
        <span className="text-sm font-bold text-white">{toolLabel}</span>
        <span className="text-xs text-white/50">Interactive Tool</span>
      </div>

      {/* Skeleton shown while the iframe is loading */}
      {!isLoaded && (
        <div
          className="w-full animate-pulse rounded-xl bg-white/5"
          style={{ height: iframeHeight }}
          aria-hidden="true"
        />
      )}

      {/* Embedded tool iframe — hidden until onLoad fires */}
      <iframe
        src={toolUrl}
        width="100%"
        style={{
          height: iframeHeight,
          display: isLoaded ? "block" : "none",
          border: "none",
        }}
        onLoad={() => setIsLoaded(true)}
        title={toolLabel}
        loading="lazy"
        allowFullScreen
      />

      {/* Full-screen link below the iframe */}
      <div className="border-t border-white/10 px-4 py-3">
        <a
          href={toolUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm text-white/60 transition-colors hover:text-white/90"
        >
          Open {toolLabel} in full screen →
        </a>
      </div>
    </div>
  );
}
