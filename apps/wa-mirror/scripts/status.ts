// status.ts — print human-readable status of all wa-mirror team sessions.
//
// Usage: tsx scripts/status.ts

import "dotenv/config";
import { closePool, query } from "../bridge/pg.js";

type Row = {
  id: number;
  team_member_email: string;
  phone_normalized: string;
  status: string;
  connected_at: string | null;
  last_seen_at: string | null;
  disconnected_at: string | null;
  disconnect_reason: string | null;
  messages_logged: string;
  messages_filtered: string;
};

async function main(): Promise<void> {
  const res = await query<Row>(
    `SELECT id, team_member_email, phone_normalized, status,
            connected_at, last_seen_at, disconnected_at, disconnect_reason,
            messages_logged, messages_filtered
       FROM whatsapp_team_sessions
       ORDER BY (status = 'connected') DESC, last_seen_at DESC NULLS LAST`
  );

  if (res.rowCount === 0) {
    process.stdout.write("(no whatsapp_team_sessions rows yet)\n");
    await closePool();
    return;
  }

  const lines = [
    "id  email                              phone           status        logged  filtered  last_seen",
    "--- ---------------------------------- --------------- ------------- ------- --------- ------------------",
  ];
  for (const r of res.rows) {
    const last = r.last_seen_at ?? r.disconnected_at ?? "-";
    lines.push(
      `${pad(String(r.id), 3)} ${pad(r.team_member_email, 34)} ${pad(r.phone_normalized, 15)} ${pad(r.status, 13)} ${pad(r.messages_logged, 7)} ${pad(r.messages_filtered, 9)} ${last}`
    );
  }
  process.stdout.write(lines.join("\n") + "\n");
  await closePool();
}

function pad(s: string, n: number): string {
  return s.length >= n ? s.slice(0, n) : s + " ".repeat(n - s.length);
}

main().catch((err) => {
  process.stderr.write(`status failed: ${err instanceof Error ? err.message : String(err)}\n`);
  process.exit(1);
});
