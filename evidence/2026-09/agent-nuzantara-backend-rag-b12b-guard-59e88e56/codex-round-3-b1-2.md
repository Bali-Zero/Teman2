---
title: "B1.2 adversarial round 3 — Codex gpt-5.6-sol (effort high, read-only, account 2 on Mini, diffs inlined, scoped to the round-2 cure)"
reviewed_sha: 775c6f39a0
at: "2026-09-11T18:36:12Z/18:41:24Z"
extraction: "last VERDICT line of /tmp/b1-2-r3/out.txt on Mini to end of file"
---

VERDICT: BLOCK

R2-N1: NOT CURED — G11 catches ordinary rebinding, but it proves only matching metadata, not that the runtime function is the parsed `def`.

- Class-body alias: caught by the `obj.__name__` check at `test_tripwire_pipeline_variants_guard.py:853-857`.
- Module-level lambda: caught by the same check (`"<lambda>"`), then by qualname/source-line checks at `:858-879`.
- Simple class decorator replacing the variant with the original: caught by `__name__`.
- `functools.wraps` wrapper: copied name/qualname pass, but its wrapper code fails `co_filename` or `co_firstlineno` at `:863-879`.
- Ordinary metaclass or `__init_subclass__` replacement: caught by function metadata checks. A replacement with forged metadata bypasses them.
- Module `__getattr__`: does not intercept the existing class attribute. Deleting/replacing the class normally fails `:832-841`; a fully spoofed substitute remains possible.
- Concrete green bypass: after the class, obtain the valid variant’s filename and first line, compile an empty function under that filename with padding to the same line, copy its qualname, and assign it back:

```python
_name = "test_no_keyword_overlap_pipeline_variant"
_old = TestCalculateEvidenceScore.__dict__[_name]
_ns = {}
exec(
    compile(
        "\n" * (_old.__code__.co_firstlineno - 1)
        + f"def {_name}(self):\n    pass\n",
        _old.__code__.co_filename,
        "exec",
    ),
    _ns,
)
_new = _ns[_name]
_new.__qualname__ = _old.__qualname__
setattr(TestCalculateEvidenceScore, _name, _new)
```

This is a plain function with the required name, qualname, resolved filename and first line, so every assertion at `:843-879` passes, while pytest executes an empty replacement. G1–G10 still inspect the untouched class-body definition.

- Collection-hook bypass: `pytest_collection_modifyitems` can set the target `pytest.Function` item’s cached `_obj` to `lambda **kwargs: None`. The class binding remains valid, so G11 stays green while pytest runs another callable. G11 imports a module at `:826`; it never examines the collected item.

R2-N2: CURED — `brief.yml:36-44` now explicitly says only cosines were measured and identifies rank, membership, formatter collection, fallback path and Qdrant server as unmeasured or simulated. `B1-2-build-spec.md:7-16,34-44,59-68` makes the same correction. The retained rank values are explicitly marked “SUPERSEDED,” not measured retrieval ranks.

1. `apps/backend-rag/backend/tests/unit/services/rag/test_tripwire_pipeline_variants_guard.py:843-879` — BLOCKER  
   Evidence: G11 compares forgeable function metadata only. The dynamic-compilation replacement above keeps G1–G11 green and replaces the test body. A `types.FunctionType` clone can likewise produce a different function object sharing the original code metadata.  
   Smallest fix: validate a structural digest of the complete runtime code object against independently compiled/pinned code, including nested code, defaults, closures and `obj.__globals__ is module.__dict__`. If exact object identity is required, capture the binding during definition/collection; it cannot be reconstructed from filename and line metadata afterward.

2. `apps/backend-rag/backend/tests/unit/services/rag/test_tripwire_pipeline_variants_guard.py:821-879` — BLOCKER  
   Evidence: this is an ordinary test executed after collection. It checks `cls.__dict__[name]`, not the callable cached in the corresponding `pytest.Function` item. A collection hook can replace `item._obj` without changing the class, leaving G11 green. Reloading the canonical module after collection creates the same separation between the module G11 inspects and the class/item pytest previously collected.  
   Smallest fix: perform the comparison in a collection/runtest hook against the actual protected `pytest.Function` items, and pin or reject in-scope hooks capable of subsequently replacing those items.

3. `apps/backend-rag/backend/tests/unit/services/rag/test_tripwire_pipeline_variants_guard.py:1-4,816-879` — MINOR  
   Evidence: the file still describes itself as “purely static/pure-function” with “No app init,” but G11 imports four test modules and executes all their module-level code. Dotted-name resolution and `sys.modules` caching can inspect another installed/shadow copy under differing pytest import modes. `Path.resolve()` correctly normalizes ordinary symlinks, but a relative `co_filename` is current-working-directory dependent.  
   Smallest fix: use the module attached to the collected item, verify `module.__file__` against the parsed path, and update the docstring to disclose import execution.
