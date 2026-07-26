"use client";

/**
 * Portal Family — list of family members, split adult/minor.
 *
 * WS3 slice 8 (GARUDA Day Edition, 2026-07-27): day-theme token alignment,
 * mirroring slices 5-7. Masthead = copper rule + Cormorant serif
 * (--font-serif) in --tx-pure (replaces lux-text-gradient); member cards read
 * --bz-card / --bz-border + the concept .panel shadow (drops the dark-only
 * rgba(255,255,255,0.01) fill and --glass-rim border); section icons read
 * --bz-copper; relationship chips read --bz-copper-text (#9d5230 = 5.05:1 on paper) // token-lint-ok: doc comment citing token value, not a color use
 * (5.70:1 on card, AA small text; dark aliases --bz-copper, AA on anthracite).
 * The destructive Alert keeps the shared component but its surface/text read
 * --state-danger tints + --bz-text-1 (text-red-500 was ~3.9:1 on paper —
 * below the 4.5:1 floor). No hardcoded hexes.
 */

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { AlertTriangle, User, Baby } from "lucide-react";

interface FamilyMember {
  id: number;
  full_name: string;
  relationship: string;
  date_of_birth: string | null;
  is_adult: boolean;
  nationality: string | null;
  passport_number: string | null;
  passport_expiry: string | null;
  visa_type: string | null;
  visa_expiry: string | null;
  email: string | null;
  phone: string | null;
}

interface FamilyResponse {
  adults: FamilyMember[];
  minors: FamilyMember[];
}

async function fetchFamily(): Promise<FamilyResponse> {
  return api.request<FamilyResponse>("/api/portal/family", { method: "GET" });
}

// Day member card (GARUDA Day concept .panel): white card on warm paper,
// hairline warm border, soft navy shadow (near-invisible on dark).
const MEMBER_CARD_STYLE = {
  background: "var(--bz-card)",
  borderColor: "var(--bz-border)",
  boxShadow: "0 14px 34px rgba(22, 33, 58, 0.07)",
} as const;

// Day masthead (GARUDA Day Edition): copper rule + Cormorant serif headline
// per concept (--font-serif, wired on <html>); Inter everywhere else.
function FamilyMasthead() {
  return (
    <section>
      <div
        aria-hidden="true"
        className="w-14 h-[3px] rounded-sm mb-4 bg-[var(--bz-copper)]"
      />
      <h1
        className="text-2xl font-semibold tracking-tight text-[var(--tx-pure)]"
        style={{ fontFamily: "var(--font-serif)" }}
      >
        Family
      </h1>
      <p className="text-sm text-[var(--tx-secondary)] mt-1">
        Spouse, children and other dependents on your record.
      </p>
    </section>
  );
}

export default function PortalFamilyPage() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["portal", "family"],
    queryFn: fetchFamily,
    staleTime: 5 * 60 * 1000,
  });

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <FamilyMasthead />
        <p className="text-sm text-[var(--tx-secondary)]">Loading…</p>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="p-6 space-y-4">
        <FamilyMasthead />
        {/* Shared Alert kept; surface/text re-tokenized at page level —
            text-red-500 fails AA small text on paper (~3.9:1). */}
        <Alert
          variant="destructive"
          style={{
            borderColor:
              "color-mix(in srgb, var(--state-danger) 30%, transparent)",
            background:
              "color-mix(in srgb, var(--state-danger) 8%, transparent)",
            color: "var(--bz-text-1)",
          }}
        >
          <AlertTriangle
            className="h-4 w-4"
            style={{ color: "var(--state-danger)" }}
          />
          <AlertTitle>Unable to load family</AlertTitle>
          <AlertDescription>
            {error instanceof Error ? error.message : "Unexpected error."}
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  const adults = data?.adults ?? [];
  const minors = data?.minors ?? [];
  const isEmpty = adults.length === 0 && minors.length === 0;

  return (
    <div className="p-6 space-y-8 max-w-3xl">
      <FamilyMasthead />

      {isEmpty ? (
        <Alert>
          <AlertTitle>No family members on file</AlertTitle>
          <AlertDescription>
            Ask the team to add them from the CRM; they'll show up here with
            their visa and passport status.
          </AlertDescription>
        </Alert>
      ) : (
        <>
          {adults.length > 0 && (
            <section className="space-y-3">
              <h2 className="text-sm font-semibold uppercase tracking-widest text-[var(--tx-secondary)] flex items-center gap-2">
                <User
                  className="w-4 h-4"
                  style={{ color: "var(--bz-copper)" }}
                />{" "}
                Adults ({adults.length})
              </h2>
              <div className="space-y-2">
                {adults.map((m) => (
                  <AdultCard key={m.id} member={m} />
                ))}
              </div>
            </section>
          )}

          {minors.length > 0 && (
            <section className="space-y-3">
              <h2 className="text-sm font-semibold uppercase tracking-widest text-[var(--tx-secondary)] flex items-center gap-2">
                <Baby
                  className="w-4 h-4"
                  style={{ color: "var(--bz-copper)" }}
                />{" "}
                Minors ({minors.length})
              </h2>
              <div className="space-y-2">
                {minors.map((m) => (
                  <MinorCard key={m.id} member={m} />
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}

function AdultCard({ member }: { member: FamilyMember }) {
  return (
    <article
      className="p-4 rounded-lg border flex flex-col gap-1"
      style={MEMBER_CARD_STYLE}
    >
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="font-medium text-[var(--tx-primary)]">
          {member.full_name}
        </h3>
        <span
          className="text-[10px] uppercase tracking-widest"
          style={{ color: "var(--bz-copper-text, var(--tx-secondary))" }}
        >
          {member.relationship}
        </span>
      </div>
      <div className="text-xs text-[var(--tx-secondary)] flex flex-wrap gap-3">
        {member.nationality && <span>{member.nationality}</span>}
        {member.passport_number && <span>PP {member.passport_number}</span>}
        {member.visa_type && <span>{member.visa_type}</span>}
        {member.visa_expiry && (
          <span>
            Visa exp {new Date(member.visa_expiry).toLocaleDateString()}
          </span>
        )}
      </div>
    </article>
  );
}

function MinorCard({ member }: { member: FamilyMember }) {
  return (
    <article
      className="p-4 rounded-lg border flex flex-col gap-1"
      style={MEMBER_CARD_STYLE}
    >
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="font-medium text-[var(--tx-primary)]">
          {member.full_name}
        </h3>
        <span
          className="text-[10px] uppercase tracking-widest"
          style={{ color: "var(--bz-copper-text, var(--tx-secondary))" }}
        >
          {member.relationship}
        </span>
      </div>
      <div className="text-xs text-[var(--tx-secondary)] flex flex-wrap gap-3">
        {member.date_of_birth && (
          <span>DOB {new Date(member.date_of_birth).toLocaleDateString()}</span>
        )}
        {member.passport_number && <span>PP {member.passport_number}</span>}
        {member.passport_expiry && (
          <span>
            PP exp {new Date(member.passport_expiry).toLocaleDateString()}
          </span>
        )}
      </div>
      <p className="text-[11px] text-[var(--tx-secondary)] italic">
        To update this record, message the team.
      </p>
    </article>
  );
}
