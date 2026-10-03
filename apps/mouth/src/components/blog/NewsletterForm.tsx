"use client";

import * as React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Mail, Check, Loader2, Sparkles, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { subscribeToNewsletter } from "@/lib/blog/newsletter";
import { useR19 } from "@/components/r19/R19Presentation";
import type { ArticleCategory, NewsletterFormProps } from "@/lib/blog/types";

// Category options for newsletter
const CATEGORY_OPTIONS: { value: ArticleCategory; label: string }[] = [
  { value: "visas", label: "Visas & Visas" },
  { value: "business", label: "Business Setup" },
  { value: "taxes", label: "Taxes" },
  { value: "property", label: "Property" },
  { value: "living", label: "Living" },
  { value: "trends", label: "Trends & Insights" },
];

// Frequency options
const FREQUENCY_OPTIONS: {
  value: "daily" | "weekly" | "monthly";
  label: string;
}[] = [
  { value: "weekly", label: "Weekly Digest" },
  { value: "daily", label: "Daily Updates" },
  { value: "monthly", label: "Monthly Roundup" },
];

// R19 tokens (from components/r19/presentation.ts): only active on R19 routes
// (`useR19()`). Elsewhere (e.g. the /property category listing, which
// `routePolicy.ts::isR19Route` excludes) the pre-R19 violet/fuchsia look is
// left untouched, exactly like CategoryNav does for its own pill skin.
const r19Panel: React.CSSProperties = {
  background: "var(--r19-surface, var(--r19-wash))",
  borderColor: "var(--r19-line)",
};
const r19Ink: React.CSSProperties = { color: "var(--r19-ink)" };
const r19Muted: React.CSSProperties = { color: "var(--r19-muted)" };
const r19Copper: React.CSSProperties = { color: "var(--r19-copper)" };
const r19Input: React.CSSProperties = {
  background: "var(--r19-surface)",
  borderColor: "var(--r19-line)",
  color: "var(--r19-ink)",
};

// Inline form variant (default)
function InlineForm({
  defaultCategories = [],
  onSuccess,
  className,
}: NewsletterFormProps) {
  const isR19 = useR19();
  const [email, setEmail] = React.useState("");
  const [status, setStatus] = React.useState<
    "idle" | "loading" | "success" | "error"
  >("idle");
  const [errorMessage, setErrorMessage] = React.useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!email || !email.includes("@")) {
      setErrorMessage("Please enter a valid email address");
      setStatus("error");
      return;
    }

    setStatus("loading");
    setErrorMessage("");

    try {
      const result = await subscribeToNewsletter({
        email,
        categories:
          defaultCategories.length > 0
            ? defaultCategories
            : ["visas", "business"],
        frequency: "weekly",
        language: "en",
      });

      if (result.success) {
        setStatus("success");
        setEmail("");
        onSuccess?.();
      } else {
        setStatus("error");
        setErrorMessage(result.message);
      }
    } catch {
      setStatus("error");
      setErrorMessage("Something went wrong. Please try again.");
    }
  };

  return (
    <div className={cn("relative", className)}>
      <AnimatePresence mode="wait">
        {status === "success" ? (
          <motion.div
            key="success"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className={cn(
              "flex items-center gap-3 p-4 rounded-xl border",
              !isR19 && "bg-emerald-500/10 border-emerald-500/20",
            )}
            style={isR19 ? r19Panel : undefined}
          >
            <div
              className={cn(
                "flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center",
                !isR19 && "bg-emerald-500/20",
              )}
              style={
                isR19
                  ? { background: "var(--r19-wash)", ...r19Copper }
                  : undefined
              }
            >
              <Check
                className={cn("w-5 h-5", !isR19 && "text-emerald-400")}
                style={isR19 ? r19Copper : undefined}
              />
            </div>
            <div>
              <p
                className={cn("font-medium", !isR19 && "text-emerald-400")}
                style={isR19 ? r19Ink : undefined}
              >
                You&apos;re subscribed!
              </p>
              <p
                className={cn("text-sm", !isR19 && "text-white/60")}
                style={isR19 ? r19Muted : undefined}
              >
                Check your email to confirm.
              </p>
            </div>
          </motion.div>
        ) : (
          <motion.form
            key="form"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onSubmit={handleSubmit}
            className="space-y-3"
          >
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Mail
                  className={cn(
                    "absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5",
                    !isR19 && "text-white/40",
                  )}
                  style={isR19 ? r19Muted : undefined}
                />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="Enter your email"
                  aria-label="Email address"
                  disabled={status === "loading"}
                  className={cn(
                    "w-full h-12 pl-11 pr-4 rounded-xl border focus:outline-none",
                    !isR19 &&
                      "bg-white/5 border-white/10 text-white placeholder-white/40 focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500/50",
                    isR19 &&
                      "placeholder:text-[color:var(--r19-muted)] focus:ring-2 focus:ring-[color:var(--r19-copper)] focus:border-[color:var(--r19-copper)]",
                    "disabled:opacity-50 transition-all duration-200",
                  )}
                  style={isR19 ? r19Input : undefined}
                />
              </div>
              <button
                type="submit"
                disabled={status === "loading"}
                className={cn(
                  "px-6 h-12 rounded-xl font-medium transition-all flex items-center gap-2",
                  !isR19 &&
                    "bg-gradient-to-r from-violet-600 to-fuchsia-600 hover:from-violet-500 hover:to-fuchsia-500",
                  "disabled:opacity-50 disabled:cursor-not-allowed",
                )}
                style={
                  isR19
                    ? {
                        background: "var(--r19-copper)",
                        color: "var(--r19-cta-ink)",
                      }
                    : undefined
                }
              >
                {status === "loading" ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <>
                    Subscribe
                    <Sparkles className="w-4 h-4" />
                  </>
                )}
              </button>
            </div>

            {status === "error" && errorMessage && (
              <motion.p
                initial={{ opacity: 0, y: -5 }}
                animate={{ opacity: 1, y: 0 }}
                className={cn("text-sm", !isR19 && "text-red-400")}
                style={isR19 ? r19Ink : undefined}
              >
                {errorMessage}
              </motion.p>
            )}
          </motion.form>
        )}
      </AnimatePresence>
    </div>
  );
}

// Sidebar variant (with category selection)
function SidebarForm({
  defaultCategories = [],
  onSuccess,
  className,
}: NewsletterFormProps) {
  const isR19 = useR19();
  const [email, setEmail] = React.useState("");
  const [name, setName] = React.useState("");
  const [categories, setCategories] = React.useState<ArticleCategory[]>(
    defaultCategories.length > 0 ? defaultCategories : ["visas", "business"],
  );
  const [frequency, setFrequency] = React.useState<
    "daily" | "weekly" | "monthly"
  >("weekly");
  const [showCategories, setShowCategories] = React.useState(false);
  const [status, setStatus] = React.useState<
    "idle" | "loading" | "success" | "error"
  >("idle");
  const [errorMessage, setErrorMessage] = React.useState("");

  const toggleCategory = (cat: ArticleCategory) => {
    setCategories((prev) =>
      prev.includes(cat) ? prev.filter((c) => c !== cat) : [...prev, cat],
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!email || !email.includes("@")) {
      setErrorMessage("Please enter a valid email address");
      setStatus("error");
      return;
    }

    if (categories.length === 0) {
      setErrorMessage("Please select at least one category");
      setStatus("error");
      return;
    }

    setStatus("loading");
    setErrorMessage("");

    try {
      const result = await subscribeToNewsletter({
        email,
        name: name || undefined,
        categories,
        frequency,
        language: "en",
      });

      if (result.success) {
        setStatus("success");
        setEmail("");
        setName("");
        onSuccess?.();
      } else {
        setStatus("error");
        setErrorMessage(result.message);
      }
    } catch {
      setStatus("error");
      setErrorMessage("Something went wrong. Please try again.");
    }
  };

  if (status === "success") {
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className={cn(
          "p-6 rounded-2xl border",
          !isR19 &&
            "bg-gradient-to-br from-emerald-500/10 to-teal-500/10 border-emerald-500/20",
          isR19 && "rounded-lg",
          className,
        )}
        style={isR19 ? r19Panel : undefined}
      >
        <div className="text-center">
          <div
            className={cn(
              "w-16 h-16 mx-auto mb-4 rounded-full flex items-center justify-center",
              !isR19 && "bg-emerald-500/20",
            )}
            style={
              isR19
                ? { background: "var(--r19-wash)", ...r19Copper }
                : undefined
            }
          >
            <Check
              className={cn("w-8 h-8", !isR19 && "text-emerald-400")}
              style={isR19 ? r19Copper : undefined}
            />
          </div>
          <h3
            className={cn(
              "font-serif text-xl mb-2",
              !isR19 && "font-semibold text-white",
            )}
            style={isR19 ? r19Ink : undefined}
          >
            Welcome Aboard!
          </h3>
          <p
            className={cn(!isR19 && "text-white/60")}
            style={isR19 ? r19Muted : undefined}
          >
            Check your inbox to confirm your subscription.
          </p>
        </div>
      </motion.div>
    );
  }

  return (
    <div
      className={cn(
        "p-6 border",
        !isR19 &&
          "rounded-2xl bg-gradient-to-br from-violet-500/10 to-fuchsia-500/10 border-violet-500/20",
        isR19 && "rounded-lg",
        className,
      )}
      style={isR19 ? r19Panel : undefined}
    >
      {/* Header */}
      <div className="mb-6 text-center">
        {isR19 ? (
          <div
            className="text-[11px] font-semibold uppercase tracking-[0.28em] mb-3"
            style={r19Copper}
          >
            Newsletter
          </div>
        ) : (
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-violet-500/20 text-violet-400 text-xs font-medium mb-3">
            <Sparkles className="w-3 h-3" />
            Newsletter
          </div>
        )}
        <h3
          className={cn(
            "font-serif text-xl mb-2",
            !isR19 && "font-semibold text-white",
          )}
          style={isR19 ? r19Ink : undefined}
        >
          Stay Ahead of the Curve
        </h3>
        <p
          className={cn("text-sm", !isR19 && "text-white/60")}
          style={isR19 ? r19Muted : undefined}
        >
          Get the latest insights on business, immigration, and life in Bali.
        </p>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Name (optional) */}
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Your name (optional)"
          aria-label="Your name"
          className={cn(
            "w-full h-11 px-4 rounded-xl text-sm border focus:outline-none",
            !isR19 &&
              "bg-white/5 border-white/10 text-white placeholder-white/40 focus:ring-2 focus:ring-violet-500/50",
            isR19 &&
              "placeholder:text-[color:var(--r19-muted)] focus:ring-2 focus:ring-[color:var(--r19-copper)]",
          )}
          style={isR19 ? r19Input : undefined}
        />

        {/* Email */}
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Your email address"
          aria-label="Email address"
          required
          className={cn(
            "w-full h-11 px-4 rounded-xl text-sm border focus:outline-none",
            !isR19 &&
              "bg-white/5 border-white/10 text-white placeholder-white/40 focus:ring-2 focus:ring-violet-500/50",
            isR19 &&
              "placeholder:text-[color:var(--r19-muted)] focus:ring-2 focus:ring-[color:var(--r19-copper)]",
          )}
          style={isR19 ? r19Input : undefined}
        />

        {/* Category selector */}
        <div>
          <button
            type="button"
            onClick={() => setShowCategories(!showCategories)}
            className={cn(
              "w-full flex items-center justify-between px-4 py-3 rounded-xl text-sm border transition-colors",
              !isR19 &&
                "bg-white/5 border-white/10 text-white hover:bg-white/10",
            )}
            style={isR19 ? r19Input : undefined}
          >
            <span>
              {categories.length === 0
                ? "Select topics"
                : `${categories.length} topic${categories.length > 1 ? "s" : ""} selected`}
            </span>
            <ChevronDown
              className={cn(
                "w-4 h-4 transition-transform",
                showCategories && "rotate-180",
              )}
            />
          </button>

          <AnimatePresence>
            {showCategories && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="overflow-hidden"
              >
                <div className="pt-2 space-y-1">
                  {CATEGORY_OPTIONS.map((cat) => {
                    const active = categories.includes(cat.value);
                    return (
                      <button
                        key={cat.value}
                        type="button"
                        onClick={() => toggleCategory(cat.value)}
                        className={cn(
                          "w-full flex items-center gap-3 px-4 py-2 rounded-lg text-sm transition-colors",
                          !isR19 &&
                            (active
                              ? "bg-violet-500/20 text-violet-400"
                              : "text-white/60 hover:text-white hover:bg-white/5"),
                        )}
                        style={
                          isR19
                            ? {
                                color: active
                                  ? "var(--r19-ink)"
                                  : "var(--r19-muted)",
                                background: active
                                  ? "var(--r19-active-bg)"
                                  : "transparent",
                              }
                            : undefined
                        }
                      >
                        <div
                          className={cn(
                            "w-4 h-4 rounded border flex items-center justify-center",
                            !isR19 &&
                              (active
                                ? "bg-violet-500 border-violet-500"
                                : "border-white/20"),
                          )}
                          style={
                            isR19
                              ? {
                                  background: active
                                    ? "var(--r19-copper)"
                                    : "transparent",
                                  borderColor: active
                                    ? "var(--r19-copper)"
                                    : "var(--r19-line)",
                                }
                              : undefined
                          }
                        >
                          {active && (
                            <Check
                              className={cn("w-3 h-3", !isR19 && "text-white")}
                              style={
                                isR19
                                  ? { color: "var(--r19-cta-ink)" }
                                  : undefined
                              }
                            />
                          )}
                        </div>
                        {cat.label}
                      </button>
                    );
                  })}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Frequency */}
        <div className="flex gap-2">
          {FREQUENCY_OPTIONS.map((freq) => {
            const active = frequency === freq.value;
            return (
              <button
                key={freq.value}
                type="button"
                onClick={() => setFrequency(freq.value)}
                className={cn(
                  "flex-1 py-2 px-3 rounded-lg text-xs font-medium transition-colors",
                  !isR19 &&
                    (active
                      ? "bg-violet-500/20 text-violet-400"
                      : "bg-white/5 text-white/60 hover:text-white hover:bg-white/10"),
                )}
                style={
                  isR19
                    ? {
                        color: active ? "var(--r19-ink)" : "var(--r19-muted)",
                        background: active
                          ? "var(--r19-active-bg)"
                          : "var(--r19-surface)",
                        border: `1px solid ${active ? "var(--r19-active-border)" : "var(--r19-line)"}`,
                      }
                    : undefined
                }
              >
                {freq.label}
              </button>
            );
          })}
        </div>

        {/* Error message */}
        {status === "error" && errorMessage && (
          <p
            className={cn("text-sm", !isR19 && "text-red-400")}
            style={isR19 ? r19Ink : undefined}
          >
            {errorMessage}
          </p>
        )}

        {/* Submit button */}
        <button
          type="submit"
          disabled={status === "loading"}
          className={cn(
            "w-full h-11 rounded-xl font-medium transition-all flex items-center justify-center gap-2",
            !isR19 &&
              "bg-gradient-to-r from-violet-600 to-fuchsia-600 hover:from-violet-500 hover:to-fuchsia-500",
            "disabled:opacity-50 disabled:cursor-not-allowed",
          )}
          style={
            isR19
              ? { background: "var(--r19-copper)", color: "var(--r19-cta-ink)" }
              : undefined
          }
        >
          {status === "loading" ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <>
              Subscribe
              <Sparkles className="w-4 h-4" />
            </>
          )}
        </button>

        {/* Privacy note */}
        <p
          className={cn("text-xs text-center", !isR19 && "text-white/40")}
          style={isR19 ? r19Muted : undefined}
        >
          We respect your privacy. Unsubscribe anytime.
        </p>
      </form>
    </div>
  );
}

// Main component with variant support
export function NewsletterForm({
  variant = "inline",
  ...props
}: NewsletterFormProps) {
  if (variant === "sidebar" || variant === "modal") {
    return <SidebarForm {...props} />;
  }
  return <InlineForm {...props} />;
}

// Export variants directly
export { InlineForm as NewsletterInline, SidebarForm as NewsletterSidebar };
