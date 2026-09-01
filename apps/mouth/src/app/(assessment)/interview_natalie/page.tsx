"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  BANK_ROWS,
  CASHBOOK_ROWS,
  EXERCISES,
  OTHER_EXPENSES,
  TOTAL_MINUTES,
  type Exercise,
} from "./data";
import {
  countWords,
  emptyField,
  flagSummary,
  flagsFor,
  JUMP_THRESHOLD,
  type ExerciseTelemetry,
  type FieldTelemetry,
} from "./telemetry";

const CANDIDATE = "Natalie Mahodim";
const ROLE = "Finance & Client Services Coordinator";
const PANEL_INBOX = "zero@balizero.com";
const STORAGE_KEY = "bz-interview-natalie-v1";

type Phase = "intro" | "running" | "done";

interface Persisted {
  answers: Record<string, string>;
  index: number;
  submitted: string[];
  startedAt: number | null;
}

function mmss(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

function wita(): string {
  return new Date().toLocaleString("en-GB", {
    timeZone: "Asia/Makassar",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function esc(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function newExerciseTelemetry(ex: Exercise): ExerciseTelemetry {
  const fields: Record<string, FieldTelemetry> = {};
  for (const f of ex.fields) fields[f.id] = emptyField();
  return { elapsedMs: 0, awayMs: 0, awayCount: 0, fields, autoLocked: false };
}

export default function InterviewNataliePage() {
  const [phase, setPhase] = useState<Phase>("intro");
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [submitted, setSubmitted] = useState<string[]>([]);
  const [sending, setSending] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [remaining, setRemaining] = useState(EXERCISES[0].minutes * 60);
  const [restored, setRestored] = useState(false);

  const exercise = EXERCISES[index];
  const startedRef = useRef<number | null>(null);
  const telemRef = useRef<ExerciseTelemetry>(
    newExerciseTelemetry(EXERCISES[0]),
  );
  const allTelemRef = useRef<Record<string, ExerciseTelemetry>>({});
  const lastEditRef = useRef<Record<string, number>>({});
  const focusedAtRef = useRef<Record<string, number>>({});
  const awaySinceRef = useRef<number | null>(null);
  const submitRef = useRef<(auto: boolean) => void>(() => {});

  // ── Restore an interrupted session ──────────────────────────────
  // Sixty minutes of handwriting cannot be asked for twice: a reload, a flat
  // battery or a stray back-gesture must not cost the candidate her answers.
  // Telemetry deliberately does NOT survive the reload — it would be a
  // fabricated measurement of a session this page did not watch.
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const saved = JSON.parse(raw) as Persisted;
      if (saved && typeof saved === "object" && saved.answers) {
        setAnswers(saved.answers);
        setSubmitted(saved.submitted || []);
        const idx = Math.min(
          Math.max(saved.index || 0, 0),
          EXERCISES.length - 1,
        );
        setIndex(idx);
        setRestored(true);
      }
    } catch {
      /* a browser that refuses storage is not a reason to fail the exam */
    }
  }, []);

  useEffect(() => {
    if (phase === "intro") return;
    try {
      window.localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          answers,
          index,
          submitted,
          startedAt: startedRef.current,
        }),
      );
    } catch {
      /* ignore */
    }
  }, [answers, index, submitted, phase]);

  // ── Countdown ───────────────────────────────────────────────────
  useEffect(() => {
    if (phase !== "running") return;
    const id = setInterval(() => {
      const started = startedRef.current;
      if (!started) return;
      const elapsedMs = Date.now() - started;
      telemRef.current.elapsedMs = elapsedMs;
      const left = exercise.minutes * 60 - Math.floor(elapsedMs / 1000);
      setRemaining(left);
      if (left <= 0) {
        telemRef.current.autoLocked = true;
        submitRef.current(true);
      }
    }, 1000);
    return () => clearInterval(id);
  }, [phase, exercise]);

  // ── Away-from-tab detection ─────────────────────────────────────
  useEffect(() => {
    if (phase !== "running") return;
    const leave = () => {
      if (awaySinceRef.current === null) {
        awaySinceRef.current = Date.now();
        telemRef.current.awayCount += 1;
      }
    };
    const back = () => {
      if (awaySinceRef.current !== null) {
        telemRef.current.awayMs += Date.now() - awaySinceRef.current;
        awaySinceRef.current = null;
      }
    };
    const visibility = () => (document.hidden ? leave() : back());
    window.addEventListener("blur", leave);
    window.addEventListener("focus", back);
    document.addEventListener("visibilitychange", visibility);
    return () => {
      window.removeEventListener("blur", leave);
      window.removeEventListener("focus", back);
      document.removeEventListener("visibilitychange", visibility);
    };
  }, [phase]);

  // ── Field instrumentation ───────────────────────────────────────
  const field = (id: string): FieldTelemetry => {
    const t = telemRef.current.fields[id];
    if (t) return t;
    telemRef.current.fields[id] = emptyField();
    return telemRef.current.fields[id];
  };

  const onFocus = (id: string) => {
    if (!focusedAtRef.current[id]) focusedAtRef.current[id] = Date.now();
  };

  const onKeyDown = (id: string, e: React.KeyboardEvent) => {
    const t = field(id);
    if (e.key === "Backspace" || e.key === "Delete") {
      t.backspaces += 1;
      return;
    }
    // Printable keys only: single-character key values, no modifier combo.
    if (e.key.length === 1 && !e.ctrlKey && !e.metaKey) {
      t.keystrokes += 1;
      if (t.timeToFirstKeyMs === null) {
        const from =
          focusedAtRef.current[id] || startedRef.current || Date.now();
        t.timeToFirstKeyMs = Date.now() - from;
      }
    }
  };

  const onPaste = (id: string, e: React.ClipboardEvent) => {
    e.preventDefault();
    const t = field(id);
    t.pasteAttempts += 1;
    t.pastedChars += (e.clipboardData?.getData("text") || "").length;
    setNotice(
      "Pasting is disabled in this assessment. Please type your answer.",
    );
    window.setTimeout(() => setNotice(null), 3500);
  };

  const onCopy = (id: string, kind: "copy" | "cut") => {
    const t = field(id);
    if (kind === "cut") t.cutEvents += 1;
    else t.copyEvents += 1;
  };

  const onChange = (id: string, value: string) => {
    const t = field(id);
    const before = answers[id] || "";
    const delta = value.length - before.length;
    if (delta > JUMP_THRESHOLD) {
      t.jumpInsertions += 1;
      t.jumpChars += delta;
    }
    const now = Date.now();
    const last = lastEditRef.current[id];
    if (last) t.maxIdleMs = Math.max(t.maxIdleMs, now - last);
    lastEditRef.current[id] = now;
    t.chars = value.length;
    t.words = countWords(value);
    setAnswers((prev) => ({ ...prev, [id]: value }));
  };

  // ── Submit one exercise ─────────────────────────────────────────
  const submitExercise = useCallback(
    async (auto: boolean) => {
      if (sending || submitted.includes(exercise.key)) return;
      setSending(true);

      // Close any open away-window so the last stretch is counted.
      if (awaySinceRef.current !== null) {
        telemRef.current.awayMs += Date.now() - awaySinceRef.current;
        awaySinceRef.current = null;
      }
      if (startedRef.current) {
        telemRef.current.elapsedMs = Date.now() - startedRef.current;
      }

      const telem = telemRef.current;
      allTelemRef.current[exercise.key] = telem;
      const flags = flagsFor(telem);
      const usedSec = Math.round(telem.elapsedMs / 1000);

      let body = `<h2>Exercise ${exercise.letter} — ${exercise.title}</h2>`;
      body += `<p><strong>Candidate:</strong> ${esc(CANDIDATE)} · ${esc(ROLE)}<br/>`;
      body += `<strong>Submitted:</strong> ${wita()} WITA<br/>`;
      body += `<strong>Time used:</strong> ${mmss(usedSec)} of ${exercise.minutes}:00${auto ? " (window expired — auto-submitted)" : ""}<br/>`;
      body += `<strong>Away from tab:</strong> ${telem.awayCount}× · ${Math.round(telem.awayMs / 1000)}s</p>`;

      body += `<h3>Integrity signals</h3>`;
      if (flags.length === 0) {
        body += `<p>No signal raised. This is not proof of anything — it means this instrument saw nothing unusual.</p>`;
      } else {
        body += `<ul>`;
        for (const f of flags) {
          body += `<li><strong>${f.code}</strong> (${f.severity}) — ${esc(f.detail)}</li>`;
        }
        body += `</ul><p style="font-size:12px;color:#666">Signals, not a verdict. Dictation, transcribing from paper, and an unusual keyboard trip the same wires as a chatbot.</p>`;
      }

      body += `<h3>Per-field measurements</h3>`;
      body += `<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;font-size:12px">`;
      body += `<tr><th>field</th><th>chars</th><th>words</th><th>keys</th><th>corrections</th><th>paste</th><th>jumps</th><th>longest pause</th></tr>`;
      for (const f of exercise.fields) {
        const t = telem.fields[f.id] || emptyField();
        body += `<tr><td>${f.id}</td><td>${t.chars}</td><td>${t.words}</td><td>${t.keystrokes}</td><td>${t.backspaces}</td><td>${t.pasteAttempts} (${t.pastedChars}c)</td><td>${t.jumpInsertions} (${t.jumpChars}c)</td><td>${Math.round(t.maxIdleMs / 1000)}s</td></tr>`;
      }
      body += `</table>`;

      body += `<h3>Answers</h3>`;
      for (const f of exercise.fields) {
        const a = (answers[f.id] || "").trim();
        body += `<p style="margin-bottom:4px"><strong>${esc(f.label)}</strong></p>`;
        body += `<pre style="white-space:pre-wrap;font-family:ui-monospace,monospace;background:#f5f5f5;padding:12px;border-radius:6px;margin-top:0">${esc(a || "(left blank)")}</pre>`;
      }

      try {
        const res = await fetch("/api/assessment/submit", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            to: PANEL_INBOX,
            subject: `[Round 2] ${CANDIDATE} — Exercise ${exercise.letter} ${exercise.title} · ${mmss(usedSec)} · ${flagSummary(flags)}`,
            body,
          }),
        });
        if (!res.ok) throw new Error(`server ${res.status}`);
        setNotice(null);
      } catch {
        // The answers are already on disk in localStorage; say so plainly
        // rather than implying the work is lost.
        setNotice(
          `Exercise ${exercise.letter} could not be sent to the panel. Your answers are saved in this browser — tell the panel now, do not close this tab.`,
        );
      }

      setSubmitted((prev) => [...prev, exercise.key]);
      setSending(false);

      if (index < EXERCISES.length - 1) {
        const next = index + 1;
        setIndex(next);
        telemRef.current = newExerciseTelemetry(EXERCISES[next]);
        startedRef.current = Date.now();
        setRemaining(EXERCISES[next].minutes * 60);
        window.scrollTo({ top: 0, behavior: "smooth" });
      } else {
        setPhase("done");
      }
    },
    [answers, exercise, index, sending, submitted],
  );

  submitRef.current = submitExercise;

  const begin = () => {
    startedRef.current = Date.now();
    telemRef.current = newExerciseTelemetry(EXERCISES[index]);
    setRemaining(EXERCISES[index].minutes * 60);
    setPhase("running");
  };

  const answeredSomething = useMemo(
    () => exercise.fields.some((f) => (answers[f.id] || "").trim().length > 0),
    [answers, exercise],
  );

  const warn = remaining <= 120;
  const danger = remaining <= 30;

  // ── Render ──────────────────────────────────────────────────────
  return (
    <div
      className="min-h-screen bg-[#0a0a0b] text-[#e8e6e1]"
      onContextMenu={(e) => {
        if (phase === "running") {
          const t = telemRef.current.fields[exercise.fields[0].id];
          if (t) t.contextMenus += 1;
        }
        return e;
      }}
    >
      <header className="sticky top-0 z-50 border-b border-white/5 bg-[#0a0a0b]/95 backdrop-blur">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/static/balizero-logo-clean.png"
              alt="Bali Zero"
              className="h-9 w-9 rounded-full"
            />
            <div className="flex flex-col leading-tight">
              <span className="text-sm font-semibold tracking-wide text-white">
                BALI ZERO
              </span>
              <span className="text-xs text-white/40">
                Round 2 · Written assessment
              </span>
            </div>
          </div>

          {phase === "running" && (
            <div className="flex items-center gap-5">
              <div className="hidden text-xs uppercase tracking-[0.2em] text-white/35 sm:block">
                {exercise.letter} · {exercise.title}
              </div>
              <div
                className={`font-mono text-2xl tabular-nums ${
                  danger
                    ? "animate-pulse text-[#c23c2c]"
                    : warn
                      ? "text-amber-400"
                      : "text-white/85"
                }`}
                aria-live="off"
              >
                {mmss(remaining)}
              </div>
            </div>
          )}
        </div>
        {phase === "running" && (
          <div className="h-[2px] w-full bg-white/5">
            <div
              className={`h-full transition-[width] duration-1000 ease-linear ${danger ? "bg-[#c23c2c]" : warn ? "bg-amber-400" : "bg-white/25"}`}
              style={{
                width: `${Math.max(0, Math.min(100, (remaining / (exercise.minutes * 60)) * 100))}%`,
              }}
            />
          </div>
        )}
        {notice && (
          <div className="border-t border-[#c23c2c]/40 bg-[#c23c2c]/15 px-6 py-3 text-center text-sm text-[#ffd9d3]">
            {notice}
          </div>
        )}
      </header>

      <main className="mx-auto max-w-4xl px-6 py-10">
        {/* ── INTRO ─────────────────────────────────────────────── */}
        {phase === "intro" && (
          <div className="space-y-8">
            <div className="space-y-3 py-6 text-center">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="/static/balizero-logo-clean.png"
                alt="Bali Zero"
                className="mx-auto h-28 w-28 rounded-full shadow-2xl shadow-[#c23c2c]/20"
              />
              <div className="pt-4 text-xs font-semibold uppercase tracking-[0.3em] text-[#c23c2c]">
                Bali Zero · Round 2
              </div>
              <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
                Written Assessment
              </h1>
              <p className="text-white/50">{ROLE}</p>
            </div>

            <div className="space-y-4 rounded-lg border border-white/[0.06] bg-white/[0.03] p-6">
              <p className="text-white/75">
                Welcome,{" "}
                <span className="font-medium text-white">{CANDIDATE}</span>.
              </p>
              <p className="text-sm text-white/60">
                Four exercises, {TOTAL_MINUTES} minutes in total. Each exercise
                opens in its own timed window; when the window closes, that
                exercise is sent and the next one opens. You cannot go back.
                Every candidate for this vacancy receives this same pack, so
                that the results compare.
              </p>
              <ul className="space-y-2 pt-2 text-sm">
                {EXERCISES.map((e) => (
                  <li key={e.key} className="flex items-baseline gap-3">
                    <span className="w-4 shrink-0 font-mono text-[#c23c2c]">
                      {e.letter}
                    </span>
                    <span className="text-white/80">{e.title}</span>
                    <span className="ml-auto font-mono text-xs text-white/40">
                      {e.minutes} min
                    </span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="space-y-3 rounded-lg border border-amber-400/20 bg-amber-400/[0.04] p-6 text-sm text-white/70">
              <div className="text-xs font-semibold uppercase tracking-[0.2em] text-amber-400/90">
                Please read — what this page records
              </div>
              <p>
                This is an unaided written test. Pasting is disabled. The page
                records how long each exercise takes, how much of it is typed,
                whether text arrives without being typed, and whether the tab is
                left during an exercise. It records those measurements alongside
                your answers and sends both to the panel. It does not record
                your screen, your camera, or anything outside this page.
              </p>
              <p>
                Write in your own words. If you use a phone, another tab, or an
                AI assistant, the measurements will show it and we would rather
                you simply did not.
              </p>
              <p className="text-white/50">
                Exercises A, B and D may be answered in English or Bahasa
                Indonesia. Exercise C must be in English — the English is the
                exercise. If an instruction is unclear, ask the panel; for
                Exercise C we will not explain wording.
              </p>
            </div>

            {restored && (
              <p className="text-sm text-amber-400/80">
                A previous session was found in this browser and your answers
                have been restored. You are resuming at Exercise{" "}
                {EXERCISES[index].letter}.
              </p>
            )}

            <button
              onClick={begin}
              className="w-full rounded-lg bg-[#c23c2c] px-6 py-4 text-base font-semibold text-white transition hover:bg-[#a83326] focus:outline-none focus:ring-2 focus:ring-[#c23c2c]/50"
            >
              Start Exercise {exercise.letter} — {exercise.minutes} minutes
            </button>
            <p className="text-center text-xs text-white/30">
              The countdown starts the moment you press this button.
            </p>
          </div>
        )}

        {/* ── RUNNING ───────────────────────────────────────────── */}
        {phase === "running" && (
          <div className="space-y-8">
            <div className="flex items-center gap-3 text-xs text-white/35">
              {EXERCISES.map((e, i) => (
                <span
                  key={e.key}
                  className={`rounded px-2 py-1 font-mono ${
                    i === index
                      ? "bg-[#c23c2c]/20 text-[#e8a79c]"
                      : submitted.includes(e.key)
                        ? "text-white/30 line-through"
                        : "text-white/20"
                  }`}
                >
                  {e.letter}
                </span>
              ))}
              <span className="ml-auto">
                Exercise {index + 1} of {EXERCISES.length}
              </span>
            </div>

            <div className="space-y-3">
              <div className="flex items-baseline gap-4">
                <span className="font-mono text-5xl font-bold text-[#c23c2c]">
                  {exercise.letter}
                </span>
                <div>
                  <h2 className="text-2xl font-semibold">{exercise.title}</h2>
                  <p className="text-xs uppercase tracking-[0.2em] text-white/35">
                    {exercise.minutes} minutes
                  </p>
                </div>
              </div>
              <p className="text-sm text-white/70">{exercise.intro}</p>
              <p className="text-xs text-amber-400/70">{exercise.language}</p>
            </div>

            {exercise.key === "A" && (
              <div className="space-y-6">
                <LedgerTable
                  caption="Bank statement — BCA · July 2026 · Sunset Villas & Kitchen"
                  rows={BANK_ROWS}
                  closing="Closing balance per bank statement, 31/07/2026 — 133.750.000"
                />
                <LedgerTable
                  caption="Cash book — July 2026, kept by the client's staff"
                  rows={CASHBOOK_ROWS}
                  closing="Closing balance per cash book, 31/07/2026 — 116.385.000"
                />
                <p className="rounded border border-white/10 bg-white/[0.02] p-3 text-xs text-white/50">
                  The merchant discount rate on the restaurant&apos;s card
                  terminal is 2% of gross card sales.
                </p>
              </div>
            )}

            {exercise.key === "B" && (
              <div className="overflow-x-auto rounded-lg border border-white/10">
                <table className="w-full text-sm">
                  <caption className="px-4 py-3 text-left text-xs uppercase tracking-[0.2em] text-white/40">
                    Other expenses — ledger detail
                  </caption>
                  <thead className="bg-white/[0.04] text-xs uppercase tracking-wide text-white/40">
                    <tr>
                      <th className="px-4 py-2 text-left font-medium">Item</th>
                      <th className="px-4 py-2 text-right font-medium">
                        June (IDR)
                      </th>
                      <th className="px-4 py-2 text-right font-medium">
                        July (IDR)
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {OTHER_EXPENSES.map((r) => (
                      <tr key={r.item} className="border-t border-white/5">
                        <td className="px-4 py-2 text-white/75">{r.item}</td>
                        <td className="px-4 py-2 text-right font-mono tabular-nums text-white/60">
                          {r.june}
                        </td>
                        <td className="px-4 py-2 text-right font-mono tabular-nums text-white/60">
                          {r.july}
                        </td>
                      </tr>
                    ))}
                    <tr className="border-t border-white/20 font-semibold">
                      <td className="px-4 py-2">Total other expenses</td>
                      <td className="px-4 py-2 text-right font-mono tabular-nums">
                        8.400.000
                      </td>
                      <td className="px-4 py-2 text-right font-mono tabular-nums">
                        11.760.000
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            )}

            {exercise.key === "C" && (
              <div className="space-y-4">
                <div className="rounded-lg border border-white/10 bg-white/[0.02] p-5 font-mono text-sm leading-relaxed text-white/70">
                  <div className="mb-3 space-y-0.5 text-xs text-white/40">
                    <div>From: g.ferrari@&lt;client&gt;.it</div>
                    <div>Sent: 21:40</div>
                    <div>Subject: Invoice — this is not acceptable</div>
                  </div>
                  <p className="whitespace-pre-wrap">
                    {`Why is my monthly invoice higher than last month? Nobody told me
about extra costs. I need an answer tonight, I have a payment
deadline tomorrow and this is the second time this happens.`}
                  </p>
                </div>
                <div className="rounded border border-white/10 bg-white/[0.02] p-4 text-xs text-white/55">
                  <div className="mb-1 uppercase tracking-[0.2em] text-white/35">
                    What you know, and what you do not
                  </div>
                  The increase is a legitimate pass-through charge and it was
                  disclosed in the engagement letter he signed. The colleague
                  who normally handles this client is unavailable until tomorrow
                  morning, so you cannot confirm the exact figure tonight.
                </div>
              </div>
            )}

            <div className="space-y-6">
              {exercise.fields.map((f) => {
                const value = answers[f.id] || "";
                const shared = {
                  value,
                  onFocus: () => onFocus(f.id),
                  onKeyDown: (e: React.KeyboardEvent) => onKeyDown(f.id, e),
                  onPaste: (e: React.ClipboardEvent) => onPaste(f.id, e),
                  onCopy: () => onCopy(f.id, "copy"),
                  onCut: () => onCopy(f.id, "cut"),
                  onDrop: (e: React.DragEvent) => e.preventDefault(),
                  spellCheck: false,
                  autoComplete: "off",
                  disabled: sending,
                };
                return (
                  <div key={f.id} className="space-y-2">
                    <label
                      htmlFor={f.id}
                      className="block whitespace-pre-wrap text-sm font-medium text-white/85"
                    >
                      {f.label}
                    </label>
                    {f.hint && (
                      <p className="font-mono text-xs text-white/35">
                        {f.hint}
                      </p>
                    )}
                    {f.short ? (
                      <input
                        id={f.id}
                        type="text"
                        {...shared}
                        onChange={(e) => onChange(f.id, e.target.value)}
                        placeholder={f.placeholder}
                        className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-white/90 placeholder:text-white/20 focus:border-[#c23c2c]/60 focus:outline-none"
                      />
                    ) : (
                      <textarea
                        id={f.id}
                        rows={f.id === "c_reply" ? 14 : 6}
                        {...shared}
                        onChange={(e) => onChange(f.id, e.target.value)}
                        placeholder={f.placeholder}
                        className="w-full resize-y rounded-lg border border-white/10 bg-white/[0.03] px-4 py-3 font-mono text-sm leading-relaxed text-white/90 placeholder:text-white/20 focus:border-[#c23c2c]/60 focus:outline-none"
                      />
                    )}
                    <div className="text-right font-mono text-[11px] text-white/25">
                      {countWords(value)} words · {value.length} characters
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="space-y-3 border-t border-white/5 pt-6">
              <button
                onClick={() => submitExercise(false)}
                disabled={sending || !answeredSomething}
                className="w-full rounded-lg bg-[#c23c2c] px-6 py-4 font-semibold text-white transition hover:bg-[#a83326] disabled:cursor-not-allowed disabled:bg-white/10 disabled:text-white/30"
              >
                {sending
                  ? "Sending…"
                  : index < EXERCISES.length - 1
                    ? `Submit ${exercise.letter} and open ${EXERCISES[index + 1].letter}`
                    : `Submit ${exercise.letter} and finish`}
              </button>
              <p className="text-center text-xs text-white/30">
                Submitting is final for this exercise. When the countdown
                reaches zero it submits on its own.
              </p>
            </div>
          </div>
        )}

        {/* ── DONE ──────────────────────────────────────────────── */}
        {phase === "done" && (
          <div className="space-y-6 py-16 text-center">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/static/balizero-logo-clean.png"
              alt="Bali Zero"
              className="mx-auto h-24 w-24 rounded-full opacity-80"
            />
            <h2 className="text-2xl font-semibold">Assessment complete</h2>
            <p className="mx-auto max-w-md text-sm text-white/60">
              All four exercises have been sent to the panel. Thank you,{" "}
              {CANDIDATE} — please close this tab and rejoin the room. The
              conversation follows.
            </p>
            <p className="font-mono text-xs text-white/25">{wita()} WITA</p>
          </div>
        )}
      </main>

      <footer className="border-t border-white/5 px-6 py-6 text-center text-xs text-white/25">
        balizero.com · internal use · all figures in this assessment are
        invented and describe no Bali Zero client
      </footer>
    </div>
  );
}

function LedgerTable({
  caption,
  rows,
  closing,
}: {
  caption: string;
  rows: {
    date: string;
    description: string;
    amount: string;
    balance: string;
  }[];
  closing: string;
}) {
  return (
    <div className="overflow-x-auto rounded-lg border border-white/10">
      <table className="w-full text-sm">
        <caption className="px-4 py-3 text-left text-xs uppercase tracking-[0.2em] text-white/40">
          {caption}
        </caption>
        <thead className="bg-white/[0.04] text-xs uppercase tracking-wide text-white/40">
          <tr>
            <th className="px-3 py-2 text-left font-medium">Date</th>
            <th className="px-3 py-2 text-left font-medium">Description</th>
            <th className="px-3 py-2 text-right font-medium">Amount</th>
            <th className="px-3 py-2 text-right font-medium">Balance</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={`${r.date}-${i}`} className="border-t border-white/5">
              <td className="whitespace-nowrap px-3 py-1.5 font-mono text-white/45">
                {r.date}
              </td>
              <td className="px-3 py-1.5 text-white/75">{r.description}</td>
              <td className="whitespace-nowrap px-3 py-1.5 text-right font-mono tabular-nums text-white/60">
                {r.amount}
              </td>
              <td className="whitespace-nowrap px-3 py-1.5 text-right font-mono tabular-nums text-white/45">
                {r.balance}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="border-t border-white/15 px-4 py-2.5 text-right font-mono text-xs text-white/70">
        {closing}
      </div>
    </div>
  );
}
