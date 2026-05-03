"use client";

import React from "react";
import { useRouter } from "next/navigation";
import {
  Settings,
  User,
  Bell,
  Shield,
  Palette,
  Globe,
  Key,
  Building,
} from "lucide-react";
import { Button } from "@/components/ui/button";

const settingsSections = [
  {
    title: "Profile",
    description: "Manage your personal information",
    icon: User,
    href: "/settings/profile",
  },
  {
    title: "Notifications",
    description: "Configure notification preferences",
    icon: Bell,
    href: "/settings/notifications",
  },
  {
    title: "Security",
    description: "Password, 2FA and active sessions",
    icon: Shield,
    href: "/settings/security",
  },
  {
    title: "Appearance",
    description: "Theme and visual preferences",
    icon: Palette,
    href: "/settings/appearance",
  },
  {
    title: "Language & Region",
    description: "Language, timezone and date format",
    icon: Globe,
    href: "/settings/locale",
  },
  {
    title: "API Keys",
    description: "Manage API keys",
    icon: Key,
    href: "/settings/api",
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
              border: "1px solid rgba(255,255,255,0.05)",
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
          border: "1px solid rgba(255,255,255,0.05)",
          background:
            "linear-gradient(145deg, rgba(32,32,36,0.7) 0%, rgba(22,22,26,0.4) 100%)",
        }}
      >
        <div
          className="p-4"
          style={{
            borderBottom: "1px solid var(--bz-border)",
            background: "rgba(32,32,36,0.3)",
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
              label: "User Management",
              description: "Add, modify or remove users",
            },
            {
              label: "Roles & Permissions",
              description: "Configure roles and permissions",
            },
            {
              label: "Integrations",
              description: "WhatsApp, Google Drive, other services",
            },
            { label: "Backup & Export", description: "Data backup and export" },
          ].map((item) => (
            <div
              key={item.label}
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
                  if (item.label === "User Management") {
                    router.push("/settings/users");
                  } else if (item.label === "Roles & Permissions") {
                    router.push("/settings/roles");
                  } else if (item.label === "Integrations") {
                    router.push("/settings/integrations");
                  } else if (item.label === "Backup & Export") {
                    router.push("/settings/backup");
                  }
                }}
              >
                Configure
              </Button>
            </div>
          ))}
        </div>
      </div>

      {/* Info Box */}
      <div
        className="rounded-xl border border-dashed p-8 text-center backdrop-blur-sm"
        style={{
          borderColor: "rgba(255,255,255,0.1)",
          background: "rgba(26,26,30,0.5)",
        }}
      >
        <Settings
          className="w-12 h-12 mx-auto mb-3 opacity-50"
          style={{ color: "var(--bz-text-2)" }}
        />
        <p
          className="text-sm max-w-md mx-auto"
          style={{ color: "var(--bz-text-2)" }}
        >
          Complete settings center to manage profile, security, notifications
          and administrative configurations.
        </p>
      </div>
    </div>
  );
}
