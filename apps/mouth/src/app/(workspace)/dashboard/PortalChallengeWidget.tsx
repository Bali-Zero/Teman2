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
 * Every tone in this file was checked against globals.css's kita
 * daylight theme block (see r19.tsx for the exact selector and values):
 * --state-info resolves to a BLUE and --state-success to a GREEN there, so
 * neither is used on this widget — only --bz-copper and neutral ink/paper
 * tokens are.
 */

import React from "react";
import { ChevronDown, Clock, Info, Trophy, Users, X } from "lucide-react";
import { formatIDR } from "@balizero/core/utils";
import { cn } from "@/lib/utils";
import "../../portal/r19-fonts.css";
import { CARD, EYEBROW, FOCUS, HAIRLINE, SERIF, StatePill } from "./r19";
import { usePortalChallenge } from "./_lib/usePortalChallenge";
import { ChampionArena, formatWindowRange, isRanked } from "./ChampionArena";
import { ChampionPortrait } from "@/components/workspace/ChampionPortrait";
import type {
  PortalChallengeAsyaMission,
  PortalChallengeEntry,
  PortalChallengeRankPrize,
  PortalChallengeResponse,
  PortalChallengeSeptemberSummary,
  PortalChallengeTier,
} from "@/lib/api/dashboard/dashboard.api";

/** Fraunces headline / Manrope body, scoped to this widget only. */
const R19_TYPE: React.CSSProperties = {
  fontFamily:
    '"Manrope", var(--font-sans), ui-sans-serif, system-ui, sans-serif',
};

/**
 * Secondary text on the hero's ink panel (ChampionArena paints it with
 * `--bz-text-1`, kita's darkest body-text token, reused as a background;
 * `--bz-surface` doubles as the "paper" foreground).
 */
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
      <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--bz-kita-ink-panel-copper)]">
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
      <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--bz-kita-ink-panel-copper)] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--bz-kita-ink-panel-copper)]">
        Selesai
      </span>
    );
  }
  const target =
    data.status === "upcoming" ? data.window_start : data.window_end;
  const { days, hours, minutes } = countdownParts(target, now);
  const prefix = data.status === "upcoming" ? "Mulai dalam" : "Berakhir dalam";
  return (
    <div className="flex flex-col items-start gap-1.5 sm:items-end">
      <span
        className={cn(
          "flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.1em]",
          INK_SECONDARY,
        )}
      >
        <Clock
          size={12}
          className="text-[var(--bz-kita-ink-panel-copper)]"
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
        // @container + min-w-0: the prize numeral sizes to THIS card, not
        // the viewport — a vw clamp rendered 169px inside a 124px card.
        "@container min-w-0 flex flex-col gap-2 p-4",
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
          "font-black tabular-nums whitespace-nowrap text-[var(--tx-pure)]",
          elevated
            ? "text-[clamp(20px,9cqi,34px)]"
            : "text-[clamp(18px,8cqi,26px)]",
        )}
        style={SERIF}
      >
        {formatIDR(prizeIdr)}
      </p>
      <p className="text-[11px] text-[var(--tx-secondary)]">
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
              <span className="text-[11px] font-semibold text-[var(--bz-copper-text)] whitespace-nowrap">
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
  const scaleMax =
    tiers.length > 0 ? Math.max(...tiers.map((t) => t.threshold)) : 0;
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
            <span className="mt-1 whitespace-nowrap text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--tx-secondary)]">
              {TIER_LABEL[t.tier] ?? `T${t.tier}`}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/** One breakdown chip: a signed contribution and the rule that earned it. */
function BreakdownChip({ label, value }: { label: string; value: number }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-[var(--bz-card-hover)] px-2.5 py-1 text-[11px] font-semibold tabular-nums text-[var(--tx-pure)]">
      <span className="text-[var(--bz-copper-text)]">
        {value > 0 ? `+${value}` : value}
      </span>
      {label}
    </span>
  );
}

function MyPositionCard({
  me,
  tiers,
  taxSuperBonusIdr,
  round2,
}: {
  me: PortalChallengeEntry | undefined;
  tiers: PortalChallengeTier[];
  taxSuperBonusIdr: number;
  round2: boolean;
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

  if (round2) {
    const ranked = isRanked(me, true);
    const points = me.points ?? 0;
    return (
      <div
        data-testid="my-position-card"
        className={cn(CARD, "p-4 flex flex-col gap-2")}
      >
        <div className="flex items-center justify-between">
          <span className={EYEBROW}>Posisi Saya</span>
          <StatePill
            tone="you"
            label={ranked ? `Rank #${me.rank}` : "Rank –"}
          />
        </div>
        <div className="flex items-baseline gap-2">
          <span
            className="font-black tabular-nums leading-none text-[clamp(36px,5vw,52px)] text-[var(--tx-pure)]"
            style={SERIF}
          >
            {points}
          </span>
          <span className="text-[11px] text-[var(--tx-secondary)]">poin</span>
        </div>
        {me.september_choice === "prize" && (
          <p className="text-[11px] font-semibold text-[var(--bz-copper-text)]">
            Mulai dari 0 — hadiah September diambil
          </p>
        )}
        <div className="flex flex-wrap gap-1.5">
          <BreakdownChip
            label="Bawa dari September"
            value={me.carry_points ?? 0}
          />
          <BreakdownChip label="registrasi" value={me.registrations ?? 0} />
          <BreakdownChip
            label="dokumen pertama"
            value={3 * (me.document_bonuses ?? 0)}
          />
          <BreakdownChip
            label="permintaan tak terjawab"
            value={-2 * (me.unanswered_requests ?? 0)}
          />
          <BreakdownChip
            label="dokumen belum ditinjau"
            value={-1 * (me.unreviewed_documents ?? 0)}
          />
        </div>
        <div
          className={cn(
            HAIRLINE,
            "rounded-md px-3 py-2 mt-1 flex items-center justify-between",
          )}
        >
          <span className="text-[11px] text-[var(--tx-secondary)]">
            Hadiah sementara
          </span>
          <span className="text-[13px] font-bold text-[var(--bz-copper-text)]">
            {formatIDR(me.total_prize_idr)}
          </span>
        </div>
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
        <p className="text-[11px] text-[var(--tx-secondary)]">
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
        <span className="text-[11px] text-[var(--tx-secondary)]">
          Hadiah sementara
        </span>
        <span className="text-[13px] font-bold text-[var(--bz-copper-text)]">
          {formatIDR(me.total_prize_idr)}
        </span>
      </div>
    </div>
  );
}

// ── Rank prize list (round 2) ───────────────────────────────

const RANK_ORDINAL: Record<number, string> = {
  1: "Pertama",
  2: "Kedua",
  3: "Ketiga",
  4: "Keempat",
  5: "Kelima",
};

function RankPrizeRow({
  rank,
  prizeIdr,
  holders,
}: {
  rank: number;
  prizeIdr: number;
  holders: PortalChallengeEntry[];
}) {
  return (
    <div
      data-testid={`rank-prize-${rank}`}
      className={cn(
        HAIRLINE,
        "flex items-center justify-between gap-3 rounded-lg px-3 py-2.5",
      )}
    >
      <div className="flex min-w-0 items-center gap-2.5">
        <span className="flex size-7 flex-shrink-0 items-center justify-center rounded-full bg-[var(--bz-card-hover)] text-[11px] font-black tabular-nums text-[var(--bz-copper-text)]">
          {rank}
        </span>
        <div className="min-w-0">
          <p className="text-[11px] font-bold uppercase tracking-[0.1em] text-[var(--tx-secondary)]">
            {RANK_ORDINAL[rank] ?? `Peringkat ${rank}`}
          </p>
          <p className="truncate text-[12px] font-semibold text-[var(--tx-pure)]">
            {holders.length > 0
              ? holders.map((h) => h.display_name).join(", ")
              : "Belum ada"}
          </p>
        </div>
      </div>
      <div className="flex-shrink-0 text-right">
        <p
          className="text-[13px] font-black tabular-nums text-[var(--tx-pure)]"
          style={SERIF}
        >
          {formatIDR(prizeIdr)}
        </p>
        {holders.length > 0 && (
          <p className="text-[11px] tabular-nums text-[var(--tx-secondary)]">
            {holders[0].points ?? 0} poin
          </p>
        )}
      </div>
    </div>
  );
}

function RankPrizeList({
  rankPrizes,
  entries,
}: {
  rankPrizes: PortalChallengeRankPrize[];
  entries: PortalChallengeEntry[];
}) {
  if (rankPrizes.length === 0) return null;
  return (
    <div data-testid="rank-prize-list" className="flex flex-col gap-2">
      <span className={EYEBROW}>Peringkat & Hadiah</span>
      {rankPrizes.map((rp) => (
        <RankPrizeRow
          key={rp.rank}
          rank={rp.rank}
          prizeIdr={rp.prize_idr}
          // A 0-point (or negative) entry never wins a rank prize — the
          // backend already ships prize_idr: 0 for it; this list must not
          // show it as the holder just because it shares the rank number.
          holders={entries.filter(
            (e) => e.rank === rp.rank && (e.points ?? 0) > 0,
          )}
        />
      ))}
    </div>
  );
}

// ── Misi Asya (round 2) ─────────────────────────────────────

function AsyaMissionCard({ mission }: { mission: PortalChallengeAsyaMission }) {
  const pct =
    mission.target_points > 0
      ? Math.min(
          100,
          Math.max(0, (mission.points / mission.target_points) * 100),
        )
      : 0;
  return (
    <div
      data-testid="asya-mission-card"
      className={cn(CARD, "p-4 flex flex-col gap-2.5")}
    >
      <div className="flex items-center justify-between">
        <span className={EYEBROW}>Misi Asya</span>
        <StatePill
          tone={mission.reached ? "ok" : "wait"}
          label={
            mission.reached
              ? "Tercapai"
              : `${mission.points}/${mission.target_points}`
          }
        />
      </div>
      <div className="flex items-center gap-2.5">
        <ChampionPortrait
          face
          name={mission.display_name}
          src={mission.avatar_url}
          sizes="80px"
          className="size-10"
        />
        <div className="min-w-0">
          <p className="truncate text-[13px] font-bold text-[var(--tx-pure)]">
            {mission.display_name}
          </p>
          <p className="text-[11px] text-[var(--tx-secondary)]">
            Target {mission.target_points} poin — hadiah{" "}
            {formatIDR(mission.prize_idr)}
          </p>
        </div>
      </div>
      <div
        role="progressbar"
        aria-label={`Progres misi ${mission.display_name}`}
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
      <div className="flex flex-wrap gap-1.5">
        <BreakdownChip
          label="bonus misi"
          value={mission.bonus_points * mission.mission_bonuses}
        />
        <BreakdownChip label="penalti" value={-mission.penalty_points} />
      </div>
    </div>
  );
}

// ── Hasil September (frozen round 1, shown inside round 2) ──

const SEPTEMBER_CHOICE_LABEL: Record<string, string> = {
  prize: "Ambil hadiah",
  carry: "Bawa poin ke Oktober",
};

function SeptemberSection({
  september,
}: {
  september: PortalChallengeSeptemberSummary;
}) {
  const sorted = [...september.entries].sort((a, b) => a.rank - b.rank);
  return (
    <div data-testid="september-results" className="mt-4 flex flex-col gap-2">
      <p className="text-[11px] text-[var(--tx-secondary)]">
        {formatWindowRange(september.window_start, september.window_end)} · WITA
        · {september.team_total_activations} klien aktivasi
      </p>
      <ul className="flex flex-col divide-y divide-[var(--bz-border)]">
        {sorted.map((e) => (
          <li
            key={e.member}
            className="flex items-center justify-between gap-2 py-1.5"
          >
            <div className="flex min-w-0 items-center gap-1.5">
              <ChampionPortrait
                face
                name={e.display_name}
                src={e.avatar_url}
                sizes="72px"
                className="size-7"
              />
              <span className="truncate text-[12px] font-semibold text-[var(--tx-pure)]">
                #{e.rank} {e.display_name}
              </span>
              {e.september_choice && (
                <StatePill
                  tone={e.september_choice === "prize" ? "ok" : "wait"}
                  label={SEPTEMBER_CHOICE_LABEL[e.september_choice]}
                />
              )}
            </div>
            <span className="text-[12px] font-bold tabular-nums text-[var(--tx-pure)] whitespace-nowrap">
              {formatIDR(e.total_prize_idr)}
            </span>
          </li>
        ))}
      </ul>
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
  round2,
}: {
  entry: PortalChallengeEntry;
  isZeroState: boolean;
  round2: boolean;
}) {
  const ranked = round2 ? isRanked(entry, true) : !isZeroState;
  return (
    <div
      className={cn(
        "grid items-center gap-2 px-3 py-2 rounded-lg",
        entry.is_me && "bg-[var(--bz-card-hover)]",
      )}
      style={{ gridTemplateColumns: "auto 1fr auto auto" }}
    >
      <span className="text-[11px] font-bold tabular-nums text-[var(--tx-secondary)] w-5">
        {ranked ? entry.rank : "–"}
      </span>
      <div className="min-w-0 flex items-center gap-1.5">
        <ChampionPortrait
          face
          name={entry.display_name}
          src={entry.avatar_url}
          sizes="96px"
          className="size-9"
        />
        <span className="text-[12px] font-semibold text-[var(--tx-pure)] truncate">
          {entry.display_name}
        </span>
        {entry.is_me && <StatePill tone="you" label="Kamu" />}
        {entry.is_tax && <StatePill tone="ink" label="Tax" />}
      </div>
      <span className="text-[11px] tabular-nums text-[var(--tx-secondary)] whitespace-nowrap">
        {round2
          ? `+${entry.registrations ?? 0} reg · +${3 * (entry.document_bonuses ?? 0)} dok · −${entry.penalty_points ?? 0}`
          : `${entry.invited} diundang`}
      </span>
      <span className="text-[13px] font-bold tabular-nums text-[var(--tx-pure)] whitespace-nowrap">
        {round2 ? (entry.points ?? 0) : entry.activations}
      </span>
    </div>
  );
}

function RankingList({
  entries,
  isZeroState,
  round2,
}: {
  entries: PortalChallengeEntry[];
  isZeroState: boolean;
  round2: boolean;
}) {
  const [expanded, setExpanded] = React.useState(false);
  const sorted = isZeroState
    ? [...entries].sort((a, b) => a.display_name.localeCompare(b.display_name))
    : [...entries].sort((a, b) => a.rank - b.rank);
  const visible = expanded ? sorted : sorted.slice(0, 5);

  return (
    <div data-testid="champion-ranking" className={cn(CARD, "flex flex-col")}>
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
              round2={round2}
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

const EVENT_LABEL: Record<string, string> = {
  registration: "Registrasi selesai",
  first_document: "Dokumen pertama",
  unanswered_request: "Permintaan tak terjawab",
  unreviewed_document: "Dokumen belum ditinjau",
  asya_bonus: "Bonus misi Asya",
};

function LiveFeed({
  activations,
  events,
  now,
}: {
  activations: PortalChallengeResponse["recent_activations"];
  events?: PortalChallengeResponse["recent_events"];
  now: number;
}) {
  if (events) {
    return (
      <div
        data-testid="live-feed"
        className={cn(CARD, "p-3 flex flex-col gap-1.5")}
      >
        <span className={cn(EYEBROW, "px-1")}>Aktivitas Terbaru</span>
        {events.length === 0 ? (
          <p className="px-1 py-2 text-[11px] text-[var(--tx-secondary)]">
            Belum ada aktivitas — kejadian pertama akan muncul di sini.
          </p>
        ) : (
          <ul className="flex flex-col">
            {events.slice(0, 10).map((e, i) => {
              const diffMs = Math.max(0, now - new Date(e.at).getTime());
              const isRecent = diffMs < 60 * 60 * 1000;
              return (
                <li
                  key={`${e.display_name}-${e.at}-${i}`}
                  className="flex items-center gap-2 px-1 py-1 text-[11px]"
                >
                  {isRecent && (
                    <span
                      aria-hidden="true"
                      className="h-1.5 w-1.5 flex-shrink-0 rounded-full bg-[var(--bz-copper)]"
                    />
                  )}
                  <span className="font-semibold text-[var(--tx-pure)] truncate">
                    {e.display_name}
                  </span>
                  <span className="flex-1 truncate text-[var(--tx-secondary)]">
                    {EVENT_LABEL[e.kind] ?? e.kind}
                  </span>
                  <span className="font-bold tabular-nums text-[var(--bz-copper-text)] whitespace-nowrap">
                    {e.points > 0 ? `+${e.points}` : e.points}
                  </span>
                  <span className="text-[var(--tx-secondary)] whitespace-nowrap">
                    {relativeMinutes(e.at, now)}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    );
  }
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
  const round2 = data.round === 2;
  const scoring = data.scoring;
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
          "inline-flex items-center gap-1.5 rounded-full border border-[var(--bz-kita-ink-panel-copper)] px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--bz-kita-ink-panel-copper)] hover:bg-[var(--bz-kita-ink-panel-copper)]/10 transition-colors",
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
              {round2 ? (
                <>
                  <li>
                    +{scoring?.registration ?? 1} poin untuk setiap{" "}
                    <span className="text-[var(--tx-pure)] font-semibold">
                      registrasi selesai
                    </span>
                    .
                  </li>
                  <li>
                    +{scoring?.first_document ?? 3} poin untuk{" "}
                    <span className="text-[var(--tx-pure)] font-semibold">
                      dokumen pertama
                    </span>{" "}
                    per proses nyata (sekali per proses, bukan per berkas).
                  </li>
                  <li>
                    {scoring?.unanswered_request ?? -2} poin jika{" "}
                    <span className="text-[var(--tx-pure)] font-semibold">
                      permintaan klien tak terjawab
                    </span>{" "}
                    lebih dari {scoring?.response_working_hours ?? 3} jam kerja.
                  </li>
                  <li>
                    {scoring?.unreviewed_document ?? -1} poin jika{" "}
                    <span className="text-[var(--tx-pure)] font-semibold">
                      dokumen belum ditinjau
                    </span>{" "}
                    lebih dari 1 hari kerja (
                    {scoring?.review_working_hours ?? 9.5} jam kerja).
                  </li>
                  <li>
                    Satu kejadian yang sama hanya kena{" "}
                    <span className="text-[var(--tx-pure)] font-semibold">
                      penalti terbesar
                    </span>{" "}
                    saja.
                  </li>
                  <li>
                    Jam layanan:{" "}
                    <span className="text-[var(--tx-pure)] font-semibold">
                      {scoring?.service_hours ?? "Senin–Jumat 09.00–18.30 WITA"}
                    </span>
                    .
                  </li>
                  <li>
                    Tidak menambah poin: duplikat, unggahan ulang, login, pesan,
                    checklist.
                  </li>
                  <li>
                    Hadiah mengikuti{" "}
                    <span className="text-[var(--tx-pure)] font-semibold">
                      peringkat akhir
                    </span>{" "}
                    (5 posisi).
                  </li>
                  <li>Tidak ada bonus Tax baru di ronde ini.</li>
                  <li>
                    «Lascia o raddoppia» adalah{" "}
                    <span className="text-[var(--tx-pure)] font-semibold">
                      nama kampanye
                    </span>
                    , bukan janji hadiah dua kali lipat.
                  </li>
                </>
              ) : (
                <>
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
                    : jika ada anggota Tim Tax naik podium, dapat hadiah podium
                    + SUPER BONUS{" "}
                    {formatIDR(data.tax_rules.podium_super_bonus_idr)}. Jika
                    tidak, anggota Tim Tax terbaik dengan minimal{" "}
                    {data.tax_rules.best_tax_fallback_threshold} aktivasi dapat{" "}
                    {formatIDR(data.tax_rules.best_tax_fallback_idr)}.
                  </li>
                </>
              )}
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

  const round2 = data.round === 2;
  const me = data.entries.find((e) => e.is_me);
  // A round-2 team total of 0 does NOT mean "no ranking yet" — positives and
  // penalties can cancel to 0 while ranks still differ (carry points, tie
  // order). The alphabetical zero-state fallback (RankingList) only applies
  // when every entry genuinely has no R2 event at all.
  const isZeroState = round2
    ? data.entries.every((e) => (e.points ?? 0) === 0 && !e.last_event_at)
    : data.team_total_activations === 0;

  return (
    <section
      data-testid="portal-challenge-widget"
      className="flex flex-col gap-2.5"
      style={R19_TYPE}
    >
      {/* Hero — one ink panel so this dominates the dashboard. */}
      <ChampionArena
        data={data}
        countdown={<CountdownBlocks data={data} now={now} />}
      />

      <div className="grid grid-cols-1 gap-2.5 xl:grid-cols-[1.4fr_1fr]">
        <RankingList
          entries={data.entries}
          isZeroState={isZeroState}
          round2={round2}
        />
        <LiveFeed
          activations={data.recent_activations}
          events={round2 ? (data.recent_events ?? []) : undefined}
          now={now}
        />
      </div>

      {round2 && data.asya_mission && (
        <AsyaMissionCard mission={data.asya_mission} />
      )}

      <details className={cn(CARD, "p-4")}>
        <summary
          className={cn(
            FOCUS,
            "cursor-pointer text-sm font-semibold text-[var(--tx-pure)]",
          )}
        >
          Hadiah, posisi saya & aturan
        </summary>
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-lg bg-[var(--bz-text-1)] p-4 text-[var(--bz-surface)]">
          <span className="text-xs">
            {round2
              ? `${formatWindowRange(data.window_start, data.window_end)} · WITA`
              : "14–29 September 2026 · WITA"}
          </span>
          <RulesDrawer data={data} />
        </div>
        {round2 ? (
          <div className="mt-5">
            <RankPrizeList
              rankPrizes={data.rank_prizes ?? []}
              entries={data.entries}
            />
          </div>
        ) : (
          <div className="mt-5 grid grid-cols-1 gap-2.5 sm:grid-cols-3">
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
        )}

        <div
          className={cn(
            "mt-3 grid grid-cols-1 gap-2.5",
            !round2 && "xl:grid-cols-[1fr_1fr]",
          )}
        >
          <MyPositionCard
            me={me}
            tiers={data.tiers}
            taxSuperBonusIdr={data.tax_rules.podium_super_bonus_idr}
            round2={round2}
          />
          {!round2 && <TaxStrip data={data} />}
        </div>
      </details>

      {round2 && data.september && (
        <details data-testid="september-details" className={cn(CARD, "p-4")}>
          <summary
            className={cn(
              FOCUS,
              "cursor-pointer text-sm font-semibold text-[var(--tx-pure)]",
            )}
          >
            Hasil September
          </summary>
          <SeptemberSection september={data.september} />
        </details>
      )}
    </section>
  );
}
