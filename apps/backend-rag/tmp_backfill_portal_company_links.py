"""
Backfill company links and NPWP/NIB for 80 portal clients.

Steps:
1. Find 80 portal clients (team_members.role='client' + active)
2. For those WITHOUT company links, match c.company_name -> companies.company_name
3. INSERT client_company_links for matches
4. Backfill NPWP/NIB from linked companies where client record is missing them
5. Print final stats
"""

from datetime import datetime, timezone

import psycopg2

DB_URL = "postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag"


def main() -> None:
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = False
    cur = conn.cursor()

    now = datetime.now(timezone.utc)

    # ── Step 1: Get all 80 portal clients ──
    cur.execute("""
        SELECT c.id, c.full_name, c.company_name, c.npwp, c.nib
        FROM team_members tm
        JOIN clients c ON c.id = tm.linked_client_id
        WHERE tm.role = 'client'
          AND tm.active = true
          AND tm.linked_client_id IS NOT NULL
        ORDER BY c.full_name
    """)
    portal_clients = cur.fetchall()
    print(f"Total portal clients: {len(portal_clients)}")

    # ── Step 2: Find those WITHOUT company links ──
    cur.execute("""
        SELECT c.id, c.full_name, c.company_name
        FROM team_members tm
        JOIN clients c ON c.id = tm.linked_client_id
        LEFT JOIN client_company_links ccl ON ccl.client_id = c.id
        WHERE tm.role = 'client'
          AND tm.active = true
          AND tm.linked_client_id IS NOT NULL
          AND ccl.id IS NULL
        ORDER BY c.full_name
    """)
    no_links = cur.fetchall()
    print(f"Portal clients WITHOUT company links: {len(no_links)}")

    # ── Step 3: Match and INSERT company links ──
    links_created = 0
    no_match_clients = []

    for client_id, full_name, company_name in no_links:
        # Skip if no company_name
        clean = (company_name or "").strip()
        if not clean or clean == "None":
            continue

        # Try ILIKE match on full name
        cur.execute("""
            SELECT id, company_name, nib, npwp_company
            FROM companies
            WHERE company_name ILIKE %s
            LIMIT 1
        """, (f"%{clean}%",))
        match = cur.fetchone()

        if not match:
            # Try without PT prefix
            stripped = clean.replace("PT ", "").replace("PT. ", "").strip()
            cur.execute("""
                SELECT id, company_name, nib, npwp_company
                FROM companies
                WHERE company_name ILIKE %s
                LIMIT 1
            """, (f"%{stripped}%",))
            match = cur.fetchone()

        if match:
            company_id = match[0]
            comp_name = match[1]

            # Check no duplicate link exists (safety)
            cur.execute("""
                SELECT id FROM client_company_links
                WHERE client_id = %s AND company_id = %s
            """, (client_id, company_id))
            if cur.fetchone():
                print(f"  SKIP (already linked): {full_name} -> {comp_name}")
                continue

            cur.execute("""
                INSERT INTO client_company_links
                    (client_id, company_id, role, is_primary, status, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (client_id, company_id, "Director", True, "active", now, now))
            links_created += 1
            print(f"  LINKED: {full_name} (id={client_id}) -> {comp_name} (id={company_id})")
        else:
            no_match_clients.append((client_id, full_name, clean))

    if no_match_clients:
        print(f"\n  NO MATCH for {len(no_match_clients)} client(s):")
        for cid, name, cname in no_match_clients:
            print(f"    id={cid}, {name}, company_name=\"{cname}\"")

    print(f"\nCompany links created: {links_created}")

    # ── Step 4: Backfill NPWP and NIB from linked companies ──
    # For ALL 80 portal clients with company links, fill missing NPWP/NIB
    cur.execute("""
        SELECT c.id, c.full_name, c.npwp, c.nib,
               comp.npwp_company, comp.nib AS comp_nib,
               ccl.is_primary
        FROM team_members tm
        JOIN clients c ON c.id = tm.linked_client_id
        JOIN client_company_links ccl ON ccl.client_id = c.id
        JOIN companies comp ON comp.id = ccl.company_id
        WHERE tm.role = 'client'
          AND tm.active = true
          AND tm.linked_client_id IS NOT NULL
        ORDER BY ccl.is_primary DESC, c.full_name
    """)
    all_linked = cur.fetchall()

    npwp_filled = 0
    nib_filled = 0
    # Track which clients we already updated (prefer primary link)
    updated_npwp: set[int] = set()
    updated_nib: set[int] = set()

    for client_id, full_name, client_npwp, client_nib, comp_npwp, comp_nib, _is_primary in all_linked:
        updates = []
        params: list = []

        # Fill NPWP if client is missing it and company has it
        empty_npwp = not client_npwp or client_npwp.strip() == ""
        has_comp_npwp = comp_npwp and comp_npwp.strip() != ""
        if empty_npwp and has_comp_npwp and client_id not in updated_npwp:
            updates.append("npwp = %s")
            params.append(comp_npwp.strip())
            updated_npwp.add(client_id)

        # Fill NIB if client is missing it and company has it
        empty_nib = not client_nib or client_nib.strip() == ""
        has_comp_nib = comp_nib and comp_nib.strip() != ""
        if empty_nib and has_comp_nib and client_id not in updated_nib:
            updates.append("nib = %s")
            params.append(comp_nib.strip())
            updated_nib.add(client_id)

        if updates:
            params.append(now)
            params.append(client_id)
            sql = f"UPDATE clients SET {', '.join(updates)}, updated_at = %s WHERE id = %s"
            cur.execute(sql, params)

            filled = []
            if "npwp" in sql and "npwp = %s" in sql.split("updated_at")[0]:
                npwp_filled += 1
                filled.append("NPWP")
            if "nib = %s" in sql.split("updated_at")[0]:
                nib_filled += 1
                filled.append("NIB")
            print(f"  BACKFILLED {'+'.join(filled)}: {full_name} (id={client_id})")

    print(f"\nNPWP backfilled: {npwp_filled}")
    print(f"NIB backfilled: {nib_filled}")

    # ── Step 5: Commit ──
    conn.commit()
    print("\n--- COMMITTED ---")

    # ── Step 6: Final stats ──
    cur.execute("""
        SELECT COUNT(DISTINCT c.id)
        FROM team_members tm
        JOIN clients c ON c.id = tm.linked_client_id
        JOIN client_company_links ccl ON ccl.client_id = c.id
        WHERE tm.role = 'client' AND tm.active = true AND tm.linked_client_id IS NOT NULL
    """)
    with_links = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(DISTINCT c.id)
        FROM team_members tm
        JOIN clients c ON c.id = tm.linked_client_id
        WHERE tm.role = 'client' AND tm.active = true AND tm.linked_client_id IS NOT NULL
        AND COALESCE(NULLIF(c.npwp, ''), NULL) IS NOT NULL
    """)
    with_npwp = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(DISTINCT c.id)
        FROM team_members tm
        JOIN clients c ON c.id = tm.linked_client_id
        WHERE tm.role = 'client' AND tm.active = true AND tm.linked_client_id IS NOT NULL
        AND COALESCE(NULLIF(c.nib, ''), NULL) IS NOT NULL
    """)
    with_nib = cur.fetchone()[0]

    print(f"\n{'='*50}")
    print(f"FINAL STATS (out of {len(portal_clients)} portal clients):")
    print(f"  With company links: {with_links}/{len(portal_clients)}")
    print(f"  With NPWP:          {with_npwp}/{len(portal_clients)}")
    print(f"  With NIB:           {with_nib}/{len(portal_clients)}")
    print(f"{'='*50}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
