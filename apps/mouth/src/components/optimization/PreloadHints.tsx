"use client";

import { useEffect } from "react";

/**
 * PreloadHints - Precarica risorse critiche per migliorare LCP e FCP
 *
 * Implementa:
 * - Preconnect a domini critici
 * - Preload font e immagini LCP
 * - Prefetch pagine probabili
 */
export function PreloadHints() {
  useEffect(() => {
    // Preconnect a domini esterni critici
    const preconnectDomains = ["https://nuzantara-rag.fly.dev"];

    preconnectDomains.forEach((domain) => {
      const link = document.createElement("link");
      link.rel = "preconnect";
      link.href = domain;
      link.crossOrigin = "anonymous";
      document.head.appendChild(link);

      // DNS prefetch per fallback
      const dnsLink = document.createElement("link");
      dnsLink.rel = "dns-prefetch";
      dnsLink.href = domain;
      document.head.appendChild(dnsLink);
    });

    // Prefetch pagine probabili (on hover)
    const prefetchPage = (url: string) => {
      const link = document.createElement("link");
      link.rel = "prefetch";
      link.href = url;
      document.head.appendChild(link);
    };

    // Aggiungi listener per prefetch intelligente
    const links = document.querySelectorAll('a[href^="/"]');
    links.forEach((link) => {
      link.addEventListener(
        "mouseenter",
        () => {
          const href = link.getAttribute("href");
          if (href && href.startsWith("/") && !href.startsWith("//")) {
            prefetchPage(href);
          }
        },
        { once: true },
      );
    });

    return () => {
      // Cleanup not needed as links remain valid
    };
  }, []);

  return null;
}

/**
 * PreloadCriticalResources - Componente SSR per risorse critiche
 * Usato in layout.tsx per precaricare font e CSS critici
 */
export function PreloadCriticalResources() {
  return (
    <>
      {/* Preload font critico */}
      <link
        rel="preload"
        href="/_next/static/media/GeistVariableVF.woff2"
        as="font"
        type="font/woff2"
        crossOrigin="anonymous"
      />
      {/* Preconnect a API */}
      <link rel="preconnect" href="https://nuzantara-rag.fly.dev" />
      <link rel="dns-prefetch" href="https://nuzantara-rag.fly.dev" />
    </>
  );
}
