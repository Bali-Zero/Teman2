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
type AccentColor = "cyan" | "purple" | "blue" | "green" | "amber" | "pink";

const themes: { id: Theme; label: string; icon: typeof Sun }[] = [
  { id: "light", label: "Light", icon: Sun },
  { id: "dark", label: "Dark", icon: Moon },
  { id: "system", label: "System", icon: Monitor },
];

// Swatch previews read the neon accent token family (same hues as the legacy
// hardcoded palette, now theme-aware via the token SSOT).
const accentColors: { id: AccentColor; label: string; color: string }[] = [
  { id: "cyan", label: "Cyan", color: "var(--bz-neon-cyan)" },
  { id: "purple", label: "Purple", color: "var(--bz-neon-purple)" },
  { id: "blue", label: "Blue", color: "var(--bz-neon-blue)" },
  { id: "green", label: "Green", color: "var(--bz-neon-emerald)" },
  { id: "amber", label: "Amber", color: "var(--bz-neon-amber)" },
  { id: "pink", label: "Pink", color: "var(--bz-neon-rose)" },
];

// This page offers a 3-way choice; the token system has five concrete themes
// (tokens/themes/*.css) and no "system" among them. Both directions of the
// mapping are therefore explicit, and "system" is resolved to a real theme at
// save time — never persisted, because the pre-paint script writes whatever it
// finds straight onto data-theme and `data-theme="system"` styles nothing.
function resolveSelection(selection: Theme): CoreTheme {
  if (selection !== "system") return selection;
  const prefersDark =
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-color-scheme: dark)").matches;
  return prefersDark ? "dark" : "light";
}

function selectionFromTheme(theme: CoreTheme): Theme {
  return theme === "light" || theme === "operative-light" ? "light" : "dark";
}

export default function AppearanceSettingsPage() {
  const router = useRouter();
  const { success } = useToast();
  const { theme, setTheme } = useTheme();
  const [isSaving, setIsSaving] = useState(false);
  const [selectedTheme, setSelectedTheme] = useState<Theme>("dark");
  const [selectedAccent, setSelectedAccent] = useState<AccentColor>("cyan");
  const [compactMode, setCompactMode] = useState(false);
  const [animationsEnabled, setAnimationsEnabled] = useState(true);

  useEffect(() => {
    // Load saved preferences. The theme is NOT read from localStorage here —
    // it comes from the provider, the single owner of the `bz-theme` key.
    const savedAccent = localStorage.getItem("accentColor") as AccentColor;
    const savedCompact = localStorage.getItem("compactMode") === "true";
    const savedAnimations = localStorage.getItem("animations") !== "false";

    if (savedAccent) setSelectedAccent(savedAccent);
    setCompactMode(savedCompact);
    setAnimationsEnabled(savedAnimations);
  }, []);

  // Reflect the theme actually in force (set by the provider, which has already
  // reconciled localStorage + the pre-paint persona default) onto the radio.
  useEffect(() => {
    setSelectedTheme(selectionFromTheme(theme));
  }, [theme]);

  const handleSave = async () => {
    setIsSaving(true);

    // Save to localStorage
    localStorage.setItem("accentColor", selectedAccent);
    localStorage.setItem("compactMode", String(compactMode));
    localStorage.setItem("animations", String(animationsEnabled));

    // Apply the theme through the provider — the ONE writer of `bz-theme` and
    // of data-theme. Before WS4 this page wrote a `theme` key nobody reads and
    // toggled a `.dark` class no selector consults (globals.css defines the
    // `dark:` variant on [data-theme], not on that class), so "Appearance
    // saved" was reported while nothing whatsoever was applied.
    setTheme(resolveSelection(selectedTheme));

    setTimeout(() => {
      setIsSaving(false);
      success(
        "Appearance saved",
        "Your display preferences have been applied.",
      );
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
            Customize the look and feel of Zantara
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

      {/* Accent Color */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-6">
        <h2 className="text-lg font-semibold text-[var(--foreground)] mb-4">
          Accent Color
        </h2>
        <div className="grid grid-cols-6 gap-3">
          {accentColors.map((accent) => {
            const isSelected = selectedAccent === accent.id;
            return (
              <button
                key={accent.id}
                onClick={() => setSelectedAccent(accent.id)}
                className={`relative w-full aspect-square rounded-xl border-2 transition-all ${
                  isSelected
                    ? "border-white scale-110"
                    : "border-transparent hover:scale-105"
                }`}
                style={{ backgroundColor: accent.color }}
                title={accent.label}
              >
                {isSelected && (
                  <Check className="w-5 h-5 text-white absolute inset-0 m-auto" />
                )}
              </button>
            );
          })}
        </div>
        <p className="text-xs text-[var(--foreground-muted)] mt-3">
          Selected:{" "}
          <span
            style={{
              color: accentColors.find((a) => a.id === selectedAccent)?.color,
            }}
          >
            {accentColors.find((a) => a.id === selectedAccent)?.label}
          </span>
        </p>
      </div>

      {/* Display Options */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-6 space-y-4">
        <h2 className="text-lg font-semibold text-[var(--foreground)]">
          Display Options
        </h2>

        {/* Compact Mode */}
        <div className="flex items-center justify-between p-3 rounded-lg bg-[var(--background)]">
          <div>
            <p className="font-medium text-[var(--foreground)]">Compact Mode</p>
            <p className="text-sm text-[var(--foreground-muted)]">
              Reduce spacing and padding
            </p>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              className="sr-only peer"
              checked={compactMode}
              onChange={() => setCompactMode(!compactMode)}
            />
            <div className="w-11 h-6 bg-[var(--background-secondary)] peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-[var(--bz-border)] after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[var(--accent)]"></div>
          </label>
        </div>

        {/* Animations */}
        <div className="flex items-center justify-between p-3 rounded-lg bg-[var(--background)]">
          <div>
            <p className="font-medium text-[var(--foreground)]">Animations</p>
            <p className="text-sm text-[var(--foreground-muted)]">
              Enable smooth transitions and effects
            </p>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              className="sr-only peer"
              checked={animationsEnabled}
              onChange={() => setAnimationsEnabled(!animationsEnabled)}
            />
            <div className="w-11 h-6 bg-[var(--background-secondary)] peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-[var(--bz-border)] after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[var(--accent)]"></div>
          </label>
        </div>
      </div>

      {/* Preview */}
      <div className="rounded-lg border border-dashed border-[var(--border)] bg-[var(--background-secondary)]/50 p-6">
        <h3 className="text-sm font-medium text-[var(--foreground-muted)] mb-3">
          Preview
        </h3>
        <div className="p-4 rounded-lg bg-[var(--background)] border border-[var(--border)]">
          <div className="flex items-center gap-3 mb-3">
            <div
              className="w-10 h-10 rounded-full"
              style={{
                backgroundColor: accentColors.find(
                  (a) => a.id === selectedAccent,
                )?.color,
              }}
            ></div>
            <div>
              <p className="font-medium text-[var(--foreground)]">
                Sample Card
              </p>
              <p className="text-sm text-[var(--foreground-muted)]">
                This is how elements will look
              </p>
            </div>
          </div>
          <button
            className="px-4 py-2 rounded-lg text-white text-sm font-medium"
            style={{
              backgroundColor: accentColors.find((a) => a.id === selectedAccent)
                ?.color,
            }}
          >
            Sample Button
          </button>
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
