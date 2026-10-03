**REWORK**

1. **HIGH — Tests inside control-flow blocks can still vanish green.**  
   Concrete line: `for node in body:` in `walk()`, whose branches handle only functions and `Test*` classes.

   Module-level and class-level `if`, `try`, `with`, and similar blocks are never traversed. For example:

   ```python
   if True:
       def test_guard():
           assert protected_behavior()
   ```

   Pytest can collect this test, but `expected` never contains it. Deselecting it passes this check while other expected tests run. Conditional redefinitions also escape duplicate detection. Traverse statements that retain the current namespace, including their alternative and exception branches; account for mutually exclusive definitions when detecting duplicates.

2. **MED — Shadowed definitions can still satisfy the same identity.**  
   Concrete lines: `seen = set()`, `walk(module, node.body, scope + [node.name])`, and `expected.add(key)`.

   Two successive `class TestA:` definitions containing `test_guard` receive separate `seen` sets but produce the same expected key. The second class replaces the first, and its test satisfies the check: green.

   Likewise, inside one class:

   ```python
   def test_guard(self):
       assert protected_behavior()

   def test_replacement(self):
       pass

   test_guard = test_replacement
   ```

   Pytest can collect the replacement under both names. Both expected identities appear, although the original guard never executes. An assignment to a non-callable would correctly produce a missing test; callable replacement is the bypass. Track namespace rebinding, or explicitly reject unsupported rebinding patterns.

3. **MED — The AST inventory includes definitions pytest intentionally does not collect.**  
   Concrete lines: `node.name.startswith("test")` and `node.name.startswith("Test")`.

   Examples include `@pytest.fixture def test_helper(...)`, a `Test*` class defining `__init__`, and a function or class with `__test__ = False`. These produce missing identities despite a successful, legitimate pytest run.

   Such constructs in the actual corpus are **not shown**. If they are forbidden conventions for these suites, enforce and describe that restriction explicitly; otherwise the inventory needs collection-aware exclusions. Ordinary skip/skipif/xfail markers are different: rejecting their skipped cases is required by this task.

4. **LOW — Classname parsing selects a prefix match rather than the actual module boundary.**  
   Concrete line: `idx = next((i for i, p in enumerate(parts) if p.startswith("test_wa_attention_")), None)`.

   Normal nested classes work: `scripts.tests.test_wa_attention_example.TestOuter.TestInner` becomes the correct qualified identity. Ordinary package prefixes also work. A package segment itself beginning `test_wa_attention_`, however, is selected prematurely and causes false RED. Such a package is **not shown**. Match against discovered module identities and validate the boundary.

5. **LOW — Two documentation claims overstate the check.**  
   Concrete lines: the comments containing `a runtime parametrize list` and `an override desynchronises this and goes RED, never green`.

   Runtime parametrization of a statically defined function does not hide that function from the AST; individual variants are simply outside the stated coverage guarantee. Collection-pattern overrides also need not cause RED—for example, expanding patterns can collect additional definitions the AST ignores. Force the assumed patterns in the pytest invocation if they are prerequisites.

Round-1 status:

- **R1-1: RESOLVED** for normal pytest JUnit classnames: class identity is retained, including nested class segments. Finding 4 covers the remaining boundary assumption.
- **R1-2: RESOLVED** for directly nested `Test*` classes. Definitions beneath control-flow statements remain uncovered under finding 1.
- **R1-3: NOT RESOLVED.** Direct repeated function definitions are detected; conditional definitions and repeated class scopes are not.
- **R1-4: RESOLVED** for the three pinned suite filenames. Deleting any of those makes `absent_suites` nonempty.
- **R1-5: RESOLVED** as disclosure of per-definition coverage and static-analysis limits, subject to the wording corrections in finding 5.

The empty-base guard and handling of grep’s reported exit statuses are correct as shown. The heredoc indentation is also correct: YAML removes the common indentation, leaving Python and the closing `PY` at the required columns. Builder proofs were supplied but cannot be independently verified in this static review.
