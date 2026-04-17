# PR #62 Results — After State (2026-04-16)

## Summary

| Metric                  | Before (baseline)              | After (PR #62)          | Delta       |
| ----------------------- | ------------------------------ | ----------------------- | ----------- |
| cell_core importable    | ❌ ModuleNotFoundError         | ✅ OK                   | fixed       |
| /api/metabolic/stats    | 503 (or 401 auth-gated)        | Pending post-deploy     | —           |
| /api/skill/stats        | degraded (or 401 auth-gated)   | Pending post-deploy     | —           |
| Docker context size     | N/A (old context)              | 16.74 MB                | —           |
| Image size              | ~1.28 GB (baseline Task 4)     | 1.28 GB                 | 0 (stable)  |
| Build time (cached)     | N/A                            | ~20s (layer cache hits) | —           |
| Build time (no-cache)   | N/A                            | 1m 49s                  | —           |

## Local Verification

### Import smoke test (inside container)

```
$ docker run --rm rag-test-pr62-clean python -c "
import cell_core.genome
import cell_core.metabolic
import cell_core.hgt
from backend.app.dependencies import get_current_user
print('OK: cell_core + backend imports pass')
"
OK: cell_core + backend imports pass
```

### Build output (tail — no-cache cold path)

```
#19 [stage-1  8/12] COPY apps/backend-rag/scripts ./scripts
#19 DONE 0.0s

#20 [stage-1  9/12] COPY apps/backend-rag/training-data ./training-data
#20 DONE 0.0s

#21 [stage-1 10/12] COPY apps/backend-rag/*.py ./
#21 DONE 0.0s

#22 [stage-1 11/12] RUN find /home/nuzantara/.local -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true ...
#22 DONE 0.4s

#23 [stage-1 12/12] RUN chown -R nuzantara:nuzantara /app
#23 DONE 0.9s

#24 exporting to image
#24 exporting layers 13.3s done
#24 exporting manifest sha256:274994fed6a4dc2c5bc19ff495192e637dad1c9c9d8f835ad3ad80cbfb36066f done
#24 exporting config sha256:882b388553f3a231a2591434be6846772e371d95bab8650b3ee056965f2e3847 done
#24 exporting manifest list sha256:5a90df259318b5dafb48611c866c9ad2c16d582892e83465abe82f9b3316f69f done
#24 naming to docker.io/library/rag-test-pr62-clean:latest done
#24 DONE 16.4s

docker build --no-cache -f apps/backend-rag/Dockerfile -t rag-test-pr62-clean .
real    1m49.38s
```

Build completed successfully. Two non-blocking linter warnings noted:

- `FromAsCasing`: `as` keyword casing mismatch (cosmetic)
- `JSONArgsRecommended`: CMD uses shell form (intentional — allows env-var expansion)

## Deferred to Post-Deploy (Task 11)

- Live endpoint verification (requires API key + deployed image)
- 30-min health monitoring
- Live cell_core SSH import check

## Changes in This PR

| SHA         | Description                                                    |
| ----------- | -------------------------------------------------------------- |
| `8fddcbe05` | docs(research): capture PR #62 baseline — import + endpoint failures |
| `931f66a30` | chore(docker): root .dockerignore scoped to backend-rag + cell-core |
| `2adf42d5e` | docs(docker): annotate backend-rag dockerignore as non-authoritative |
| `fe5e239e0` | feat(docker): rewrite backend-rag Dockerfile for monorepo-root context |
| `c6854d68e` | ci(fly): deploy from monorepo root with --dockerfile/--config flags |
| `0a874e763` | ci(security): use monorepo-root context for Snyk Docker scan |
| `05736eb3a` | docs(claude-md): document monorepo-root Docker build context gotcha |
| `fbe31ff31` | docs(scars): resolve PR #56 cell-core-in-Docker scar (PR #62) |
