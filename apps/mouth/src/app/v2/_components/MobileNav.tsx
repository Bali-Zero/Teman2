"use client";

import { useState, useEffect } from "react";
import { Menu, X } from "lucide-react";

interface MobileNavProps {
  items: { label: string; href: string }[];
}

export function MobileNav({ items }: MobileNavProps) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    document.documentElement.style.overflow = open ? "hidden" : "";
    return () => {
      document.documentElement.style.overflow = "";
    };
  }, [open]);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        aria-label="Open menu"
        className="md:hidden inline-flex items-center justify-center w-10 h-10 rounded-lg"
        style={{
          color: "#ffffff",
          background: "rgba(255,255,255,0.06)",
          border: "1px solid rgba(255,255,255,0.14)",
        }}
      >
        <Menu size={22} strokeWidth={2.2} />
      </button>

      {open && (
        <div
          className="md:hidden fixed inset-0 z-[400] flex flex-col"
          style={{
            background: "color-mix(in srgb, var(--surface-base) 96%, #000)",
            backdropFilter: "blur(12px)",
          }}
        >
          <div
            className="flex items-center justify-end px-5 h-14"
            style={{ borderBottom: "1px solid var(--nav-border)" }}
          >
            <button
              onClick={() => setOpen(false)}
              aria-label="Close menu"
              className="inline-flex items-center justify-center w-9 h-9 rounded-md"
              style={{ color: "var(--text-primary)" }}
            >
              <X size={22} strokeWidth={2} />
            </button>
          </div>

          <ul className="flex flex-col gap-1 list-none p-5 m-0">
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
                  }}
                >
                  {item.label}
                </a>
              </li>
            ))}
          </ul>

          <div className="mt-auto p-5 flex flex-col gap-3">
            <a
              href="#top"
              onClick={() => setOpen(false)}
              className="block text-center px-5 py-3 rounded-xl text-[14px] font-semibold"
              style={{
                background: "var(--accent-funnel)",
                color: "var(--text-on-accent)",
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
              }}
            >
              Login
            </a>
          </div>
        </div>
      )}
    </>
  );
}
