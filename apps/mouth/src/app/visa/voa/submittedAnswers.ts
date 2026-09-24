/**
 * The sessionStorage key the wizard hands its answers to the verdict screen
 * under, written just before the eligibility check is sent and stamped with
 * the result hash once the backend returns one. Separate from the wizard's
 * own resume key (`bz.garuda_voa.wizard`), which the wizard deletes on
 * completion — the verdict's decline mirror used to read that one, and so
 * always found it gone.
 *
 * sessionStorage, not localStorage: this is a same-tab hand-off to the one
 * screen the wizard is about to route to, not a return-visit feature, so it
 * should not outlive the tab. A TTL and a hash stamp narrow it further — a
 * visitor who runs a second check in the same tab, or opens a stale result
 * link the stored entry no longer belongs to, must never see an earlier
 * check's nationality/dates mirrored back as if they were this one's.
 */
export const SUBMITTED_ANSWERS_KEY = "bz.garuda_voa.submitted";

const TTL_MS = 30 * 60 * 1000;

interface SubmittedAnswersEntry {
  savedAt: number;
  hash?: string;
  values: Record<string, unknown>;
}

function readEntry(): SubmittedAnswersEntry | null {
  try {
    const raw = window.sessionStorage.getItem(SUBMITTED_ANSWERS_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as SubmittedAnswersEntry;
  } catch {
    return null;
  }
}

/** Written by the wizard, just before the eligibility check POSTs. Not yet stamped for any hash — the mirror stays omitted until {@link stampSubmittedAnswersHash} runs. */
export function writeSubmittedAnswers(values: Record<string, unknown>): void {
  try {
    const entry: SubmittedAnswersEntry = { savedAt: Date.now(), values };
    window.sessionStorage.setItem(SUBMITTED_ANSWERS_KEY, JSON.stringify(entry));
  } catch {
    /* private mode: the verdict simply omits the mirror line */
  }
}

/** Stamped once the POST returns a result hash — before that, the mirror cannot know which check it belongs to. */
export function stampSubmittedAnswersHash(hash: string): void {
  try {
    const entry = readEntry();
    if (!entry) return;
    entry.hash = hash;
    window.sessionStorage.setItem(SUBMITTED_ANSWERS_KEY, JSON.stringify(entry));
  } catch {
    /* nothing to stamp — the mirror stays omitted */
  }
}

/**
 * Read back for `hash`. Returns null (mirror omitted) unless the stored
 * entry is stamped for THIS hash and younger than the TTL — a different
 * hash means a later check ran in the same tab, and an expired entry is
 * retained data with no remaining use.
 */
export function readSubmittedAnswersForHash(
  hash: string,
): Record<string, unknown> | null {
  const entry = readEntry();
  if (!entry) return null;
  if (entry.hash !== hash) return null;
  if (Date.now() - entry.savedAt > TTL_MS) return null;
  return entry.values ?? null;
}

/** The self-service delete path: erase the mirror along with the check it describes — never an unrelated entry from another check in the same tab. */
export function clearSubmittedAnswersForHash(hash: string): void {
  try {
    const entry = readEntry();
    if (entry?.hash === hash) {
      window.sessionStorage.removeItem(SUBMITTED_ANSWERS_KEY);
    }
  } catch {
    /* nothing to clear */
  }
}
