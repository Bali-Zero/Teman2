# Final-delta review

VERDICT: PASS

Concrete findings:

- [Low Severity] Single-quoted Python string literals (`r'...'`) are unsupported by the matcher `/^r(f?)"((?:\\[^\n]|[^"\\\n])*)"/`. Any future backend pattern using single quotes will safely trigger the fail-closed mechanism.
- [Low Severity] The f-string interpolation replacer `/\{\{|\}\}|\{([A-Z_][A-Z0-9_]*)\}|[{}]/g` restricts variable names strictly to `[A-Z0-9_]`. If the Python backend introduces method calls or expressions (e.g., `{_E33_NAME.lower()}`), it will intentionally fail closed.
- [Low Severity] The comment scrubber `replace(/^[ \t]*#.*$/gm, "")` only captures full-line comments. Inline comments appended to a pattern (e.g., `r"regex", # legacy note`) will break the `_p` tuple regex parser and fail closed.
- [Low Severity] The call argument extractor strictly requires a trailing comma after the context keyword argument (`(?:ctx=(?:True|False),\s*)?`), or trailing the rule itself.

Material limitations:

- **Regex Engine Semantic Divergence:** JavaScript's `RegExp` execution does not have 100% parity with Python's `re` module. JS `\s` encompasses a broader set of Unicode whitespace characters, and JS `\b` word boundaries exhibit minor evaluation differences. This induces a slight frontend overmatching profile, which correctly aligns with the accepted baseline debt.
- **Hyper-Rigid Syntactical Coupling:** The updated TypeScript reader enforces absolute character-for-character compliance for the `_p` factory signature and body. By stripping all whitespace and matching against a strictly hardcoded string (`(pattern_id:str,raw:str...`), the adapter successfully mitigates the prior vulnerability where a positional parameter reordering was incorrectly accepted. Any future modifications to type hints, parameter order, default values, or `re.compile` flags will intentionally and instantly fail closed, tightly coupling the frontend CI to exact backend formatting conventions.

# Historical full-source review

VERDICT: PASS

Concrete findings:

- [Low Severity] `apps/mouth/src/i18n/secondhome-backend-patterns.ts:16`: Single-quoted Python string literals (`r'...'`) are unsupported by the matcher `/^r(f?)"((?:\\[^\n]|[^"\\\n])*)"/`. Any future backend pattern using single quotes will safely trigger the fail-closed mechanism.
- [Low Severity] `apps/mouth/src/i18n/secondhome-backend-patterns.ts:25`: The f-string interpolation replacer `/\{\{|\}\}|\{([A-Z_][A-Z0-9_]*)\}|[{}]/g` restricts variable names strictly to `[A-Z0-9_]`. If the Python backend introduces method calls or expressions (e.g., `{_E33_NAME.lower()}`), it will intentionally fail closed.
- [Low Severity] `apps/mouth/src/i18n/secondhome-backend-patterns.ts:7`: The comment scrubber `replace(/^[ \t]*#.*$/gm, "")` only captures full-line comments. Inline comments appended to a pattern (e.g. `r"regex", # legacy note`) will break the `_p` tuple regex parser and fail closed.
- [Low Severity] `apps/mouth/src/i18n/secondhome-backend-patterns.ts:44`: The call argument extractor strictly requires a trailing comma after the context keyword argument (`(?:ctx=(?:True|False),\s*)?`). If the Python formatter ever removes this trailing comma, the parser will fail closed.

Material limitations:

- **Regex Engine Semantic Divergence:** JavaScript's `RegExp` execution does not have 100% parity with Python's `re` module. Most notably, JS `\s` encompasses a broader set of Unicode whitespace characters, and JS `\b` word boundaries exhibit minor evaluation differences. This induces a slight frontend overmatching profile, which correctly aligns with the prompt's accepted baseline debt.
- **Rigid Syntactical Coupling:** The TypeScript reader relies on the exact AST string layout of `e33_claim_guard.py`. Modifying the type hint (e.g., from `tuple[ForbiddenPattern, ...]` to `Sequence`) or changing the line breaks and parameter ordering inside the `_p` factory signature will instantly break extraction. While this flawlessly fulfills the requirement to never silently skip clauses, it tightly couples the frontend CI to backend formatting conventions.
- **Node VM Export Extraction Risks:** The strategy of extracting `RULES` in `secondhome-article-claims.test.ts` via `node:vm` works perfectly because `ts.transpile` strips type data, and stripping the AST node down to `const ${d.getText(tree)};` handles basic variable assignments. However, if the target file ever adopts complex export syntaxes (e.g., `export { RULES }` at the bottom of the file), the AST manipulation logic will fail to recreate an executable evaluation string.

# Disposition

The four low formatting findings are accepted fail-closed limits. Backend Unicode/context/negation parity is not claimed. The separate named-export concern is disproved by the recorded in-memory innocence probe. The factory signature is now pinned with its body; the prior parser accepts reordered arguments and the final parser rejects them. Historical PASS binds only the earlier hashes; the final-delta PASS binds the final hashes. Both Kimi attempts timed out without a verdict.
