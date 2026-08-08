// down-alarm.test.ts — guilt AND innocence for "announce the failure to
// recover, never the disconnection".
//
// Guilt: a line that stays down past the threshold must speak, exactly once,
// with the right duration, and its recovery must close the incident.
// Innocence: the 81% of flaps that heal inside the threshold must produce ZERO
// messages, a clean first connect must be silent, and a terminal logout must
// never arm this clock (index.ts already reports it p0).
//
// Every clock value is injected. There is no timer and no sleep in this corpus:
// a test that waits 25 real minutes would be deleted by the first person in a
// hurry, and one that mocks Date.now() globally would not prove the module reads
// the time it is GIVEN.

import { describe, expect, it } from "vitest";

import type { DownState } from "../bridge/down-alarm.js";
import {
  onConnected,
  onDisconnected,
  thresholdMs,
} from "../bridge/down-alarm.js";

const MIN = 60_000;
const THRESHOLD = 25 * MIN;

function freshStates(): Map<string, DownState> {
  return new Map<string, DownState>();
}

describe("onDisconnected — guilt", () => {
  it("speaks once the line has been down past the threshold, naming the duration", () => {
    const s = freshStates();
    const t0 = 1_000_000;
    expect(onDisconnected(s, "ari", t0, THRESHOLD)).toEqual({ speak: false });
    // a retry 10 minutes in: still inside the recovery distribution, still silent
    expect(onDisconnected(s, "ari", t0 + 10 * MIN, THRESHOLD)).toEqual({
      speak: false,
    });
    expect(onDisconnected(s, "ari", t0 + 26 * MIN, THRESHOLD)).toEqual({
      speak: true,
      kind: "still-down",
      downMinutes: 26,
    });
  });

  it("speaks EXACTLY once per incident, however many retries follow", () => {
    const s = freshStates();
    const t0 = 0;
    onDisconnected(s, "ari", t0, THRESHOLD);
    const first = onDisconnected(s, "ari", t0 + 30 * MIN, THRESHOLD);
    expect(first.speak).toBe(true);
    for (const later of [40, 55, 120, 360]) {
      expect(onDisconnected(s, "ari", t0 + later * MIN, THRESHOLD)).toEqual({
        speak: false,
      });
    }
  });

  it("fires exactly AT the threshold, not one tick later", () => {
    const s = freshStates();
    onDisconnected(s, "ari", 0, THRESHOLD);
    expect(onDisconnected(s, "ari", THRESHOLD - 1, THRESHOLD)).toEqual({
      speak: false,
    });
    expect(onDisconnected(s, "ari", THRESHOLD, THRESHOLD)).toMatchObject({
      speak: true,
      kind: "still-down",
    });
  });

  it("tracks accounts independently — one line down does not mute another", () => {
    const s = freshStates();
    onDisconnected(s, "ari", 0, THRESHOLD);
    onDisconnected(s, "asya", 20 * MIN, THRESHOLD);
    expect(onDisconnected(s, "ari", 30 * MIN, THRESHOLD)).toMatchObject({
      speak: true,
    });
    // asya went down 10 minutes ago, not 30 — it must stay silent
    expect(onDisconnected(s, "asya", 30 * MIN, THRESHOLD)).toEqual({
      speak: false,
    });
  });

  it("re-arms for a NEW incident after a recovery", () => {
    const s = freshStates();
    onDisconnected(s, "ari", 0, THRESHOLD);
    expect(onDisconnected(s, "ari", 30 * MIN, THRESHOLD)).toMatchObject({
      speak: true,
    });
    expect(onConnected(s, "ari", 31 * MIN)).toMatchObject({
      speak: true,
      kind: "recovered",
    });
    // second incident, hours later
    onDisconnected(s, "ari", 200 * MIN, THRESHOLD);
    expect(onDisconnected(s, "ari", 240 * MIN, THRESHOLD)).toMatchObject({
      speak: true,
      kind: "still-down",
      downMinutes: 40,
    });
  });

  it("honours threshold=0 as the announce-immediately escape hatch", () => {
    const s = freshStates();
    expect(onDisconnected(s, "ari", 5_000, 0)).toEqual({
      speak: true,
      kind: "still-down",
      downMinutes: 0,
    });
    // and still only once — the escape hatch is not a licence to spam a wave
    expect(onDisconnected(s, "ari", 6_000, 0)).toEqual({ speak: false });
  });
});

describe("onDisconnected — innocence", () => {
  it("says NOTHING about a flap that heals inside the threshold", () => {
    const s = freshStates();
    // the measured median: 1.0 minute
    expect(onDisconnected(s, "ari", 0, THRESHOLD)).toEqual({ speak: false });
    expect(onConnected(s, "ari", 1 * MIN)).toEqual({ speak: false });
    expect(s.size).toBe(0);
  });

  it("never arms the clock on a TERMINAL close, and leaves no state behind", () => {
    const s = freshStates();
    expect(onDisconnected(s, "ari", 0, THRESHOLD, { terminal: true })).toEqual({
      speak: false,
    });
    expect(s.size).toBe(0);
    // 25 minutes of terminal retries would be a contradiction (retries stop),
    // but even if they happened, this path must stay mute: index.ts owns the p0.
    expect(
      onDisconnected(s, "ari", 30 * MIN, THRESHOLD, { terminal: true }),
    ).toEqual({ speak: false });
    // and a later QR re-link connects silently, not "recovered from" an
    // incident nobody was ever told about
    expect(onConnected(s, "ari", 40 * MIN)).toEqual({ speak: false });
  });

  it("a terminal close AFTER an announced incident cannot re-announce", () => {
    const s = freshStates();
    onDisconnected(s, "ari", 0, THRESHOLD);
    expect(onDisconnected(s, "ari", 30 * MIN, THRESHOLD)).toMatchObject({
      speak: true,
    });
    expect(
      onDisconnected(s, "ari", 60 * MIN, THRESHOLD, { terminal: true }),
    ).toEqual({ speak: false });
  });
});

describe("onConnected", () => {
  it("is silent on a clean first connect (nothing was ever down)", () => {
    const s = freshStates();
    expect(onConnected(s, "ari", 12345)).toEqual({ speak: false });
  });

  it("closes an ANNOUNCED incident with the total time down", () => {
    const s = freshStates();
    onDisconnected(s, "ari", 0, THRESHOLD);
    onDisconnected(s, "ari", 26 * MIN, THRESHOLD); // announces
    expect(onConnected(s, "ari", 91 * MIN)).toEqual({
      speak: true,
      kind: "recovered",
      downMinutes: 91,
    });
    expect(s.size).toBe(0);
  });

  it("is silent for an incident that was never announced", () => {
    const s = freshStates();
    onDisconnected(s, "ari", 0, THRESHOLD);
    onDisconnected(s, "ari", 5 * MIN, THRESHOLD); // still under the line
    expect(onConnected(s, "ari", 6 * MIN)).toEqual({ speak: false });
  });
});

describe("the shared incident map (cicatrix W107 — one cure, every call site)", () => {
  it("the crash-restart path cannot re-announce what the close path announced", () => {
    // session.ts (close) and index.ts (crash restart) pass the SAME map. Two
    // maps would let the same outage speak twice.
    const shared = freshStates();
    onDisconnected(shared, "ari", 0, THRESHOLD); // close path arms
    expect(onDisconnected(shared, "ari", 30 * MIN, THRESHOLD)).toMatchObject({
      speak: true,
    }); // close path announces
    expect(onDisconnected(shared, "ari", 31 * MIN, THRESHOLD)).toEqual({
      speak: false,
    }); // crash path, same incident
  });

  it("the crash-restart path can arm an incident the close path never saw", () => {
    const shared = freshStates();
    expect(onDisconnected(shared, "vino", 0, THRESHOLD)).toEqual({
      speak: false,
    });
    expect(onDisconnected(shared, "vino", 26 * MIN, THRESHOLD)).toMatchObject({
      speak: true,
      kind: "still-down",
    });
  });
});

describe("a clock that moves backwards", () => {
  it("never reports a negative duration and never speaks for it", () => {
    const s = freshStates();
    onDisconnected(s, "ari", 100 * MIN, THRESHOLD);
    // NTP step / sleep-wake: now is EARLIER than downSince
    expect(onDisconnected(s, "ari", 10 * MIN, THRESHOLD)).toEqual({
      speak: false,
    });
    const v = onConnected(s, "ari", 10 * MIN);
    expect(v.speak).toBe(false);
  });

  it("clamps the duration REPORTED when the recovery timestamp precedes the outage", () => {
    // This is the one place a negative duration is observable: the incident was
    // announced, so the recovery speaks — and it must not say "recovered after
    // -20m". Found by mutation: with the clamp removed, every other backwards-
    // clock assertion still passed, because a negative duration reads as "under
    // the threshold" and the module stays silent. A guard that is only ever
    // exercised through a silent path is not proven by the silence.
    const s = freshStates();
    onDisconnected(s, "ari", 0, THRESHOLD);
    expect(onDisconnected(s, "ari", 30 * MIN, THRESHOLD)).toMatchObject({
      speak: true,
    });
    expect(onConnected(s, "ari", -20 * MIN)).toEqual({
      speak: true,
      kind: "recovered",
      downMinutes: 0,
    });
  });

  it("a backwards clock does not corrupt a later honest measurement", () => {
    const s = freshStates();
    onDisconnected(s, "ari", 100 * MIN, THRESHOLD);
    onDisconnected(s, "ari", 10 * MIN, THRESHOLD); // backwards, silent
    expect(onDisconnected(s, "ari", 130 * MIN, THRESHOLD)).toEqual({
      speak: true,
      kind: "still-down",
      downMinutes: 30,
    });
  });
});

describe("thresholdMs", () => {
  it("defaults to 25 minutes — the p90 of the measured recovery distribution", () => {
    expect(thresholdMs({} as NodeJS.ProcessEnv)).toBe(25 * MIN);
    expect(
      thresholdMs({ WA_MIRROR_DOWN_ALERT_MINUTES: "" } as NodeJS.ProcessEnv),
    ).toBe(25 * MIN);
    expect(
      thresholdMs({ WA_MIRROR_DOWN_ALERT_MINUTES: "   " } as NodeJS.ProcessEnv),
    ).toBe(25 * MIN);
  });

  it("honours a valid override, including fractional minutes", () => {
    expect(
      thresholdMs({ WA_MIRROR_DOWN_ALERT_MINUTES: "5" } as NodeJS.ProcessEnv),
    ).toBe(5 * MIN);
    expect(
      thresholdMs({ WA_MIRROR_DOWN_ALERT_MINUTES: "0.5" } as NodeJS.ProcessEnv),
    ).toBe(30_000);
    expect(
      thresholdMs({ WA_MIRROR_DOWN_ALERT_MINUTES: "0" } as NodeJS.ProcessEnv),
    ).toBe(0);
  });

  it("falls back to the default rather than disarming on garbage", () => {
    // NaN would make every `downMs < threshold` comparison FALSE... and every
    // `>=` false too, so the organ would go mute. Silence is the one outcome a
    // watchdog may never choose by accident.
    for (const bad of ["abc", "NaN", "-5", "Infinity-ish", "1e"]) {
      expect(
        thresholdMs({
          WA_MIRROR_DOWN_ALERT_MINUTES: bad,
        } as NodeJS.ProcessEnv),
      ).toBe(25 * MIN);
    }
  });
});
