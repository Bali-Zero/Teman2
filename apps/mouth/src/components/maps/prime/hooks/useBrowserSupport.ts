"use client";
import { useEffect, useState } from "react";

export interface BrowserSupport {
  supported: boolean;
  chromium: boolean;
  webgl2: boolean;
  isMobile: boolean;
  loading: boolean;
}

function detectChromium(): boolean {
  const nav = navigator as Navigator & {
    userAgentData?: { brands: Array<{ brand: string }> };
  };
  if (nav.userAgentData?.brands?.length) {
    return nav.userAgentData.brands.some(
      (b) => b.brand === "Chromium" || b.brand === "Google Chrome",
    );
  }
  const ua = navigator.userAgent;
  if (/Firefox\/|Gecko\//.test(ua) && !/Chrome\/|Edg\//.test(ua)) return false;
  return /Chrome\/|Edg\//.test(ua);
}

function detectWebGL2(): boolean {
  try {
    const canvas = document.createElement("canvas");
    return canvas.getContext("webgl2") != null;
  } catch {
    return false;
  }
}

function detectMobile(): boolean {
  if (
    typeof window === "undefined" ||
    typeof window.matchMedia !== "function"
  ) {
    return false;
  }
  return window.matchMedia("(pointer:coarse) and (max-width: 768px)").matches;
}

export function useBrowserSupport(): BrowserSupport {
  const [state, setState] = useState<BrowserSupport>({
    supported: false,
    chromium: false,
    webgl2: false,
    isMobile: false,
    loading: true,
  });

  useEffect(() => {
    const chromium = detectChromium();
    const webgl2 = detectWebGL2();
    const isMobile = detectMobile();
    setState({
      supported: chromium && webgl2,
      chromium,
      webgl2,
      isMobile,
      loading: false,
    });
  }, []);

  return state;
}
