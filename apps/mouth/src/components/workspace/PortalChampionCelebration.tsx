"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowUpRight, X } from "lucide-react";
import { ChampionPortrait } from "./ChampionPortrait";

export interface ChampionGoal {
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
    if (
      !goal ||
      typeof goal.member !== "string" ||
      !goal.member ||
      typeof goal.display_name !== "string" ||
      !goal.display_name.trim() ||
      goal.display_name.length > 120 ||
      !Number.isSafeInteger(goal.activations) ||
      goal.activations < 1 ||
      typeof goal.at !== "string"
    )
      return null;
    const age = now - Date.parse(goal.at);
    if (!Number.isFinite(age) || age < -5_000 || age > 90_000) return null;
    return goal;
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
    let source: EventSource;
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
      if (stopped) return;
      source = new EventSource(
        `/api/dashboard/portal-challenge/events${lastId ? `?last_event_id=${encodeURIComponent(lastId)}` : ""}`,
      );
      source.addEventListener("ready", (event) => {
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
      source.addEventListener("goal", (event) => {
        const message = event as MessageEvent<string>;
        if (!message.lastEventId || seen.has(message.lastEventId)) return;
        const goal = parseChampionGoal(message.data, Date.now() + clockOffset);
        if (!goal) return;
        lastId = message.lastEventId;
        seen.add(message.lastEventId);
        if (seen.size > 200) seen.delete(seen.values().next().value!);
        refresh();
        onGoal(goal);
      });
      source.onerror = () => {
        if (source.readyState !== EventSource.CLOSED || stopped) return;
        source.close();
        const delay = Math.min(60_000, 5_000 * 2 ** Math.min(retries++, 4));
        retryTimer = setTimeout(connect, delay + Math.random() * 1000);
      };
      source.addEventListener("closed", () => {
        stopped = true;
        clearTimeout(retryTimer);
        source.close();
        refresh();
      });
    };
    connect();
    return () => {
      stopped = true;
      clearTimeout(retryTimer);
      source.close();
    };
  }, [identity, onGoal, queryClient]);
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
    const timeout = window.setTimeout(dismiss, 6500);
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
        {celebrating && current
          ? `GOAL oleh ${current.display_name}. ${current.activations} poin.`
          : ""}
      </div>
      <AnimatePresence>
        {current && visible && identity && (
          <motion.aside
            key={`${current.member}:${current.at}`}
            initial={reduceMotion ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={reduceMotion ? undefined : { opacity: 0 }}
            className="fixed inset-0 z-[100] flex items-center justify-center overflow-hidden bg-[color-mix(in_srgb,var(--bz-text-1)_88%,transparent)] p-5 text-[var(--bz-surface)] backdrop-blur-md"
            aria-label="Selebrasi Portal Champion"
            role="dialog"
            aria-modal="true"
            onClick={dismiss}
          >
            {!reduceMotion &&
              [0, 1, 2].map((ring) => (
                <motion.div
                  key={ring}
                  aria-hidden="true"
                  initial={{ scale: 0.3, opacity: 0 }}
                  animate={{ scale: [0.3, 1.7, 2.6], opacity: [0, 0.4, 0] }}
                  transition={{ duration: 2.6, delay: ring * 0.3, repeat: 1 }}
                  className="absolute size-[65vw] max-w-[800px] rounded-full border border-[var(--bz-kita-ink-panel-copper)]"
                />
              ))}
            <motion.div
              initial={reduceMotion ? false : { y: 45, scale: 0.92 }}
              animate={{ y: 0, scale: 1 }}
              transition={{ type: "spring", damping: 20 }}
              className="relative w-full max-w-2xl text-center"
              onClick={(event) => event.stopPropagation()}
            >
              <p className="mb-4 text-xs font-bold uppercase tracking-[0.4em] text-[var(--bz-kita-ink-panel-copper)]">
                Portal Champion · +1 poin
              </p>
              <p
                aria-hidden="true"
                className="text-[clamp(80px,19vw,180px)] font-black italic leading-none tracking-[-0.08em]"
              >
                GOAL
                <span className="text-[var(--bz-kita-ink-panel-copper)]">
                  !
                </span>
              </p>
              <ChampionPortrait
                name={current.display_name}
                src={current.avatar_url}
                className="my-5 size-28 border-4 border-[var(--bz-kita-ink-panel-copper)] shadow-2xl sm:size-40"
              />
              <div>
                <h2 className="text-[clamp(26px,5vw,52px)] font-bold leading-tight">
                  GOAL oleh {current.display_name}
                </h2>
                <p className="mt-3 text-base opacity-80">
                  Satu aktivasi lagi.{" "}
                  <strong className="text-[var(--bz-kita-ink-panel-copper)]">
                    {current.activations} poin
                  </strong>{" "}
                  terkumpul.
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
          </motion.aside>
        )}
      </AnimatePresence>
    </>,
    document.body,
  );
}
