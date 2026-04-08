import { NextResponse } from 'next/server';
import { runQuery } from '@/lib/neo4j';
import { QUERIES } from '@/lib/queries';
import { BALI_INSTITUTIONS } from '@/lib/geo';

export async function GET(_req: Request, { params }: { params: Promise<{ name: string }> }) {
  const { name } = await params;
  const province = decodeURIComponent(name);

  try {
    const [officials, anomalies] = await Promise.all([
      runQuery<{
        name: string; jabatan: string; nip: string | null;
        kantor: string; total_assets: number; has_lhkpn: boolean;
      }>(QUERIES.provinceDetail, { province }),
      runQuery<{
        official: string; year_from: number; year_to: number; delta_pct: number;
      }>(QUERIES.anomalies, { province }),
    ]);

    const stats = {
      officials: officials.length,
      lhkpn: officials.filter((o) => o.has_lhkpn).length,
      total_assets: officials.reduce((sum, o) => sum + (o.total_assets ?? 0), 0),
    };

    const institutionsWithCounts = BALI_INSTITUTIONS.map((inst) => {
      const matched = officials.filter((o) => o.kantor === inst.name);
      const instAnomalies = anomalies.filter((a) =>
        matched.some((o) => o.name === a.official)
      );
      return {
        ...inst,
        official_count: matched.length,
        anomaly_count: instAnomalies.length,
      };
    });

    return NextResponse.json({
      institutions: institutionsWithCounts,
      stats,
      top_holders: officials.slice(0, 5).map((o) => ({
        name: o.name,
        jabatan: o.jabatan,
        total_assets: o.total_assets ?? 0,
      })),
      anomalies: anomalies.map((a) => ({
        official: a.official,
        type: 'asset_delta',
        delta_pct: a.delta_pct,
        year: a.year_to,
      })),
    });
  } catch {
    return NextResponse.json({ error: 'Query failed' }, { status: 500 });
  }
}
