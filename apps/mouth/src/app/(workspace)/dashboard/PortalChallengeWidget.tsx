"use client";

/**
 * "Portal Champion" live leaderboard — hero widget at the top of the kita
 * staff dashboard for the 14–29 Sept 2026 (WITA) client-activation challenge.
 *
 * R19 (concept-F) idiom, page-local (see ./r19.tsx). Backend contract:
 * GET /api/dashboard/portal-challenge (PR #6481) — usePortalChallenge
 * swallows every failure into `null`, so this widget renders a quiet
 * placeholder instead of an error banner or a crash until the endpoint
 * ships/deploys.
 *
 * Only clients who register AND log in with a PIN count as "aktivasi" — the
 * rules drawer spells this out in Bahasa Indonesia for the team.
 *
 * DESIGN GATE ROUND 2 (2026-09-14): the hero band is a dark "ink" panel so
 * the widget dominates the dashboard rather than reading as a settings card.
 * It reuses --bz-text-1 (a dark ink-navy TOKEN already declared for kita
 * body text, globals.css) as a BACKGROUND instead of introducing a new hex
 * literal — "tokens only" is honoured by reuse, not by a new declaration.
 * Every tone in this file was checked against globals.css's
 * [data-theme="operative-light"] block: --state-info is #1d4ed8 (blue) and
 * --state-success is #147a3a (green) on kita, so neither is used here —
 * only --bz-copper (#b5633a on kita) and neutral ink/paper tokens are.
 */

import React from "react";
import { ChevronDown, Clock, Info, Trophy, Users, X } from "lucide-react";
import { formatIDR } from "@balizero/core/utils";
import { cn } from "@/lib/utils";
import "../../portal/r19-fonts.css";
import { CARD, EYEBROW, FOCUS, HAIRLINE, SERIF, StatePill } from "./r19";
import { usePortalChallenge } from "./_lib/usePortalChallenge";
import type {
  PortalChallengeEntry,
  PortalChallengeResponse,
  PortalChallengeTier,
} from "@/lib/api/dashboard/dashboard.api";

/** Fraunces headline / Manrope body, scoped to this widget only. */
const R19_TYPE: React.CSSProperties = {
  fontFamily:
    '"Manrope", var(--font-sans), ui-sans-serif, system-ui, sans-serif',
};

/**
 * The hero band's ink panel. `--bz-text-1` is kita's darkest body-text token
 * (#172033) — reused here as a background rather than declaring a new dark
 * literal. `--bz-surface` (kita's card white) doubles as "paper" foreground.
 */
const INK_PANEL = "bg-[var(--bz-text-1)] text-[var(--bz-surface)]";
const INK_SECONDARY =
  "text-[color-mix(in_srgb,var(--bz-surface)_62%,transparent)]";

// ── Time helpers ────────────────────────────────────────────

const DAY_MS = 24 * 60 * 60 * 1000;

export function countdownParts(targetIso: string, nowMs: number) {
  const remaining = Math.max(0, new Date(targetIso).getTime() - nowMs);
  const days = Math.floor(remaining / DAY_MS);
  const hours = Math.floor((remaining % DAY_MS) / (60 * 60 * 1000));
  const minutes = Math.floor((remaining % (60 * 60 * 1000)) / (60 * 1000));
  return { remaining, days, hours, minutes };
}

export function relativeMinutes(iso: string, nowMs: number): string {
  const diffMs = Math.max(0, nowMs - new Date(iso).getTime());
  const minutes = Math.floor(diffMs / (60 * 1000));
  if (minutes < 1) return "baru saja";
  if (minutes < 60) return `${minutes} menit lalu`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} jam lalu`;
  const days = Math.floor(hours / 24);
  return `${days} hari lalu`;
}

/** Ticks once a minute — a countdown of days/hours/minutes needs no more. */
function useNow(intervalMs = 60_000): number {
  const [now, setNow] = React.useState(() => Date.now());
  React.useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return now;
}

// ── Countdown ───────────────────────────────────────────────

const TIER_LABEL: Record<number, string> = {
  1: "Juara 1",
  2: "Juara 2",
  3: "Juara 3",
};

/** One HARI / JAM / MENIT numeral block, tabular, on the dark hero band. */
function CountdownBlock({ value, label }: { value: number; label: string }) {
  return (
    <div className="flex flex-col items-center gap-0.5">
      <span
        className="font-black tabular-nums leading-none text-[clamp(26px,3.4vw,34px)]"
        style={SERIF}
      >
        {String(value).padStart(2, "0")}
      </span>
      <span className="text-[9px] font-semibold uppercase tracking-[0.16em] text-[var(--bz-copper)]">
        {label}
      </span>
    </div>
  );
}

function CountdownBlocks({
  data,
  now,
}: {
  data: PortalChallengeResponse;
  now: number;
}) {
  if (data.status === "closed") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--bz-copper)] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--bz-copper)]">
        Selesai
      </span>
    );
  }
  const target =
    data.status === "upcoming" ? data.window_start : data.window_end;
  const { days, hours, minutes } = countdownParts(target, now);
  const prefix = data.status === "upcoming" ? "Mulai dalam" : "Berakhir dalam";
  return (
    <div className="flex flex-col items-end gap-1.5">
      <span
        className={cn(
          "flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.1em]",
          INK_SECONDARY,
        )}
      >
        <Clock
          size={12}
          className="text-[var(--bz-copper)]"
          aria-hidden="true"
        />
        {prefix}
      </span>
      <div className="flex items-start gap-3">
        <CountdownBlock value={days} label="Hari" />
        <span className="text-[22px] font-black leading-none pt-0.5">:</span>
        <CountdownBlock value={hours} label="Jam" />
        <span className="text-[22px] font-black leading-none pt-0.5">:</span>
        <CountdownBlock value={minutes} label="Menit" />
      </div>
    </div>
  );
}

// ── Podium ──────────────────────────────────────────────────

/** Visual podium order on desktop: 2nd — 1st (elevated) — 3rd. */
function podiumOrderClass(tier: number): string {
  if (tier === 1) return "md:order-2";
  if (tier === 2) return "md:order-1";
  return "md:order-3";
}

export function PodiumCard({
  tier,
  threshold,
  prizeIdr,
  entries,
  isZeroState,
}: {
  tier: 1 | 2 | 3;
  threshold: number;
  prizeIdr: number;
  entries: PortalChallengeEntry[];
  isZeroState?: boolean;
}) {
  const elevated = tier === 1;
  const holder = entries.find((e) => e.award_tier === tier);
  const contender = entries
    .filter((e) => e.award_tier === null)
    .sort((a, b) => b.activations - a.activations)[0];
  const missing = holder
    ? 0
    : Math.max(0, threshold - (contender?.activations ?? 0));

  return (
    <div
      data-testid={`podium-tier-${tier}`}
      className={cn(
        CARD,
        "flex flex-col gap-2 p-4",
        podiumOrderClass(tier),
        elevated && "md:-translate-y-2 md:shadow-md md:pb-5",
      )}
    >
      <div className="flex items-center justify-between">
        <span className={EYEBROW}>{TIER_LABEL[tier] ?? `Tier ${tier}`}</span>
        <Trophy
          size={elevated ? 18 : 14}
          className="text-[var(--bz-copper)]"
          aria-hidden="true"
        />
      </div>
      <p
        className={cn(
          "font-black text-[var(--tx-pure)]",
          elevated
            ? "text-[clamp(26px,3.6vw,38px)]"
            : "text-[clamp(20px,2.6vw,26px)]",
        )}
        style={SERIF}
      >
        {formatIDR(prizeIdr)}
      </p>
      <p className="text-[10px] text-[var(--tx-secondary)]">
        minimal {threshold} aktivasi
      </p>
      <div className={cn(HAIRLINE, "rounded-md px-2.5 py-2 mt-1")}>
        {holder ? (
          <div className="flex items-center justify-between gap-2">
            <span className="text-[12px] font-semibold text-[var(--tx-pure)] truncate">
              {holder.display_name}
            </span>
            <span className="text-[11px] font-bold tabular-nums text-[var(--bz-copper-text)]">
              {holder.activations}
            </span>
          </div>
        ) : isZeroState ? (
          <span className="text-[11px] text-[var(--tx-secondary)]">
            Ayo jadi yang pertama!
          </span>
        ) : (
          <div className="flex items-center justify-between gap-2">
            <span className="text-[11px] text-[var(--tx-secondary)]">
              Belum ada
            </span>
            {missing > 0 && (
              <span className="text-[10px] font-semibold text-[var(--bz-copper-text)] whitespace-nowrap">
                butuh {missing} lagi
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Posisi saya ─────────────────────────────────────────────

/** Fixed 0..top-tier-threshold scale so all three tier ticks are visible. */
function PositionScale({
  activations,
  tiers,
}: {
  activations: number;
  tiers: PortalChallengeTier[];
}) {
  const scaleMax = Math.max(...tiers.map((t) => t.threshold));
  const pct = scaleMax > 0 ? Math.min(100, (activations / scaleMax) * 100) : 0;
  return (
    <div className="relative pt-1 pb-4">
      <div
        role="progressbar"
        aria-valuenow={Math.round(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
        className="relative h-2 w-full overflow-hidden rounded-full bg-[var(--bz-border)]"
      >
        <div
          className="h-full rounded-full bg-[var(--bz-copper)] transition-[width] duration-700 ease-out motion-reduce:transition-none"
          style={{ width: `${pct}%` }}
        />
      </div>
      {tiers.map((t) => {
        const left =
          scaleMax > 0 ? Math.min(100, (t.threshold / scaleMax) * 100) : 0;
        // The rightmost tick sits at exactly 100% — centering it would push
        // half the label past the card edge, so it right-aligns instead.
        const isEdge = left >= 100;
        return (
          <div
            key={t.tier}
            className={cn(
              "absolute top-1 flex flex-col",
              isEdge ? "items-end right-0" : "items-center -translate-x-1/2",
            )}
            style={isEdge ? undefined : { left: `${left}%` }}
          >
            <span
              aria-hidden="true"
              className="h-2 w-px bg-[var(--bz-base)]/60"
            />
            <span className="mt-1 whitespace-nowrap text-[8px] font-semibold uppercase tracking-[0.08em] text-[var(--tx-secondary)]">
              {TIER_LABEL[t.tier] ?? `T${t.tier}`}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function MyPositionCard({
  me,
  tiers,
  taxSuperBonusIdr,
}: {
  me: PortalChallengeEntry | undefined;
  tiers: PortalChallengeTier[];
  taxSuperBonusIdr: number;
}) {
  if (!me) {
    return (
      <div data-testid="my-position-card" className={cn(CARD, "p-4")}>
        <span className={EYEBROW}>Posisi Saya</span>
        <p className="mt-2 text-[12px] text-[var(--tx-secondary)]">
          Kamu belum tercatat sebagai peserta tantangan ini.
        </p>
      </div>
    );
  }
  const nextTier = tiers.find((t) => t.threshold === me.next_tier_threshold);
  const nextLine =
    me.next_tier_threshold != null && me.to_next_tier != null && nextTier
      ? `${me.to_next_tier} lagi untuk ${TIER_LABEL[nextTier.tier] ?? `Tier ${nextTier.tier}`} — ${formatIDR(nextTier.prize_idr)}`
      : me.award_tier === 1
        ? "Sudah di puncak — Juara 1!"
        : "Sudah mencapai tingkat maksimal saat ini";

  return (
    <div
      data-testid="my-position-card"
      className={cn(CARD, "p-4 flex flex-col gap-2")}
    >
      <div className="flex items-center justify-between">
        <span className={EYEBROW}>Posisi Saya</span>
        <StatePill
          tone="you"
          label={me.activations === 0 ? "Rank –" : `Rank #${me.rank}`}
        />
      </div>
      <div className="flex items-baseline gap-2">
        <span
          className="font-black tabular-nums leading-none text-[clamp(36px,5vw,52px)] text-[var(--tx-pure)]"
          style={SERIF}
        >
          {me.activations}
        </span>
        <span className="text-[11px] text-[var(--tx-secondary)]">aktivasi</span>
      </div>
      <PositionScale activations={me.activations} tiers={tiers} />
      <p className="text-[11px] font-semibold text-[var(--bz-copper-text)]">
        {nextLine}
      </p>
      {me.is_tax && (
        <p className="text-[10px] text-[var(--tx-secondary)]">
          Sebagai Tim Tax, naik podium juga mengaktifkan SUPER BONUS{" "}
          {formatIDR(taxSuperBonusIdr)}.
        </p>
      )}
      <div
        className={cn(
          HAIRLINE,
          "rounded-md px-3 py-2 mt-1 flex items-center justify-between",
        )}
      >
        <span className="text-[10px] text-[var(--tx-secondary)]">
          Hadiah sementara
        </span>
        <span className="text-[13px] font-bold text-[var(--bz-copper-text)]">
          {formatIDR(me.total_prize_idr)}
        </span>
      </div>
    </div>
  );
}

// ── Tim Tax strip ───────────────────────────────────────────

function TaxStrip({ data }: { data: PortalChallengeResponse }) {
  const taxEntries = [...data.entries.filter((e) => e.is_tax)].sort(
    (a, b) => b.activations - a.activations,
  );
  if (taxEntries.length === 0) return null;

  const podiumTax = taxEntries.find((e) => e.award_tier !== null);
  const bestTax = taxEntries[0];
  const fallbackEligible =
    !podiumTax &&
    bestTax &&
    bestTax.activations >= data.tax_rules.best_tax_fallback_threshold;

  return (
    <div
      data-testid="tax-strip"
      className={cn(CARD, "p-4 flex flex-col gap-2.5")}
    >
      <div className="flex items-center justify-between">
        <span className={EYEBROW}>Tim Tax</span>
        <Users
          size={14}
          className="text-[var(--bz-copper)]"
          aria-hidden="true"
        />
      </div>
      {podiumTax ? (
        <p className="text-[12px] text-[var(--tx-pure)]">
          <span className="font-semibold">{podiumTax.display_name}</span> naik
          podium — SUPER BONUS{" "}
          <span className="font-bold text-[var(--bz-copper-text)]">
            {formatIDR(data.tax_rules.podium_super_bonus_idr)}
          </span>{" "}
          berlaku
        </p>
      ) : fallbackEligible ? (
        <p className="text-[12px] text-[var(--tx-pure)]">
          <span className="font-semibold">{bestTax.display_name}</span> memimpin
          Tim Tax — bonus{" "}
          <span className="font-bold text-[var(--bz-copper-text)]">
            {formatIDR(data.tax_rules.best_tax_fallback_idr)}
          </span>
        </p>
      ) : (
        <p className="text-[12px] text-[var(--tx-secondary)]">
          Belum ada anggota Tim Tax yang mencapai{" "}
          {data.tax_rules.best_tax_fallback_threshold} aktivasi.
        </p>
      )}
      <ul className="flex flex-col divide-y divide-[var(--bz-border)]">
        {taxEntries.slice(0, 5).map((e) => (
          <li
            key={e.member}
            className="flex items-center justify-between gap-2 py-1.5"
          >
            <span className="text-[11px] font-medium text-[var(--tx-pure)] truncate">
              {e.display_name}
            </span>
            <span className="text-[12px] font-bold tabular-nums text-[var(--tx-pure)]">
              {e.activations}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ── Ranking list ────────────────────────────────────────────

function RankingRow({
  entry,
  isZeroState,
}: {
  entry: PortalChallengeEntry;
  isZeroState: boolean;
}) {
  return (
    <div
      className={cn(
        "grid items-center gap-2 px-3 py-2 rounded-lg",
        entry.is_me && "bg-[var(--bz-card-hover)]",
      )}
      style={{ gridTemplateColumns: "auto 1fr auto auto" }}
    >
      <span className="text-[11px] font-bold tabular-nums text-[var(--tx-secondary)] w-5">
        {isZeroState ? "–" : entry.rank}
      </span>
      <div className="min-w-0 flex items-center gap-1.5">
        <span className="text-[12px] font-semibold text-[var(--tx-pure)] truncate">
          {entry.display_name}
        </span>
        {entry.is_me && <StatePill tone="you" label="Kamu" />}
        {entry.is_tax && <StatePill tone="ink" label="Tax" />}
      </div>
      <span className="text-[11px] tabular-nums text-[var(--tx-secondary)] whitespace-nowrap">
        {entry.invited} diundang
      </span>
      <span className="text-[13px] font-bold tabular-nums text-[var(--tx-pure)] whitespace-nowrap">
        {entry.activations}
      </span>
    </div>
  );
}

function RankingList({
  entries,
  isZeroState,
}: {
  entries: PortalChallengeEntry[];
  isZeroState: boolean;
}) {
  const [expanded, setExpanded] = React.useState(false);
  const sorted = isZeroState
    ? [...entries].sort((a, b) => a.display_name.localeCompare(b.display_name))
    : [...entries].sort((a, b) => a.rank - b.rank);
  const visible = expanded ? sorted : sorted.slice(0, 5);

  return (
    <div className={cn(CARD, "flex flex-col")}>
      <div className={cn(HAIRLINE, "border-x-0 border-t-0 px-4 py-3")}>
        <span className={EYEBROW}>Papan Peringkat</span>
      </div>
      <div className="flex flex-col py-1">
        {visible.length === 0 ? (
          <p className="px-4 py-6 text-center text-[11px] text-[var(--tx-secondary)]">
            Belum ada aktivasi tercatat
          </p>
        ) : (
          visible.map((entry) => (
            <RankingRow
              key={entry.member}
              entry={entry}
              isZeroState={isZeroState}
            />
          ))
        )}
      </div>
      {sorted.length > 5 && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          className={cn(
            FOCUS,
            "flex items-center justify-center gap-1.5 border-t border-[var(--bz-border)] px-4 py-2.5 text-[11px] font-semibold text-[var(--tx-secondary)] hover:text-[var(--tx-pure)] transition-colors",
          )}
        >
          {expanded ? "Sembunyikan" : "Lihat semua"}
          <ChevronDown
            size={13}
            className={cn(
              "transition-transform motion-reduce:transition-none",
              expanded && "rotate-180",
            )}
          />
        </button>
      )}
    </div>
  );
}

// ── Live feed ───────────────────────────────────────────────

function LiveFeed({
  activations,
  now,
}: {
  activations: PortalChallengeResponse["recent_activations"];
  now: number;
}) {
  return (
    <div
      data-testid="live-feed"
      className={cn(CARD, "p-3 flex flex-col gap-1.5")}
    >
      <span className={cn(EYEBROW, "px-1")}>Aktivitas Terbaru</span>
      {activations.length === 0 ? (
        <p className="px-1 py-2 text-[11px] text-[var(--tx-secondary)]">
          Belum ada aktivitas — undangan pertama akan muncul di sini.
        </p>
      ) : (
        <ul className="flex flex-col">
          {activations.slice(0, 6).map((a, i) => {
            const diffMs = Math.max(0, now - new Date(a.at).getTime());
            const isRecent = diffMs < 60 * 60 * 1000;
            return (
              <li
                key={`${a.display_name}-${a.at}-${i}`}
                className="flex items-center gap-2 px-1 py-1 text-[11px]"
              >
                {isRecent && (
                  <span
                    aria-hidden="true"
                    className="h-1.5 w-1.5 flex-shrink-0 rounded-full bg-[var(--bz-copper)]"
                  />
                )}
                <span className="font-semibold text-[var(--tx-pure)] truncate flex-1">
                  {a.display_name}
                </span>
                <span className="text-[var(--tx-secondary)] whitespace-nowrap">
                  {relativeMinutes(a.at, now)}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

// ── Rules drawer ────────────────────────────────────────────

function RulesDrawer({ data }: { data: PortalChallengeResponse }) {
  const [open, setOpen] = React.useState(false);

  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-expanded={open}
        aria-haspopup="dialog"
        className={cn(
          FOCUS,
          "inline-flex items-center gap-1.5 rounded-full border border-[var(--bz-copper)]/50 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--bz-copper)] hover:border-[var(--bz-copper)] transition-colors",
        )}
      >
        <Info size={12} aria-hidden="true" />
        Aturan
      </button>
      {open && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <button
            type="button"
            aria-label="Tutup aturan"
            onClick={() => setOpen(false)}
            className="absolute inset-0 bg-black/40 motion-reduce:transition-none"
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Aturan tantangan Portal Champion"
            className={cn(
              CARD,
              "relative m-3 w-full max-w-sm overflow-y-auto p-5 shadow-xl",
            )}
          >
            <div className="flex items-center justify-between mb-3">
              <h3
                className="text-[15px] font-black text-[var(--tx-pure)]"
                style={SERIF}
              >
                Aturan Tantangan
              </h3>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Tutup"
                className={cn(
                  FOCUS,
                  "rounded p-1 text-[var(--tx-secondary)] hover:text-[var(--tx-pure)]",
                )}
              >
                <X size={16} />
              </button>
            </div>
            <ul className="flex flex-col gap-2.5 text-[12px] text-[var(--tx-secondary)] leading-relaxed">
              <li>
                Hanya klien yang{" "}
                <span className="text-[var(--tx-pure)] font-semibold">
                  mendaftar dan login dengan PIN
                </span>{" "}
                yang dihitung sebagai klien aktivasi.
              </li>
              {data.tiers.map((t) => (
                <li key={t.tier}>
                  <span className="text-[var(--tx-pure)] font-semibold">
                    {TIER_LABEL[t.tier] ?? `Tier ${t.tier}`}
                  </span>{" "}
                  ≥ {t.threshold} aktivasi → {formatIDR(t.prize_idr)}.
                </li>
              ))}
              <li>
                Peringkat menentukan tingkat hadiah: jika peraih peringkat 1
                belum mencapai ambang Juara 1, ia menerima hadiah tingkat di
                bawahnya sesuai ambang yang sudah tercapai.
              </li>
              <li>
                <span className="text-[var(--tx-pure)] font-semibold">
                  Tim Tax
                </span>
                : jika ada anggota Tim Tax naik podium, dapat hadiah podium +
                SUPER BONUS {formatIDR(data.tax_rules.podium_super_bonus_idr)}.
                Jika tidak, anggota Tim Tax terbaik dengan minimal{" "}
                {data.tax_rules.best_tax_fallback_threshold} aktivasi dapat{" "}
                {formatIDR(data.tax_rules.best_tax_fallback_idr)}.
              </li>
            </ul>
          </div>
        </div>
      )}
    </>
  );
}

// ── Skeleton / placeholder ──────────────────────────────────

function WidgetSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-2 xl:grid-cols-4" aria-hidden="true">
      {[0, 1, 2, 3].map((i) => (
        <div
          key={i}
          className="h-[140px] rounded-xl bg-[var(--bz-surface)] animate-pulse"
        />
      ))}
    </div>
  );
}

function QuietPlaceholder() {
  return (
    <div className={cn(CARD, "flex items-center gap-2.5 px-4 py-3")}>
      <Trophy
        size={14}
        className="text-[var(--tx-secondary)]"
        aria-hidden="true"
      />
      <p className="text-[11px] text-[var(--tx-secondary)]">
        Tantangan Portal Champion akan tampil di sini begitu datanya tersedia.
      </p>
    </div>
  );
}

// ── Main widget ─────────────────────────────────────────────

export function PortalChallengeWidget({ identity }: { identity: string }) {
  const { data, isLoading } = usePortalChallenge(identity);
  const now = useNow();

  if (!identity) return null;
  if (isLoading) return <WidgetSkeleton />;
  if (!data) return <QuietPlaceholder />;

  const me = data.entries.find((e) => e.is_me);
  const isZeroState = data.team_total_activations === 0;

  return (
    <section
      data-testid="portal-challenge-widget"
      className="flex flex-col gap-2.5"
      style={R19_TYPE}
    >
      {/* Hero band — dark ink panel so this dominates the dashboard. */}
      <div className={cn("rounded-lg p-6", INK_PANEL)}>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex flex-col gap-3">
            <div>
              <div
                aria-hidden="true"
                className="mb-3 h-[3px] w-14 rounded-sm bg-[var(--bz-copper)]"
              />
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--bz-copper)]">
                14–29 September 2026 · WITA
              </p>
              <h2
                className="mt-1 text-[clamp(26px,3.2vw,36px)] leading-[1.05] tracking-[-0.02em]"
                style={SERIF}
              >
                Portal Champion
              </h2>
            </div>
            <div>
              <span
                className="block font-black tabular-nums text-[clamp(52px,8vw,84px)]"
                style={{ ...SERIF, lineHeight: 0.9, marginBottom: "0.35em" }}
              >
                {data.team_total_activations}
              </span>
              <p className={cn("text-[12px]", INK_SECONDARY)}>
                {isZeroState
                  ? "Belum ada klien aktivasi — jadilah yang pertama!"
                  : "klien aktivasi terkumpul dari seluruh tim"}
              </p>
            </div>
          </div>
          <div className="flex flex-col items-end gap-2.5">
            <CountdownBlocks data={data} now={now} />
            <RulesDrawer data={data} />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
        {data.tiers.map((t) => (
          <PodiumCard
            key={t.tier}
            tier={t.tier}
            threshold={t.threshold}
            prizeIdr={t.prize_idr}
            entries={data.entries}
            isZeroState={isZeroState}
          />
        ))}
      </div>

      <div className="grid grid-cols-1 gap-2.5 xl:grid-cols-[1fr_1fr]">
        <MyPositionCard
          me={me}
          tiers={data.tiers}
          taxSuperBonusIdr={data.tax_rules.podium_super_bonus_idr}
        />
        <TaxStrip data={data} />
      </div>

      <div className="grid grid-cols-1 gap-2.5 xl:grid-cols-[1.4fr_1fr]">
        <RankingList entries={data.entries} isZeroState={isZeroState} />
        <LiveFeed activations={data.recent_activations} now={now} />
      </div>
    </section>
  );
}
