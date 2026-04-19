import { Pool } from "pg";

let _pool: Pool | null = null;

/** Resolve the connection URL: DATABASE_URL_LOCAL first, then FLY_TUNNEL_URL. */
export function resolveDbUrl(env: NodeJS.ProcessEnv = process.env): {
  url: string;
  source: "local" | "tunnel";
} {
  const local = env.DATABASE_URL_LOCAL?.trim();
  if (local) return { url: local, source: "local" };
  const tunnel = env.FLY_TUNNEL_URL?.trim();
  if (tunnel) return { url: tunnel, source: "tunnel" };
  throw new Error(
    "Set DATABASE_URL_LOCAL or start `fly proxy 15432 -a nuzantara-postgres` " +
      "and export FLY_TUNNEL_URL. See apps/admin-dashboard-local/.env.example.",
  );
}

/** Process-wide lazy pool. Small max since this runs locally. */
export async function getPool(): Promise<Pool> {
  if (_pool) return _pool;
  const { url, source } = resolveDbUrl();
  _pool = new Pool({ connectionString: url, max: 3 });
  // Fire a console line so the operator knows which source we bound to.
  // Safe in a dev-only tool; would be a logger call in a production app.
  console.log(`[admin-dashboard-local] connected via ${source}`);
  return _pool;
}

/** Only used by tests to reset the memoised pool. */
export function _resetPoolForTests(): void {
  _pool = null;
}
