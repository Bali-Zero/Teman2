"use client";

/**
 * Unmissable banner for the Visa Oracle testing campaign (slots T01-T06).
 *
 * Reuses the testing page's client and types; no backend endpoint of its own.
 * Fails silent by design: on any fetch error, 401/403 or missing field it
 * renders nothing. It shows only for an assigned tester, on a campaign day
 * (Asia/Makassar calendar, never the browser's zone), while at least one of
 * the viewer's own cases for today is not yet submitted.
 */

import React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { testingApi } from "../intelligence/visa-oracle/testing/api";
import type { CampaignData } from "../intelligence/visa-oracle/testing/types";
import { FOCUS, SERIF } from "./r19";

const TIMEZONE = "Asia/Makassar";
const PER_DAY = 5;
const HREF = "/intelligence/visa-oracle/testing";

/** YYYY-MM-DD on the Bali calendar. */
export function baliDate(now: Date): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: TIMEZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(now);
}

/** Submitted count for the viewer's own cases today, or null = do not show. */
export function bannerProgress(
  data: CampaignData | null | undefined,
  today: string,
): number | null {
  const slot = data?.viewer?.slot;
  const start = data?.campaign?.start_date;
  const end = data?.campaign?.end_date;
  if (!slot || !start || !end || !Array.isArray(data?.assignments)) {
    return null;
  }
  if (today < start || today > end) return null;
  const mine = data.assignments.filter(
    (a) => a?.slot === slot && a?.day === today,
  );
  if (mine.length === 0) return null;
  const submitted = mine.filter((a) => a.record?.status === "submitted");
  if (submitted.length === mine.length) return null;
  return submitted.length;
}

export function VisaOracleTestingBanner({
  identity,
  now = () => new Date(),
}: {
  identity: string;
  /** Injectable clock, so tests control "today" without fake timers. */
  now?: () => Date;
}) {
  const { data, isError } = useQuery<CampaignData>({
    queryKey: ["visa-oracle-testing-banner", identity],
    queryFn: () => testingApi.load(),
    staleTime: 60_000,
    refetchInterval: 5 * 60_000,
    retry: false,
    enabled: Boolean(identity),
  });
  if (isError) return null;
  const submitted = bannerProgress(data, baliDate(now()));
  if (submitted === null) return null;

  return (
    <section
      role="region"
      aria-label="Pengingat Uji Visa Oracle"
      data-testid="visa-oracle-testing-banner"
      className="mb-4 rounded-2xl border-2 border-[var(--bz-kita-ink-panel-copper)] bg-[var(--bz-text-1)] p-5 text-[var(--bz-surface)] sm:p-8"
    >
      <div className="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
        <div className="max-w-3xl">
          <h2
            className="text-[clamp(28px,4vw,44px)] font-black leading-tight"
            style={SERIF}
          >
            Uji Visa Oracle — hari ini
          </h2>
          <p className="mt-3 text-base leading-relaxed sm:text-lg">
            Buka email dari Zantara (zantara@balizero.com): panduan Uji Visa
            Oracle ada di lampiran. Kasus hari ini harus dimulai hari ini,
            sebelum akhir hari WITA.
          </p>
          <p className="mt-3 text-base font-bold text-[var(--bz-kita-ink-panel-copper)] sm:text-lg">
            {submitted}/{PER_DAY} kasus hari ini terkirim
          </p>
        </div>
        <Link
          href={HREF}
          className={`inline-flex min-h-14 shrink-0 items-center justify-center gap-2 bg-[var(--bz-copper)] px-8 text-lg font-extrabold text-[var(--bz-on-warm)] hover:opacity-90 ${FOCUS}`}
        >
          Mulai uji sekarang →
        </Link>
      </div>
    </section>
  );
}
