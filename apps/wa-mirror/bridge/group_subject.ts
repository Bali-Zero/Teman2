// group_subject.ts — capture and backfill WhatsApp group names (subjects).
//
// PROBLEM (2026-06-30): every group in whatsapp_message_context had an empty
// `group_subject_snapshot`, so every dashboard rendered groups as the raw JID
// (`1203...@g.us`). Root cause: the bridge only subscribed to `messages.upsert`
// and hardcoded `groupSubject: null` in extractMessageRecord — the group name
// lives ONLY in Baileys `groupMetadata()` / `groupFetchAllParticipating()`,
// never in the message envelope, and nothing ever fetched it.
//
// This module is the fix:
//   - an in-memory Map<groupJid, subject> populated on connection open and on
//     `groups.update` events,
//   - read by extractMessageRecord so NEW rows persist a real subject,
//   - a one-shot DB backfill (hydrateAllGroupSubjects) that updates historical
//     rows for every group the connected account still participates in.
//
// Read-only toward WhatsApp (groupFetchAllParticipating / groupMetadata are
// fetches, never sends) — consistent with the bridge's read-only contract
// (session.ts:12). Defensive by design: nothing here throws into the event
// loop; a fetch failure degrades to "subject stays null" (the prior behaviour),
// never breaks message capture.

import type { Pool } from "pg";
import type { WASocket } from "@whiskeysockets/baileys";
import type { Logger } from "pino";

// Process-wide cache. extractMessageRecord (a pure sync fn with no socket
// access) reads this; session.ts writes it. Shared across all account sessions
// in the process — a group subject is the same regardless of which mirrored
// member observed it.
const groupSubjectCache = new Map<string, string>();

/** Read a cached group subject, or null if unknown. Pure, never throws. */
export function getGroupSubject(
  groupJid: string | null | undefined,
): string | null {
  if (!groupJid) return null;
  const s = groupSubjectCache.get(groupJid);
  return s && s.length > 0 ? s : null;
}

/** Cache one (jid, subject) pair if the subject is non-empty. */
export function setGroupSubject(
  groupJid: string,
  subject: string | null | undefined,
): void {
  if (!groupJid) return;
  if (subject && subject.trim().length > 0) {
    groupSubjectCache.set(groupJid, subject.trim());
  }
}

/**
 * Persist a single group's subject onto all historical rows for that JID that
 * still lack one. Idempotent; only fills empty/NULL snapshots (never clobbers a
 * subject already captured). Swallows DB errors to a warn — backfill must never
 * crash the session.
 */
async function persistGroupSubject(
  pool: Pool,
  groupJid: string,
  subject: string,
  logger: Logger,
): Promise<number> {
  try {
    const res = await pool.query(
      `UPDATE whatsapp_message_context
          SET group_subject_snapshot = $2
        WHERE group_jid = $1
          AND chat_type = 'group'
          AND COALESCE(group_subject_snapshot, '') = ''`,
      [groupJid, subject],
    );
    return res.rowCount ?? 0;
  } catch (err) {
    logger.warn(
      { groupJid, err: (err as Error).message },
      "wa-mirror group-subject DB backfill failed",
    );
    return 0;
  }
}

/**
 * One-shot hydration: fetch every group the connected account participates in,
 * cache each subject, and backfill historical rows. Called once per session on
 * connection open. A single `groupFetchAllParticipating()` returns all groups
 * with metadata, avoiding per-JID rate-limit pressure.
 *
 * Fully defensive: any failure logs a warn and returns — message capture is
 * unaffected, subjects simply stay as they were.
 */
export async function hydrateAllGroupSubjects(
  sock: WASocket,
  pool: Pool,
  logger: Logger,
): Promise<void> {
  let groups: Record<string, { subject?: string }>;
  try {
    groups = await sock.groupFetchAllParticipating();
  } catch (err) {
    logger.warn(
      { err: (err as Error).message },
      "wa-mirror groupFetchAllParticipating failed — group subjects not hydrated this session",
    );
    return;
  }

  const jids = Object.keys(groups);
  let cached = 0;
  let backfilledRows = 0;
  let backfilledGroups = 0;

  for (const jid of jids) {
    const subject = groups[jid]?.subject;
    if (!subject || subject.trim().length === 0) continue;
    setGroupSubject(jid, subject);
    cached += 1;
    const n = await persistGroupSubject(pool, jid, subject.trim(), logger);
    if (n > 0) {
      backfilledRows += n;
      backfilledGroups += 1;
    }
  }

  logger.info(
    {
      groupsFetched: jids.length,
      subjectsCached: cached,
      backfilledGroups,
      backfilledRows,
    },
    "wa-mirror group subjects hydrated",
  );
}

/**
 * Subscribe to live group rename events so the cache (and DB) stay current
 * after the initial hydration. `groups.update` carries partial group objects;
 * `groups.upsert` carries full ones on (re)join. Both are best-effort.
 *
 * Returns a disposer to unregister the listeners on connection close.
 */
export function attachGroupSubjectListeners(
  sock: WASocket,
  pool: Pool,
  logger: Logger,
): () => void {
  const onUpdate = (
    updates: Array<{ id?: string; subject?: string }>,
  ): void => {
    for (const u of updates) {
      if (u.id && u.subject && u.subject.trim().length > 0) {
        setGroupSubject(u.id, u.subject);
        void persistGroupSubject(pool, u.id, u.subject.trim(), logger);
      }
    }
  };
  const onUpsert = (groups: Array<{ id?: string; subject?: string }>): void => {
    for (const g of groups) {
      if (g.id && g.subject && g.subject.trim().length > 0) {
        setGroupSubject(g.id, g.subject);
        void persistGroupSubject(pool, g.id, g.subject.trim(), logger);
      }
    }
  };

  sock.ev.on("groups.update", onUpdate);
  sock.ev.on("groups.upsert", onUpsert);

  return () => {
    try {
      sock.ev.off("groups.update", onUpdate);
      sock.ev.off("groups.upsert", onUpsert);
    } catch {
      // socket may already be torn down
    }
  };
}
