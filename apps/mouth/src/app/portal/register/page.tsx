"use client";

import React, { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Image from "next/image";
import { Lock, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { logger } from "@/lib/logger";

function RegisterContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = searchParams?.get("token");

  const [isValidating, setIsValidating] = useState(true);
  const [isValid, setIsValid] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [clientName, setClientName] = useState("");
  const [clientEmail, setClientEmail] = useState("");
  const [pin, setPin] = useState("");
  const [confirmPin, setConfirmPin] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isComplete, setIsComplete] = useState(false);

  useEffect(() => {
    if (!token) {
      setIsValidating(false);
      setError("Invalid invitation link. Please check the link in your email.");
      return;
    }

    const validateToken = async () => {
      try {
        const result = await api.portal.validateInviteToken(token);
        if (result.valid) {
          setIsValid(true);
          setClientName(result.clientName || "");
          setClientEmail(result.email || "");
        } else {
          setError(result.message || "This invitation is no longer valid.");
        }
      } catch (err) {
        logger.error(
          "Token validation failed",
          {},
          err instanceof Error ? err : new Error(String(err)),
        );
        setError("Failed to validate invitation. Please try again.");
      } finally {
        setIsValidating(false);
      }
    };

    validateToken();
  }, [token]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (pin !== confirmPin) {
      setError("PINs do not match");
      return;
    }

    if (pin.length < 4 || pin.length > 6 || !/^\d+$/.test(pin)) {
      setError("PIN must be 4-6 digits");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const result = await api.portal.completeRegistration({
        token: token!,
        pin,
      });

      if (result.success) {
        setIsComplete(true);
        // Redirect to login after 3 seconds
        setTimeout(() => {
          router.push("/login");
        }, 3000);
      } else {
        setError(result.message || "Registration failed. Please try again.");
      }
    } catch (err) {
      logger.error(
        "Registration failed",
        {},
        err instanceof Error ? err : new Error(String(err)),
      );
      setError("Registration failed. Please try again or contact support.");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isValidating) {
    return (
      <div className="min-h-screen bg-[#2a2a2a] flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 text-[#4FD1C5] animate-spin mx-auto mb-4" />
          <p className="text-muted-cool">Validating your invitation...</p>
        </div>
      </div>
    );
  }

  if (isComplete) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-lg p-8 max-w-md w-full text-center">
          <div className="p-4 bg-emerald-100 rounded-full w-20 h-20 mx-auto mb-6 flex items-center justify-center">
            <CheckCircle2 className="w-10 h-10 text-emerald-600" />
          </div>
          <div className="flex items-center justify-center mb-4">
            <div className="relative w-16 h-16 rounded-full overflow-hidden">
              <Image
                src="/assets/logo/balizero-logo-clean.png"
                alt="Bali Zero"
                fill
                className="object-cover scale-110"
              />
            </div>
          </div>
          <h1 className="text-2xl font-bold text-[#E6E7EB] mb-2">
            Welcome to Bali Zero!
          </h1>
          <p className="text-muted-cool mb-6">
            Your portal account has been activated. Redirecting you to login...
          </p>
          <div className="flex items-center justify-center gap-2 text-[#4FD1C5]">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span className="text-sm">Redirecting...</span>
          </div>
        </div>
      </div>
    );
  }

  if (!isValid) {
    return (
      <div className="min-h-screen bg-[#2a2a2a] flex items-center justify-center p-4">
        <div className="bg-[#242424] border border-white/5 rounded-2xl shadow-lg p-8 max-w-md w-full text-center">
          <div className="p-4 bg-red-500/20 rounded-full w-20 h-20 mx-auto mb-6 flex items-center justify-center">
            <AlertCircle className="w-10 h-10 text-red-500" />
          </div>
          <h1 className="text-2xl font-bold text-[#E6E7EB] mb-2">
            Invalid Invitation
          </h1>
          <p className="text-muted-cool mb-6">
            {error ||
              "This invitation link is no longer valid. Please contact your account manager for a new invitation."}
          </p>
          <a
            href="mailto:support@balizero.com"
            className="inline-block px-6 py-3 bg-[#4FD1C5] text-[#0B0E13] rounded-lg font-medium hover:bg-[#4FD1C5]/80 transition-colors"
          >
            Contact Support
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#2a2a2a] flex items-center justify-center p-4">
      <div className="bg-[#242424] border border-white/5 rounded-2xl shadow-lg p-8 max-w-md w-full">
        <div className="text-center mb-8">
          <div className="flex items-center justify-center mb-4">
            <div className="relative w-16 h-16 rounded-full overflow-hidden">
              <Image
                src="/assets/logo/balizero-logo-clean.png"
                alt="Bali Zero"
                fill
                className="object-cover scale-110"
              />
            </div>
          </div>
          <div className="p-4 bg-[#4FD1C5]/20 rounded-full w-20 h-20 mx-auto mb-6 flex items-center justify-center">
            <Lock className="w-10 h-10 text-[#4FD1C5]" />
          </div>
          <h1 className="text-2xl font-bold text-[#E6E7EB] mb-2">
            Create Your PIN
          </h1>
          <p className="text-muted-cool">
            Welcome,{" "}
            <span className="font-medium text-[#E6E7EB]">{clientName}</span>!
            <br />
            Set a 4-6 digit PIN to secure your portal access.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-[#E6E7EB] mb-2">
              Email
            </label>
            <input
              type="email"
              value={clientEmail}
              disabled
              className="w-full px-4 py-3 bg-surface-editorial-elevated border border-white/5 rounded-lg text-muted-cool"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-[#E6E7EB] mb-2">
              Create PIN (4-6 digits)
            </label>
            <input
              type="password"
              inputMode="numeric"
              pattern="[0-9]*"
              maxLength={6}
              value={pin}
              onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))}
              placeholder="Enter PIN"
              className="w-full px-4 py-3 bg-surface-editorial-elevated border border-white/5 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#4FD1C5] focus:border-[#4FD1C5]/50 text-center text-2xl tracking-widest text-[#E6E7EB] placeholder:text-muted-cool"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-[#E6E7EB] mb-2">
              Confirm PIN
            </label>
            <input
              type="password"
              inputMode="numeric"
              pattern="[0-9]*"
              maxLength={6}
              value={confirmPin}
              onChange={(e) => setConfirmPin(e.target.value.replace(/\D/g, ""))}
              placeholder="Confirm PIN"
              className="w-full px-4 py-3 bg-surface-editorial-elevated border border-white/5 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#4FD1C5] focus:border-[#4FD1C5]/50 text-center text-2xl tracking-widest text-[#E6E7EB] placeholder:text-muted-cool"
            />
          </div>

          {error && (
            <div className="p-3 bg-red-500/20 border border-red-500/30 rounded-lg">
              <p className="text-sm text-red-400 text-center">{error}</p>
            </div>
          )}

          <button
            type="submit"
            disabled={isSubmitting || pin.length < 4 || confirmPin.length < 4}
            className={`w-full py-3 rounded-lg font-medium transition-colors ${
              isSubmitting || pin.length < 4 || confirmPin.length < 4
                ? "bg-surface-editorial-elevated text-muted-cool cursor-not-allowed"
                : "bg-[#4FD1C5] text-[#0B0E13] hover:bg-[#4FD1C5]/80"
            }`}
          >
            {isSubmitting ? (
              <span className="flex items-center justify-center gap-2">
                <Loader2 className="w-5 h-5 animate-spin" />
                Creating Account...
              </span>
            ) : (
              "Activate My Portal"
            )}
          </button>
        </form>

        <p className="text-xs text-muted-cool text-center mt-6">
          By continuing, you agree to our Terms of Service and Privacy Policy.
        </p>
      </div>
    </div>
  );
}

export default function RegisterPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-[#2a2a2a] flex items-center justify-center">
          <div className="text-center">
            <Loader2 className="w-12 h-12 text-[#4FD1C5] animate-spin mx-auto mb-4" />
            <p className="text-muted-cool">Loading...</p>
          </div>
        </div>
      }
    >
      <RegisterContent />
    </Suspense>
  );
}
