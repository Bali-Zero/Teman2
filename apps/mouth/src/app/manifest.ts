import type { MetadataRoute } from "next";

/**
 * Web App Manifest (FASE 6 — PWA).
 *
 * Next.js App Router serves this at `/manifest.webmanifest` and auto-injects the
 * `<link rel="manifest">` tag into every page's <head>. Makes the Bali Zero
 * client portal (my.balizero.com) installable to a phone home screen and gives
 * it a standalone, app-like shell on launch.
 *
 * The service worker (public/sw.js, registered in layout.tsx) handles offline
 * API caching; this manifest is the install/appearance half of the PWA contract.
 *
 * `start_url` points at the portal: an installed icon should land the client in
 * their self-service area, not the public marketing site. Colours match the
 * operative-light "paper" portal surface (ink #16213a on paper #f4f1ea).
 */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Bali Zero Portal",
    short_name: "Bali Zero",
    description:
      "Your Bali Zero client portal — documents, visa & company status, and direct contact with your case officer.",
    start_url: "/portal",
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: "#f4f1ea",
    theme_color: "#16213a",
    lang: "en",
    categories: ["business", "productivity"],
    icons: [
      {
        src: "/assets/logo/balizero-logo-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/assets/logo/balizero-logo-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  };
}
