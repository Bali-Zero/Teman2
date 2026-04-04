const STORAGE_KEY = "visa_oracle_session";
const MAX_QUESTIONS = 3;
const SESSION_TTL_MS = 24 * 60 * 60 * 1000; // 24 hours

interface SessionData {
  sessionId: string;
  questionsUsed: number;
  createdAt: number;
}

function generateSessionId(): string {
  return `vo_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

function isSessionExpired(session: SessionData): boolean {
  return Date.now() - session.createdAt > SESSION_TTL_MS;
}

function createNewSession(): SessionData {
  return {
    sessionId: generateSessionId(),
    questionsUsed: 0,
    createdAt: Date.now(),
  };
}

function saveSession(session: SessionData): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  } catch {
    // localStorage unavailable (private mode, quota exceeded, etc.)
  }
}

export function getSession(): SessionData {
  if (typeof window === "undefined") {
    return createNewSession();
  }

  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const session = JSON.parse(raw) as SessionData;
      if (!isSessionExpired(session)) {
        return session;
      }
    }
  } catch {
    // Corrupted data — fall through to create new session
  }

  const fresh = createNewSession();
  saveSession(fresh);
  return fresh;
}

export function incrementQuestions(): SessionData {
  const session = getSession();
  const updated: SessionData = {
    ...session,
    questionsUsed: session.questionsUsed + 1,
  };
  saveSession(updated);
  return updated;
}

export function getRemainingQuestions(): number {
  const session = getSession();
  return Math.max(0, MAX_QUESTIONS - session.questionsUsed);
}

export function hasQuestionsRemaining(): boolean {
  return getRemainingQuestions() > 0;
}

export { STORAGE_KEY, MAX_QUESTIONS };
export type { SessionData };
