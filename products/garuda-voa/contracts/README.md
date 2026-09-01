# GARUDA VOA contract freeze

Version: `1.0.0`

Frozen means every lane builds against this version. A lane never edits the contract to fit its
code. Contract changes go through the orchestrator; business-visible changes also require owner
approval.

Generate the TypeScript contract:

```sh
./node_modules/.bin/openapi-typescript products/garuda-voa/contracts/openapi.yaml \
  --output apps/mouth/src/lib/api/garuda-voa.generated.d.ts
```

CI regenerates, then gates drift:

```sh
git diff --exit-code -- apps/mouth/src/lib/api/garuda-voa.generated.d.ts
```
