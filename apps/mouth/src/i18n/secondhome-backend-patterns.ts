// Test-only reader of e33_claim_guard.py's current declaration format. This is
// lexical vocabulary reuse, not a port of its context/negation logic or Python
// Unicode regex semantics. No Python runtime, imports or source execution.
export function backendPatterns(source: string): Map<string, RegExp> {
  const fail = (): never => {
    throw new Error(
      "Unsupported backend E33 vocabulary syntax; review the adapter",
    );
  };
  const clean = source.replace(/^[ \t]*#.*$/gm, "");
  const one = (pattern: RegExp): string => {
    const matches = [...clean.matchAll(pattern)];
    return matches.length === 1 ? matches[0][1] : fail();
  };
  const constants: Record<string, string> = Object.create(null);
  const strings = (expression: string): string => {
    let rest = expression.trim();
    let value = "";
    while (rest) {
      const token = /^r(f?)"((?:\\[^\n]|[^"\\\n])*)"/.exec(rest);
      if (!token) return fail();
      value += token[1]
        ? token[2].replace(
            /\{\{|\}\}|\{([A-Z_][A-Z0-9_]*)\}|[{}]/g,
            (brace, name) => {
              if (brace === "{{" || brace === "}}") return brace[0];
              return name &&
                Object.prototype.hasOwnProperty.call(constants, name)
                ? constants[name]
                : fail();
            },
          )
        : token[2];
      rest = rest.slice(token[0].length).trim();
    }
    return value || fail();
  };
  constants._E33_NAME = strings(one(/^_E33_NAME = (.+)$/gm));
  constants._NEG = strings(one(/^_NEG = \(\n([\s\S]*?)^\)/gm));
  // A later reassignment must not leave us reading an obsolete declaration.
  for (const name of ["_E33_NAME", "_NEG", "E33_FORBIDDEN_PATTERNS"]) {
    if (
      [...clean.matchAll(new RegExp(`^${name}\\b[^\\n]*=`, "gm"))].length !== 1
    )
      fail();
  }
  const factory = one(
    /^def _p(\([\s\S]*?\) -> ForbiddenPattern:\n[\s\S]*?)(?=^\S)/gm,
  );
  if (
    factory.replace(/\s+/g, "") !==
    "(pattern_id:str,raw:str,description:str,registry_ref:str,*,ctx:bool=True)->ForbiddenPattern:returnForbiddenPattern(pattern_id=pattern_id,regex=re.compile(raw,re.IGNORECASE),description=description,registry_ref=registry_ref,requires_e33_context=ctx,)"
  )
    fail();
  let rest = one(
    /^E33_FORBIDDEN_PATTERNS: tuple\[ForbiddenPattern, \.\.\.\] = \(\n([\s\S]*?)^\)/gm,
  ).trim();
  const patterns = new Map<string, RegExp>();
  while (rest) {
    // Consume the WHOLE call, including metadata and the sole supported ctx
    // option. An unrecognised expression cannot become a silently skipped row.
    const call =
      /^_p\(\s*"([a-z0-9_]+)",\s*((?:rf?"(?:\\[^\n]|[^"\\\n])*"\s*)+),\s*"(?:\\[^\n]|[^"\\\n])*",\s*(?:"[a-z0-9_]+"|LEGACY_ERROR_REF),\s*(?:ctx=(?:True|False),\s*)?\),/.exec(
        rest,
      );
    if (!call || patterns.has(call[1])) return fail();
    const raw = strings(call[2]);
    // Python-only escapes can be accepted as *different* identity escapes by
    // JS. Reject unsupported escapes rather than silently changing the rule.
    for (const escape of raw.matchAll(/\\([A-Za-z])/g)) {
      if (!"bBdDsSwWfnrtv".includes(escape[1])) fail();
    }
    try {
      patterns.set(call[1], new RegExp(raw, "i"));
    } catch {
      return fail();
    }
    rest = rest.slice(call[0].length).trim();
  }
  if (!patterns.size) fail();
  return patterns;
}
