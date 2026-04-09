import { NextResponse } from 'next/server';
import { runQuery } from '@/lib/neo4j';
import { QUERIES } from '@/lib/queries';
import type { PersonData } from '@/lib/types';

export async function GET() {
  try {
    const rows = await runQuery<PersonData>(QUERIES.persons);
    return NextResponse.json({ persons: rows });
  } catch {
    return NextResponse.json({ error: 'Query failed' }, { status: 500 });
  }
}
