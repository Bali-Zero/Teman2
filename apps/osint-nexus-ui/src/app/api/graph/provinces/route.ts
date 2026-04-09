import { NextResponse } from 'next/server';
import { runQuery } from '@/lib/neo4j';
import { QUERIES } from '@/lib/queries';
import { PROVINCE_CENTROIDS } from '@/lib/geo';

export async function GET() {
  try {
    const rows = await runQuery<{
      province: string;
      officials: number;
      with_lhkpn: number;
      total_assets: number;
    }>(QUERIES.provinces);

    const provinces = rows.map((r) => ({
      name: r.province,
      official_count: r.officials,
      lhkpn_count: r.with_lhkpn,
      total_assets: r.total_assets ?? 0,
      centroid: PROVINCE_CENTROIDS[r.province] ?? { lat: -2.5, lng: 118.0 },
    }));

    return NextResponse.json({ provinces });
  } catch {
    return NextResponse.json({ error: 'Query failed' }, { status: 500 });
  }
}
