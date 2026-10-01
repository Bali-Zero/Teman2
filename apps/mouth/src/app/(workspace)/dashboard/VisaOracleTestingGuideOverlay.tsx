"use client";

/**
 * Testing-guide overlay for the Visa Oracle campaign (slots T01-T06).
 *
 * Mounted once in the workspace layout so an assigned tester sees the guide on
 * every Kita page, not only the dashboard. It shares the banner's query key and
 * its show-rule (`bannerProgress`), so the dashboard does not fetch twice.
 * Fails silent: any fetch error renders nothing. "Nanti" snoozes it for 30
 * minutes via sessionStorage, keyed by the Bali date so it never carries over
 * to the next day.
 */

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { testingApi } from "../intelligence/visa-oracle/testing/api";
import type { CampaignData } from "../intelligence/visa-oracle/testing/types";
import { baliDate, bannerProgress } from "./VisaOracleTestingBanner";
import { FOCUS, SERIF } from "./r19";

const HREF = "/intelligence/visa-oracle/testing";
const PER_DAY = 5;
const SNOOZE_MS = 30 * 60_000;
const TITLE_ID = "visa-oracle-testing-guide-title";

export function guideDismissKey(today: string): string {
  return `visa-oracle-testing-guide-dismissed:${today}`;
}

function snoozed(today: string, nowMs: number): boolean {
  try {
    const raw = window.sessionStorage.getItem(guideDismissKey(today));
    const at = raw === null ? NaN : Number(raw);
    return Number.isFinite(at) && nowMs - at < SNOOZE_MS;
  } catch {
    return false;
  }
}

const STEPS = [
  "Buka halaman pengujian — di bagian “Penugasan Anda” ada lima kasus hari ini.",
  "Kunci kelima ekspektasi dulu: isi “Hasil yang Anda harapkan dan alasannya”, pilih “Dasar ekspektasi”, catat “Browser dan versi” dan “Perangkat / OS”, lalu tekan “Kunci ekspektasi”. Ekspektasi yang terkunci tidak bisa diubah.",
  "Klik “Buka Visa Oracle” dan masukkan jawaban sintetis kasus secara manual.",
  "Catat hasil, “Simpan draf ke server” bila perlu, lalu tekan “Kirim observasi”.",
  "Tinjau hasil Anda sendiri di “Antrean reviewer” — bukan milik rekan.",
];

export function VisaOracleTestingGuideOverlay({
  identity,
  now = () => new Date(),
}: {
  identity: string;
  /** Injectable clock, so tests control "today" and the 30-minute snooze. */
  now?: () => Date;
}) {
  const pathname = usePathname();
  const [closed, setClosed] = useState(false);
  const [, rerender] = useState(0);
  const primaryRef = useRef<HTMLAnchorElement | null>(null);
  const dialogRef = useRef<HTMLDivElement | null>(null);

  const { data, isError } = useQuery<CampaignData>({
    queryKey: ["visa-oracle-testing-banner", identity],
    queryFn: () => testingApi.load(),
    staleTime: 60_000,
    refetchInterval: 5 * 60_000,
    retry: false,
    enabled: Boolean(identity),
  });

  const current = now();
  const today = baliDate(current);
  const submitted = isError ? null : bannerProgress(data, today);
  const onTestingPage = Boolean(pathname?.startsWith(HREF));
  const visible =
    submitted !== null &&
    !onTestingPage &&
    !closed &&
    !snoozed(today, current.getTime());

  const dismiss = () => {
    try {
      window.sessionStorage.setItem(
        guideDismissKey(today),
        String(now().getTime()),
      );
    } catch {
      /* storage unavailable: dismiss for this mount only */
    }
    setClosed(true);
    rerender((n) => n + 1);
  };

  const dismissRef = useRef(dismiss);
  dismissRef.current = dismiss;

  useEffect(() => {
    if (!visible) return;
    primaryRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        dismissRef.current();
        return;
      }
      if (e.key !== "Tab") return;
      const nodes = dialogRef.current?.querySelectorAll<HTMLElement>(
        "a[href], button:not([disabled])",
      );
      if (!nodes || nodes.length === 0) return;
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      const active = document.activeElement;
      if (e.shiftKey && active === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [visible]);

  if (!visible) return null;

  return (
    <div
      data-testid="visa-oracle-testing-guide-overlay"
      className="fixed inset-0 z-[60] overflow-y-auto bg-black/60"
    >
      <div className="flex min-h-full items-center justify-center p-3 sm:p-6">
        <div
          ref={dialogRef}
          role="dialog"
          aria-modal="true"
          aria-labelledby={TITLE_ID}
          className="w-full max-w-2xl rounded-2xl border-2 border-[var(--bz-kita-ink-panel-copper)] bg-[var(--bz-text-1)] p-5 text-[var(--bz-surface)] sm:p-8"
        >
          <h2
            id={TITLE_ID}
            className="text-[clamp(26px,4vw,38px)] font-black leading-tight"
            style={SERIF}
          >
            Panduan Uji Visa Oracle
          </h2>
          <p className="mt-3 text-base font-bold text-[var(--bz-kita-ink-panel-copper)]">
            Hari ini: {submitted}/{PER_DAY} kasus terkirim. Kasus hari ini harus
            dimulai hari ini, sebelum akhir hari WITA.
          </p>
          <ol className="mt-4 list-decimal space-y-3 pl-6 text-base leading-relaxed">
            {STEPS.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
          <p className="mt-5 rounded-lg border border-[var(--bz-kita-ink-panel-copper)] p-3 text-base leading-relaxed">
            Hanya data sintetis dari kasus — jangan pernah data klien asli, juga
            di screenshot. Ada yang janggal di Oracle? Tulis di observasi.
            Pertanyaan: hubungi Zero.
          </p>
          <div className="mt-6 flex flex-col gap-3 sm:flex-row">
            <Link
              ref={primaryRef}
              href={HREF}
              onClick={() => setClosed(true)}
              className={`inline-flex min-h-14 items-center justify-center bg-[var(--bz-copper)] px-8 text-lg font-extrabold text-[var(--bz-on-warm)] hover:opacity-90 ${FOCUS}`}
            >
              Mulai uji sekarang →
            </Link>
            <button
              type="button"
              onClick={dismiss}
              className={`inline-flex min-h-14 items-center justify-center border-2 border-[var(--bz-surface)] px-8 text-lg font-bold hover:opacity-90 ${FOCUS}`}
            >
              Nanti
            </button>
          </div>
          <p className="mt-4 text-[13px] leading-snug">
            Panduan PDF lengkap ada di email dari Zantara
            (zantara@balizero.com).
          </p>
        </div>
      </div>
    </div>
  );
}
