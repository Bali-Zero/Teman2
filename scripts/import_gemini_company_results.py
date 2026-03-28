#!/usr/bin/env python3
"""Import Gemini-extracted company data into the database."""
import asyncio
import json
import glob
import sys
import os

DB_URL = "postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag"


async def import_results(result_dir: str):
    import asyncpg

    conn = await asyncpg.connect(DB_URL)
    files = sorted(glob.glob(os.path.join(result_dir, "batch_*_result.json")))
    print(f"Found {len(files)} result files")

    total_updated = 0
    total_links_updated = 0
    total_errors = 0

    for fpath in files:
        batch_name = os.path.basename(fpath)
        try:
            raw = open(fpath).read().strip()
            # Extract JSON from Gemini output (may have markdown wrapping)
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()

            companies = json.loads(raw)
            if not isinstance(companies, list):
                companies = [companies]
        except Exception as e:
            print(f"  {batch_name}: PARSE ERROR - {e}")
            total_errors += 1
            continue

        print(f"  {batch_name}: {len(companies)} companies")

        for co in companies:
            cid = co.get("company_id")
            if not cid:
                continue

            try:
                # Update company fields
                updates = []
                params = []
                idx = 1

                if co.get("kbli_codes"):
                    updates.append(f"kbli_code = ${idx}")
                    params.append(str(co["kbli_codes"]))
                    idx += 1

                if co.get("notaris_name"):
                    # Store in custom_fields
                    pass  # TODO: add notaris column or use custom_fields

                if updates:
                    params.append(cid)
                    await conn.execute(
                        f"UPDATE companies SET {', '.join(updates)} WHERE id = ${idx} AND (kbli_code IS NULL OR kbli_code = '')",
                        *params,
                    )

                # Update shareholder links
                shareholders = co.get("shareholders", [])
                nominal = co.get("share_nominal_value")

                for sh in shareholders:
                    name = (sh.get("name") or "").strip().upper()
                    shares = sh.get("shares_count")
                    pct = sh.get("ownership_percentage")

                    if not name or (not shares and not pct):
                        continue

                    # Find matching link
                    name_parts = [p for p in name.split() if len(p) > 2]
                    link = None
                    for part in name_parts:
                        link = await conn.fetchrow(
                            """
                            SELECT ccl.id, ccl.shares_count, ccl.share_nominal_value, ccl.ownership_percentage
                            FROM client_company_links ccl
                            JOIN clients cl ON cl.id = ccl.client_id
                            WHERE ccl.company_id = $1 AND UPPER(cl.full_name) LIKE '%' || $2 || '%'
                            LIMIT 1
                        """,
                            cid,
                            part,
                        )
                        if link:
                            break

                    if not link:
                        continue

                    sets = []
                    uparams = []
                    uidx = 1

                    if shares and (
                        link["shares_count"] is None or link["shares_count"] == 0
                    ):
                        sets.append(f"shares_count = ${uidx}")
                        uparams.append(int(shares))
                        uidx += 1

                    if nominal and (
                        link["share_nominal_value"] is None
                        or float(link["share_nominal_value"] or 0) == 0
                    ):
                        sets.append(f"share_nominal_value = ${uidx}")
                        uparams.append(float(nominal))
                        uidx += 1

                    if pct and (
                        link["ownership_percentage"] is None
                        or float(link["ownership_percentage"] or 0) == 0
                    ):
                        sets.append(f"ownership_percentage = ${uidx}")
                        uparams.append(float(pct))
                        uidx += 1

                    if sets:
                        uparams.append(link["id"])
                        await conn.execute(
                            f"UPDATE client_company_links SET {', '.join(sets)} WHERE id = ${uidx}",
                            *uparams,
                        )
                        total_links_updated += 1

                total_updated += 1

            except Exception as e:
                print(f"    Error on company {cid}: {e}")
                total_errors += 1

    # Final stats
    final_shares = await conn.fetchval(
        "SELECT COUNT(*) FROM client_company_links WHERE shares_count > 0"
    )
    final_companies = await conn.fetchval(
        "SELECT COUNT(DISTINCT company_id) FROM client_company_links WHERE shares_count > 0"
    )

    print(f"\n=== Import Complete ===")
    print(f"Companies processed: {total_updated}")
    print(f"Links updated: {total_links_updated}")
    print(f"Errors: {total_errors}")
    print(f"Total links with shares > 0: {final_shares}")
    print(f"Total companies with capital: {final_companies} / 736")

    await conn.close()


if __name__ == "__main__":
    result_dir = sys.argv[1] if len(sys.argv) > 1 else "ai-dispatch-output/company-extraction"
    asyncio.run(import_results(result_dir))
