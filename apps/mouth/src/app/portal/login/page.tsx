"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { Loader2, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { toast } from "sonner";

export default function PortalLoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [pin, setPin] = useState("");
  const [step, setStep] = useState<"email" | "pin">("email");
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmitEmail = (e: React.FormEvent) => {
    e.preventDefault();
    if (email) setStep("pin");
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      await api.login(email, pin);
      router.push("/portal");
    } catch {
      toast.error("Login failed", { description: "Invalid email or PIN" });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div
      className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden"
      style={{ background: "var(--bz-base, #0c0c0e)" }}
    >
      {/* Ambient glow — oro antico bottom-left, cool indigo top-right */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: `
            radial-gradient(ellipse 60% 50% at 10% 90%, rgba(201,169,110,0.06) 0%, transparent 60%),
            radial-gradient(ellipse 50% 60% at 90% 10%, rgba(94,127,181,0.05) 0%, transparent 60%)
          `,
        }}
      />

      {/* Batik texture */}
      <div
        className="absolute inset-0 pointer-events-none opacity-[0.025]"
        style={{
          backgroundImage: "var(--bz-batik-texture)",
          backgroundSize: "20px 20px",
        }}
      />

      {/* Card */}
      <div className="relative z-10 w-full max-w-[360px]">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8 gap-3">
          <Image
            src="/static/balizero-logo-clean.png"
            alt="Bali Zero"
            width={40}
            height={40}
            className="rounded-full"
            priority
          />
          <div className="text-center">
            <div
              className="text-[15px] font-semibold"
              style={{ color: "var(--bz-text-1, #edeae4)" }}
            >
              Bali Zero
            </div>
            <div
              className="text-[11px] mt-0.5"
              style={{ color: "var(--bz-text-3, #575350)" }}
            >
              Client Portal
            </div>
          </div>
          <p
            className="text-[11px] text-center mt-1"
            style={{ color: "var(--bz-text-3, #575350)" }}
          >
            Access your documents, visa status &amp; messages
          </p>
        </div>

        {/* Form card */}
        <div
          className="rounded-xl p-6 space-y-5 border"
          style={{
            background: "var(--bz-card, #202024)",
            borderColor: "var(--bz-border, rgba(255,255,255,0.055))",
          }}
        >
          {step === "email" ? (
            <form onSubmit={handleSubmitEmail} className="space-y-4">
              <div className="space-y-1.5">
                <label
                  className="text-[11px] font-medium uppercase tracking-[0.5px]"
                  style={{ color: "var(--bz-text-2, #8c8884)" }}
                >
                  Email Address
                </label>
                <Input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="text-[13px]"
                  style={{
                    background: "var(--bz-surface, #1a1a1e)",
                    borderColor: "var(--bz-border, rgba(255,255,255,0.055))",
                    color: "var(--bz-text-1, #edeae4)",
                  }}
                  required
                  autoFocus
                />
              </div>
              <Button
                type="submit"
                className="w-full font-medium text-[13px] text-white"
                style={{ background: "var(--bz-accent-warm, #c9a96e)" }}
              >
                Continue <ArrowRight className="w-3.5 h-3.5 ml-2" />
              </Button>
            </form>
          ) : (
            <form
              onSubmit={handleLogin}
              className="space-y-4 animate-in slide-in-from-right-4 fade-in"
            >
              <div className="space-y-1.5">
                <div className="flex justify-between items-center">
                  <label
                    className="text-[11px] font-medium uppercase tracking-[0.5px]"
                    style={{ color: "var(--bz-text-2, #8c8884)" }}
                  >
                    Access PIN
                  </label>
                  <button
                    type="button"
                    onClick={() => setStep("email")}
                    className="text-[11px] transition-colors"
                    style={{ color: "var(--bz-accent-warm, #c9a96e)" }}
                  >
                    Change Email
                  </button>
                </div>
                <Input
                  type="password"
                  value={pin}
                  onChange={(e) => setPin(e.target.value)}
                  placeholder="••••••"
                  className="text-center text-2xl tracking-widest text-[13px]"
                  style={{
                    background: "var(--bz-surface, #1a1a1e)",
                    borderColor: "var(--bz-border, rgba(255,255,255,0.055))",
                    color: "var(--bz-text-1, #edeae4)",
                  }}
                  maxLength={6}
                  required
                  autoFocus
                />
              </div>
              <Button
                type="submit"
                className="w-full font-medium text-[13px] text-white"
                style={{ background: "var(--bz-accent-warm, #c9a96e)" }}
                disabled={isLoading}
              >
                {isLoading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  "Enter Portal"
                )}
              </Button>
            </form>
          )}

          <p
            className="text-[10px] text-center pt-2"
            style={{ color: "var(--bz-text-3, #575350)" }}
          >
            Don&apos;t have a PIN? Check your invitation email or contact
            support.
          </p>
        </div>

        {/* Team workspace link */}
        <div className="text-center mt-4">
          <a
            href="/login"
            className="text-[11px] transition-colors"
            style={{ color: "var(--bz-text-3, #575350)" }}
            onMouseEnter={(e) =>
              (e.currentTarget.style.color = "var(--bz-accent, #d4845a)")
            }
            onMouseLeave={(e) =>
              (e.currentTarget.style.color = "var(--bz-text-3, #575350)")
            }
          >
            Team workspace →
          </a>
        </div>
      </div>
    </div>
  );
}
