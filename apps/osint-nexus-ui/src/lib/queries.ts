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
    OPTIONAL MATCH (o)-[:WORKS_AT]->(k:Kanim_Office)
    RETURN o.name AS name, o.jabatan AS jabatan, o.nip AS nip, k.name AS kantor
  `,
} as const;
