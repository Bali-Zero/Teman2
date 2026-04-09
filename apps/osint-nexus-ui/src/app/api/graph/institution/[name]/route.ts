import { NextResponse } from 'next/server';
import { runQuery } from '@/lib/neo4j';
import { QUERIES } from '@/lib/queries';

export async function GET(_req: Request, { params }: { params: Promise<{ name: string }> }) {
  const { name } = await params;
  const institution = decodeURIComponent(name);

  try {
    const officials = await runQuery<{
      name: string; jabatan: string; nip: string | null;
      total_assets: number; has_lhkpn: boolean;
    }>(QUERIES.institutionOfficials, { institution });

    const relationships: { from: string; to: string; type: string }[] = [];
    const kepala = officials.find((o) =>
      o.jabatan?.toLowerCase().includes('kepala kantor') ||
      o.jabatan?.toLowerCase().includes('kepala')
    );
    if (kepala) {
      officials.forEach((o) => {
        if (o.name !== kepala.name) {
          relationships.push({ from: kepala.name, to: o.name, type: 'SUPERVISES' });
        }
      });
    }

    return NextResponse.json({
      officials: officials.map((o) => ({
        name: o.name,
        jabatan: o.jabatan,
        nip: o.nip,
        has_lhkpn: o.has_lhkpn,
        total_assets: o.total_assets ?? 0,
        anomaly: false,
      })),
      relationships,
    });
  } catch {
    return NextResponse.json({ error: 'Query failed' }, { status: 500 });
  }
}
