# B1.2 round-2 cure spec — the runtime binding of every protected name

Round 2 (Codex, `codex-round-2-b1-2.md`) showed that an AST guard which counts `def` nodes cannot
see a later class-body rebinding (`test_x_pipeline_variant = test_x`), a class decorator, a
module-level `setattr`, or any other runtime replacement: pytest runs whatever object the class
attribute is bound to, not the `def` the guard parsed. Enumerating rebinding syntaxes is a
fix-of-a-fix; the surface is the RUNTIME binding, so the guard measures that.

## G11 — the object pytest collects is the `def` the guard inspected

For each of the 18 protected names (9 originals + 9 `_pipeline_variant`s):

1. Import the test module by its dotted name (`backend.tests.` + path without `.py`, `/` → `.`)
   with `importlib.import_module` — no app init beyond what the module already does at import.
2. `cls = getattr(module, class_name)`; require `cls.__module__ == module.__name__` and
   `cls.__qualname__ == class_name` (the module-level class name is not rebound to another class).
3. `obj = cls.__dict__[name]` (NOT `getattr`: no inheritance, no descriptor); require
   `inspect.isfunction(obj)`, `obj.__name__ == name`, `obj.__qualname__ == f"{class_name}.{name}"`,
   and `Path(obj.__code__.co_filename).resolve() == <the parsed file>.resolve()`.
4. Let `node` be the single `FunctionDef`/`AsyncFunctionDef` G7 found for `name`; require
   `obj.__code__.co_firstlineno == min([node.lineno] + [d.lineno for d in node.decorator_list])`.
   (CPython sets `co_firstlineno` to the first decorator's line for a decorated function.)
5. Keep G7; extend its message to point at G11 for non-`def` rebindings.

Every mismatch message names the node id, the protected name, the expected and the observed
qualname/line, so a red is legible.

## Mutations that must be RED (Dux re-measures them independently)

- (r1) after the valid variant in `test_reasoning.py`: `test_no_keyword_overlap_pipeline_variant = test_no_keyword_overlap` → G11
- (r2) module level after the class: `TestCalculateEvidenceScore.test_no_keyword_overlap_pipeline_variant = lambda self: None` → G11
- (r3) a class decorator on `TestCalculateEvidenceScore` that replaces the variant attribute → G11
- all seven earlier mutations stay red (m1 G6, m2 G7, m3 G8, m4 G2+G9, m5a G1+G9, m5b G4+G6, m6 G9)

## Fence

Only `tests/unit/services/rag/test_tripwire_pipeline_variants_guard.py`. Nothing else.
