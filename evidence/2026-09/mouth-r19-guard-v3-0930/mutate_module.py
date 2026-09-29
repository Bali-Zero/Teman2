#!/usr/bin/env python3
"""Single-rule mutations of the two R19 colour-guard modules. Each mutant edits
ONE rule (spec section in the name), runs the table, and restores the file.
A mutant is KILLED when the table goes red. Run from the worktree root."""
import pathlib, re, shutil, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parents[3]
APP = ROOT / "apps/mouth"
GUARD = "src/test/r19-colour-guard.ts"
SOURCE = "src/test/r19-colour-source.ts"
TABLE = "src/test/r19-colour-guard.test.ts"

MUTANTS = [
    ("s1 quoted strings are not removed", GUARD, "(whole, url) => (url ? whole : \"\")", "(whole) => whole"),
    ("s2 data URIs are not decoded", GUARD, "if (/^data:/i.test(argument)) {", "if (false) {"),
    ("s2 a base64 payload is not decoded", GUARD, "if (base64) {", "if (false) {"),
    ("s3 gradients are not judged", GUARD, "if (gradient) return gradient[0];", ""),
    ("s4 theme( is not judged", GUARD, "if (theme) return theme[0];", ""),
    ("s4 default-palette var(--color-*) is not judged", GUARD, "if (palette.has(match[1].toLowerCase())) return match[0];", ""),
    ("s4 every var(--color-*) is judged", GUARD, "if (palette.has(match[1].toLowerCase())) return match[0];", "return match[0];"),
    ("s5 var() is not removed", GUARD, "v = withoutVar(v);", ""),
    ("s6 relative colour origin is not judged", GUARD, "const hit = colourLiteralIn(origin, property);", "const hit = null;"),
    ("s6 relative colour function name is judged", GUARD, "`(?<![a-z0-9-])(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\\\\(\\\\s*from\\\\s+`", "`(?<![a-z0-9-])(?:hwb)\\\\(\\\\s*from\\\\s+`"),
    ("s7 light-dark is a wrapper", GUARD, 'const COLOUR_FUNCTIONS = "rgba?|hsla?|hwb|lab|lch|oklab|oklch|color|light-dark";', 'const COLOUR_FUNCTIONS = "rgba?|hsla?|hwb|lab|lch|oklab|oklch|color";'),
    ("s7 hwb is not a colour function", GUARD, 'const COLOUR_FUNCTIONS = "rgba?|hsla?|hwb|lab|lch|oklab|oklch|color|light-dark";', 'const COLOUR_FUNCTIONS = "rgba?|hsla?|lab|lch|oklab|oklch|color|light-dark";'),
    ("s7 function boundary allows a hyphen prefix", GUARD, "`(?<![a-z0-9-])(?:${COLOUR_FUNCTIONS})\\\\(`", "`(?:${COLOUR_FUNCTIONS})\\\\(`"),
    ("s8 hex is not judged", GUARD, "if (!transparent) return match[0];", ""),
    ("s8 alpha-0 8-digit hex is judged", GUARD, '(digits.length === 8 && digits.slice(6) === "00")', "false"),
    ("s8 alpha-0 4-digit hex is judged", GUARD, '(digits.length === 4 && digits[3] === "0") ||', ""),
    ("s9 words are judged in every property", GUARD, "if (colourBearing(property)) {", "if (true) {"),
    ("s9 words are never judged", GUARD, "if (colourBearing(property)) {", "if (false) {"),
    ("s9 filter is not colour-bearing", GUARD, '  "filter",\n', ""),
    ("s9 custom properties are not colour-bearing", GUARD, 'p.startsWith("--") ||', ""),
    ("s9 system colours are not colours", GUARD, "const COLOUR_WORDS = new Set([...NAMED_COLOURS, ...SYSTEM_COLOURS]);", "const COLOUR_WORDS = new Set([...NAMED_COLOURS]);"),
    ("s2/§2 backdrop declarations are not judged", GUARD, 'if (p.includes("backdrop")) return prop;', ""),
    ("§2 --tw-gradient- declarations are not judged", GUARD, 'if (p.startsWith("--tw-gradient-")) return prop;', ""),
    ("§2 inline style split ignores parentheses", GUARD, "} else if (ch === \"(\") {\n      depth++;\n    } else if (ch === \")\") {\n      depth = Math.max(0, depth - 1);\n    }\n    if (ch === separator", "}\n    if (ch === separator"),
    ("§3 font-black is not judged", GUARD, 'utility === "font-black" ||', ""),
    ("§3 a non-utility token with a colour bracket is innocent", GUARD, 'colourLiteralIn(part.replaceAll("_", " ")) !== null', "false"),
    ("§3 arbitrary shadow fallbacks are not exposed", GUARD, "arbitrary ? exposeTwFallbacks(value) : value", "value"),
    ("§3 every token exposes its fallbacks", GUARD, "arbitrary ? exposeTwFallbacks(value) : value", "exposeTwFallbacks(value)"),
    ("§3 variants are not stripped from the utility", GUARD, "return token.slice(last + 1).replace(/^!|!$/g, \"\");", "return token.replace(/^!|!$/g, \"\");"),
    ("§3 @property blocks are judged", GUARD, "css.replace(/@property[^{]*", "css.replace(/@propertyX[^{]*"),
    ("§3 the loader does not check bg-white", GUARD, '!white || !white.includes("--color-white")', "false"),
    ("§3 the loader does not check the packages/core alias", GUARD, 'if (!ds.candidatesToCss(["bg-surface-base"])[0]) {', "if (false) {"),
    ("§3 forbiddenClassToken does not throw before load", GUARD, "if (!designSystem) {", "if (false) {"),
    ("§3 the loader does not check the export", GUARD, 'typeof tw.__unstable__loadDesignSystem !== "function"', "false"),
    ("§6 the R19 root style is judged", GUARD, 'if (element.getAttribute("data-presentation") === "r19") continue;', ""),
    ("§6 the R19 root style is exempt only by tag", GUARD, 'element.getAttribute("data-presentation") === "r19"', 'element.getAttribute("data-presentation") !== null || true'),
    ("§4 className suffix positions are not judged", SOURCE, 'name.endsWith("ClassName")', "false"),
    ("§4 twJoin is not a class helper", SOURCE, '"twMerge", "twJoin"', '"twMerge"'),
    ("§4 template text is not judged in class positions", SOURCE, "emit(n.head, n.head.text);", ""),
    ("§4 style attribute is not a root", SOURCE, 'name === "style"', 'name === "style-x"'),
    ("§4 CSSProperties variables are not roots", SOURCE, "if (isCssProperties(node.type)) this.styleRoot(node.initializer, 0, new Set());", "if (false) this.styleRoot(node.initializer, 0, new Set());"),
    ("§4 Record<_, CSSProperties> is not a root", SOURCE, "else if (isCssPropertiesRecord(node.type)) this.styleMap(node.initializer, 0, new Set());", "else if (false) this.styleMap(node.initializer, 0, new Set());"),
    ("§4 as/satisfies CSSProperties are not roots", SOURCE, "(ts.isAsExpression(node) ||\n        ts.isSatisfiesExpression(node) ||", "(ts.isAsExpression(node) && false ||\n        ts.isSatisfiesExpression(node) && false ||"),
    ("§4 CSSProperties function returns are not roots", SOURCE, "} else if (isFunctionLike(node) && isCssProperties(node.type)) {", "} else if (false) {"),
    ("§4 the false branch of a ternary is not a style", SOURCE, "this.styleRoot(node.whenFalse, hops, visited);", ""),
    ("§4 the true branch of a ternary is not a style", SOURCE, "this.styleRoot(node.whenTrue, hops, visited);", ""),
    ("§4 spread elements are not followed", SOURCE, "this.styleRoot(property.expression, hops, visited);", ""),
    ("§4 the right side of || is not a style", SOURCE, "this.styleRoot(node.left, hops, visited);\n        this.styleRoot(node.right, hops, visited);", "this.styleRoot(node.left, hops, visited);"),
    ("§4 Object.assign arguments are not styles", SOURCE, "else if (ts.isCallExpression(node) && this.isObjectAssign(node)) {", "else if (false) {"),
    ("§4 a backdrop key is not judged", SOURCE, 'if (prop?.includes("backdrop")) this.report(property, "style", prop);', ""),
        ("§4 a computed string key is not read", SOURCE, "if (ts.isStringLiteralLike(inner)) return inner.text;", ""),
    ("§4 colour attributes are not judged", SOURCE, "COLOUR_ATTRIBUTES.has(name) || name.endsWith(\"Color\")", "false"),
    ("§4 stroke is not a colour attribute", SOURCE, '  "stroke",\n', ""),
    ("§4 names ending in Color are not colour attributes", SOURCE, 'COLOUR_ATTRIBUTES.has(name) || name.endsWith("Color")', "COLOUR_ATTRIBUTES.has(name)"),
    ("§4 themeColor is not judged", SOURCE, 'key === "themeColor" || key === "theme-color"', "false"),
    ("§4 the string key theme-color is not judged", SOURCE, 'key === "themeColor" || key === "theme-color"', 'key === "themeColor"'),
    ("§4 meta theme-color is not judged", SOURCE, 'element.tagName.getText() !== "meta"', "true"),
    ("§4 a hop limit of 2", SOURCE, "const MAX_HOPS = 3;", "const MAX_HOPS = 2;"),
    ("§4 a hop limit of 4", SOURCE, "const MAX_HOPS = 3;", "const MAX_HOPS = 4;"),
    ("§4 identifiers are not resolved", SOURCE, "if (ts.isIdentifier(n)) return follow(n);", "if (ts.isIdentifier(n)) return;"),
    ("§4 member access is not resolved", SOURCE, "if (ts.isPropertyAccessExpression(n) || ts.isElementAccessExpression(n)) return follow(n);", "if (ts.isPropertyAccessExpression(n) || ts.isElementAccessExpression(n)) return;"),
    ("§4 in-file calls are not resolved", SOURCE, "if (ts.isIdentifier(n.expression)) follow(n);", ""),
    ("§4 a member of a local alias is not resolved", SOURCE, "if (depth < MAX_HOPS) values.push( ...this.memberValues(this.resolve(object, depth),", "if (false) values.push( ...this.memberValues(this.resolve(object, depth),"),
    ("§4 comparison operands are judged", SOURCE, "if (COMPARISONS.has(op)) return;", ""),
    ("§4 the condition of a ternary is judged", SOURCE, "walk(n.whenTrue);\n        return walk(n.whenFalse);", "walk(n.condition);\n        walk(n.whenTrue);\n        return walk(n.whenFalse);"),
    ("§4 the left of && is judged", SOURCE, "if (op === ts.SyntaxKind.AmpersandAmpersandToken) return walk(n.right);", ""),
    ("§4 object keys are judged in style values", SOURCE, 'if (mode === "class" && ts.isStringLiteralLike(n.name))', "if (ts.isStringLiteralLike(n.name))"),
    ("§4 object keys are not judged in class positions", SOURCE, 'if (mode === "class" && ts.isStringLiteralLike(n.name))', "if (false)"),
    ("§4 template expressions are not joined in style values", SOURCE, "[n.head.text, ...n.templateSpans.map((s) => s.literal.text)]", "[n.head.text]"),
    ("§4 the token definitions file is not exempt", SOURCE, 'const TOKEN_DEFINITIONS = "/src/components/r19/presentation.ts";', 'const TOKEN_DEFINITIONS = "/nowhere.ts";'),
    ("§4 every presentation.ts is exempt", SOURCE, "endsWith(TOKEN_DEFINITIONS)", 'endsWith("presentation.ts")'),
    ("§4 JSX is parsed as TS", SOURCE, "if (path.endsWith(\".tsx\")) return ts.ScriptKind.TSX;", ""),
    ("§4 findings are not de-duplicated", SOURCE, "if (this.seen.has(key)) return;", ""),
    ("§4 types are walked", SOURCE, "if (ts.isTypeNode(n)) return;", ""),
    ("§5 css module comments are judged", GUARD, "const clean = css.replace(/\\/\\*[\\s\\S]*?", "const clean = css.replace(/\\/\\*NOPE[\\s\\S]*?"),
    ("§5 css module at-rule statements are declarations", GUARD, 'if (colon <= 0 || trimmed.startsWith("@")) return;', "if (colon <= 0) return;"),
]

def main() -> int:
    tmp = pathlib.Path(tempfile.mkdtemp())
    backups = {}
    for rel in {GUARD, SOURCE}:
        backups[rel] = tmp / pathlib.Path(rel).name
        shutil.copy(APP / rel, backups[rel])
    survivors = 0
    try:
        for name, rel, old, new in MUTANTS:
            text = backups[rel].read_text()
            pattern = re.compile(r"\s*".join(re.escape(t) for t in old.split()))
            found = pattern.findall(text)
            if len(found) != 1:
                print(f"BROKEN MUTANT ({len(found)} matches): {name}")
                survivors += 1
                continue
            (APP / rel).write_text(pattern.sub(lambda _: new, text, count=1))
            run = subprocess.run(["npx", "vitest", "run", TABLE], cwd=APP, capture_output=True, text=True)
            failed = re.search(r"Tests\s+(\d+) failed", run.stdout + run.stderr)
            killed = run.returncode != 0
            survivors += not killed
            print(f"{'KILLED' if killed else 'SURVIVED':8} {failed.group(1) + ' rows' if failed else 'suite error':12} {name}")
            shutil.copy(backups[rel], APP / rel)
    finally:
        for rel, backup in backups.items():
            shutil.copy(backup, APP / rel)
    print(f"{len(MUTANTS)} mutants, {survivors} survived")
    return 1 if survivors else 0

if __name__ == "__main__":
    sys.exit(main())
