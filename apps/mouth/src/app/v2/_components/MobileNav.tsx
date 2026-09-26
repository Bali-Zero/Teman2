"use client";

import { useState, useEffect } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Menu, X } from "lucide-react";
import { trackFunnelEvent } from "@balizero/core/analytics";
import { getOrCreateSessionId } from "@balizero/core/auth";
import { buildWhatsAppLink, type Funnel } from "@/lib/whatsapp-utm";

interface MobileNavProps {
  items: { label: string; href: string }[];
  funnel: Funnel;
}

export function MobileNav({ items, funnel }: MobileNavProps) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (!open) return;
    const desktop = window.matchMedia("(min-width: 768px)");
    const closeOnDesktop = () => {
      if (desktop.matches) setOpen(false);
    };
    closeOnDesktop();
    desktop.addEventListener("change", closeOnDesktop);
    return () => desktop.removeEventListener("change", closeOnDesktop);
  }, [open]);

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      {/* Hamburger button — flex-shrink-0 prevents compression at 390px */}
      <Dialog.Trigger asChild>
        <button
          aria-label="Open menu"
          className="md:hidden inline-flex items-center justify-center flex-shrink-0 w-10 h-10 rounded-lg"
          style={{
            color: "#ffffff",
            background: "rgba(255,255,255,0.06)",
            border: "1px solid rgba(255,255,255,0.14)",
          }}
        >
          <Menu size={22} strokeWidth={2.2} />
        </button>
      </Dialog.Trigger>

      <Dialog.Portal>
        {/* Backdrop tap-to-close — rendered beneath the drawer panel */}
        <Dialog.Overlay
          aria-hidden="true"
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 398,
            background: "rgba(0,0,0,0.45)",
          }}
        />

        {/* Drawer panel */}
        <Dialog.Content
          aria-describedby={undefined}
          className="md:hidden fixed inset-y-0 left-0 z-[399] flex flex-col w-[min(80vw,320px)]"
          style={{
            background: "var(--nav-bg)",
            borderRight: "1px solid var(--nav-border)",
            backdropFilter: "blur(16px)",
            WebkitBackdropFilter: "blur(16px)",
            overflowY: "auto",
          }}
        >
          <Dialog.Title className="sr-only">Navigation menu</Dialog.Title>
          {/* Header row with close button */}
          <div
            className="flex items-center justify-between px-5 h-14 flex-shrink-0"
            style={{ borderBottom: "1px solid var(--nav-border)" }}
          >
            <span
              className="text-[11px] font-bold uppercase tracking-widest"
              style={{ color: "var(--text-tertiary)" }}
            >
              Menu
            </span>
            <Dialog.Close asChild>
              <button
                aria-label="Close menu"
                className="inline-flex items-center justify-center w-9 h-9 rounded-md"
                style={{ color: "var(--text-primary)" }}
              >
                <X size={22} strokeWidth={2} />
              </button>
            </Dialog.Close>
          </div>

          {/* Nav links */}
          <ul className="flex flex-col gap-1 list-none p-5 m-0 flex-1">
            {items.map((item) => (
              <li key={item.href}>
                <a
                  href={item.href}
                  onClick={() => setOpen(false)}
                  className="block px-4 py-3 rounded-xl text-[18px] font-semibold"
                  style={{
                    color: "var(--text-primary)",
                    background:
                      "color-mix(in srgb, var(--accent-funnel) 6%, transparent)",
                    border:
                      "1px solid color-mix(in srgb, var(--accent-funnel) 14%, transparent)",
                    textDecoration: "none",
                  }}
                >
                  {item.label}
                </a>
              </li>
            ))}
          </ul>

          {/* Footer CTAs */}
          <div className="p-5 flex flex-col gap-3 flex-shrink-0">
            <a
              href={buildWhatsAppLink(funnel)}
              onClick={() => {
                setOpen(false);
                void trackFunnelEvent(`${funnel}_whatsapp_cta`, {
                  sessionId: getOrCreateSessionId(),
                  payload: { trigger: "drawer" },
                });
              }}
              className="block text-center px-5 py-3 rounded-xl text-[14px] font-semibold"
              style={{
                background: "var(--accent-funnel)",
                color: "var(--text-on-accent)",
                textDecoration: "none",
              }}
            >
              Get Started
            </a>
            <a
              href="/login"
              onClick={() => setOpen(false)}
              className="block text-center px-5 py-3 rounded-xl text-[13px] font-semibold"
              style={{
                border: "1px solid var(--border-default)",
                color: "var(--text-secondary)",
                textDecoration: "none",
              }}
            >
              Login
            </a>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
