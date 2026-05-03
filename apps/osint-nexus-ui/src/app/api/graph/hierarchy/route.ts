import { NextResponse } from 'next/server';
import { runQuery } from '@/lib/neo4j';
import { QUERIES } from '@/lib/queries';
import type { HierarchyChain, SupervisesChain } from '@/lib/types';

export async function GET() {
  try {
    const [partOfRows, supervisesRows] = await Promise.all([
      runQuery<HierarchyChain>(QUERIES.hierarchy),
      runQuery<SupervisesChain>(QUERIES.supervisesChains),
    ]);

    return NextResponse.json({
      part_of: partOfRows,
      supervises: supervisesRows,
    });
  } catch {
    return NextResponse.json({ error: 'Query failed' }, { status: 500 });
  }
}
