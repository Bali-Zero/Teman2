"use client";

import { useEffect, useRef } from "react";
import KBLIIntroOverlay from "@/components/kbli/KBLIIntroOverlay";

interface KBLINavigatorClientProps {
  // no props needed for URL source
}

export default function KBLINavigatorClient({}: KBLINavigatorClientProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    const handlePopState = (event: PopStateEvent) => {
      // If the user presses back, we tell the iframe to switch back to the previous section
      if (event.state && event.state.section && iframeRef.current) {
        iframeRef.current.contentWindow?.postMessage(
          {
            type: "SET_SECTION",
            section: event.state.section,
          },
          "*",
        );
      }
    };

    window.addEventListener("popstate", handlePopState);

    // Initial state setup to handle the first back button press correctly
    if (!window.history.state) {
      window.history.replaceState(
        { section: "welcome" },
        "",
        window.location.href,
      );
    }

    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  return (
    <div className="relative w-full h-screen bg-[#2a2a2a] overflow-hidden">
      <KBLIIntroOverlay />
      <iframe
        ref={iframeRef}
        src="/kbli-navigator/index.html"
        className="w-full h-full border-none"
        style={{ pointerEvents: "auto" }}
        title="KBLI 2025 Navigator"
        id="kbli-frame"
        allow="autoplay"
      />
    </div>
  );
}
