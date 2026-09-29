• **Verdict: ACCEPT-WITH-NOTES**

1. "collected Test* classes ... (nested ones too)": pytest does not collect test methods from nested classes. Either the noun "collected" is wrong (walk visits bodies pytest never collects — conservative but mislabeled) or the parenthetical overclaims walk depth. Verify `walk()` actually recurses into nested class bodies before keeping the claim.
2. "nested ones too" conflicts with the residual "the body of a class that is not walked (a non-Test class ...)": a Test* class nested inside a non-Test class body is simultaneously claimed walked and declared unseen.
3. The yml still says "any .**code**/.**dict**/.**globals** access in a suite or in conftest.py" un-narrowed, while the docstring scopes refusals to walked scope. A literal `.__code__` inside a function body in a suite is presumably unseen. Narrow the yml sentence or confirm a separate full-file scan exists.
4. The docstring's walked-scope-only list (assignment-target, load, decorator, reflection-call) omits the import-binding and rebinding refusals, and the yml leaves those two unscoped — an import binding `test*` or a rebinding inside a function body would be invisible. The two texts are inconsistent on this.
5. Understated residual: `getattr(fn, "__code__")` with a literal string is neither in the refused-call list (setattr/globals/locals/vars/exec/eval/**import**/register) nor named as a residual.
6. The characterization test matches the declared residuals, but its docstring repeats the "collected" noun from item 1.
