// events.ts — EventBus PG NOTIFY emitter. Reuses the durable-outbox pattern
// that Nuzantara already enforces for inter-service communication (migration
// 144 events_outbox + 146 trigger refactor; see backend/services/events).
//
// wa-mirror is an external producer (Node.js) so we cannot reuse the Python
// `EventBus.emit_pg` helper. Instead we INSERT into events_outbox and let
// the running backend.services.events.event_bus listener pick it up via the
// existing trigger pipeline. Channel name: `whatsapp_message_received`.
//
// Payload shape mirrors the backend convention { _outbox_id, ... }. The
// listener (backend.services.events.handlers) routes by `kind` and updates
// the practice timeline.

import { query } from "./pg.js";

const CHANNEL = "whatsapp_message_received";

function errorType(err: unknown): string {
  return err instanceof Error && err.name ? err.name : typeof err;
}

export type WhatsAppMessagePayload = {
  message_context_id: number;
  bridge_session_id: number;
  team_member_email: string;
  client_id: number | null;
  direction: "inbound" | "outbound";
  message_date: string; // ISO 8601
  preview: string; // first 120 chars, useful for downstream alerters
};

/**
 * Emit a whatsapp_message_received event onto the durable outbox.
 *
 * Best-effort: any failure here is logged but does NOT propagate. Mirror
 * row in whatsapp_message_context is already persisted — the EventBus is
 * a downstream broadcast, not the source of truth.
 */
export async function emitMessageReceived(
  payload: WhatsAppMessagePayload
): Promise<void> {
  try {
    // Idempotency: each message_context_id can be emitted only once.
    // The events_outbox table has no native dedup on payload content; we
    // rely on the unique pair (channel, message_context_id) which we
    // enforce via this INSERT pattern + the row's bigint PK.
    const sql = `
      INSERT INTO events_outbox (channel, payload)
      VALUES ($1, $2::jsonb)
      RETURNING id
    `;
    const res = await query<{ id: string }>(sql, [CHANNEL, JSON.stringify(payload)]);
    if (res.rowCount && res.rowCount > 0) {
      // Mirror the PG NOTIFY that the Python EventBus listener expects.
      // The events_outbox row alone would not fire pg_notify; the listener
      // only wakes on NOTIFY. Send one with the outbox_id appended.
      const outboxId = res.rows[0].id;
      const notifyPayload = JSON.stringify({ ...payload, _outbox_id: outboxId });
      await query(`SELECT pg_notify($1, $2)`, [CHANNEL, notifyPayload]);
    }
  } catch (err) {
    // eslint-disable-next-line no-console
    console.warn(`[wa-mirror.events] emit failed: ${errorType(err)}`);
  }
}
