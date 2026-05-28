import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  getRemainingQuestions,
  getSession,
  getVisaResults,
  hasQuestionsRemaining,
  incrementQuestions,
  MAX_QUESTIONS,
  saveVisaResults,
  STORAGE_KEY,
} from "./storage";

const NOW = new Date("2026-05-23T04:00:00.000Z");
const ONE_DAY_MS = 24 * 60 * 60 * 1000;
const SESSION_ID_PATTERN = new RegExp(`^vo_${NOW.getTime()}_[a-z0-9]+$`);

function storedSession(): unknown {
  const raw = window.localStorage.getItem(STORAGE_KEY);
  return raw ? JSON.parse(raw) : null;
}

describe("visa oracle storage", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
    vi.spyOn(Math, "random").mockReturnValue(0.123456789);
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  it("creates and persists a new session when none exists", () => {
    const session = getSession();

    expect(session).toEqual({
      sessionId: expect.stringMatching(SESSION_ID_PATTERN),
      questionsUsed: 0,
      createdAt: NOW.getTime(),
    });
    expect(storedSession()).toEqual(session);
  });

  it("returns an existing unexpired session without replacing it", () => {
    const existing = {
      sessionId: "vo_existing",
      questionsUsed: 2,
      createdAt: NOW.getTime() - 60_000,
    };
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(existing));

    expect(getSession()).toEqual(existing);
    expect(storedSession()).toEqual(existing);
  });

  it("replaces expired or corrupted sessions with a fresh one", () => {
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        sessionId: "vo_expired",
        questionsUsed: 3,
        createdAt: NOW.getTime() - ONE_DAY_MS - 1,
      }),
    );

    const expiredReplacement = getSession();

    expect(expiredReplacement.sessionId).not.toBe("vo_expired");
    expect(expiredReplacement.questionsUsed).toBe(0);

    window.localStorage.setItem(STORAGE_KEY, "{bad json");

    const corruptedReplacement = getSession();

    expect(corruptedReplacement).toEqual({
      sessionId: expect.stringMatching(SESSION_ID_PATTERN),
      questionsUsed: 0,
      createdAt: NOW.getTime(),
    });
    expect(storedSession()).toEqual(corruptedReplacement);
  });

  it("increments the question count and clamps remaining questions at zero", () => {
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        sessionId: "vo_existing",
        questionsUsed: MAX_QUESTIONS - 1,
        createdAt: NOW.getTime(),
      }),
    );

    const updated = incrementQuestions();

    expect(updated).toEqual({
      sessionId: "vo_existing",
      questionsUsed: MAX_QUESTIONS,
      createdAt: NOW.getTime(),
    });
    expect(getRemainingQuestions()).toBe(0);
    expect(hasQuestionsRemaining()).toBe(false);

    const exhausted = incrementQuestions();

    expect(exhausted.questionsUsed).toBe(MAX_QUESTIONS + 1);
    expect(getRemainingQuestions()).toBe(0);
  });

  it("stores visa results in session storage and falls back to an empty list", () => {
    const visas = [{ type: "E33G" }, { type: "C1" }];

    expect(getVisaResults()).toEqual([]);

    saveVisaResults(visas);

    expect(getVisaResults()).toEqual(visas);

    window.sessionStorage.setItem("visa_oracle_results", "{bad json");

    expect(getVisaResults()).toEqual([]);
  });
});
