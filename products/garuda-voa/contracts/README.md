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

The staff UI imports the generated schemas from that product artifact. Keep the
generator's formatting; the file is excluded from Prettier.

The required `Frontend Tests (Next.js) (mouth, true)` CI job checks freshness
without rewriting the checkout:

```sh
./node_modules/.bin/openapi-typescript products/garuda-voa/contracts/openapi.yaml \
  --output apps/mouth/src/lib/api/garuda-voa.generated.d.ts --check
```

Changes confined to `products/` currently select all test suites through the
conservative change-map fallback, so a contract-only edit runs this check too.
The separate `garuda-contract-parity` job continues to enforce the Python
contract invariants. This product artifact is independent of the global backend
`schema.d.ts`; generating it does not refresh or alter that unrelated snapshot.
