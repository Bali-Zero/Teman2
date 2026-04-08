import { NextResponse } from 'next/server';
import { runQuery } from '@/lib/neo4j';
import { QUERIES } from '@/lib/queries';

export async function GET() {
  try {
    const rows = await runQuery<{
      nodes: number;
      relationships: number;
      officials: number;
      lhkpn_reports: number;
    }>(QUERIES.stats);
    return NextResponse.json(rows[0] ?? { nodes: 0, relationships: 0, officials: 0, lhkpn_reports: 0 });
  } catch {
    return NextResponse.json({ error: 'Neo4j connection failed' }, { status: 500 });
  }
}
