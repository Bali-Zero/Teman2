import { NextResponse } from 'next/server';
import { runQuery } from '@/lib/neo4j';

export async function GET() {
  try {
    const rows = await runQuery<{
      name: string;
      jabatan: string;
      nip: string | null;
      pangkat: string | null;
      angkatan: string | null;
      asal: string | null;
      agama: string | null;
      ttl: string | null;
      kantors: string[];
      total_assets: number;
      asset_count: number;
      has_lhkpn: boolean;
    }>(`
      MATCH (o:Official)
      OPTIONAL MATCH (o)-[:WORKS_AT]->(k)
      OPTIONAL MATCH (o)-[owns:OWNS]->(asset)
      WITH o,
           collect(DISTINCT k.name) AS kantors,
           sum(owns.nilai) AS total_assets,
           count(DISTINCT CASE WHEN owns IS NOT NULL THEN asset END) AS asset_count
      RETURN o.name AS name, o.jabatan AS jabatan, o.nip AS nip,
             o.pangkat AS pangkat, o.angkatan AS angkatan, o.asal AS asal,
             o.agama AS agama, o.ttl AS ttl,
             kantors, total_assets, asset_count, asset_count > 0 AS has_lhkpn
      ORDER BY total_assets DESC
    `);

    return NextResponse.json({ officials: rows });
  } catch {
    return NextResponse.json({ error: 'Query failed' }, { status: 500 });
  }
}
