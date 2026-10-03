REWORK

1. “Any statement in walked scope that LOADS…” overclaims. `loads_of` excludes function and class definitions; their defaults, decorators and bases can reference tests undetected. Say “non-definition statements.”

2. The refusal list still leaves rebinding, imports, duplicate definitions, class restrictions and decorators unqualified. Defining “in walked scope” does not scope entries lacking that phrase.

3. “Exactly that and nothing wider,” “apply … only,” and bodies being “not seen” misdescribe control-flow handling: `flow_problems` and `loads_of` use recursive `ast.walk`, reaching function and otherwise-unwalked class bodies beneath control flow.

4. “Not walked, hence not defended” is too absolute. Whole-tree `hook_problems` still rejects introspection attributes, `.register()` calls, `.pluginmanager` access and certain body-swap assignments inside those bodies. The characterization examples establish specific accepted snippets, not universal exemptions.

5. “An attribute name built from pieces” / “built at runtime” understates the residual. Literal `getattr(x, "__code__")` also avoids the introspection attribute check, subject to other checks; string construction is unnecessary.

6. The retained “Constructs the AST cannot follow are refused” and “a green run must mean every definition executed” remain incompatible with the declared bypasses. Matching JUnit identities cannot guarantee execution of the original bodies.
