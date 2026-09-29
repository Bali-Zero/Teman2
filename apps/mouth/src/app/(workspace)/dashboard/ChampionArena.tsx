"use client";

import { useId, useState, type ReactNode } from "react";
import Link from "next/link";
import { motion, useReducedMotion } from "framer-motion";
import { ArrowUpRight, ChevronDown, Crown, Crosshair } from "lucide-react";
import { ChampionPortrait } from "@/components/workspace/ChampionPortrait";
import type {
  PortalChallengeEntry,
  PortalChallengeResponse,
} from "@/lib/api/dashboard/dashboard.api";
import { cn } from "@/lib/utils";
import { FOCUS, SERIF } from "./r19";

const HAIRLINE_ON_INK =
  "border-[color-mix(in_srgb,var(--bz-surface)_15%,transparent)]";

const DAY_MS = 24 * 60 * 60 * 1000;

/** The score this widget races on: R2 races on `points`, R1 on `activations`. */
export function scoreOf(entry: PortalChallengeEntry, round2: boolean): number {
  return round2 ? (entry.points ?? 0) : entry.activations;
}

/**
 * A 0-activation entry has no honest rank in R1 — the ranking shows "–" too.
 * R2 generalises the rule: a 0-point entry with at least one R2 event (e.g.
 * +3 then -3) still ranks, since it competed; only a truly untouched member
 * shows "–".
 */
export function isRanked(
  entry: PortalChallengeEntry,
  round2: boolean,
): boolean {
  return round2
    ? scoreOf(entry, round2) !== 0 || Boolean(entry.last_event_at)
    : entry.activations > 0;
}

function rankLabel(entry: PortalChallengeEntry, round2: boolean): string {
  return isRanked(entry, round2) ? `#${entry.rank}` : "–";
}

/**
 * Round 2's date range, e.g. "30 Sep – 29 Okt 2026". `window_end` is
 * EXCLUSIVE (the contract's midnight-open convention), so the displayed end
 * date is one day before it.
 */
export function formatWindowRange(startIso: string, endIso: string): string {
  const start = new Date(startIso);
  const end = new Date(new Date(endIso).getTime() - DAY_MS);
  const day = new Intl.DateTimeFormat("id-ID", {
    day: "numeric",
    month: "short",
    timeZone: "Asia/Makassar",
  });
  const dayYear = new Intl.DateTimeFormat("id-ID", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "Asia/Makassar",
  });
  return `${day.format(start)} – ${dayYear.format(end)}`;
}

/**
 * The Portal Champion hero: title, team total, countdown, podium and the
 * selected contender's next target in ONE ink panel. The countdown is
 * rendered by the widget, which owns the ticking clock.
 */
export function ChampionArena({
  data,
  countdown,
}: {
  data: PortalChallengeResponse;
  countdown: ReactNode;
}) {
  const [selected, setSelected] = useState<string | null>(null);
  const pickerId = useId();
  const reduceMotion = useReducedMotion();
  const round2 = data.round === 2;
  const entries = [...data.entries].sort(
    (first, second) => first.rank - second.rank,
  );
  const contender =
    entries.find((entry) => entry.member === selected) ??
    entries.find((entry) => entry.is_me) ??
    entries[0];
  const rival =
    contender &&
    [...entries]
      .reverse()
      .find((entry) => scoreOf(entry, round2) > scoreOf(contender, round2));
  const leaders = round2
    ? entries.filter((entry) => isRanked(entry, round2)).slice(0, 3)
    : entries.filter((entry) => entry.activations > 0).slice(0, 3);
  const isZeroState = round2
    ? (data.team_total_points ?? 0) === 0
    : data.team_total_activations === 0;

  return (
    <div
      data-testid="champion-arena"
      className="relative overflow-hidden rounded-2xl bg-[var(--bz-text-1)] p-4 text-[var(--bz-surface)] sm:p-6"
    >
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -right-24 -top-28 size-96 rounded-full border-[40px] border-[var(--bz-kita-ink-panel-copper)] opacity-[0.06]"
      />
      <div className="relative flex flex-wrap items-start justify-between gap-x-8 gap-y-5">
        <div className="min-w-0">
          <div
            aria-hidden="true"
            className="mb-3 h-[3px] w-14 rounded-sm bg-[var(--bz-copper)]"
          />
          <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-[var(--bz-kita-ink-panel-copper)]">
            {round2
              ? `${data.campaign ?? "Lascia o raddoppia"} · ${formatWindowRange(data.window_start, data.window_end)} · WITA`
              : data.status === "closed"
                ? "Hasil akhir"
                : data.status === "upcoming"
                  ? "Bersiap untuk bertanding"
                  : "Final sprint · Perebutan juara"}
          </p>
          <h2
            className="mt-1.5 text-[clamp(30px,3.6vw,44px)] leading-[1.02] tracking-[-0.02em]"
            style={SERIF}
          >
            Portal Champion
          </h2>
          <p className="mt-1.5 text-base opacity-80 sm:text-lg" style={SERIF}>
            {data.status === "closed"
              ? "Setiap poin berarti."
              : "Satu poin. Semua bisa berubah."}
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-x-8 gap-y-4">
          <div
            data-testid="champion-team-total"
            className="flex items-end gap-2.5"
          >
            <span
              className="font-black tabular-nums leading-[0.85] text-[clamp(36px,4vw,48px)]"
              style={SERIF}
            >
              {round2
                ? (data.team_total_points ?? 0)
                : data.team_total_activations}
            </span>
            <span className="max-w-[11rem] pb-0.5 text-[12px] leading-snug opacity-70">
              {round2
                ? "poin tim"
                : isZeroState
                  ? "Belum ada klien aktivasi — jadilah yang pertama!"
                  : "klien aktivasi dari seluruh tim"}
            </span>
          </div>
          {countdown}
        </div>
      </div>
      {(leaders.length > 0 || contender) && (
        <div
          className={cn(
            "relative mt-6 grid gap-4",
            leaders.length > 0 &&
              contender &&
              "lg:grid-cols-[minmax(0,1fr)_minmax(17rem,20rem)] lg:items-end",
          )}
        >
          {leaders.length > 0 && (
            <div className="grid grid-cols-3 items-end gap-2 sm:gap-4">
              {leaders.map((entry, index) => (
                <motion.button
                  key={entry.member}
                  layout={!reduceMotion}
                  type="button"
                  onClick={() => setSelected(entry.member)}
                  aria-pressed={contender?.member === entry.member}
                  aria-label={`Lihat peluang ${entry.display_name}`}
                  className={cn(
                    FOCUS,
                    "group relative flex min-w-0 flex-col items-center rounded-xl border px-1.5 pb-3 pt-3 text-center transition-colors sm:px-4 sm:pb-4",
                    index === 0
                      ? "order-2 border-[var(--bz-kita-ink-panel-copper)] bg-[color-mix(in_srgb,var(--bz-copper)_14%,transparent)]"
                      : HAIRLINE_ON_INK,
                    index === 1 && "order-1",
                    index === 2 && "order-3",
                    contender?.member === entry.member &&
                      "ring-2 ring-[var(--bz-kita-ink-panel-copper)] ring-offset-2 ring-offset-[var(--bz-text-1)]",
                  )}
                >
                  {index === 0 && (
                    <Crown
                      size={22}
                      className="mb-1.5 text-[var(--bz-kita-ink-panel-copper)]"
                      aria-hidden="true"
                    />
                  )}
                  <ChampionPortrait
                    face
                    name={entry.display_name}
                    src={entry.avatar_url}
                    sizes="(max-width: 640px) 240px, 360px"
                    className={cn(
                      "mb-2.5 aspect-square w-full border-2 border-[var(--bz-kita-ink-panel-copper)]",
                      index === 0
                        ? "max-w-24 sm:max-w-36"
                        : "max-w-20 sm:max-w-28",
                    )}
                  />
                  <span className="text-[10px] font-bold uppercase tracking-widest opacity-70">
                    #{entry.rank}
                    {entry.is_me ? " · Kamu" : ""}
                  </span>
                  <span className="mt-0.5 line-clamp-2 max-w-full break-words text-xs font-bold leading-tight sm:text-lg">
                    {entry.display_name}
                  </span>
                  <motion.span
                    key={scoreOf(entry, round2)}
                    initial={reduceMotion ? false : { opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mt-1.5 text-3xl font-black tabular-nums leading-none sm:text-5xl"
                    style={SERIF}
                  >
                    {scoreOf(entry, round2)}
                  </motion.span>
                  <span className="mt-1 text-[10px] uppercase tracking-[0.2em] opacity-60">
                    poin
                  </span>
                </motion.button>
              ))}
            </div>
          )}
          {contender && (
            <div
              data-testid="champion-target"
              className={cn(
                "flex min-w-0 flex-col rounded-xl border bg-[color-mix(in_srgb,var(--bz-surface)_4%,transparent)] p-4 sm:p-5",
                HAIRLINE_ON_INK,
              )}
            >
              <div aria-live="polite">
                <div className="flex items-center gap-3">
                  <ChampionPortrait
                    face
                    name={contender.display_name}
                    src={contender.avatar_url}
                    sizes="120px"
                    className="size-12 border border-[var(--bz-kita-ink-panel-copper)]"
                  />
                  <div className="min-w-0">
                    <p className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.2em] text-[var(--bz-kita-ink-panel-copper)]">
                      <Crosshair size={13} aria-hidden="true" />
                      {data.status === "closed"
                        ? "Hasil akhir"
                        : "Target berikutnya"}
                    </p>
                    <p className="mt-0.5 truncate text-base font-bold">
                      {contender.display_name}
                      {contender.is_me ? " · Kamu" : ""}
                    </p>
                    <p className="text-xs tabular-nums opacity-70">
                      Peringkat {rankLabel(contender, round2)} ·{" "}
                      {scoreOf(contender, round2)} poin
                    </p>
                  </div>
                </div>
                <p
                  className="mt-4 text-xl leading-snug sm:text-2xl"
                  style={SERIF}
                >
                  {data.status === "closed"
                    ? `${scoreOf(contender, round2)} ${round2 ? "poin" : "aktivasi"} tercatat.`
                    : rival
                      ? `${scoreOf(rival, round2) - scoreOf(contender, round2) + 1} poin untuk melewati ${rival.display_name}.`
                      : scoreOf(contender, round2) > 0
                        ? "Di puncak. Pertahankan posisimu!"
                        : "Jadilah pencetak poin pertama."}
                </p>
              </div>
              {data.status === "live" && (
                <Link
                  href="/clients"
                  className={cn(
                    FOCUS,
                    "mt-3 inline-flex items-center gap-1.5 self-start text-xs font-bold text-[var(--bz-kita-ink-panel-copper)]",
                  )}
                >
                  Bantu klien aktivasi portal{" "}
                  <ArrowUpRight size={15} aria-hidden="true" />
                </Link>
              )}
              <div className={cn("mt-4 border-t pt-4", HAIRLINE_ON_INK)}>
                <label
                  htmlFor={pickerId}
                  className="text-[10px] font-bold uppercase tracking-[0.2em] opacity-70"
                >
                  Lihat peluang peserta lain
                </label>
                <div className="relative mt-2">
                  <select
                    id={pickerId}
                    value={contender.member}
                    onChange={(event) => setSelected(event.target.value)}
                    className={cn(
                      FOCUS,
                      "w-full appearance-none truncate rounded-lg border bg-[var(--bz-text-1)] py-2.5 pl-3 pr-9 text-sm text-[var(--bz-surface)]",
                      "border-[color-mix(in_srgb,var(--bz-surface)_25%,transparent)]",
                    )}
                  >
                    {entries.map((entry) => (
                      <option key={entry.member} value={entry.member}>
                        {`${rankLabel(entry, round2)} · ${entry.display_name}${entry.is_me ? " (Kamu)" : ""} — ${scoreOf(entry, round2)} poin`}
                      </option>
                    ))}
                  </select>
                  <ChevronDown
                    size={16}
                    aria-hidden="true"
                    className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 opacity-70"
                  />
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
