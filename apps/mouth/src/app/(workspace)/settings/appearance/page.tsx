"use client";

import React, { useState, useEffect } from "react";
import {
  Palette,
  Sun,
  Moon,
  Monitor,
  Check,
  ArrowLeft,
  Save,
} from "lucide-react";
import { useRouter } from "next/navigation";
import {
  useTheme,
  type Theme as CoreTheme,
} from "@balizero/core/components/ThemeProvider";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";

type Theme = "light" | "dark" | "system";

const themes: { id: Theme; label: string; icon: typeof Sun }[] = [
  { id: "light", label: "Light", icon: Sun },
  { id: "dark", label: "Dark", icon: Moon },
  { id: "system", label: "System", icon: Monitor },
];

// This page offers a 3-way choice; the token system has five concrete themes
// (tokens/themes/*.css) and no "system" among them. Both directions of the
// mapping are therefore explicit, and "system" is resolved to a real theme at
// save time — never persisted, because the pre-paint script writes whatever it
// finds straight onto data-theme and `data-theme="system"` styles nothing.
function resolveSelection(selection: Theme): CoreTheme {
  if (selection === "light") return "operative-light";
  if (selection === "dark") return "operative-dark";
  const prefersDark =
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-color-scheme: dark)").matches;
  return prefersDark ? "operative-dark" : "operative-light";
}

function selectionFromTheme(theme: CoreTheme): Theme {
  return theme === "light" || theme === "operative-light" ? "light" : "dark";
}

// Only the theme is offered here: the accent, compact-mode and animation
// toggles this page used to show wrote localStorage keys no code reads.
export default function AppearanceSettingsPage() {
  const router = useRouter();
  const { success } = useToast();
  const { theme, setTheme } = useTheme();
  const [isSaving, setIsSaving] = useState(false);
  const [selectedTheme, setSelectedTheme] = useState<Theme>("light");

  // Reflect the theme actually in force (set by the provider, which has already
  // reconciled localStorage + the pre-paint persona default) onto the radio.
  useEffect(() => {
    setSelectedTheme(selectionFromTheme(theme));
  }, [theme]);

  const handleSave = async () => {
    setIsSaving(true);

    // Apply the theme through the provider — the ONE writer of `bz-theme` and
    // of data-theme. Before WS4 this page wrote a `theme` key nobody reads and
    // toggled a `.dark` class no selector consults (globals.css defines the
    // `dark:` variant on [data-theme], not on that class), so "Appearance
    // saved" was reported while nothing whatsoever was applied.
    setTheme(resolveSelection(selectedTheme));

    setTimeout(() => {
      setIsSaving(false);
      success("Appearance saved", "Your theme has been applied.");
    }, 500);
  };

  return (
    <div className="space-y-6 max-w-2xl">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => router.push("/settings")}
        >
          <ArrowLeft className="w-4 h-4" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold text-[var(--foreground)] flex items-center gap-2">
            <Palette className="w-6 h-6 text-[var(--bz-accent)]" />
            Appearance Settings
          </h1>
          <p className="text-sm text-[var(--foreground-muted)]">
            Light or dark theme for the workspace
          </p>
        </div>
      </div>

      {/* Theme Selection */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-6">
        <h2 className="text-lg font-semibold text-[var(--foreground)] mb-4">
          Theme
        </h2>
        <div className="grid grid-cols-3 gap-3">
          {themes.map((theme) => {
            const Icon = theme.icon;
            const isSelected = selectedTheme === theme.id;
            return (
              <button
                key={theme.id}
                onClick={() => setSelectedTheme(theme.id)}
                className={`relative p-4 rounded-xl border-2 transition-all ${
                  isSelected
                    ? "border-[var(--accent)] bg-[var(--accent)]/10"
                    : "border-[var(--border)] bg-[var(--background)] hover:border-[var(--border-hover)]"
                }`}
              >
                <Icon
                  className={`w-8 h-8 mx-auto mb-2 ${isSelected ? "text-[var(--accent)]" : "text-[var(--foreground-muted)]"}`}
                />
                <p
                  className={`text-sm font-medium ${isSelected ? "text-[var(--accent)]" : "text-[var(--foreground)]"}`}
                >
                  {theme.label}
                </p>
                {isSelected && (
                  <div className="absolute top-2 right-2">
                    <Check className="w-4 h-4 text-[var(--accent)]" />
                  </div>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Save Button */}
      <div className="flex justify-end">
        <Button onClick={handleSave} disabled={isSaving}>
          <Save className="w-4 h-4 mr-2" />
          {isSaving ? "Saving..." : "Save Changes"}
        </Button>
      </div>
    </div>
  );
}
