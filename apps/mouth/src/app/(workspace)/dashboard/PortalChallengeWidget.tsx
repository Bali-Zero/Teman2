"use client";

/**
 * "Portal Champion" live leaderboard — hero widget at the top of the kita
 * staff dashboard for the 14–29 Sept 2026 (WITA) client-activation challenge.
 *
 * R19 (concept-F) idiom, page-local (see ./r19.tsx). Backend contract:
 * GET /api/dashboard/portal-challenge, being built in parallel and NOT
 * deployed yet — usePortalChallenge swallows every failure into `null`, so
 * this widget renders a quiet placeholder instead of an error banner or a
 * crash until the endpoint ships.
 *
 * Only clients who register AND log in with a PIN count as "aktivasi" — the
 * rules drawer spells this out in Bahasa Indonesia for the team.
 */

import React from "react";
import { ChevronDown, Clock, Info, Trophy, Users, X } from "lucide-react";
import { formatIDR } from "@balizero/core/utils";
import { cn } from "@/lib/utils";
import "../../portal/r19-fonts.css";
import {
  CARD,
  EYEBROW,
  FOCUS,
  HAIRLINE,
  Masthead,
  ProgressBar,
  SERIF,
  StatePill,
} from "./r19";
import { usePortalChallenge } from "./_lib/usePortalChallenge";
import type {
  PortalChallengeEntry,
  PortalChallengeResponse,
} from "@/lib/api/dashboard/dashboard.api";

/** Fraunces headline / Manrope body, scoped to this widget only. */
const R19_TYPE: React.CSSProperties = {
  fontFamily:
    '"Manrope", var(--font-sans), ui-sans-serif, system-ui, sans-serif',
};

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

function CountdownStrip({
  data,
  now,
}: {
  data: PortalChallengeResponse;
  now: number;
}) {
  if (data.status === "closed") {
    return <StatePill tone="ok" label="Selesai" />;
  }
  const target =
    data.status === "upcoming" ? data.window_start : data.window_end;
  const { days, hours, minutes } = countdownParts(target, now);
  const prefix = data.status === "upcoming" ? "Mulai dalam" : "Berakhir dalam";
  return (
    <div className="flex items-center gap-2.5">
      <Clock size={14} className="text-[var(--bz-copper)]" aria-hidden="true" />
      <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--tx-secondary)]">
        {prefix}
      </span>
      <span
        className="font-black tabular-nums text-[18px] leading-none text-[var(--tx-pure)]"
        style={SERIF}
      >
        {days}
        <span className="text-[11px] font-semibold ml-0.5 mr-1.5">h</span>
        {String(hours).padStart(2, "0")}
        <span className="text-[11px] font-semibold ml-0.5 mr-1.5">j</span>
        {String(minutes).padStart(2, "0")}
        <span className="text-[11px] font-semibold ml-0.5">m</span>
      </span>
    </div>
  );
}

// ── Podium ──────────────────────────────────────────────────

const TIER_LABEL: Record<number, string> = {
  1: "Juara 1",
  2: "Juara 2",
  3: "Juara 3",
};

export function PodiumCard({
  tier,
  threshold,
  prizeIdr,
  entries,
}: {
  tier: 1 | 2 | 3;
  threshold: number;
  prizeIdr: number;
  entries: PortalChallengeEntry[];
}) {
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
      className={cn(CARD, "flex flex-col gap-2 p-4")}
    >
      <div className="flex items-center justify-between">
        <span className={EYEBROW}>{TIER_LABEL[tier] ?? `Tier ${tier}`}</span>
        <Trophy
          size={14}
          className="text-[var(--bz-copper)]"
          aria-hidden="true"
        />
      </div>
      <p className="text-[15px] font-black text-[var(--tx-pure)]" style={SERIF}>
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
        ) : (
          <div className="flex items-center justify-between gap-2">
            <span className="text-[11px] text-[var(--tx-secondary)]">
              belum ada
            </span>
            {missing > 0 && (
              <span className="text-[10px] font-semibold text-[var(--bz-copper-text)] whitespace-nowrap">
                kurang {missing}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Posisi saya ─────────────────────────────────────────────

function MyPositionCard({ me }: { me: PortalChallengeEntry | undefined }) {
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
  const nextThreshold = me.next_tier_threshold;
  const toNext = me.to_next_tier;
  return (
    <div
      data-testid="my-position-card"
      className={cn(CARD, "p-4 flex flex-col gap-2.5")}
    >
      <div className="flex items-center justify-between">
        <span className={EYEBROW}>Posisi Saya</span>
        <StatePill tone="you" label={`Rank #${me.rank}`} />
      </div>
      <div className="flex items-baseline gap-2">
        <span
          className="text-[26px] font-black tabular-nums leading-none text-[var(--tx-pure)]"
          style={SERIF}
        >
          {me.activations}
        </span>
        <span className="text-[11px] text-[var(--tx-secondary)]">aktivasi</span>
      </div>
      {nextThreshold != null && toNext != null && toNext > 0 ? (
        <div className="flex flex-col gap-1">
          <ProgressBar value={me.activations} max={nextThreshold} />
          <p className="text-[10px] text-[var(--tx-secondary)]">
            {toNext} lagi menuju {nextThreshold} aktivasi
          </p>
        </div>
      ) : (
        <p className="text-[10px] text-[var(--state-success)]">
          Sudah mencapai tingkat tertinggi
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
  const taxEntries = data.entries.filter((e) => e.is_tax);
  if (taxEntries.length === 0) return null;

  const podiumTax = taxEntries.find((e) => e.award_tier !== null);
  const bestTax = [...taxEntries].sort(
    (a, b) => b.activations - a.activations,
  )[0];
  const fallbackEligible =
    !podiumTax &&
    bestTax &&
    bestTax.activations >= data.tax_rules.best_tax_fallback_threshold;

  return (
    <div
      data-testid="tax-strip"
      className={cn(CARD, "p-4 flex flex-col gap-2")}
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
          Tim Tax ({bestTax.activations} aktivasi) — bonus{" "}
          <span className="font-bold text-[var(--bz-copper-text)]">
            {formatIDR(data.tax_rules.best_tax_fallback_idr)}
          </span>
        </p>
      ) : (
        <p className="text-[12px] text-[var(--tx-secondary)]">
          Belum ada anggota Tim Tax yang mencapai{" "}
          {data.tax_rules.best_tax_fallback_threshold} aktivasi
          {bestTax
            ? ` (tertinggi: ${bestTax.display_name}, ${bestTax.activations})`
            : ""}
          .
        </p>
      )}
    </div>
  );
}

// ── Ranking list ────────────────────────────────────────────

function RankingRow({ entry }: { entry: PortalChallengeEntry }) {
  return (
    <div
      className={cn(
        "grid items-center gap-2 px-3 py-2 rounded-lg",
        entry.is_me && "bg-[var(--bz-card-hover)]",
      )}
      style={{ gridTemplateColumns: "auto 1fr auto auto" }}
    >
      <span className="text-[11px] font-bold tabular-nums text-[var(--tx-secondary)] w-5">
        {entry.rank}
      </span>
      <div className="min-w-0 flex items-center gap-1.5">
        <span className="text-[12px] font-semibold text-[var(--tx-pure)] truncate">
          {entry.display_name}
        </span>
        {entry.is_me && <StatePill tone="you" label="Kamu" />}
        {entry.is_tax && <StatePill tone="ours" label="Tax" />}
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

function RankingList({ entries }: { entries: PortalChallengeEntry[] }) {
  const [expanded, setExpanded] = React.useState(false);
  const sorted = [...entries].sort((a, b) => a.rank - b.rank);
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
            <RankingRow key={entry.member} entry={entry} />
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
  if (activations.length === 0) return null;
  return (
    <div className={cn(CARD, "p-3 flex flex-col gap-1.5")}>
      <span className={cn(EYEBROW, "px-1")}>Aktivitas Terbaru</span>
      <ul className="flex flex-col">
        {activations.slice(0, 6).map((a, i) => (
          <li
            key={`${a.display_name}-${a.at}-${i}`}
            className="flex items-center justify-between gap-2 px-1 py-1 text-[11px]"
          >
            <span className="font-semibold text-[var(--tx-pure)] truncate">
              {a.display_name}
            </span>
            <span className="text-[var(--tx-secondary)] whitespace-nowrap">
              {relativeMinutes(a.at, now)}
            </span>
          </li>
        ))}
      </ul>
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
          "inline-flex items-center gap-1.5 rounded-full border border-[var(--bz-border)] px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--tx-secondary)] hover:text-[var(--tx-pure)] hover:border-[var(--bz-border-hover)] transition-colors",
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

  return (
    <section
      data-testid="portal-challenge-widget"
      className={cn(CARD, "p-5 flex flex-col gap-4")}
      style={R19_TYPE}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <Masthead
          eyebrow="14–29 September 2026 · WITA"
          title="Portal Champion"
          subtitle={`${data.team_total_activations} klien aktivasi terkumpul dari seluruh tim`}
        />
        <div className="flex flex-col items-end gap-2">
          <CountdownStrip data={data} now={now} />
          <RulesDrawer data={data} />
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
          />
        ))}
      </div>

      <div className="grid grid-cols-1 gap-2.5 xl:grid-cols-[1fr_1fr]">
        <MyPositionCard me={me} />
        <TaxStrip data={data} />
      </div>

      <div className="grid grid-cols-1 gap-2.5 xl:grid-cols-[1.4fr_1fr]">
        <RankingList entries={data.entries} />
        <LiveFeed activations={data.recent_activations} now={now} />
      </div>
    </section>
  );
}
