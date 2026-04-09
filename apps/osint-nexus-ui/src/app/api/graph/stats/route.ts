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
      properties: number;
      vehicles: number;
      bank_accounts: number;
      organizations: number;
      kanim_offices: number;
      persons: number;
      owns_count: number;
      works_at_count: number;
      family_of_count: number;
      met_with_count: number;
      supervises_count: number;
      part_of_count: number;
    }>(QUERIES.statsDetailed);

    const r = rows[0];
    if (!r) {
      return NextResponse.json({ nodes: 0, relationships: 0, officials: 0, lhkpn_reports: 0, nodes_by_type: {}, rels_by_type: {} });
    }

    return NextResponse.json({
      nodes: r.nodes,
      relationships: r.relationships,
      officials: r.officials,
      lhkpn_reports: r.lhkpn_reports,
      nodes_by_type: {
        Officials: r.officials,
        Properties: r.properties,
        Vehicles: r.vehicles,
        BankAccounts: r.bank_accounts,
        Organizations: r.organizations,
        Kanim_Office: r.kanim_offices,
        Persons: r.persons,
      },
      rels_by_type: {
        OWNS: r.owns_count,
        WORKS_AT: r.works_at_count,
        FAMILY_OF: r.family_of_count,
        MET_WITH: r.met_with_count,
        SUPERVISES: r.supervises_count,
        PART_OF: r.part_of_count,
      },
    });
  } catch {
    return NextResponse.json({ error: 'Neo4j connection failed' }, { status: 500 });
  }
}
