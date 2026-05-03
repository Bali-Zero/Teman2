export const QUERIES = {
  stats: `
    CALL {
      MATCH (n) RETURN count(n) AS nodes
    }
    CALL {
      MATCH ()-[r]->() RETURN count(r) AS relationships
    }
    CALL {
      MATCH (o:Official) RETURN count(o) AS officials
    }
    CALL {
      MATCH (o:Official)-[:OWNS]->()
      RETURN count(DISTINCT o) AS lhkpn_reports
    }
    RETURN nodes, relationships, officials, lhkpn_reports
  `,

  provinces: `
    MATCH (o:Official)-[:WORKS_AT]->(k:Kanim_Office)
    OPTIONAL MATCH (o)-[owns:OWNS]->(asset)
    WITH k.kota AS province,
         count(DISTINCT o) AS officials,
         count(DISTINCT CASE WHEN owns IS NOT NULL THEN o END) AS with_lhkpn,
         sum(owns.nilai) AS total_assets
    RETURN province, officials, with_lhkpn, total_assets
    ORDER BY officials DESC
  `,

  provinceDetail: `
    MATCH (o:Official)-[:WORKS_AT]->(k:Kanim_Office)
    WHERE k.kota = $province
    OPTIONAL MATCH (o)-[owns:OWNS]->(asset)
    WITH o, k,
         sum(owns.nilai) AS total_assets,
         count(DISTINCT CASE WHEN owns IS NOT NULL THEN asset END) AS asset_count
    RETURN o.name AS name, o.jabatan AS jabatan, o.nip AS nip,
           k.name AS kantor, total_assets, asset_count > 0 AS has_lhkpn
    ORDER BY total_assets DESC
  `,

  anomalies: `
    MATCH (o:Official)-[:WORKS_AT]->(k:Kanim_Office)
    WHERE k.kota = $province
    MATCH (o)-[r1:OWNS]->(a)
    MATCH (o)-[r2:OWNS]->(a)
    WHERE r2.tahun = r1.tahun + 1 AND r1.nilai > 0
    WITH o.name AS official,
         r1.tahun AS year_from,
         r2.tahun AS year_to,
         sum(r1.nilai) AS val_before,
         sum(r2.nilai) AS val_after
    WHERE val_before > 0
    WITH official, year_from, year_to,
         toFloat(val_after - val_before) / val_before * 100 AS delta_pct
    WHERE abs(delta_pct) > 30
    RETURN official, year_from, year_to, delta_pct
    ORDER BY abs(delta_pct) DESC
  `,

  institutionOfficials: `
    MATCH (o:Official)-[:WORKS_AT]->(k:Kanim_Office {name: $institution})
    OPTIONAL MATCH (o)-[owns:OWNS]->(asset)
    WITH o, sum(owns.nilai) AS total_assets,
         count(DISTINCT CASE WHEN owns IS NOT NULL THEN asset END) AS asset_count
    RETURN o.name AS name, o.jabatan AS jabatan, o.nip AS nip,
           total_assets, asset_count > 0 AS has_lhkpn
    ORDER BY total_assets DESC
  `,

  officialAssets: `
    MATCH (o:Official {name: $name})-[owns:OWNS]->(asset)
    WITH owns.tahun AS year, labels(asset)[0] AS asset_type,
         collect({
           type: labels(asset)[0],
           nilai: owns.nilai,
           sumber: owns.sumber,
           lokasi: asset.lokasi,
           luas_tanah_m2: asset.luas_tanah_m2,
           luas_bangunan_m2: asset.luas_bangunan_m2,
           jenis: asset.jenis,
           merk_model: asset.merk_model,
           tahun_perolehan: asset.tahun_perolehan
         }) AS items,
         sum(owns.nilai) AS subtotal
    RETURN year, asset_type, subtotal, items
    ORDER BY year ASC, asset_type ASC
  `,

  officialProfile: `
    MATCH (o:Official {name: $name})
    OPTIONAL MATCH (o)-[:WORKS_AT]->(k)
    WITH o, collect(DISTINCT k.name) AS kantors
    RETURN o.name AS name, o.jabatan AS jabatan, o.nip AS nip,
           kantors[0] AS kantor,
           o.pangkat AS pangkat, o.angkatan AS angkatan, o.asal AS asal,
           o.agama AS agama, o.ttl AS ttl,
           kantors
  `,

  officialConnections: `
    MATCH (o:Official {name: $name})
    OPTIONAL MATCH (o)-[r1:FAMILY_OF]-(fam)
    OPTIONAL MATCH (o)-[r2:MET_WITH]-(met)
    OPTIONAL MATCH (o)-[r3:SUPERVISES]->(subordinate)
    OPTIONAL MATCH (supervisor)-[r4:SUPERVISES]->(o)
    OPTIONAL MATCH (o)-[r5:ALUMNI]-(alumni)
    OPTIONAL MATCH (o)-[r6:PARENT_OF]-(child)
    OPTIONAL MATCH (o)-[r7:WORKS_AT]->(org)
    WITH o,
         collect(DISTINCT CASE WHEN fam IS NOT NULL THEN {name: fam.name, type: labels(fam)[0], notes: fam.notes, person_type: fam.person_type} END) AS family_raw,
         collect(DISTINCT CASE WHEN met IS NOT NULL THEN {name: met.name, type: labels(met)[0], context: r2.context, predicate: r2.raw_predicate} END) AS met_raw,
         collect(DISTINCT CASE WHEN subordinate IS NOT NULL THEN {name: subordinate.name, jabatan: subordinate.jabatan} END) AS subordinates_raw,
         collect(DISTINCT CASE WHEN supervisor IS NOT NULL THEN {name: supervisor.name, jabatan: supervisor.jabatan} END) AS supervisors_raw,
         collect(DISTINCT CASE WHEN alumni IS NOT NULL THEN {name: alumni.name, angkatan: r5.angkatan} END) AS alumni_raw,
         collect(DISTINCT CASE WHEN child IS NOT NULL THEN {name: child.name} END) AS children_raw,
         collect(DISTINCT CASE WHEN org IS NOT NULL THEN {name: org.name, type: labels(org)[0], jabatan: r7.jabatan, context: r7.context} END) AS workplaces_raw
    RETURN [x IN family_raw WHERE x IS NOT NULL] AS family,
           [x IN met_raw WHERE x IS NOT NULL] AS met_with,
           [x IN subordinates_raw WHERE x IS NOT NULL] AS subordinates,
           [x IN supervisors_raw WHERE x IS NOT NULL] AS supervisors,
           [x IN alumni_raw WHERE x IS NOT NULL] AS alumni,
           [x IN children_raw WHERE x IS NOT NULL] AS children,
           [x IN workplaces_raw WHERE x IS NOT NULL] AS workplaces
  `,

  statsDetailed: `
    CALL {
      MATCH (n) RETURN count(n) AS nodes
    }
    CALL {
      MATCH ()-[r]->() RETURN count(r) AS relationships
    }
    CALL {
      MATCH (o:Official) RETURN count(o) AS officials
    }
    CALL {
      MATCH (o:Official)-[:OWNS]->()
      RETURN count(DISTINCT o) AS lhkpn_reports
    }
    CALL {
      MATCH (n:Property) RETURN count(n) AS properties
    }
    CALL {
      MATCH (n:Vehicle) RETURN count(n) AS vehicles
    }
    CALL {
      MATCH (n:BankAccount) RETURN count(n) AS bank_accounts
    }
    CALL {
      MATCH (n:Organization) RETURN count(n) AS organizations
    }
    CALL {
      MATCH (n:Kanim_Office) RETURN count(n) AS kanim_offices
    }
    CALL {
      MATCH (n:Person) RETURN count(n) AS persons
    }
    CALL {
      MATCH ()-[r:OWNS]->() RETURN count(r) AS owns_count
    }
    CALL {
      MATCH ()-[r:WORKS_AT]->() RETURN count(r) AS works_at_count
    }
    CALL {
      MATCH ()-[r:FAMILY_OF]-() RETURN count(r) AS family_of_count
    }
    CALL {
      MATCH ()-[r:MET_WITH]-() RETURN count(r) AS met_with_count
    }
    CALL {
      MATCH ()-[r:SUPERVISES]->() RETURN count(r) AS supervises_count
    }
    CALL {
      MATCH ()-[r:PART_OF]->() RETURN count(r) AS part_of_count
    }
    RETURN nodes, relationships, officials, lhkpn_reports,
           properties, vehicles, bank_accounts, organizations, kanim_offices, persons,
           owns_count, works_at_count, family_of_count, met_with_count, supervises_count, part_of_count
  `,

  organizations: `
    MATCH (org:Organization)
    OPTIONAL MATCH (o:Official)-[:WORKS_AT]->(org)
    RETURN org.name AS name, org.tipe AS tipe, org.lokasi AS lokasi,
           count(o) AS official_count, collect(DISTINCT o.name) AS officials
    ORDER BY official_count DESC
  `,

  hierarchy: `
    MATCH path = (a)-[:PART_OF*1..5]->(b)
    WITH [n IN nodes(path) | {name: n.name, type: labels(n)[0]}] AS chain
    RETURN chain
  `,

  supervisesChains: `
    MATCH path = (a:Official)-[:SUPERVISES*1..5]->(b:Official)
    WHERE NOT ()-[:SUPERVISES]->(a)
    WITH [n IN nodes(path) | {name: n.name, jabatan: n.jabatan}] AS chain
    RETURN chain
    ORDER BY size(chain) DESC
  `,

  relationships: `
    MATCH (a)-[r]->(b)
    WHERE type(r) IN ['FAMILY_OF', 'MET_WITH', 'SUPERVISES', 'ALUMNI', 'PARENT_OF']
    RETURN a.name AS from, b.name AS to, type(r) AS type,
           r.context AS context, r.raw_predicate AS predicate, b.notes AS notes
    ORDER BY type(r), a.name
  `,

  persons: `
    MATCH (p:Person)
    OPTIONAL MATCH (o:Official)-[:FAMILY_OF]-(p)
    RETURN p.name AS name, p.person_type AS person_type, p.notes AS notes,
           p.relationship_to_us AS relationship_to_us,
           collect(DISTINCT o.name) AS connected_to
    ORDER BY p.name
  `,
} as const;
