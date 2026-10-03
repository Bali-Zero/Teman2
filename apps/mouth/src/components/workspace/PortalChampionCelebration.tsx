"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowUpRight, X } from "lucide-react";
import { ChampionPortrait } from "./ChampionPortrait";

export type ChampionKind = "goal" | "bomb" | "penalty";
export type ChampionReason = "unanswered_request" | "unreviewed_document";

export interface ChampionGoal {
  kind: ChampionKind;
  points?: number;
  reason?: ChampionReason;
  member: string;
  display_name: string;
  avatar_url?: string | null;
  activations: number;
  at: string;
}

export function parseChampionGoal(
  raw: string,
  now = Date.now(),
): ChampionGoal | null {
  try {
    const goal = JSON.parse(raw);
    // A missing kind is a classic goal; an unknown one is never shown as a goal.
    const kind = goal?.kind ?? "goal";
    if (kind !== "goal" && kind !== "bomb" && kind !== "penalty") return null;
    if (
      !goal ||
      typeof goal.member !== "string" ||
      !goal.member ||
      typeof goal.display_name !== "string" ||
      !goal.display_name.trim() ||
      goal.display_name.length > 120 ||
      !Number.isSafeInteger(goal.activations) ||
      typeof goal.at !== "string"
    )
      return null;
    const age = now - Date.parse(goal.at);
    if (!Number.isFinite(age) || age < -5_000 || age > 90_000) return null;
    // `activations` is the member's Round 2 total: a goal or bomb still counts
    // when penalties hold that total at zero or below. An unknown penalty
    // reason is dropped so it falls back to the generic line.
    const reason =
      goal.reason === "unanswered_request" ||
      goal.reason === "unreviewed_document"
        ? goal.reason
        : undefined;
    return { ...goal, kind, reason };
  } catch {
    return null;
  }
}

export function useChampionGoals(
  identity: string,
  onGoal: (goal: ChampionGoal) => void,
) {
  const queryClient = useQueryClient();
  useEffect(() => {
    if (!identity || typeof EventSource === "undefined") return;
    let source: EventSource | undefined;
    let stopped = false;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let retries = 0;
    let lastId = "";
    let clockOffset = 0;
    const seen = new Set<string>();
    const refresh = () =>
      void queryClient.invalidateQueries({
        queryKey: ["portal-challenge", identity],
      });
    const connect = () => {
      if (stopped || source) return;
      const current = new EventSource(
        `/api/dashboard/portal-challenge/events${lastId ? `?last_event_id=${encodeURIComponent(lastId)}` : ""}`,
      );
      source = current;
      current.addEventListener("ready", (event) => {
        const message = event as MessageEvent<string>;
        lastId = message.lastEventId || lastId;
        retries = 0;
        try {
          const serverNow = Date.parse(JSON.parse(message.data).server_time);
          if (Number.isFinite(serverNow)) clockOffset = serverNow - Date.now();
        } catch {
          clockOffset = 0;
        }
        refresh();
      });
      const onTakeover = (event: Event) => {
        const message = event as MessageEvent<string>;
        if (!message.lastEventId || seen.has(message.lastEventId)) return;
        const goal = parseChampionGoal(message.data, Date.now() + clockOffset);
        if (!goal) return;
        lastId = message.lastEventId;
        seen.add(message.lastEventId);
        if (seen.size > 200) seen.delete(seen.values().next().value!);
        refresh();
        onGoal(goal);
      };
      for (const name of ["goal", "bomb", "penalty"])
        current.addEventListener(name, onTakeover);
      current.onerror = () => {
        if (
          current.readyState !== EventSource.CLOSED ||
          stopped ||
          source !== current
        )
          return;
        current.close();
        source = undefined;
        const delay = Math.min(60_000, 5_000 * 2 ** Math.min(retries++, 4));
        retryTimer = setTimeout(connect, delay + Math.random() * 1000);
      };
      current.addEventListener("closed", () => {
        stopped = true;
        clearTimeout(retryTimer);
        current.close();
        source = undefined;
        refresh();
      });
    };
    // A hidden tab holds no stream (each one pins an API→RAG connection); on return it
    // resumes from its cursor, and replay covers the 90 s a hidden queue would keep.
    const followVisibility = () => {
      if (stopped) return;
      clearTimeout(retryTimer);
      if (document.visibilityState === "hidden") {
        source?.close();
        source = undefined;
      } else connect();
    };
    followVisibility();
    document.addEventListener("visibilitychange", followVisibility);
    return () => {
      stopped = true;
      clearTimeout(retryTimer);
      document.removeEventListener("visibilitychange", followVisibility);
      source?.close();
    };
  }, [identity, onGoal, queryClient]);
}

const DISPLAY_MS: Record<ChampionKind, number> = {
  goal: 9000,
  bomb: 9000,
  penalty: 6000,
};
const PENALTY_REASON: Record<ChampionReason, string> = {
  unanswered_request: "Permintaan klien belum dijawab > 3 jam kerja",
  unreviewed_document: "Dokumen belum ditinjau > 1 hari kerja",
};
const COPPER = "text-[var(--bz-kita-ink-panel-copper)]";
const CONFETTI = Array.from({ length: 36 }, (_, i) => {
  const angle = (i / 36) * Math.PI * 2 + (i % 3) * 0.17;
  const dist = 260 + ((i * 53) % 340);
  return {
    x: Math.cos(angle) * dist,
    y: Math.sin(angle) * dist - 120,
    fall: 260 + ((i * 37) % 200),
    rotate: ((i * 97) % 720) - 360,
    delay: (i % 6) * 0.04,
    size: 8 + (i % 4) * 3,
    tone: i % 3,
  };
});

function penaltyPoints(goal: ChampionGoal) {
  return `\u2212${Math.abs(goal.points ?? (goal.reason === "unreviewed_document" ? 1 : 2))} poin`;
}

function signedPoints(total: number) {
  return total < 0 ? `\u2212${-total}` : `${total}`;
}

function announcement(goal: ChampionGoal) {
  if (goal.kind === "bomb")
    return `BOM! +${goal.points ?? 3} poin untuk ${goal.display_name}. Dokumen pertama klien.`;
  if (goal.kind === "penalty")
    return `Aduh. ${penaltyPoints(goal)} untuk ${goal.display_name}. ${goal.reason ? PENALTY_REASON[goal.reason] : ""}`;
  return `GOAL oleh ${goal.display_name}. ${signedPoints(goal.activations)} poin.`;
}

export function PortalChampionCelebration({ identity }: { identity: string }) {
  const [goals, setGoals] = useState<(ChampionGoal & { receivedAt: number })[]>(
    [],
  );
  const [visible, setVisible] = useState(false);
  const reduceMotion = useReducedMotion();
  const dismissButton = useRef<HTMLButtonElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  const receive = useCallback(
    (goal: ChampionGoal) =>
      setGoals((pending) =>
        [...pending, { ...goal, receivedAt: Date.now() }].slice(-20),
      ),
    [],
  );
  const dismiss = useCallback(
    () =>
      setGoals((pending) =>
        pending
          .slice(1)
          .filter((goal) => Date.now() - goal.receivedAt <= 90_000),
      ),
    [],
  );
  useChampionGoals(identity, receive);
  const current = goals[0];
  const celebrating = Boolean(current && visible && identity);
  const goal = current?.kind === "goal";
  const bomb = current?.kind === "bomb";
  const penalty = current?.kind === "penalty";

  useEffect(() => {
    if (!celebrating) return;
    previousFocus.current =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    return () => {
      if (previousFocus.current?.isConnected) previousFocus.current.focus();
    };
  }, [celebrating]);

  useEffect(() => {
    const update = () => {
      setVisible(document.visibilityState === "visible");
      setGoals((pending) =>
        pending.filter((goal) => Date.now() - goal.receivedAt <= 90_000),
      );
    };
    update();
    document.addEventListener("visibilitychange", update);
    return () => document.removeEventListener("visibilitychange", update);
  }, []);
  useEffect(() => {
    setGoals([]);
  }, [identity]);
  useEffect(() => {
    if (!current || !visible) return;
    dismissButton.current?.focus();
    const timeout = window.setTimeout(dismiss, DISPLAY_MS[current.kind]);
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") dismiss();
      if (event.key === "Tab") {
        const controls = dismissButton.current
          ?.closest("aside")
          ?.querySelectorAll<HTMLElement>("a[href],button");
        if (!controls?.length) return;
        const first = controls[0];
        const last = controls[controls.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };
    window.addEventListener("keydown", escape);
    return () => {
      window.clearTimeout(timeout);
      window.removeEventListener("keydown", escape);
    };
  }, [current, visible, dismiss]);

  if (typeof document === "undefined") return null;
  return createPortal(
    <>
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {celebrating && current ? announcement(current) : ""}
      </div>
      <AnimatePresence>
        {current && visible && identity && (
          <motion.aside
            key={`${current.member}:${current.at}`}
            data-takeover={current.kind}
            initial={reduceMotion ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={reduceMotion ? undefined : { opacity: 0 }}
            className={`fixed inset-0 z-[100] flex items-center justify-center overflow-hidden p-5 text-[var(--bz-surface)] backdrop-blur-md ${
              penalty
                ? "bg-[color-mix(in_srgb,var(--bz-text-1)_94%,var(--bz-text-3))]"
                : bomb
                  ? "bg-[color-mix(in_srgb,var(--bz-text-1)_82%,var(--bz-red))]"
                  : "bg-[color-mix(in_srgb,var(--bz-text-1)_88%,transparent)]"
            }`}
            aria-label={
              penalty ? "Penalti Portal Champion" : "Selebrasi Portal Champion"
            }
            role="dialog"
            aria-modal="true"
            onClick={dismiss}
          >
            {!reduceMotion &&
              !penalty &&
              [0, 1, 2].map((ring) => (
                <motion.div
                  key={ring}
                  aria-hidden="true"
                  data-testid={bomb ? "champion-shockwave" : undefined}
                  initial={{ scale: 0.3, opacity: 0 }}
                  animate={{
                    scale: bomb ? [0.1, 2.2, 4] : [0.3, 1.7, 2.6],
                    opacity: bomb ? [0.9, 0.5, 0] : [0, 0.4, 0],
                  }}
                  transition={{
                    duration: bomb ? 1.6 : 2.6,
                    delay: ring * (bomb ? 0.18 : 0.3),
                    repeat: bomb ? 2 : 1,
                  }}
                  className={`absolute size-[65vw] max-w-[800px] rounded-full ${
                    bomb
                      ? "border-[6px] border-[var(--bz-red)]"
                      : "border border-[var(--bz-kita-ink-panel-copper)]"
                  }`}
                />
              ))}
            {!reduceMotion && bomb && (
              <motion.div
                aria-hidden="true"
                initial={{ opacity: 0.95 }}
                animate={{ opacity: 0 }}
                transition={{ duration: 0.7 }}
                className="absolute inset-0 bg-[var(--bz-kita-ink-panel-copper)]"
              />
            )}
            {!reduceMotion && penalty && (
              <motion.div
                aria-hidden="true"
                initial={{ scale: 1.8, opacity: 0.5 }}
                animate={{ scale: 0.25, opacity: 0 }}
                transition={{ duration: 4, ease: "easeIn" }}
                className="absolute size-[65vw] max-w-[800px] rounded-full border border-[var(--bz-text-3)]"
              />
            )}
            {!reduceMotion &&
              goal &&
              CONFETTI.map((piece, index) => (
                <motion.span
                  key={index}
                  aria-hidden="true"
                  data-testid="champion-confetti"
                  initial={{ x: 0, y: 0, opacity: 1, scale: 0.4, rotate: 0 }}
                  animate={{
                    x: piece.x,
                    y: [0, piece.y, piece.y + piece.fall],
                    opacity: [1, 1, 0],
                    scale: 1,
                    rotate: piece.rotate,
                  }}
                  transition={{
                    duration: 3.2,
                    delay: piece.delay,
                    ease: "easeOut",
                  }}
                  style={{ width: piece.size, height: piece.size * 0.55 }}
                  className={`pointer-events-none absolute left-1/2 top-1/2 rounded-[2px] ${
                    [
                      "bg-[var(--bz-kita-ink-panel-copper)]",
                      "bg-[var(--bz-surface)]",
                      "bg-[var(--bz-red)]",
                    ][piece.tone]
                  }`}
                />
              ))}
            <motion.div
              data-testid={!reduceMotion && goal ? "champion-shake" : undefined}
              animate={
                !reduceMotion && goal
                  ? { x: [0, -14, 12, -9, 6, 0], scale: [1, 1.05, 1] }
                  : undefined
              }
              transition={{ duration: 0.6, delay: 0.25 }}
              className="relative w-full max-w-2xl"
            >
              <motion.div
                initial={
                  reduceMotion
                    ? false
                    : { y: penalty ? -40 : 45, scale: penalty ? 1.06 : 0.92 }
                }
                animate={
                  penalty && !reduceMotion
                    ? { y: [0, 14], scale: [1, 0.97] }
                    : { y: 0, scale: 1 }
                }
                transition={
                  penalty
                    ? { duration: 5, ease: "easeOut" }
                    : { type: "spring", damping: goal ? 12 : 20 }
                }
                className="relative w-full text-center"
                onClick={(event) => event.stopPropagation()}
              >
                <p
                  className={`mb-4 text-xs font-bold uppercase tracking-[0.4em] ${penalty ? "opacity-70" : COPPER}`}
                >
                  Portal Champion ·{" "}
                  {penalty
                    ? penaltyPoints(current)
                    : bomb
                      ? `+${current.points ?? 3} poin`
                      : `+${current.points ?? 1} poin`}
                </p>
                <p
                  aria-hidden="true"
                  className={`font-black italic leading-none tracking-[-0.08em] ${
                    penalty
                      ? "text-[clamp(64px,15vw,140px)] opacity-60"
                      : bomb
                        ? "text-[clamp(90px,22vw,220px)]"
                        : "text-[clamp(96px,24vw,240px)]"
                  }`}
                >
                  {penalty ? (
                    "Aduh\u2026"
                  ) : bomb ? (
                    <>
                      BOM<span className="text-[var(--bz-red)]">!</span>
                    </>
                  ) : (
                    <>
                      GOAL<span className={COPPER}>!</span>
                    </>
                  )}
                </p>
                {(goal || bomb) && (
                  <p
                    aria-hidden="true"
                    className={`mt-2 text-[clamp(28px,6vw,64px)] font-black ${COPPER}`}
                  >
                    +{current.points ?? (bomb ? 3 : 1)} poin
                  </p>
                )}
                {penalty && (
                  <motion.p
                    aria-hidden="true"
                    initial={reduceMotion ? false : { y: -60, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    transition={{ duration: 1.6, ease: "easeIn" }}
                    className="mt-2 text-[clamp(28px,6vw,64px)] font-black opacity-70"
                  >
                    {penaltyPoints(current)}
                  </motion.p>
                )}
                <ChampionPortrait
                  name={current.display_name}
                  src={current.avatar_url}
                  className={`my-5 size-28 border-4 shadow-2xl sm:size-40 ${
                    penalty
                      ? "border-[var(--bz-text-3)] opacity-70 grayscale"
                      : "border-[var(--bz-kita-ink-panel-copper)]"
                  }`}
                />
                <div>
                  <h2 className="text-[clamp(26px,5vw,52px)] font-bold leading-tight">
                    {penalty
                      ? current.display_name
                      : bomb
                        ? `BOMBA oleh ${current.display_name}`
                        : `GOAL oleh ${current.display_name}`}
                  </h2>
                  <p className="mt-3 text-base opacity-80">
                    {penalty ? (
                      current.reason ? (
                        PENALTY_REASON[current.reason]
                      ) : (
                        "Poin dikurangi."
                      )
                    ) : bomb ? (
                      <>Dokumen pertama klien untuk {current.display_name}.</>
                    ) : (
                      <>
                        Satu aktivasi lagi.{" "}
                        <strong className={COPPER}>
                          {signedPoints(current.activations)} poin
                        </strong>{" "}
                        terkumpul.
                      </>
                    )}
                  </p>
                </div>
                <div className="pointer-events-auto mt-7 flex flex-wrap items-center justify-center gap-4">
                  <Link
                    href="/dashboard"
                    onClick={dismiss}
                    className="inline-flex items-center gap-2 rounded-full bg-[var(--bz-kita-ink-panel-copper)] px-5 py-3 text-sm font-bold text-[var(--bz-text-1)] focus-visible:outline-2 focus-visible:outline-offset-4"
                  >
                    Lihat klasemen <ArrowUpRight size={17} />
                  </Link>
                  <button
                    ref={dismissButton}
                    type="button"
                    onClick={dismiss}
                    className="inline-flex items-center gap-2 rounded-full border border-current px-5 py-3 text-sm focus-visible:outline-2 focus-visible:outline-offset-4"
                    aria-label="Tutup selebrasi"
                  >
                    Lanjut bekerja <X size={16} />
                  </button>
                </div>
              </motion.div>
            </motion.div>
          </motion.aside>
        )}
      </AnimatePresence>
    </>,
    document.body,
  );
}
