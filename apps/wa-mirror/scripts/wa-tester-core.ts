// wa-tester-core.ts — pure, unit-testable logic for wa-tester.
//
// Deliberately kept OUTSIDE bridge/ (the read-only mirror organ). wa-tester
// is a separate, single-purpose tool: it sends test messages from Zero's own
// WhatsApp number to the Zantara bot and records the replies. Nothing in
// here touches Postgres, the CRM, Telegram, or the wa-mirror sessions/
// roster — see docs/wa-tester.md for the full boundary.
//
// Everything in this file is a pure function or a pure state machine (no
// I/O, no Baileys socket, no clock reads except via injected `nowMs`
// parameters) so it can be unit-tested without a live WhatsApp connection.
// The live-socket glue lives in scripts/wa-tester.ts and imports from here.

import { parseJid } from "../bridge/filters.js";
import { normalizePhone, phoneDigits } from "../bridge/phone.js";

// ---------------------------------------------------------------------------
// THE ONE RULE — hardcoded recipient allowlist.
//
// wa-tester runs from Zero's REAL WhatsApp number. The one thing that makes
// that safe is that it can NEVER send to anyone but the Zantara bot. This
// constant is not read from a flag, env var, or config file anywhere in this
// tool — grep the repo for BOT_PHONE_E164 if you doubt it.
// ---------------------------------------------------------------------------
export const BOT_PHONE_E164 = "+628213465159"; // Zantara WA bot (+62 821 3465 159)
export const BOT_PHONE_DIGITS = "628213465159";
export const BOT_JID = `${BOT_PHONE_DIGITS}@s.whatsapp.net`;

// Zero's own number — used ONLY to derive the default auth-state path and
// the QR filename. NEVER used as a send target.
export const TESTER_PHONE_E164 = "+6282230102328"; // +62 822 3010 2328
export const TESTER_PHONE_DIGITS = "6282230102328";

export const DEFAULT_REPLY_TIMEOUT_S = 90;
export const DEFAULT_INTER_QUESTION_DELAY_S = 20;
export const QUIET_PERIOD_S = 10;

// ---------------------------------------------------------------------------
// Recipient allowlist guard
// ---------------------------------------------------------------------------

/** Keys a battery author might (mistakenly or maliciously) use to try to
 * redirect a send to a different number. Checked at the battery root AND on
 * every question object. Any OTHER key is ignored — this guard only fires
 * on fields that are plausibly "who do we send this to". */
const RECIPIENT_LOOKALIKE_KEYS = [
  "to",
  "recipient",
  "jid",
  "phone",
  "number",
  "target",
  "send_to",
] as const;

/**
 * True if `value` (E.164, bare digits, local 0-prefixed, or a JID string
 * like "628213465159@s.whatsapp.net") resolves to the hardcoded bot number.
 * Fails CLOSED: anything that cannot be confidently matched is NOT the bot.
 */
export function matchesBotRecipient(value: string): boolean {
  const jidPart = value.includes("@")
    ? value.split("@")[0].split(":")[0]
    : value;
  const normalized = normalizePhone(jidPart);
  if (normalized && phoneDigits(normalized) === BOT_PHONE_DIGITS) return true;
  const rawDigits = jidPart.replace(/\D/g, "");
  return rawDigits.length > 0 && rawDigits === BOT_PHONE_DIGITS;
}

// ---------------------------------------------------------------------------
// Receive-side matcher — scar #3 UNDER-match (WhatsApp LID rollout).
//
// `matchesBotRecipient` above is the SEND-side guard: it only ever sees a
// battery author's plain value (phone/JID string), never a live Baileys
// remoteJid. Receive-side used to do `m.key.remoteJid !== BOT_JID` — strict
// string equality against the bot's `@s.whatsapp.net` phone-JID. Under
// WhatsApp's `@lid` (Linked Identity Device) rollout, the SAME bot
// conversation can arrive tagged with an opaque `@lid` identifier instead
// of the phone-JID (Baileys reassigns this per-session, not something the
// tester controls) — the strict `!==` silently drops every reply that
// arrives that way, producing `reply_count: 0` even though the bot answered
// (verified against Postgres ground truth). This is the classic guard
// UNDER-match: the check watches one literal form and goes quiet when the
// same fact shows up in another form.
// ---------------------------------------------------------------------------

/**
 * True if `remoteJid` is the bot's own conversation — either directly (the
 * phone-JID form) or via a `@lid` JID that `resolvedLidPhoneE164` (an
 * out-of-band Baileys `signalRepository.lidMapping.getPNForLID` lookup,
 * performed by the live-socket caller) resolved to the bot's number.
 *
 * Fails CLOSED like `matchesBotRecipient`: an unresolved or non-matching LID
 * (`resolvedLidPhoneE164` null/other) is NOT the bot — a reply from some
 * other contact must never be misattributed to the bot just because both
 * arrived as LIDs.
 */
export function isBotReplyJid(
  remoteJid: string | null | undefined,
  resolvedLidPhoneE164: string | null,
): boolean {
  const parsed = parseJid(remoteJid);
  if (parsed.kind === "phone") {
    return phoneDigits(parsed.phone) === BOT_PHONE_DIGITS;
  }
  if (parsed.kind === "lid") {
    if (!resolvedLidPhoneE164) return false;
    return phoneDigits(resolvedLidPhoneE164) === BOT_PHONE_DIGITS;
  }
  return false;
}

export type AllowlistViolation = { ok: false; error: string };
export type AllowlistOk = { ok: true };

/**
 * Scans one object (battery root or a single question) for any
 * recipient-lookalike field and refuses if it does not resolve to the bot.
 * Called BEFORE any send — see validateBattery below.
 */
export function checkRecipientAllowlist(
  obj: Record<string, unknown>,
  ctx: string,
): AllowlistOk | AllowlistViolation {
  for (const key of RECIPIENT_LOOKALIKE_KEYS) {
    if (!(key in obj)) continue;
    const val = obj[key];
    if (typeof val !== "string" || val.trim() === "") continue;
    if (!matchesBotRecipient(val)) {
      return {
        ok: false,
        error:
          `${ctx}: field '${key}'=${JSON.stringify(val)} does not resolve to the ` +
          `hardcoded bot recipient (${BOT_PHONE_E164}) — refusing to send. ` +
          "wa-tester allows ONLY the Zantara bot number, no exceptions, no override.",
      };
    }
  }
  return { ok: true };
}

// ---------------------------------------------------------------------------
// Battery parsing / validation
// ---------------------------------------------------------------------------

export type BatteryQuestion = { id: string; text: string };

export type Battery = {
  questions: BatteryQuestion[];
  reply_timeout_s: number;
  inter_question_delay_s: number;
};

export type ValidateBatteryResult =
  | { ok: true; battery: Battery }
  | { ok: false; error: string };

function coercePositiveNumber(value: unknown, fallback: number): number {
  if (typeof value === "number" && Number.isFinite(value) && value > 0)
    return value;
  return fallback;
}

export function validateBattery(raw: unknown): ValidateBatteryResult {
  if (typeof raw !== "object" || raw === null || Array.isArray(raw)) {
    return { ok: false, error: "battery: root must be a JSON object" };
  }
  const obj = raw as Record<string, unknown>;

  const rootGuard = checkRecipientAllowlist(obj, "battery");
  if (!rootGuard.ok) return rootGuard;

  if (!Array.isArray(obj.questions) || obj.questions.length === 0) {
    return {
      ok: false,
      error: "battery: 'questions' must be a non-empty array",
    };
  }

  const questions: BatteryQuestion[] = [];
  const seenIds = new Set<string>();
  for (let i = 0; i < obj.questions.length; i++) {
    const q = obj.questions[i];
    if (typeof q !== "object" || q === null || Array.isArray(q)) {
      return { ok: false, error: `battery.questions[${i}]: must be an object` };
    }
    const qObj = q as Record<string, unknown>;

    const qGuard = checkRecipientAllowlist(qObj, `battery.questions[${i}]`);
    if (!qGuard.ok) return qGuard;

    if (typeof qObj.id !== "string" || qObj.id.trim() === "") {
      return {
        ok: false,
        error: `battery.questions[${i}]: 'id' must be a non-empty string`,
      };
    }
    if (typeof qObj.text !== "string" || qObj.text.trim() === "") {
      return {
        ok: false,
        error: `battery.questions[${i}]: 'text' must be a non-empty string`,
      };
    }
    if (seenIds.has(qObj.id)) {
      return {
        ok: false,
        error: `battery.questions[${i}]: duplicate id '${qObj.id}'`,
      };
    }
    seenIds.add(qObj.id);
    questions.push({ id: qObj.id, text: qObj.text });
  }

  return {
    ok: true,
    battery: {
      questions,
      reply_timeout_s: coercePositiveNumber(
        obj.reply_timeout_s,
        DEFAULT_REPLY_TIMEOUT_S,
      ),
      inter_question_delay_s: coercePositiveNumber(
        obj.inter_question_delay_s,
        DEFAULT_INTER_QUESTION_DELAY_S,
      ),
    },
  };
}

// ---------------------------------------------------------------------------
// Reply collection — quiet-period state machine
// ---------------------------------------------------------------------------

export type CollectedReply = { text: string; timestampMs: number };

export type CollectorVerdict = "collecting" | "stop_quiet" | "stop_timeout";

/**
 * Pure decision engine for "have we collected enough replies to this
 * question yet?". No clock reads, no timers — the caller (live socket code
 * or a test) supplies `nowMs` and reply events explicitly.
 *
 * Rule: keep collecting until EITHER
 *   (a) reply_timeout_s has elapsed since sent_at with ZERO replies (hard
 *       timeout, question is answered with 0 replies), or
 *   (b) at least one reply has arrived AND quiet_period_s has elapsed since
 *       the LAST reply (quiet-period complete), or
 *   (c) reply_timeout_s has elapsed since sent_at regardless of reply count
 *       (safety cap — never wait past the hard timeout even mid-quiet-window).
 */
export class ReplyCollector {
  private readonly replies: CollectedReply[] = [];
  private readonly sentAtMs: number;
  private readonly hardTimeoutMs: number;
  private readonly quietPeriodMs: number;

  constructor(opts: {
    sentAtMs: number;
    replyTimeoutS: number;
    quietPeriodS?: number;
  }) {
    this.sentAtMs = opts.sentAtMs;
    this.hardTimeoutMs = opts.replyTimeoutS * 1000;
    this.quietPeriodMs = (opts.quietPeriodS ?? QUIET_PERIOD_S) * 1000;
  }

  addReply(text: string, timestampMs: number): void {
    this.replies.push({ text, timestampMs });
  }

  get count(): number {
    return this.replies.length;
  }

  get all(): CollectedReply[] {
    return [...this.replies];
  }

  verdict(nowMs: number): CollectorVerdict {
    const elapsedSinceSent = nowMs - this.sentAtMs;
    if (this.replies.length === 0) {
      return elapsedSinceSent >= this.hardTimeoutMs
        ? "stop_timeout"
        : "collecting";
    }
    if (elapsedSinceSent >= this.hardTimeoutMs) return "stop_timeout";
    const lastReplyAt = this.replies[this.replies.length - 1].timestampMs;
    const quietElapsed = nowMs - lastReplyAt;
    return quietElapsed >= this.quietPeriodMs ? "stop_quiet" : "collecting";
  }
}

// ---------------------------------------------------------------------------
// Reconnect bookkeeping (pure) — used by --pair's bounded 515 reconnect
// ---------------------------------------------------------------------------

/** Should the live socket reconnect after a `connection: "close"` event?
 * `terminal` must come from bridge/session.js's isTerminalCloseCode — this
 * function only owns the bounded-attempt-count decision, not the Baileys
 * close-code classification (never duplicate that logic; import it). */
export function shouldReconnect(params: {
  terminal: boolean;
  attempt: number;
  maxAttempts: number;
}): boolean {
  if (params.terminal) return false;
  return params.attempt < params.maxAttempts;
}

// ---------------------------------------------------------------------------
// Message text extraction (loose Baileys duck-typing, mirrors the local
// convention in bridge/message_capture.ts's private extractBody — kept as a
// SEPARATE small copy here rather than exporting from bridge/, since bridge/
// stays byte-identical/untouched per the read-only-mirror invariant).
// ---------------------------------------------------------------------------

type LooseMessageShape = {
  conversation?: string | null;
  extendedTextMessage?: { text?: string | null } | null;
};

export function extractMessageText(message: unknown): string {
  const m = (message ?? {}) as LooseMessageShape;
  if (typeof m.conversation === "string" && m.conversation.length > 0) {
    return m.conversation;
  }
  if (
    typeof m.extendedTextMessage?.text === "string" &&
    m.extendedTextMessage.text.length > 0
  ) {
    return m.extendedTextMessage.text;
  }
  return "";
}

/** Mirrors bridge/message_capture.ts's private parseTimestamp — same
 * Baileys messageTimestamp shape (number | numeric-string | Long-like). */
export function parseMessageTimestampMs(
  value: number | string | { toNumber?: () => number } | null | undefined,
): number {
  if (typeof value === "number") return value * 1000;
  if (typeof value === "string") {
    const n = Number(value);
    return Number.isFinite(n) ? n * 1000 : Date.now();
  }
  if (value && typeof value.toNumber === "function") {
    return value.toNumber() * 1000;
  }
  return Date.now();
}

// ---------------------------------------------------------------------------
// Transcript assembly
// ---------------------------------------------------------------------------

export type QuestionResult = {
  id: string;
  text: string;
  sent_at: string; // ISO 8601
  replies: { text: string; timestamp: string; latency_ms: number }[];
  reply_count: number;
  first_reply_latency_ms: number | null;
};

export function buildQuestionResult(
  question: BatteryQuestion,
  sentAtMs: number,
  replies: CollectedReply[],
): QuestionResult {
  const repliesOut = replies.map((r) => ({
    text: r.text,
    timestamp: new Date(r.timestampMs).toISOString(),
    latency_ms: r.timestampMs - sentAtMs,
  }));
  return {
    id: question.id,
    text: question.text,
    sent_at: new Date(sentAtMs).toISOString(),
    replies: repliesOut,
    reply_count: repliesOut.length,
    first_reply_latency_ms:
      repliesOut.length > 0 ? repliesOut[0].latency_ms : null,
  };
}

export type Transcript = {
  battery_file: string;
  bot_jid: string;
  started_at: string;
  finished_at: string;
  questions: QuestionResult[];
  summary: {
    total_questions: number;
    questions_with_zero_replies: number;
  };
};

export function buildTranscript(opts: {
  batteryFile: string;
  botJid: string;
  startedAtMs: number;
  finishedAtMs: number;
  results: QuestionResult[];
}): Transcript {
  const zeroReplyCount = opts.results.filter((r) => r.reply_count === 0).length;
  return {
    battery_file: opts.batteryFile,
    bot_jid: opts.botJid,
    started_at: new Date(opts.startedAtMs).toISOString(),
    finished_at: new Date(opts.finishedAtMs).toISOString(),
    questions: opts.results,
    summary: {
      total_questions: opts.results.length,
      questions_with_zero_replies: zeroReplyCount,
    },
  };
}

export function transcriptHasZeroReplyQuestion(
  transcript: Transcript,
): boolean {
  return transcript.summary.questions_with_zero_replies > 0;
}

// ---------------------------------------------------------------------------
// Pairing-state detection (pure) — used by --status / --send-battery's
// isPaired() gate in scripts/wa-tester.ts.
// ---------------------------------------------------------------------------

export type StoredCreds = { registered?: boolean; me?: { id?: string } };

/**
 * True if the on-disk creds.json indicates a paired session, under EITHER
 * Baileys pairing flow. `registered` is set only by the pairing-CODE flow;
 * QR-companion pairing (the flow wa-tester's `--pair` actually drives) sets
 * `creds.me` instead and leaves `registered: false` — a session paired via
 * QR is very much paired even though `registered` reads false.
 */
export function isPairedFromCreds(creds: StoredCreds): boolean {
  return creds.registered === true || typeof creds.me?.id === "string";
}
