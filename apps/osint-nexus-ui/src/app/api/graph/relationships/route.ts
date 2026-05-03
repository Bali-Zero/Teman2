import { NextResponse } from 'next/server';
import { runQuery } from '@/lib/neo4j';
import { QUERIES } from '@/lib/queries';
import type { RelationshipIntel } from '@/lib/types';

export async function GET() {
  try {
    const rows = await runQuery<RelationshipIntel>(QUERIES.relationships);
    return NextResponse.json({ relationships: rows });
  } catch {
    return NextResponse.json({ error: 'Query failed' }, { status: 500 });
  }
}
