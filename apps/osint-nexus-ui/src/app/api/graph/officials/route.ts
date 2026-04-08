import { NextResponse } from 'next/server';
import { runQuery } from '@/lib/neo4j';

export async function GET() {
  try {
    const rows = await runQuery<{
      name: string;
      jabatan: string;
      nip: string | null;
      kantor: string;
      total_assets: number;
      has_lhkpn: boolean;
    }>(`
      MATCH (o:Official)
      OPTIONAL MATCH (o)-[:WORKS_AT]->(k:Kanim_Office)
      OPTIONAL MATCH (o)-[owns:OWNS]->(asset)
      WITH o, k, sum(owns.nilai) AS total_assets,
           count(DISTINCT CASE WHEN owns IS NOT NULL THEN asset END) AS asset_count
      RETURN o.name AS name, o.jabatan AS jabatan, o.nip AS nip,
             k.name AS kantor, total_assets, asset_count > 0 AS has_lhkpn
      ORDER BY total_assets DESC
    `);

    return NextResponse.json({ officials: rows });
  } catch {
    return NextResponse.json({ error: 'Query failed' }, { status: 500 });
  }
}
