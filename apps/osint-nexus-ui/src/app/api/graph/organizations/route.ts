import { NextResponse } from 'next/server';
import { runQuery } from '@/lib/neo4j';
import { QUERIES } from '@/lib/queries';
import type { OrganizationData } from '@/lib/types';

export async function GET() {
  try {
    const rows = await runQuery<OrganizationData>(QUERIES.organizations);
    return NextResponse.json({ organizations: rows });
  } catch {
    return NextResponse.json({ error: 'Query failed' }, { status: 500 });
  }
}
