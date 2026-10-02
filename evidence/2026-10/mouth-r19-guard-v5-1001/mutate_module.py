#!/usr/bin/env python3
"""Mutate one R19 colour-guard rule, run the complete table, then restore it.

A row failure or timeout kills a mutant. A transform/load/parse failure is
BROKEN and proves nothing. The script must finish with no broken or surviving
mutants.
"""

import pathlib
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import os

ROOT = pathlib.Path(__file__).resolve().parents[3]
APP = ROOT / "apps/mouth"
GUARD = "src/test/r19-colour-guard.ts"
SOURCE = "src/test/r19-colour-source.ts"
TABLE = "src/test/r19-colour-guard.test.ts"
TIMEOUT = int(os.environ.get("R19_MUTANT_TIMEOUT", "12"))

MUTANTS = [
    # Value/declaration/class/DOM rules retained from v3.4.
    ("s1 quoted strings are not removed", GUARD, '(whole, url) => (url ? whole : "")', "(whole) => whole"),
    ("s2 data URIs are not decoded", GUARD, "if (/^data:/i.test(argument)) {", "if (false) {"),
    ("s2 a base64 payload is not decoded", GUARD, "if (base64) {", "if (false) {"),
    ("s3 gradients are not judged", GUARD, "if (gradient) return gradient[0];", ""),
    ("s4 theme() is not judged", GUARD, "if (theme) return theme[0];", ""),
    ("s4 default-palette var is not judged", GUARD, "if (palette.has(match[1].toLowerCase())) return match[0];", ""),
    ("s4 every color var is judged", GUARD, "if (palette.has(match[1].toLowerCase())) return match[0];", "return match[0];"),
    ("s5 var() is not removed", GUARD, "v = withoutVar(v);", ""),
    ("s6 relative colour origin is not judged", GUARD, "const hit = colourLiteralIn(origin, property);", "const hit = null;"),
    ("s7 light-dark is not a colour function", GUARD, 'const COLOUR_FUNCTIONS = "rgba?|hsla?|hwb|lab|lch|oklab|oklch|color|light-dark";', 'const COLOUR_FUNCTIONS = "rgba?|hsla?|hwb|lab|lch|oklab|oklch|color";'),
    ("s7 hwb is not a colour function", GUARD, 'const COLOUR_FUNCTIONS = "rgba?|hsla?|hwb|lab|lch|oklab|oklch|color|light-dark";', 'const COLOUR_FUNCTIONS = "rgba?|hsla?|lab|lch|oklab|oklch|color|light-dark";'),
    ("s8 hex is not judged", GUARD, "if (!transparent) return match[0];", ""),
    ("s8 alpha-0 8-digit hex is judged", GUARD, '(digits.length === 8 && digits.slice(6) === "00")', "false"),
    ("s8 alpha-0 4-digit hex is judged", GUARD, '(digits.length === 4 && digits[3] === "0") ||', ""),
    ("s9 words are judged in every property", GUARD, "if (colourBearing(property)) {", "if (true) {"),
    ("s9 words are never judged", GUARD, "if (colourBearing(property)) {", "if (false) {"),
    ("s9 filter is not colour-bearing", GUARD, '  "filter",\n', ""),
    ("s9 custom properties are not colour-bearing", GUARD, 'p.startsWith("--") ||', ""),
    ("s9 system colours are not colours", GUARD, "const COLOUR_WORDS = new Set([...NAMED_COLOURS, ...SYSTEM_COLOURS]);", "const COLOUR_WORDS = new Set([...NAMED_COLOURS]);"),
    ("s2 backdrop declarations are not judged", GUARD, 'if (p.includes("backdrop")) return prop;', ""),
    ("s2 gradient declarations are not judged", GUARD, 'if (p.startsWith("--tw-gradient-")) return prop;', ""),
    ("s3 font-black is not judged", GUARD, 'utility === "font-black" ||', ""),
    ("s3 arbitrary values are not judged", GUARD, 'colourLiteralIn(part.replaceAll("_", " ")) !== null', "false"),
    ("s3 arbitrary shadow fallbacks are hidden", GUARD, "arbitrary ? exposeTwFallbacks(value) : value", "value"),
    ("s3 variants are not stripped", GUARD, 'return token.slice(last + 1).replace(/^!|!$/g, "");', 'return token.replace(/^!|!$/g, "");'),
    ("s3 property blocks are judged", GUARD, "css.replace(/@property[^{]*", "css.replace(/@propertyX[^{]*"),
    ("s3 loader does not check bg-white", GUARD, '!white || !white.includes("--color-white")', "false"),
    ("s3 loader does not check core alias", GUARD, 'if (!ds.candidatesToCss(["bg-surface-base"])[0]) {', "if (false) {"),
    ("s3 class token does not fail before load", GUARD, "if (!designSystem) {", "if (false) {"),
    ("s3 loader export is not checked", GUARD, 'typeof tw.__unstable__loadDesignSystem !== "function"', "false"),
    ("s5 css comments are judged", GUARD, r"const clean = css.replace(/\/\*[\s\S]*?", r"const clean = css.replace(/\/\*NOPE[\s\S]*?"),
    ("s5 at-rules become declarations", GUARD, 'if (colon <= 0 || trimmed.startsWith("@")) return;', "if (colon <= 0) return;"),
    ("s6 R19 root style is judged", GUARD, 'if (element.getAttribute("data-presentation") === "r19") continue;', ""),
    ("s6 every data-presentation style is exempt", GUARD, 'element.getAttribute("data-presentation") === "r19"', 'element.getAttribute("data-presentation") !== null || true'),

    # Positions P1-P4.
    ("P1 className suffix is not judged", SOURCE, 'name.endsWith("ClassName")', "false"),
    ("P1 twJoin is not a helper", SOURCE, '"twMerge", "twJoin"', '"twMerge"'),
    ("P2 style JSX attribute is not a root", SOURCE, 'name === "style" &&', 'name === "style-x" &&'),
    ("P2 CSSProperties variable is not a root", SOURCE, "if (isCssProperties(node.type)) this.styleRoot(node.initializer);", "if (false) this.styleRoot(node.initializer);"),
    ("P2 CSSProperties record is not a root", SOURCE, "else if (isCssPropertiesRecord(node.type))\n        this.styleMap(node.initializer);", "else if (false)\n        this.styleMap(node.initializer);"),
    ("P2 CSSProperties assertion is not a root", SOURCE, "isCssProperties(node.type)\n    ) {\n      this.styleRoot(node.expression);", "false\n    ) {\n      this.styleRoot(node.expression);"),
    ("P2 CSSProperties return is not a root", SOURCE, "} else if (isFunctionLike(node) && isCssProperties(node.type)) {", "} else if (false) {"),
    ("P2 backdrop key is not judged", SOURCE, 'if (css?.includes("backdrop")) this.report(property, "style", css, use);', ""),
    ("P3/P4 stroke is not judged", SOURCE, '  "stroke",\n', ""),
    ("P3/P4 Color suffix is not judged", SOURCE, 'COLOUR_ATTRIBUTES.has(name) || name.endsWith("Color")', "COLOUR_ATTRIBUTES.has(name)"),
    ("P4 themeColor is not judged", SOURCE, 'key === "themeColor" || key === "theme-color"', "false"),
    ("P4 meta theme-color is not judged", SOURCE, 'element.tagName.getText() !== "meta"', "true"),
    ("P1 comparisons are judged", SOURCE, "if (COMPARISONS.has(operator)) return;", ""),
    ("P1 ternary condition is judged", SOURCE, "walk(current.whenTrue);\n        walk(current.whenFalse);", "walk(current.condition);\n        walk(current.whenTrue);\n        walk(current.whenFalse);"),
    ("P1 left side of and is judged", SOURCE, "walk(current.right);\n          return;", "walk(current.left);\n          walk(current.right);\n          return;"),
    ("P1 style object keys are judged", SOURCE, 'if (mode === "class" && ts.isStringLiteralLike(current.name))', "if (ts.isStringLiteralLike(current.name))"),
    ("P1 class object keys are not judged", SOURCE, 'if (mode === "class" && ts.isStringLiteralLike(current.name))', "if (false)"),
    ("P1 call receiver is not walked", SOURCE, "if (ts.isPropertyAccessExpression(callee)) walk(callee.expression);", "if (ts.isPropertyAccessExpression(callee)) return;"),
    ("P1 call arguments are not walked", SOURCE, "for (const argument of current.arguments) walk(argument);", ""),
    ("type nodes are walked", SOURCE, "if (ts.isTypeNode(current)) return;", ""),
    ("token definitions are not exempt", SOURCE, 'const TOKEN_DEFINITIONS = "/src/components/r19/presentation.ts";', 'const TOKEN_DEFINITIONS = "/nowhere.ts";'),
    ("every presentation file is exempt", SOURCE, "endsWith(TOKEN_DEFINITIONS)", 'endsWith("presentation.ts")'),
    ("TSX is parsed as TS", SOURCE, 'if (path.endsWith(".tsx")) return ts.ScriptKind.TSX;', ""),

    # v4 evaluator, fixed point, checker, and fail-closed depth.
    ("memo is removed", SOURCE, "if (cached) return cached;", "if (false && cached) return cached;"),
    ("in-progress guard is removed", SOURCE, "if (active.has(key)) {", "if (false) {"),
    ("depth cap is removed", SOURCE, "if (this.depth >= MAX_EVALUATION_DEPTH) {", "if (false) {"),
    ("depth cap does not report unresolved", SOURCE, "this.onDepthExceeded();", ""),
    ("checker is replaced by file-scope name lookup", SOURCE, ": this.checker.getSymbolAtLocation(identifier);", ': this.checker.getSymbolsInScope(this.sourceFile, ts.SymbolFlags.Variable | ts.SymbolFlags.Function).find((candidate) => candidate.name === identifier.text);'),
    ("shorthand value symbol is not used", SOURCE, "this.checker.getShorthandAssignmentValueSymbol(parent)", "this.checker.getSymbolAtLocation(identifier)"),
    ("binding declarations are discarded", SOURCE, "ts.isBindingElement(declaration) ||", ""),

    # Declarations and source rules.
    ("conditional false source is ignored", SOURCE, "add(this.sources(node.whenTrue));\n        add(this.sources(node.whenFalse));", "add(this.sources(node.whenTrue));"),
    ("and right source is ignored", SOURCE, "if (operator === ts.SyntaxKind.AmpersandAmpersandToken) {\n          add(this.sources(node.right));\n        } else if (", "if (operator === ts.SyntaxKind.AmpersandAmpersandToken) {\n        } else if ("),
    ("or/nullish left source is ignored", SOURCE, "add(this.sources(node.left));\n          add(this.sources(node.right));", "add(this.sources(node.right));"),
    ("binary plus right source is ignored", SOURCE, "add(this.stringSources(this.sources(node.left)));\n          add(this.stringSources(this.sources(node.right)));", "add(this.stringSources(this.sources(node.left)));"),
    ("dynamic member ignores object members", SOURCE, "add(this.allMembers(receivers));", ""),
    ("dynamic member ignores array elements", SOURCE, "add(this.elements(receivers));", ""),
    ("for-of identifier source is ignored", SOURCE, "if (statement && ts.isForOfStatement(statement))\n          return this.elements(this.sources(statement.expression));", "if (false)\n          return new Set();"),
    ("binding default is ignored", SOURCE, "if (binding.initializer) add(this.sources(binding.initializer));", ""),
    ("rest binding loses its whole source", SOURCE, "if (binding.dotDotDotToken) {\n      add(whole);", "if (binding.dotDotDotToken) {\n      return out;"),
    ("array binding does not use elements", SOURCE, "add(this.elements(whole));", "add(whole);"),
    ("renamed binding reads its local name", SOURCE, "const named = binding.propertyName ?? binding.name;", "const named = binding.name;"),
    ("nested binding has no owner source", SOURCE, "if (ts.isBindingElement(owner)) return this.declarationValue(owner);", "if (ts.isBindingElement(owner)) return new Set();"),
    ("map callback parameter has no receiver element", SOURCE, "add(this.elements(this.sources(callee.expression)));", ""),
    ("parameter default is ignored", SOURCE, "if (parameter.initializer) add(this.sources(parameter.initializer));", ""),
    ("useCallback variable call is not resolved", SOURCE, 'callee.text === "useCallback" &&', 'callee.text === "never-useCallback" &&'),
    ("useMemo value is not resolved", SOURCE, 'callee.text === "useMemo" &&', 'callee.text === "never-useMemo" &&'),
    ("in-file call returns are ignored", SOURCE, "for (const fn of this.functionsOf(callee))", "for (const fn of [] as ts.FunctionLikeDeclaration[])"),
    ("Object.values has no elements", SOURCE, 'method === "values" &&', 'method === "never-values" &&'),
    ("Object.assign arguments are ignored", SOURCE, 'method === "assign"', 'method === "never-assign"'),
    ("element-returning methods are ignored", SOURCE, "if (ELEMENT_OF.has(method)) return this.elements(this.sources(receiver));", "if (false) return new Set();"),
    ("same-container methods are ignored", SOURCE, "if (SAME_CONTAINER.has(method)) return this.sources(receiver);", "if (false) return new Set();"),
    ("concat receiver and args are ignored", SOURCE, 'if (method === "concat") {', 'if (method === "never-concat") {'),
    ("map and flatMap have no synthetic result", SOURCE, 'if (method === "map" || method === "flatMap") {', 'if (method === "never-map") {'),
    ("flatMap does not flatten array returns", SOURCE, 'if (method === "flatMap") {', "if (false) {"),
    ("string transforms are ignored", SOURCE, "if (STRING_TRANSFORMS.has(method)) {", "if (false) {"),
    ("join ignores container elements", SOURCE, 'if (method === "join") {', "if (false) {"),
    ("member property initializer is ignored", SOURCE, "keyText(property.name) === name", "false"),
    ("member spread is ignored", SOURCE, "add(this.member(this.sources(property.expression), name));", ""),
    ("allMembers property initializer is ignored", SOURCE, "addValue(this.sources(property.initializer));", "addValue(new Set());"),
    ("allMembers spread is ignored", SOURCE, "addValue(this.allMembers(this.sources(property.expression)));", "addValue(new Set());"),
    ("array elements are ignored", SOURCE, "else addValue(this.sources(element));", "else void element;"),
    ("array spreads are ignored", SOURCE, "addValue(this.elements(this.sources(element.expression)));", "addValue(new Set());"),
    ("resolved template spans are ignored", SOURCE, "node.templateSpans.forEach((span, index) => {", "node.templateSpans.slice(0, 0).forEach((span, index) => {"),
    ("resolved template span loses context", SOURCE, 'text += index === replacementIndex ? replacement : "var(--r19-x)";', 'text += "var(--r19-x)";'),
    ("P1 object source names are ignored", SOURCE, "if (isAstNode(source) && ts.isObjectLiteralExpression(source)) {\n        for (const property of source.properties) {", "if (false) {\n        for (const property of source.properties) {"),
    ("P1 array source elements are ignored", SOURCE, "isSyntheticContainer(source) ||\n        (isAstNode(source) && ts.isArrayLiteralExpression(source))", "isSyntheticContainer(source) ||\n        false"),
    ("P2 per-root visited guard is removed", SOURCE, "if (visited.has(object)) return;", "if (false) return;"),
    ("P2 spread object descent is removed", SOURCE, "this.styleObject(source, visited, use);", "void source;"),
    # v5 one pass: a cut is red, P1 descends once per use, work is bounded.
    ("named callbacks are not bound", SOURCE, "for (const receiver of this.namedCallbackReceivers(fn))", "for (const receiver of [] as ts.Expression[])"),
    ("named callbacks bind only the first call site", SOURCE, "this.namedCallbackReceivers(fn))\n          add(", "this.namedCallbackReceivers(fn).slice(0, 1))\n          add("),
    ("named callbacks bind any parameter", SOURCE, "isCallableFunction(fn) && fn.parameters[0] === parameter", "isCallableFunction(fn)"),
    ("named callbacks accept any method", SOURCE, "CALLBACK_METHODS.has(callee.name.text) &&\n            ts.isIdentifier(callback)", "ts.isIdentifier(callback)"),
    ("a cut reports nothing", SOURCE, "if (this.firstCut) {", "if (false) {"),
    ("the cycle finding is reported at line 1", SOURCE, "line: this.lineOf(this.firstCut.use),", "line: 1,"),
    ("the cut line is not reported", SOURCE, "`cycle: a value depends on itself (cut at line ${this.lineOf(this.firstCut.node)})`", '"cycle: a value depends on itself"'),
    ("the cut line is the use line", SOURCE, "(cut at line ${this.lineOf(this.firstCut.node)})", "(cut at line ${this.lineOf(this.firstCut.use)})"),
    ("the cycle finding is added only when there is no other finding", SOURCE, "if (this.firstCut) {", "if (this.firstCut && this.findings.length === 0) {"),
    ("the last cut is reported instead of the first", SOURCE, "this.firstCut ??= { use: this.activeUse, node };", "this.firstCut = { use: this.activeUse, node };"),
    ("the P1 per-use visited check is removed", SOURCE, "if (descended.has(source)) return;", ""),
    ("the P1 per-use visited set is never filled", SOURCE, "descended.add(source);", ""),
    ("P1 synthetic containers are not descended", SOURCE, "isSyntheticContainer(source) ||\n        (isAstNode(source)", "false ||\n        (isAstNode(source)"),
    ("the work bound is ignored", SOURCE, "if (this.work >= MAX_GUARD_WORK) {", "if (false) {"),
    ("the bound is reached but no finding is added", SOURCE, "if (!this.workExceeded) this.onWorkExceeded();", ""),
    ("the work finding is added once per use", SOURCE, "if (!this.workExceeded) this.onWorkExceeded();", "this.onWorkExceeded();"),
    ("the bound fires at 0", SOURCE, "const MAX_GUARD_WORK = 20000;", "const MAX_GUARD_WORK = 0;"),
    ("judged sources are not charged", SOURCE, "if (!this.withUse(resolvedUse, () => this.evaluator.charge())) return;", ""),
    ("contextual strings are not charged", SOURCE, "if (!this.charge()) break;", ""),
    ("the judged-source charge runs outside the use", SOURCE, "this.withUse(resolvedUse, () => this.evaluator.charge())", "this.evaluator.charge()"),
    ("unresolved findings are reported at line 1", SOURCE, "const line = this.lineOf(this.activeUse);\n    const key", "const line = 1;\n    const key"),
    ("windows paths are not normalised", SOURCE, 'path.replaceAll("\\\\", "/")', 'path.replaceAll("\\\\\\\\", "/")'),
    ("resolved use line is not reported", SOURCE, "...(useLine !== undefined && useLine !== line ? { use: useLine } : {}),", ""),
]

# Argued equivalent, not run: only the memo key separator.
EQUIVALENT = [
    # Memo keys only need to keep operation and name apart; the separator is a
    # NUL or the six characters \\u0000, neither occurs in an operation name or in
    # a property name the guard reads, so the key partition is identical.
    ("the memo key separator is the text backslash-u0000", SOURCE, "`${operation}\\u0000${name}`", "`${operation}\\\\u0000${name}`"),
]


def main() -> int:
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="r19-v5-mutants-"))
    backups = {}
    for rel in {GUARD, SOURCE}:
        backup = tmp / pathlib.Path(rel).name
        shutil.copy(APP / rel, backup)
        backups[rel] = backup

    match = os.environ.get("R19_MUTANT_FILTER")
    selected = [
        mutant for mutant in MUTANTS if not match or re.search(match, mutant[0])
    ]
    tally = {"KILLED": 0, "BROKEN": 0, "SURVIVED": 0}
    try:
        for name, rel, old, new in selected:
            baseline = backups[rel].read_text()
            matches = baseline.count(old)
            if matches != 1:
                print(f"BROKEN   pattern matched {matches} times: {name}")
                tally["BROKEN"] += 1
                continue
            (APP / rel).write_text(baseline.replace(old, new, 1))
            # Own process group: a timeout must kill vitest too, not only npx,
            # or the hung run keeps a core busy under every later mutant.
            run = subprocess.Popen(
                ["npx", "vitest", "run", TABLE],
                cwd=APP,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
            try:
                stdout, stderr = run.communicate(timeout=TIMEOUT)
                output = stdout + stderr
                failed = re.search(r"Tests\s+(\d+) failed", output)
                if failed:
                    verdict = "KILLED"
                    detail = failed.group(1) + " rows"
                elif run.returncode != 0:
                    verdict = "BROKEN"
                    detail = "suite did not run"
                else:
                    verdict = "SURVIVED"
                    detail = "0 rows"
            except subprocess.TimeoutExpired:
                os.killpg(run.pid, signal.SIGKILL)
                run.communicate()
                verdict = "KILLED"
                detail = "time bound"
            tally[verdict] += 1
            print(f"{verdict:8} {detail:12} {name}")
            shutil.copy(backups[rel], APP / rel)
    finally:
        for rel, backup in backups.items():
            shutil.copy(backup, APP / rel)

    print(
        f"{len(selected) + len(EQUIVALENT)} mutants: {tally['KILLED']} killed, "
        f"{tally['BROKEN']} broken, {tally['SURVIVED']} survived, "
        f"{len(EQUIVALENT)} equivalent (argued, not run)"
    )
    return 1 if tally["BROKEN"] or tally["SURVIVED"] else 0


if __name__ == "__main__":
    sys.exit(main())
