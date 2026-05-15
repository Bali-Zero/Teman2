// heartbeat.ts — whatsapp_team_sessions lifecycle.
//
// Each team member gets exactly one ACTIVE row at a time:
//   pending → (QR scanned) → connected → ... → disconnected | expired | revoked
//
// The lifecycle is owned here. Other modules call:
//   - openSession() once at process start (per team member)
//   - markConnected() after Baileys "open" event
//   - touch() on every successful message (updates last_seen_at + counters)
//   - markDisconnected() on Baileys "close" / "logout"

import { query } from "./pg.js";

export type SessionRow = {
  id: number;
  team_member_email: string;
  team_member_phone?: string;
  team_member_name?: string;
  phone_normalized: string;
  session_label: string;
  auth_state_path: string;
  status: "pending" | "connected" | "disconnected" | "expired" | "revoked";
};

/**
 * Open (or reopen) the unique active session row for this team member.
 *
 * If an active row already exists with the same team_member_email + phone,
 * reuse it (status returns to "pending" until we see Baileys "open").
 * Otherwise INSERT a new row.
 */
export async function openSession(opts: {
  teamMemberKey: string;
  teamMemberPhone: string;
  teamMemberName: string;
  phoneNormalized: string;
  sessionLabel: string;
  authStatePath: string;
}): Promise<SessionRow> {
  // 1. Try to find an existing non-final row for this team member.
  const findSql = `
    SELECT id, team_member_email, phone_normalized, session_label,
           auth_state_path, status
    FROM whatsapp_team_sessions
    WHERE team_member_email = $1
      AND status NOT IN ('disconnected', 'expired', 'revoked')
    ORDER BY created_at DESC
    LIMIT 1
  `;
  const existing = await query<SessionRow>(findSql, [opts.teamMemberKey]);
  if (existing.rowCount && existing.rowCount > 0) {
    const row = existing.rows[0];
    // Update auth path in case it moved on disk between restarts.
    await query(
      `UPDATE whatsapp_team_sessions
         SET auth_state_path = $1,
             phone_normalized = $2,
             session_label = $3,
             team_member_phone = $4,
             team_member_name = $5,
             status = 'pending',
             updated_at = NOW()
       WHERE id = $6`,
      [
        opts.authStatePath,
        opts.phoneNormalized,
        opts.sessionLabel,
        opts.teamMemberPhone,
        opts.teamMemberName,
        row.id,
      ]
    );
    return { ...row, status: "pending" };
  }

  // 2. Otherwise INSERT a fresh row.
  const insertSql = `
    INSERT INTO whatsapp_team_sessions
      (team_member_email, team_member_phone, team_member_name,
       phone_normalized, session_label, auth_state_path, status)
    VALUES ($1, $2, $3, $4, $5, $6, 'pending')
    RETURNING id, team_member_email, phone_normalized, session_label,
              auth_state_path, status
  `;
  const inserted = await query<SessionRow>(insertSql, [
    opts.teamMemberKey,
    opts.teamMemberPhone,
    opts.teamMemberName,
    opts.phoneNormalized,
    opts.sessionLabel,
    opts.authStatePath,
  ]);
  return inserted.rows[0];
}

export async function markConnected(sessionId: number): Promise<void> {
  await query(
    `UPDATE whatsapp_team_sessions
       SET status = 'connected',
           connected_at = COALESCE(connected_at, NOW()),
           last_seen_at = NOW(),
           disconnected_at = NULL,
           disconnect_reason = NULL,
           updated_at = NOW()
     WHERE id = $1`,
    [sessionId]
  );
}

export async function touch(sessionId: number): Promise<void> {
  await query(
    `UPDATE whatsapp_team_sessions
       SET last_seen_at = NOW(), updated_at = NOW()
     WHERE id = $1`,
    [sessionId]
  );
}

export async function incrementMessagesLogged(sessionId: number, by = 1): Promise<void> {
  await query(
    `UPDATE whatsapp_team_sessions
       SET messages_logged = messages_logged + $1,
           last_seen_at = NOW(),
           updated_at = NOW()
     WHERE id = $2`,
    [by, sessionId]
  );
}

export async function incrementMessagesFiltered(sessionId: number, by = 1): Promise<void> {
  await query(
    `UPDATE whatsapp_team_sessions
       SET messages_filtered = messages_filtered + $1,
           last_seen_at = NOW(),
           updated_at = NOW()
     WHERE id = $2`,
    [by, sessionId]
  );
}

export async function markDisconnected(
  sessionId: number,
  reason: string,
  newStatus: "disconnected" | "expired" | "revoked" = "disconnected"
): Promise<void> {
  await query(
    `UPDATE whatsapp_team_sessions
       SET status = $1,
           disconnected_at = NOW(),
           disconnect_reason = $2,
           updated_at = NOW()
     WHERE id = $3`,
    [newStatus, reason.slice(0, 64), sessionId]
  );
}
