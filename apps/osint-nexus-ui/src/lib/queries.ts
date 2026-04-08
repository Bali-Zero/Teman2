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
    OPTIONAL MATCH (o)-[:FAMILY_OF]-(fam)
    OPTIONAL MATCH (o)-[:MET_WITH]-(met)
    OPTIONAL MATCH (o)-[:SUPERVISES]-(sup)
    WITH o,
         collect(DISTINCT CASE WHEN fam IS NOT NULL THEN {name: fam.name, type: labels(fam)[0]} END) AS family_raw,
         collect(DISTINCT CASE WHEN met IS NOT NULL THEN {name: met.name, type: labels(met)[0]} END) AS met_raw,
         collect(DISTINCT CASE WHEN sup IS NOT NULL THEN {name: sup.name, rel: 'SUPERVISES'} END) AS sup_raw
    RETURN [x IN family_raw WHERE x IS NOT NULL] AS family,
           [x IN met_raw WHERE x IS NOT NULL] AS met_with,
           [x IN sup_raw WHERE x IS NOT NULL] AS supervises
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
} as const;
