// down-alarm.ts — announce the FAILURE TO RECOVER, never the disconnection.
//
// WHY THIS EXISTS (measured, not assumed).
//
// research/operations/2026-08-06-telegram-messaging-study.md §5.2 paired every
// bridge disconnection in a 29.5-day corpus with the next reconnection:
// 718 disconnections, 718 followed by a reconnection, median 1.0 min, 81% under
// 5 min, p90 25 min, max 358 min. Re-measured on the live spool 2026-08-08 over
// the whole retained window (2026-07-08..2026-08-07): 741 `wa-bridge:disconnected`
// + 725 `wa-bridge:connected` + 25 `wa-bridge:loggedout` = 1491 records, the
// second-loudest producer on the fleet at ~24-52 events/day.
//
// Every one of those 1466 non-terminal lines announced a condition that healed
// itself, usually within a minute — and the 358-minute tail, the one incident
// shape a human actually needs, was indistinguishable from the noise. The channel
// was reporting the SYMPTOM (a socket closed) instead of the FAULT (a line that
// is not coming back).
//
// So: hold the disconnection silently, and speak only if it OUTLASTS the
// threshold. A recovery inside the threshold says nothing at all — there is
// nothing for a reader to do about a socket that already reconnected. A recovery
// that closes an incident we DID announce is worth one digest line, because a
// reader who saw the alarm needs to know it ended.
//
// Terminal logout is NOT this path: `index.ts` announces it p0 and stops
// retrying, because no amount of waiting fixes a device unlinked on the phone.
// Registering it here too would have the still-down alarm re-announce, 25 minutes
// later, a condition already reported and already known to be terminal.
//
// The state is per-process and in memory: if the bridge restarts while a line is
// down, `downSince` is lost and the clock restarts from the next close. That is
// stated rather than hidden — a restart re-attempts the connection anyway, and a
// line still down will re-arm the alarm on its next close.

/** One account's open incident. Absent from the map == the line is up. */
export interface DownState {
  /** epoch ms of the first close of the CURRENT incident */
  downSince: number;
  /** true once the still-down alarm has fired for this incident */
  announced: boolean;
}

export type Verdict =
  | { speak: false }
  | { speak: true; kind: "still-down"; downMinutes: number }
  | { speak: true; kind: "recovered"; downMinutes: number };

const DEFAULT_THRESHOLD_MINUTES = 25;

/**
 * Minutes a line may be down before the alarm speaks. Default 25 = the p90 of
 * the measured recovery distribution, so ~10% of real incidents reach it.
 *
 * `WA_MIRROR_DOWN_ALERT_MINUTES=0` is a deliberate escape hatch: it restores
 * announce-on-every-disconnection. An unparseable or negative value falls back
 * to the default rather than silently disarming the alarm (a threshold of NaN
 * would make every comparison false and the organ mute — the exact failure this
 * module exists to end).
 */
export function thresholdMs(env: NodeJS.ProcessEnv = process.env): number {
  const raw = env.WA_MIRROR_DOWN_ALERT_MINUTES;
  if (raw === undefined || raw.trim() === "") {
    return DEFAULT_THRESHOLD_MINUTES * 60_000;
  }
  const parsed = Number(raw);
  if (!Number.isFinite(parsed) || parsed < 0) {
    return DEFAULT_THRESHOLD_MINUTES * 60_000;
  }
  return parsed * 60_000;
}

function elapsed(state: DownState, now: number): number {
  // A clock that moved backwards (NTP step, sleep/wake) must never produce a
  // negative duration: it would read as "recovered instantly" and mute the tail.
  return Math.max(0, now - state.downSince);
}

function minutes(ms: number): number {
  return Math.round(ms / 60_000);
}

/**
 * Record a close. Speaks at most ONCE per incident, and only when the line has
 * been down for at least `threshold`.
 *
 * `terminal` lives HERE, as an argument, rather than as an `if (!terminal)` at
 * the call site: the rule "a terminal logout never arms the still-down clock" is
 * then part of the tested unit instead of a comment above an untested branch — a
 * guard whose only statement is prose is a guard nobody proved (cicatrix W115).
 * A terminal close leaves NO state behind, so a later QR re-link connects
 * silently instead of reporting a recovery from an incident never announced.
 */
export function onDisconnected(
  states: Map<string, DownState>,
  account: string,
  now: number,
  threshold: number,
  opts: { terminal?: boolean } = {},
): Verdict {
  if (opts.terminal) return { speak: false };
  const state = states.get(account);
  if (!state) {
    states.set(account, { downSince: now, announced: false });
    // A zero threshold means "announce immediately" — honour it on the very
    // first close, otherwise the escape hatch would need a second close to fire.
    if (threshold <= 0) {
      const created = states.get(account) as DownState;
      created.announced = true;
      return { speak: true, kind: "still-down", downMinutes: 0 };
    }
    return { speak: false };
  }
  if (state.announced) return { speak: false };
  const downMs = elapsed(state, now);
  if (downMs < threshold) return { speak: false };
  state.announced = true;
  return { speak: true, kind: "still-down", downMinutes: minutes(downMs) };
}

/**
 * Record an open. Speaks only to CLOSE an incident that was announced; a
 * recovery nobody was told about is not news, and neither is the first connect
 * after a clean start (no state == nothing was ever down).
 */
export function onConnected(
  states: Map<string, DownState>,
  account: string,
  now: number,
): Verdict {
  const state = states.get(account);
  if (!state) return { speak: false };
  states.delete(account);
  if (!state.announced) return { speak: false };
  return {
    speak: true,
    kind: "recovered",
    downMinutes: minutes(elapsed(state, now)),
  };
}

/**
 * The one shared incident map. `session.ts` (close/open) and `index.ts` (crash
 * restart) must read the SAME state: two maps would let the crash path re-arm an
 * incident the close path already announced, which is how a cure applied to one
 * of several call sites reopens itself (cicatrix W107).
 */
export const downStates = new Map<string, DownState>();
