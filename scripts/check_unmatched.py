import asyncio, asyncpg, unicodedata, re

def norm(s):
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    s = re.sub(r'[^A-Za-z ]', '', s)
    return s.upper().strip()

async def main():
    conn = await asyncpg.connect('postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:5555/nuzantara_rag?sslmode=disable')

    all_clients = await conn.fetch("SELECT id, full_name, deleted_at IS NOT NULL as is_deleted FROM clients")
    active = [c for c in all_clients if not c['is_deleted']]
    deleted = [c for c in all_clients if c['is_deleted']]
    print(f"Total: {len(all_clients)} (active={len(active)}, deleted={len(deleted)})")

    # Build indexes from ALL clients
    by_norm = {}
    by_word = {}  # word → [(id, name, deleted)]

    for c in all_clients:
        n = norm(c['full_name'])
        by_norm[n] = (c['id'], c['full_name'], c['is_deleted'])
        for w in n.split():
            if len(w) >= 4:
                by_word.setdefault(w, []).append((c['id'], c['full_name'], c['is_deleted']))

    # Get ALL unmatched folder names (run the full matching again)
    import httpx
    OAUTH_CLIENT_ID = '930328104463-m3g4gq72095rip08269kvt8s7et9ev12.apps.googleusercontent.com'
    OAUTH_CLIENT_SECRET = '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'
    OAUTH_REFRESH_TOKEN = '1//0gbiun0bBkNVCCgYIARAAGBASNwF-L9IrGvLMkg0QQ7fz0x98C1zyFqsCvzyijl7NjxUXoJ8K_-BAN8t-ZuQyT5uIv2iVJUPSiMA'
    FID = '1mNi2FkhZqP9inJH2Y1taXLCgS95UkYk4'

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post('https://oauth2.googleapis.com/token', data={
            'client_id': OAUTH_CLIENT_ID, 'client_secret': OAUTH_CLIENT_SECRET,
            'refresh_token': OAUTH_REFRESH_TOKEN, 'grant_type': 'refresh_token',
        })
        token = resp.json()['access_token']
        headers = {'Authorization': f'Bearer {token}'}
        all_folders = []
        pt = None
        while True:
            p = {'q': f"'{FID}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
                 'supportsAllDrives': 'true', 'includeItemsFromAllDrives': 'true',
                 'fields': 'nextPageToken,files(id,name)', 'pageSize': '1000'}
            if pt: p['pageToken'] = pt
            r = await client.get('https://www.googleapis.com/drive/v3/files', headers=headers, params=p)
            d = r.json()
            all_folders.extend(d.get('files', []))
            pt = d.get('nextPageToken')
            if not pt: break

    # Parse folder names
    folder_names = []
    for f in all_folders:
        name = f['name']
        fname = name.split('_', 1)[1].strip() if '_' in name else name
        folder_names.append(fname)

    # Quick match (exact + norm) to find unmatched
    matched = set()
    for fn in folder_names:
        fn_up = fn.upper().strip()
        fn_n = norm(fn)
        if fn_up in {c['full_name'].upper().strip() for c in all_clients if not c['is_deleted']}:
            matched.add(fn)
        elif fn_n in {norm(c['full_name']) for c in all_clients if not c['is_deleted']}:
            matched.add(fn)

    unmatched = [fn for fn in folder_names if fn not in matched]
    print(f"\nUnmatched folders: {len(unmatched)}")

    # Now deep check each unmatched — 10 strategies
    found_in_deleted = 0
    found_fuzzy = 0
    truly_missing = 0

    results = {"deleted": [], "fuzzy": [], "missing": []}

    for fn in unmatched:
        fn_n = norm(fn)
        ws = [w for w in fn_n.split() if len(w) >= 3]

        # Check 1: exact in deleted
        if fn_n in by_norm:
            cid, cname, is_del = by_norm[fn_n]
            if is_del:
                found_in_deleted += 1
                results["deleted"].append((fn, cname))
                continue

        # Check 2: first+last in ALL clients
        if len(ws) >= 2:
            first_w, last_w = ws[0], ws[-1]
            if len(first_w) >= 3 and len(last_w) >= 3:
                hits = [e for e in by_word.get(first_w, []) if any(w == last_w for w in norm(e[1]).split())]
                if len(hits) == 1:
                    found_fuzzy += 1
                    results["fuzzy"].append((fn, hits[0][1], hits[0][2]))
                    continue
                elif len(hits) > 1:
                    # Pick one with most words in common
                    best = max(hits, key=lambda h: len(set(ws) & set(norm(h[1]).split())))
                    common = len(set(ws) & set(norm(best[1]).split()))
                    if common >= 2:
                        found_fuzzy += 1
                        results["fuzzy"].append((fn, best[1], best[2]))
                        continue

        # Check 3: any rare word (appears <= 2 times)
        rare_hits = None
        for w in ws:
            if len(w) >= 5:
                candidates = by_word.get(w, [])
                if 1 <= len(candidates) <= 2:
                    s = set(c[0] for c in candidates)
                    rare_hits = s if rare_hits is None else rare_hits & s
        if rare_hits and len(rare_hits) == 1:
            cid = rare_hits.pop()
            cname = next(c['full_name'] for c in all_clients if c['id'] == cid)
            is_del = next(c['is_deleted'] for c in all_clients if c['id'] == cid)
            found_fuzzy += 1
            results["fuzzy"].append((fn, cname, is_del))
            continue

        # Check 4: substring >= 8 chars
        found = False
        if len(fn_n) >= 8:
            for cn, (cid, cname, is_del) in by_norm.items():
                if len(cn) >= 8 and (fn_n in cn or cn in fn_n):
                    found_fuzzy += 1
                    results["fuzzy"].append((fn, cname, is_del))
                    found = True
                    break
        if found:
            continue

        truly_missing += 1
        if len(results["missing"]) < 30:
            results["missing"].append(fn)

    print(f"\n=== RESULTS ===")
    print(f"Found in deleted clients: {found_in_deleted}")
    print(f"Found fuzzy (active+deleted): {found_fuzzy}")
    print(f"Truly not in DB: {truly_missing}")

    print(f"\n=== Sample DELETED matches ({min(10, len(results['deleted']))}) ===")
    for fn, cname in results["deleted"][:10]:
        print(f"  {fn:40s} → {cname} (DELETED)")

    print(f"\n=== Sample FUZZY matches ({min(10, len(results['fuzzy']))}) ===")
    for fn, cname, is_del in results["fuzzy"][:10]:
        status = "DELETED" if is_del else "ACTIVE"
        print(f"  {fn:40s} → {cname} ({status})")

    print(f"\n=== Sample TRULY MISSING ({min(15, len(results['missing']))}) ===")
    for fn in results["missing"][:15]:
        print(f"  {fn}")

    await conn.close()

asyncio.run(main())
