// status.ts — print human-readable status of all wa-mirror team sessions.
//
// Usage: tsx scripts/status.ts

import "dotenv/config";
import { closePool, query } from "../bridge/pg.js";

type Row = {
  id: number;
  team_member_email: string;
  team_member_phone: string | null;
  team_member_name: string | null;
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
    `SELECT id, team_member_email, team_member_phone, team_member_name,
            phone_normalized, status,
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
    "id  name                  account         status        logged  filtered  last_seen",
    "--- --------------------- --------------- ------------- ------- --------- ------------------",
  ];
  for (const r of res.rows) {
    const last = r.last_seen_at ?? r.disconnected_at ?? "-";
    const account = r.team_member_phone ?? r.phone_normalized ?? r.team_member_email;
    const name = r.team_member_name ?? r.team_member_email;
    lines.push(
      `${pad(String(r.id), 3)} ${pad(name, 21)} ${pad(account, 15)} ${pad(r.status, 13)} ${pad(r.messages_logged, 7)} ${pad(r.messages_filtered, 9)} ${last}`
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
