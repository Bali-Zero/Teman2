"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { User, Palette, Building } from "lucide-react";
import { Button } from "@/components/ui/button";

const settingsSections = [
  {
    title: "Profile",
    description: "Your account information",
    icon: User,
    href: "/settings/profile",
  },
  {
    title: "Appearance",
    description: "Light or dark theme",
    icon: Palette,
    href: "/settings/appearance",
  },
];

export default function SettingsPage() {
  const router = useRouter();

  const handleSettingsClick = (href: string) => {
    router.push(href);
  };

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <div>
        <h1
          className="text-2xl font-bold"
          style={{ color: "var(--bz-text-1)" }}
        >
          Settings
        </h1>
        <p className="text-sm" style={{ color: "var(--bz-text-2)" }}>
          Manage your account and preferences
        </p>
      </div>

      {/* Settings Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {settingsSections.map((section) => (
          <div
            key={section.title}
            onClick={() => handleSettingsClick(section.href)}
            className="p-4 rounded-xl cursor-pointer transition-all duration-300 group hover:shadow-xl hover:-translate-y-0.5 backdrop-blur-md"
            style={{
              border: "1px solid var(--bz-border)",
              background:
                "linear-gradient(145deg, rgba(35,35,40,0.6) 0%, rgba(25,25,30,0.3) 100%)",
            }}
          >
            <div className="flex items-start gap-4">
              <div
                className="p-2 rounded-lg transition-colors"
                style={{ background: "var(--bz-card)" }}
              >
                <section.icon
                  className="w-5 h-5 transition-colors"
                  style={{ color: "var(--bz-text-2)" }}
                />
              </div>
              <div>
                <h3
                  className="font-medium"
                  style={{ color: "var(--bz-text-1)" }}
                >
                  {section.title}
                </h3>
                <p className="text-sm" style={{ color: "var(--bz-text-2)" }}>
                  {section.description}
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Admin Section */}
      <div
        className="rounded-xl overflow-hidden shadow-2xl backdrop-blur-xl"
        style={{
          border: "1px solid var(--bz-border)",
          background:
            "linear-gradient(145deg, rgba(35,35,40,0.6) 0%, rgba(25,25,30,0.3) 100%)",
        }}
      >
        <div
          className="p-4"
          style={{
            borderBottom: "1px solid var(--bz-border)",
            background: "var(--bz-glass-rim)",
          }}
        >
          <div className="flex items-center gap-2">
            <Building
              className="w-5 h-5"
              style={{ color: "var(--bz-accent)" }}
            />
            <h2 className="font-semibold" style={{ color: "var(--bz-text-1)" }}>
              Administration
            </h2>
          </div>
          <p className="text-sm mt-1" style={{ color: "var(--bz-text-2)" }}>
            Settings reserved for administrators
          </p>
        </div>
        <div className="p-4 space-y-3">
          {[
            {
              label: "Integrations",
              description: "Google Drive",
              href: "/settings/integrations",
            },
          ].map((item) => (
            <div
              key={item.label}
              onClick={() => router.push(item.href)}
              className="flex items-center justify-between p-3 rounded-lg cursor-pointer transition-colors hover:opacity-80"
            >
              <div>
                <p
                  className="text-sm font-medium"
                  style={{ color: "var(--bz-text-1)" }}
                >
                  {item.label}
                </p>
                <p className="text-xs" style={{ color: "var(--bz-text-2)" }}>
                  {item.description}
                </p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={(e) => {
                  e.stopPropagation();
                  router.push(item.href);
                }}
              >
                Configure
              </Button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
