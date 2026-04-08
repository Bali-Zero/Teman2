import { NextResponse } from 'next/server';
import { runQuery } from '@/lib/neo4j';
import { QUERIES } from '@/lib/queries';
import type {
  YearlyAssets, OfficialProfile, OfficialConnections,
  FamilyConnection, MetWithConnection, SupervisionConnection,
  AlumniConnection, WorkplaceConnection,
} from '@/lib/types';

export async function GET(_req: Request, { params }: { params: Promise<{ name: string }> }) {
  const { name } = await params;
  const officialName = decodeURIComponent(name);

  try {
    const [profileRows, assetRows, connectionRows] = await Promise.all([
      runQuery<{
        name: string; jabatan: string; nip: string | null; kantor: string;
        pangkat: string | null; angkatan: string | null; asal: string | null;
        agama: string | null; ttl: string | null; kantors: string[];
      }>(QUERIES.officialProfile, { name: officialName }),
      runQuery<{
        year: number; asset_type: string; subtotal: number;
        items: Array<Record<string, unknown>>;
      }>(QUERIES.officialAssets, { name: officialName }),
      runQuery<{
        family: FamilyConnection[];
        met_with: MetWithConnection[];
        subordinates: SupervisionConnection[];
        supervisors: SupervisionConnection[];
        alumni: AlumniConnection[];
        children: { name: string }[];
        workplaces: WorkplaceConnection[];
      }>(QUERIES.officialConnections, { name: officialName }),
    ]);

    const rawProfile = profileRows[0];
    const profile: OfficialProfile = rawProfile
      ? {
          name: rawProfile.name,
          jabatan: rawProfile.jabatan,
          nip: rawProfile.nip,
          kantor: rawProfile.kantor ?? '',
          pangkat: rawProfile.pangkat ?? null,
          angkatan: rawProfile.angkatan ?? null,
          asal: rawProfile.asal ?? null,
          agama: rawProfile.agama ?? null,
          ttl: rawProfile.ttl ?? null,
          kantors: (rawProfile.kantors ?? []).filter(Boolean),
        }
      : {
          name: officialName, jabatan: '', nip: null, kantor: '',
          pangkat: null, angkatan: null, asal: null, agama: null, ttl: null,
          kantors: [],
        };

    const rawConnections = connectionRows[0];
    const connections: OfficialConnections = rawConnections
      ? {
          family: (rawConnections.family ?? []).filter((f) => f && f.name),
          met_with: (rawConnections.met_with ?? []).filter((m) => m && m.name),
          subordinates: (rawConnections.subordinates ?? []).filter((s) => s && s.name),
          supervisors: (rawConnections.supervisors ?? []).filter((s) => s && s.name),
          alumni: (rawConnections.alumni ?? []).filter((a) => a && a.name),
          children: (rawConnections.children ?? []).filter((c) => c && c.name),
          workplaces: (rawConnections.workplaces ?? []).filter((w) => w && w.name),
        }
      : { family: [], met_with: [], subordinates: [], supervisors: [], alumni: [], children: [], workplaces: [] };

    const assetsByYear: Record<number, YearlyAssets> = {};
    const years = new Set<number>();

    for (const row of assetRows) {
      const y = row.year;
      years.add(y);
      if (!assetsByYear[y]) {
        assetsByYear[y] = { properties: [], vehicles: [], cash: 0, total: 0 };
      }

      if (row.asset_type === 'Property') {
        for (const item of row.items) {
          assetsByYear[y].properties.push({
            lokasi: (item.lokasi as string) ?? '',
            luas_tanah_m2: (item.luas_tanah_m2 as number) ?? 0,
            luas_bangunan_m2: (item.luas_bangunan_m2 as number) ?? 0,
            nilai: (item.nilai as number) ?? 0,
            sumber: (item.sumber as string) ?? '',
          });
        }
      } else if (row.asset_type === 'Vehicle') {
        for (const item of row.items) {
          assetsByYear[y].vehicles.push({
            jenis: (item.jenis as string) ?? '',
            merk_model: (item.merk_model as string) ?? '',
            tahun_perolehan: (item.tahun_perolehan as number) ?? 0,
            nilai: (item.nilai as number) ?? 0,
            sumber: (item.sumber as string) ?? '',
          });
        }
      } else if (row.asset_type === 'BankAccount') {
        assetsByYear[y].cash += row.subtotal;
      }

      assetsByYear[y].total += row.subtotal;
    }

    const sortedYears = [...years].sort();
    const delta: { from_year: number; to_year: number; pct_change: number }[] = [];
    for (let i = 1; i < sortedYears.length; i++) {
      const prev = assetsByYear[sortedYears[i - 1]]?.total ?? 0;
      const curr = assetsByYear[sortedYears[i]]?.total ?? 0;
      if (prev > 0) {
        delta.push({
          from_year: sortedYears[i - 1],
          to_year: sortedYears[i],
          pct_change: ((curr - prev) / prev) * 100,
        });
      }
    }

    return NextResponse.json({
      profile,
      connections,
      lhkpn_years: sortedYears,
      assets_by_year: assetsByYear,
      delta,
    });
  } catch {
    return NextResponse.json({ error: 'Query failed' }, { status: 500 });
  }
}
