"use client";

import dynamic from "next/dynamic";

// Lazy-load Sonner Toaster so its ~128 KB chunk isn't on the critical path.
// Rendered on every route via layout.tsx, but toasts are rare — splitting it
// removes it from initial JS and loads only after hydration.
const Toaster = dynamic(() => import("sonner").then((m) => m.Toaster), {
  ssr: false,
});

export function LazyToaster() {
  return (
    <Toaster
      position="bottom-right"
      theme="dark"
      richColors
      closeButton
      toastOptions={{
        style: {
          background: "var(--background-elevated)",
          border: "1px solid var(--border)",
          color: "var(--foreground)",
        },
      }}
    />
  );
}
