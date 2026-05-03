# PR #62 Baseline — Before State (2026-04-16)

## Goal

Evidence capture for the "before" side of the Dockerfile cell-core fix. Used to prove PR #62 actually moved numbers.

## 1. Deployed image metadata

### flyctl releases --app nuzantara-rag (head -5)

```
 VERSION │ STATUS   │ DESCRIPTION │ USER              │ DATE
 v2909   │ complete │ Release     │ zero@balizero.com │ 15h33m ago
 v2908   │ complete │ Release     │ zero@balizero.com │ 16h41m ago
 v2907   │ complete │ Release     │ zero@balizero.com │ 16h43m ago
 v2906   │ complete │ Release     │ zero@balizero.com │ 16h44m ago
```

Current production release: **v2909** (deployed ~15h33m before capture, 2026-04-16)

### flyctl image show --app nuzantara-rag

```
Image Details
 MACHINE ID     │ REGISTRY        │ REPOSITORY    │ TAG                                    │ VERSION │ DIGEST
 1781e5eda03438 │ registry.fly.io │ nuzantara-rag │ deployment-01KPATZ5W998QXMQW9SFB8PZEG  │ N/A     │ sha256:16a2c71100eb699d43e573cb0c7ae6b8f4b5541967d06b89eb9eb84779d0b34f
 e82e510f76d608 │ registry.fly.io │ nuzantara-rag │ deployment-01KPATZ5W998QXMQW9SFB8PZEG  │ N/A     │ sha256:16a2c71100eb699d43e573cb0c7ae6b8f4b5541967d06b89eb9eb84779d0b34f
```

Both machines running identical image. Labels show this was built from GH_SHA=9d8203323917ffaad41bd18dbae3b1f1d8432a28 on push to Balizero1987/Teman2.

**Deployed image digest:** `sha256:16a2c71100eb699d43e573cb0c7ae6b8f4b5541967d06b89eb9eb84779d0b34f`
**Tag:** `deployment-01KPATZ5W998QXMQW9SFB8PZEG`
**Image size:** not reported by flyctl image show (N/A for VERSION field).

## 2. cell-core import failure (root cause evidence)

### Machine 1781e5eda03438 (region: sin)

```
flyctl ssh console --app nuzantara-rag -C 'python -c "from cell_core.genome import Genome"'

No machine specified, using 1781e5eda03438 in region sin
Connecting to fdaa:31:dc12:a7b:74f:c22f:d0a4:2...
Traceback (most recent call last):
  File "<string>", line 1, in <module>
ModuleNotFoundError: No module named 'cell_core'
Error: ssh shell: Process exited with status 1
```

### Machine e82e510f76d608 (region: sin)

```
flyctl ssh console --app nuzantara-rag -C 'python -c "import cell_core"'

No machine specified, using e82e510f76d608 in region sin
Connecting to fdaa:31:dc12:a7b:6cf:eb37:a867:2...
Traceback (most recent call last):
  File "<string>", line 1, in <module>
ModuleNotFoundError: No module named 'cell_core'
Error: ssh shell: Process exited with status 1
```

**Finding: `cell_core` is NOT installed in the deployed container on either machine.** This is the root cause — the Dockerfile does not install the `cell_core` package, so all three degraded routers (`/api/skill/*`, `/api/experience/*`, `/api/metabolic/*`) run in degraded/fallback mode.

## 3. Endpoint degradation evidence

API key not available in this session (secret names visible via `flyctl secrets list`, values inaccessible — `API_KEYS` and `NUZ_API_KEY` are deployed secrets). All three endpoints return 401 when called unauthenticated.

The 401 responses still confirm the endpoints exist and auth is gated correctly. The root-cause verification comes from Step 2 (direct `flyctl ssh` import check), which does not require an API key.

### /api/metabolic/stats

```
curl -s https://nuzantara-rag.fly.dev/api/metabolic/stats

HTTP 401
{"detail":"Authentication required"}
```

### /api/skill/stats

```
curl -s https://nuzantara-rag.fly.dev/api/skill/stats

HTTP 401
{"detail":"Authentication required"}
```

### /api/experience/stats

```
curl -s https://nuzantara-rag.fly.dev/api/experience/stats

HTTP 401
{"detail":"Authentication required"}
```

All three endpoints reachable (no 404/502/503 at the network level), auth-gated with 401. Degradation mode (503 or fake-empty 200) is behind auth — root cause confirmed via SSH import check above.

## Summary

| Metric | Before state |
|---|---|
| cell_core importable | NO — `ModuleNotFoundError: No module named 'cell_core'` on both machines |
| /api/metabolic/stats | 401 auth-gated (endpoint exists; degradation mode behind auth) |
| /api/skill/stats | 401 auth-gated (endpoint exists; degradation mode behind auth) |
| /api/experience/stats | 401 auth-gated (endpoint exists) |
| Deployed image digest | `sha256:16a2c71100eb699d43e573cb0c7ae6b8f4b5541967d06b89eb9eb84779d0b34f` |
| Image tag | `deployment-01KPATZ5W998QXMQW9SFB8PZEG` |
| Release version | v2909 |
| GH commit at deploy | `9d8203323917ffaad41bd18dbae3b1f1d8432a28` |
| Capture timestamp | 2026-04-16 |
