"use client";

import { useState } from "react";
import Link from "next/link";
import { motion, useReducedMotion } from "framer-motion";
import { ArrowUpRight, Crown, Crosshair } from "lucide-react";
import { ChampionPortrait } from "@/components/workspace/ChampionPortrait";
import type { PortalChallengeResponse } from "@/lib/api/dashboard/dashboard.api";
import { cn } from "@/lib/utils";
import { FOCUS, SERIF } from "./r19";

export function ChampionArena({ data }: { data: PortalChallengeResponse }) {
  const [selected, setSelected] = useState<string | null>(null);
  const reduceMotion = useReducedMotion();
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
      .find((entry) => entry.activations > contender.activations);
  const leaders = entries.filter((entry) => entry.activations > 0).slice(0, 3);

  return (
    <div
      data-testid="champion-arena"
      className="relative overflow-hidden rounded-2xl bg-[var(--bz-text-1)] p-4 text-[var(--bz-surface)] sm:p-7"
    >
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -right-24 -top-28 size-96 rounded-full border-[40px] border-[var(--bz-kita-ink-panel-copper)] opacity-[0.06]"
      />
      <div className="relative mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.24em] text-[var(--bz-kita-ink-panel-copper)]">
            {data.status === "closed"
              ? "Hasil akhir"
              : data.status === "upcoming"
                ? "Bersiap untuk mulai"
                : "Perebutan juara"}
          </p>
          <h3
            className="mt-2 text-[clamp(28px,4vw,48px)] leading-none"
            style={SERIF}
          >
            {data.status === "closed"
              ? "Setiap poin berarti."
              : "Satu poin. Semua bisa berubah."}
          </h3>
        </div>
        <span className="text-xs opacity-70">
          {data.team_total_activations} aktivasi tim
        </span>
      </div>
      {leaders.length > 0 && (
        <div className="relative mb-6 grid grid-cols-3 items-end gap-2 sm:gap-5">
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
                "group relative flex min-w-0 flex-col items-center rounded-xl border p-2 pt-4 text-center transition-colors sm:p-5",
                index === 0
                  ? "order-2 border-[var(--bz-kita-ink-panel-copper)] bg-[color-mix(in_srgb,var(--bz-copper)_14%,transparent)]"
                  : "border-[color-mix(in_srgb,var(--bz-surface)_15%,transparent)]",
                index === 1 && "order-1",
                index === 2 && "order-3",
                contender?.member === entry.member &&
                  "ring-2 ring-[var(--bz-kita-ink-panel-copper)] ring-offset-2 ring-offset-[var(--bz-text-1)]",
              )}
            >
              {index === 0 && (
                <Crown
                  size={25}
                  className="mb-2 text-[var(--bz-kita-ink-panel-copper)]"
                  aria-hidden="true"
                />
              )}
              <ChampionPortrait
                name={entry.display_name}
                src={entry.avatar_url}
                className={cn(
                  "mb-3 aspect-square w-full max-w-32 border-2 border-[var(--bz-kita-ink-panel-copper)]",
                  index === 0 && "sm:max-w-44",
                )}
              />
              <span className="text-[10px] font-bold uppercase tracking-widest opacity-70">
                #{entry.rank}
                {entry.is_me ? " · Kamu" : ""}
              </span>
              <span className="mt-1 max-w-full truncate text-sm font-bold sm:text-xl">
                {entry.display_name}
              </span>
              <motion.span
                key={entry.activations}
                initial={reduceMotion ? false : { opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-3 text-4xl font-black tabular-nums sm:text-6xl"
                style={SERIF}
              >
                {entry.activations}
              </motion.span>
              <span className="mt-1 text-[10px] uppercase tracking-[0.2em] opacity-60">
                poin
              </span>
            </motion.button>
          ))}
        </div>
      )}
      {contender && (
        <div className="relative rounded-xl border border-[color-mix(in_srgb,var(--bz-surface)_15%,transparent)] p-4">
          <div className="mb-4 flex flex-wrap gap-2" aria-label="Pilih peserta">
            {entries.map((entry) => (
              <button
                key={entry.member}
                type="button"
                onClick={() => setSelected(entry.member)}
                aria-pressed={entry.member === contender.member}
                className={cn(
                  FOCUS,
                  "rounded-full border px-3 py-2 text-xs transition-colors",
                  entry.member === contender.member
                    ? "border-[var(--bz-kita-ink-panel-copper)] bg-[var(--bz-kita-ink-panel-copper)] text-[var(--bz-text-1)]"
                    : "border-[color-mix(in_srgb,var(--bz-surface)_20%,transparent)]",
                )}
              >
                {entry.display_name}
                {entry.is_me ? " · Kamu" : ""}
              </button>
            ))}
          </div>
          <div className="flex items-start gap-3" aria-live="polite">
            <Crosshair
              className="mt-1 shrink-0 text-[var(--bz-kita-ink-panel-copper)]"
              size={22}
              aria-hidden="true"
            />
            <div>
              <p className="text-sm font-bold">
                {contender.display_name} ·{" "}
                {data.status === "closed" ? "Hasil akhir" : "Target berikutnya"}
              </p>
              <p className="mt-1 text-lg sm:text-2xl" style={SERIF}>
                {data.status === "closed"
                  ? `${contender.activations} aktivasi tercatat.`
                  : rival
                    ? `${rival.activations - contender.activations + 1} poin untuk melewati ${rival.display_name}.`
                    : contender.activations > 0
                      ? "Di puncak. Pertahankan posisimu!"
                      : "Jadilah pencetak poin pertama."}
              </p>
              {data.status === "live" && (
                <Link
                  href="/clients"
                  className={cn(
                    FOCUS,
                    "mt-3 inline-flex items-center gap-1.5 text-xs font-bold text-[var(--bz-kita-ink-panel-copper)]",
                  )}
                >
                  Bantu klien aktivasi portal{" "}
                  <ArrowUpRight size={15} aria-hidden="true" />
                </Link>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
