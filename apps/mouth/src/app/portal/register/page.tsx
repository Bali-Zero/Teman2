"use client";

/**
 * Register — invite-token validation + PIN creation.
 *
 * WS3 final slice (GARUDA Day Edition, 2026-07-26): aligned to the day
 * tokens (was a forced-dark #2a2a2a/#242424 page with teal #4FD1C5 accents
 * and near-white #E6E7EB text — including on the isComplete screen, which
 * rendered a WHITE slate-50 card with that same near-white heading:
 * ~1.2:1, unreadable; fixed as part of the pass). Paper shell (--bz-base),
 * warm card (--bz-card + --bz-border + concept .panel shadow), serif-grade
 * ink headings (--tx-pure), forms = warm paper inputs + token borders +
 * copper focus rings, CTAs = darker copper step --bz-copper-text with
 * theme-aware --bz-on-warm fg (5.70:1 light; 6.74:1 dark — the base
 * copper step with white would be 4.37:1, below the 4.5:1 AA floor).
 * Status colors read --state-* AA tokens. Layout unchanged.
 */

import React, { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Image from "next/image";
import { Lock, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { logger } from "@/lib/logger";

const CARD_STYLE = {
  background: "var(--bz-card)",
  borderColor: "var(--bz-border)",
  boxShadow: "0 14px 34px rgba(22, 33, 58, 0.07)",
} as const;

const CTA_STYLE = {
  background: "var(--bz-copper-text)",
  color: "var(--bz-on-warm)",
} as const;

const INPUT_CLASS =
  "w-full px-4 py-3 bg-[var(--bz-base)] border border-[var(--bz-border)] rounded-lg text-[var(--tx-primary)] placeholder:text-[var(--tx-tertiary)] focus:outline-none focus:ring-2 focus:ring-[color-mix(in_srgb,var(--bz-copper)_25%,transparent)] focus:border-[var(--bz-copper)]";

function ValidatingScreen({ message }: { message: string }) {
  return (
    <div className="min-h-screen bg-[var(--bz-base)] flex items-center justify-center">
      <div className="text-center">
        <Loader2 className="w-12 h-12 text-[var(--bz-copper)] animate-spin mx-auto mb-4" />
        <p className="text-[var(--tx-secondary)]">{message}</p>
      </div>
    </div>
  );
}

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
          router.push("/portal/login-upgraded");
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
    return <ValidatingScreen message="Validating your invitation..." />;
  }

  if (isComplete) {
    return (
      <div className="min-h-screen bg-[var(--bz-base)] flex items-center justify-center p-4">
        <div
          className="rounded-2xl border p-8 max-w-md w-full text-center"
          style={CARD_STYLE}
        >
          <div
            className="p-4 rounded-full w-20 h-20 mx-auto mb-6 flex items-center justify-center"
            style={{
              background:
                "color-mix(in srgb, var(--state-success) 12%, transparent)",
            }}
          >
            <CheckCircle2
              className="w-10 h-10"
              style={{ color: "var(--state-success)" }}
            />
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
          <h1 className="text-2xl font-bold text-[var(--tx-pure)] mb-2">
            Welcome to Bali Zero!
          </h1>
          <p className="text-[var(--tx-secondary)] mb-6">
            Your portal account has been activated. Redirecting you to login...
          </p>
          <div className="flex items-center justify-center gap-2 text-[var(--bz-copper-text)]">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span className="text-sm">Redirecting...</span>
          </div>
        </div>
      </div>
    );
  }

  if (!isValid) {
    return (
      <div className="min-h-screen bg-[var(--bz-base)] flex items-center justify-center p-4">
        <div
          className="rounded-2xl border p-8 max-w-md w-full text-center"
          style={CARD_STYLE}
        >
          <div
            className="p-4 rounded-full w-20 h-20 mx-auto mb-6 flex items-center justify-center"
            style={{
              background:
                "color-mix(in srgb, var(--state-danger) 12%, transparent)",
            }}
          >
            <AlertCircle
              className="w-10 h-10"
              style={{ color: "var(--state-danger)" }}
            />
          </div>
          <h1 className="text-2xl font-bold text-[var(--tx-pure)] mb-2">
            Invalid Invitation
          </h1>
          <p className="text-[var(--tx-secondary)] mb-6">
            {error ||
              "This invitation link is no longer valid. Please contact your account manager for a new invitation."}
          </p>
          <a
            href="mailto:zantara@balizero.com"
            className="inline-block px-6 py-3 rounded-lg font-medium transition-opacity hover:opacity-90"
            style={CTA_STYLE}
          >
            Contact Support
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--bz-base)] flex items-center justify-center p-4">
      <div
        className="rounded-2xl border p-8 max-w-md w-full"
        style={CARD_STYLE}
      >
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
          <div
            className="p-4 rounded-full w-20 h-20 mx-auto mb-6 flex items-center justify-center"
            style={{
              background:
                "color-mix(in srgb, var(--bz-copper) 12%, transparent)",
            }}
          >
            <Lock className="w-10 h-10" style={{ color: "var(--bz-copper)" }} />
          </div>
          <h1 className="text-2xl font-bold text-[var(--tx-pure)] mb-2">
            Create Your PIN
          </h1>
          <p className="text-[var(--tx-secondary)]">
            Welcome,{" "}
            <span className="font-medium text-[var(--tx-pure)]">
              {clientName}
            </span>
            !
            <br />
            Set a 4-6 digit PIN to secure your portal access.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-[var(--tx-primary)] mb-2">
              Email
            </label>
            <input
              type="email"
              value={clientEmail}
              disabled
              className={`${INPUT_CLASS} disabled:text-[var(--tx-secondary)] disabled:opacity-70`}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-[var(--tx-primary)] mb-2">
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
              className={`${INPUT_CLASS} text-center text-2xl tracking-widest`}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-[var(--tx-primary)] mb-2">
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
              className={`${INPUT_CLASS} text-center text-2xl tracking-widest`}
            />
          </div>

          {error && (
            <div
              className="p-3 rounded-lg border"
              style={{
                background:
                  "color-mix(in srgb, var(--state-danger) 8%, transparent)",
                borderColor:
                  "color-mix(in srgb, var(--state-danger) 30%, transparent)",
              }}
            >
              <p
                className="text-sm text-center"
                style={{ color: "var(--state-danger)" }}
              >
                {error}
              </p>
            </div>
          )}

          <button
            type="submit"
            disabled={isSubmitting || pin.length < 4 || confirmPin.length < 4}
            className="w-full py-3 rounded-lg font-medium transition-opacity disabled:cursor-not-allowed"
            style={
              isSubmitting || pin.length < 4 || confirmPin.length < 4
                ? {
                    background: "var(--bz-border)",
                    color: "var(--tx-secondary)",
                  }
                : CTA_STYLE
            }
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

        <p className="text-xs text-[var(--tx-secondary)] text-center mt-6">
          By continuing, you agree to our Terms of Service and Privacy Policy.
        </p>
      </div>
    </div>
  );
}

export default function RegisterPage() {
  return (
    <Suspense fallback={<ValidatingScreen message="Loading..." />}>
      <RegisterContent />
    </Suspense>
  );
}
