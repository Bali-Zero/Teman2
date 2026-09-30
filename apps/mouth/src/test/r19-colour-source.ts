// Where colour lives in a source file is decided by the TypeScript syntax
// tree, never by a regex over text: a position is a JSX attribute, a call
// argument or an object literal in a style position. Comments and JSX prose do
// not exist for this scanner. What a class token or a value IS is decided by
// r19-colour-guard.ts.

import ts from "typescript";
import {
  colourLiteralIn,
  forbiddenClassToken,
  forbiddenDeclaration,
  type Finding,
} from "./r19-colour-guard";

export type { Finding };

const CLASS_HELPERS = new Set(["cn", "clsx", "cva", "twMerge", "twJoin"]);
const COLOUR_ATTRIBUTES = new Set([
  "fill",
  "stroke",
  "color",
  "stopColor",
  "floodColor",
  "lightingColor",
  "bgcolor",
]);
const MAX_HOPS = 3;

// One budget per resolution: `hops` counts identifier and call steps, `visited`
// is the path of nodes being resolved. Every helper receives this same object.
type Budget = { hops: number; visited: Set<ts.Node> };
const TOKEN_DEFINITIONS = "/src/components/r19/presentation.ts";

const COMPARISONS = new Set<ts.SyntaxKind>([
  ts.SyntaxKind.EqualsEqualsToken,
  ts.SyntaxKind.EqualsEqualsEqualsToken,
  ts.SyntaxKind.ExclamationEqualsToken,
  ts.SyntaxKind.ExclamationEqualsEqualsToken,
  ts.SyntaxKind.LessThanToken,
  ts.SyntaxKind.LessThanEqualsToken,
  ts.SyntaxKind.GreaterThanToken,
  ts.SyntaxKind.GreaterThanEqualsToken,
  ts.SyntaxKind.InKeyword,
  ts.SyntaxKind.InstanceOfKeyword,
]);

function scriptKind(path: string): ts.ScriptKind {
  if (path.endsWith(".tsx")) return ts.ScriptKind.TSX;
  if (path.endsWith(".jsx")) return ts.ScriptKind.JSX;
  if (path.endsWith(".js")) return ts.ScriptKind.JS;
  return ts.ScriptKind.TS;
}

function unwrap(node: ts.Node): ts.Node {
  let n = node;
  while (
    ts.isParenthesizedExpression(n) ||
    ts.isAsExpression(n) ||
    ts.isSatisfiesExpression(n) ||
    ts.isNonNullExpression(n) ||
    ts.isTypeAssertionExpression(n)
  ) {
    n = n.expression;
  }
  return n;
}

function isFunctionLike(node: ts.Node): node is ts.FunctionLikeDeclaration {
  return (
    ts.isFunctionDeclaration(node) ||
    ts.isFunctionExpression(node) ||
    ts.isArrowFunction(node) ||
    ts.isMethodDeclaration(node)
  );
}

function isCssProperties(type: ts.TypeNode | undefined): boolean {
  if (!type || !ts.isTypeReferenceNode(type)) return false;
  const name = type.typeName;
  return ts.isIdentifier(name)
    ? name.text === "CSSProperties"
    : name.right.text === "CSSProperties";
}

function isCssPropertiesRecord(type: ts.TypeNode | undefined): boolean {
  if (!type || !ts.isTypeReferenceNode(type)) return false;
  return (
    ts.isIdentifier(type.typeName) &&
    type.typeName.text === "Record" &&
    isCssProperties(type.typeArguments?.[1])
  );
}

function attributeName(attribute: ts.JsxAttribute): string {
  return ts.isIdentifier(attribute.name)
    ? attribute.name.text
    : attribute.name.getText();
}

function keyText(name: ts.PropertyName): string | undefined {
  if (
    ts.isIdentifier(name) ||
    ts.isStringLiteralLike(name) ||
    ts.isNumericLiteral(name)
  ) {
    return name.text;
  }
  if (ts.isComputedPropertyName(name)) {
    const inner = unwrap(name.expression);
    if (ts.isStringLiteralLike(inner)) return inner.text;
  }
  return undefined;
}

function cssProperty(key: string): string {
  return key.startsWith("--")
    ? key
    : key.replace(/[A-Z]/g, (c) => `-${c.toLowerCase()}`);
}

export function forbiddenSourceColour(path: string, source: string): Finding[] {
  if (`/${path.replaceAll("\\", "/")}`.endsWith(TOKEN_DEFINITIONS)) return [];
  const sf = ts.createSourceFile(
    path,
    source,
    ts.ScriptTarget.Latest,
    true,
    scriptKind(path),
  );
  return new Scanner(sf).run();
}

class Scanner {
  private findings: Finding[] = [];
  private seen = new Set<string>();
  private variables = new Map<string, ts.Expression[]>();
  private functions = new Map<string, ts.FunctionLikeDeclaration[]>();
  private bindings = new Map<string, ts.BindingElement[]>();

  constructor(private sf: ts.SourceFile) {
    const index = (node: ts.Node) => {
      if (
        ts.isVariableDeclaration(node) &&
        ts.isIdentifier(node.name) &&
        node.initializer
      ) {
        const list = this.variables.get(node.name.text) ?? [];
        list.push(node.initializer);
        this.variables.set(node.name.text, list);
      } else if (ts.isBindingElement(node) && ts.isIdentifier(node.name)) {
        const list = this.bindings.get(node.name.text) ?? [];
        list.push(node);
        this.bindings.set(node.name.text, list);
      } else if (
        ts.isParameter(node) &&
        ts.isIdentifier(node.name) &&
        node.initializer
      ) {
        const list = this.variables.get(node.name.text) ?? [];
        list.push(node.initializer);
        this.variables.set(node.name.text, list);
      } else if (ts.isFunctionDeclaration(node) && node.name) {
        const list = this.functions.get(node.name.text) ?? [];
        list.push(node);
        this.functions.set(node.name.text, list);
      }
      ts.forEachChild(node, index);
    };
    index(sf);
  }

  run(): Finding[] {
    this.visit(this.sf);
    return this.findings;
  }

  private report(node: ts.Node, position: string, text: string) {
    const line =
      this.sf.getLineAndCharacterOfPosition(node.getStart(this.sf)).line + 1;
    const key = `${line}|${position}|${text}`;
    if (this.seen.has(key)) return;
    this.seen.add(key);
    this.findings.push({ line, position, text });
  }

  // ---- roots: the positions the entity names ------------------------------

  private visit(node: ts.Node) {
    if (ts.isJsxAttribute(node)) this.jsxAttribute(node);
    else if (ts.isCallExpression(node)) this.classHelperCall(node);
    else if (ts.isVariableDeclaration(node) && node.initializer) {
      if (isCssProperties(node.type))
        this.styleRoot(node.initializer, this.budget());
      else if (isCssPropertiesRecord(node.type))
        this.styleMap(node.initializer, this.budget());
    } else if (
      (ts.isAsExpression(node) ||
        ts.isSatisfiesExpression(node) ||
        ts.isTypeAssertionExpression(node)) &&
      isCssProperties(node.type)
    ) {
      this.styleRoot(node.expression, this.budget());
    } else if (isFunctionLike(node) && isCssProperties(node.type)) {
      for (const expression of this.returnsOf(node))
        this.styleRoot(expression, this.budget());
    } else if (ts.isPropertyAssignment(node)) {
      const key = keyText(node.name);
      if (key === "themeColor" || key === "theme-color")
        this.colourValue(node.initializer, "theme-color");
    } else if (
      ts.isJsxSelfClosingElement(node) ||
      ts.isJsxOpeningElement(node)
    ) {
      this.metaThemeColor(node);
    }
    ts.forEachChild(node, (child) => this.visit(child));
  }

  private jsxAttribute(attribute: ts.JsxAttribute) {
    const name = attributeName(attribute);
    const value = attribute.initializer;
    if (!value) return;
    if (
      name === "className" ||
      name === "class" ||
      name.endsWith("ClassName")
    ) {
      this.classPosition(value);
    } else if (name === "style") {
      if (ts.isJsxExpression(value) && value.expression) {
        this.styleRoot(value.expression, this.budget());
      }
    } else if (COLOUR_ATTRIBUTES.has(name) || name.endsWith("Color")) {
      this.colourValue(value, name);
    }
  }

  private classHelperCall(call: ts.CallExpression) {
    const callee = call.expression;
    const name = ts.isIdentifier(callee)
      ? callee.text
      : ts.isPropertyAccessExpression(callee)
        ? callee.name.text
        : "";
    if (!CLASS_HELPERS.has(name)) return;
    for (const argument of call.arguments) this.classPosition(argument);
  }

  private metaThemeColor(
    element: ts.JsxSelfClosingElement | ts.JsxOpeningElement,
  ) {
    if (element.tagName.getText() !== "meta") return;
    const attributes = element.attributes.properties.filter(ts.isJsxAttribute);
    const named = attributes.find((a) => attributeName(a) === "name");
    const nameText =
      named?.initializer && ts.isStringLiteral(named.initializer)
        ? named.initializer.text
        : "";
    if (nameText !== "theme-color") return;
    const content = attributes.find((a) => attributeName(a) === "content");
    if (content?.initializer)
      this.colourValue(content.initializer, "theme-color");
  }

  // ---- judging -------------------------------------------------------------

  private classPosition(node: ts.Node) {
    this.strings(node, "class", this.budget(), (at, text) => {
      for (const token of text.split(/\s+/).filter(Boolean)) {
        if (forbiddenClassToken(token)) this.report(at, "class", token);
      }
    });
  }

  private colourValue(node: ts.Node, attribute: string) {
    this.strings(node, "value", this.budget(), (at, text) => {
      if (colourLiteralIn(text, "color"))
        this.report(at, "colour attribute", `${attribute}: ${text}`);
    });
  }

  // ---- style positions -----------------------------------------------------

  private styleRoot(expression: ts.Node, b: Budget) {
    const node = unwrap(expression);
    if (b.visited.has(node)) return;
    b.visited.add(node);
    if (ts.isConditionalExpression(node)) {
      this.styleRoot(node.whenTrue, b);
      this.styleRoot(node.whenFalse, b);
    } else if (ts.isBinaryExpression(node)) {
      const op = node.operatorToken.kind;
      if (op === ts.SyntaxKind.AmpersandAmpersandToken)
        this.styleRoot(node.right, b);
      else if (
        op === ts.SyntaxKind.BarBarToken ||
        op === ts.SyntaxKind.QuestionQuestionToken
      ) {
        this.styleRoot(node.left, b);
        this.styleRoot(node.right, b);
      }
    } else if (ts.isObjectLiteralExpression(node)) {
      this.styleObject(node, b);
    } else if (ts.isCallExpression(node) && this.isObjectAssign(node)) {
      for (const argument of node.arguments) this.styleRoot(argument, b);
    } else if (b.hops < MAX_HOPS) {
      for (const resolved of this.resolve(node, b)) {
        b.hops++;
        this.styleRoot(resolved, b);
        b.hops--;
      }
    }
    b.visited.delete(node);
  }

  private styleMap(expression: ts.Node, b: Budget) {
    const node = unwrap(expression);
    if (!ts.isObjectLiteralExpression(node)) return;
    for (const property of node.properties) {
      if (ts.isPropertyAssignment(property))
        this.styleRoot(property.initializer, b);
    }
  }

  private isObjectAssign(call: ts.CallExpression): boolean {
    const callee = call.expression;
    return (
      ts.isPropertyAccessExpression(callee) &&
      ts.isIdentifier(callee.expression) &&
      callee.expression.text === "Object" &&
      callee.name.text === "assign"
    );
  }

  private styleObject(object: ts.ObjectLiteralExpression, b: Budget) {
    for (const property of object.properties) {
      if (ts.isSpreadAssignment(property)) {
        this.styleRoot(property.expression, b);
      } else if (
        ts.isPropertyAssignment(property) ||
        ts.isShorthandPropertyAssignment(property)
      ) {
        const key = ts.isPropertyAssignment(property)
          ? keyText(property.name)
          : property.name.text;
        const prop = key === undefined ? undefined : cssProperty(key);
        if (prop?.includes("backdrop")) this.report(property, "style", prop);
        const value = ts.isPropertyAssignment(property)
          ? property.initializer
          : property.name;
        this.strings(value, "value", b, (at, text) => {
          const hit =
            prop === undefined
              ? colourLiteralIn(text)
              : forbiddenDeclaration(prop, text);
          if (hit) this.report(at, "style", `${prop ?? "?"}: ${text}`);
        });
      }
    }
  }

  // ---- in-file resolution (P5) ---------------------------------------------

  private returnsOf(fn: ts.FunctionLikeDeclaration): ts.Expression[] {
    if (!fn.body) return [];
    if (!ts.isBlock(fn.body)) return [fn.body];
    const returns: ts.Expression[] = [];
    const find = (node: ts.Node) => {
      if (isFunctionLike(node)) return;
      if (ts.isReturnStatement(node) && node.expression)
        returns.push(node.expression);
      ts.forEachChild(node, find);
    };
    find(fn.body);
    return returns;
  }

  private budget(): Budget {
    return { hops: 0, visited: new Set() };
  }

  // The object and array literals an expression can stand for, through `?:`,
  // `??`, `||`, in-file identifiers, calls and member reads, handed to `emit`
  // while the hop that reached them is still counted. An identifier or call
  // costs a hop; a node already on the path ends as "not resolved".
  private reach(nodes: ts.Node[], b: Budget, emit: (o: ts.Node) => void) {
    for (const raw of nodes) {
      const node = unwrap(raw);
      if (
        ts.isObjectLiteralExpression(node) ||
        ts.isArrayLiteralExpression(node)
      ) {
        emit(node);
      } else if (ts.isConditionalExpression(node)) {
        this.reach([node.whenTrue, node.whenFalse], b, emit);
      } else if (ts.isBinaryExpression(node)) {
        const op = node.operatorToken.kind;
        if (op === ts.SyntaxKind.AmpersandAmpersandToken) {
          this.reach([node.right], b, emit);
        } else if (
          op === ts.SyntaxKind.BarBarToken ||
          op === ts.SyntaxKind.QuestionQuestionToken
        ) {
          this.reach([node.left, node.right], b, emit);
        }
      } else if (
        ts.isIdentifier(node) ||
        ts.isPropertyAccessExpression(node) ||
        ts.isElementAccessExpression(node) ||
        ts.isCallExpression(node)
      ) {
        if (b.visited.has(node)) continue;
        b.visited.add(node);
        const resolved = this.resolve(node, b);
        const hop = ts.isIdentifier(node) || ts.isCallExpression(node);
        if (hop) b.hops++;
        this.reach(resolved, b, emit);
        if (hop) b.hops--;
        b.visited.delete(node);
      }
    }
  }

  private memberValues(
    objects: ts.Node[],
    name: string | undefined,
    b: Budget,
  ): ts.Node[] {
    const values: ts.Node[] = [];
    this.reach(objects, b, (object) => {
      if (ts.isArrayLiteralExpression(object)) {
        values.push(...object.elements);
      } else if (ts.isObjectLiteralExpression(object)) {
        for (const property of object.properties) {
          if (ts.isPropertyAssignment(property)) {
            const key = keyText(property.name);
            if (name === undefined || key === undefined || key === name) {
              values.push(property.initializer);
            }
          } else if (ts.isShorthandPropertyAssignment(property)) {
            if (name === undefined || property.name.text === name)
              values.push(property.name);
          } else if (ts.isSpreadAssignment(property)) {
            values.push(...this.memberValues([property.expression], name, b));
          }
        }
      }
    });
    return values;
  }

  // What a destructured binding stands for: the matching member of what its
  // pattern destructures, and its own default initializer.
  private bindingValues(element: ts.BindingElement, b: Budget): ts.Node[] {
    const out: ts.Node[] = element.initializer ? [element.initializer] : [];
    const pattern = element.parent;
    const owner = pattern.parent;
    let sources: ts.Node[] = [];
    if (ts.isVariableDeclaration(owner)) {
      sources = owner.initializer ? [owner.initializer] : [];
    } else if (ts.isBindingElement(owner)) {
      sources = this.bindingValues(owner, b);
    }
    let key: string | undefined;
    if (ts.isObjectBindingPattern(pattern) && !element.dotDotDotToken) {
      const named = element.propertyName ?? element.name;
      if (ts.isIdentifier(named) || ts.isStringLiteralLike(named))
        key = named.text;
    }
    out.push(...this.memberValues(sources, key, b));
    return out;
  }

  // The in-file nodes an expression stands for: a variable's or binding's
  // initializer, a function call's return expressions, a member of a resolved
  // object.
  private resolve(expression: ts.Node, b: Budget): ts.Node[] {
    const node = unwrap(expression);
    if (ts.isIdentifier(node)) {
      if (b.hops >= MAX_HOPS) return [];
      const declared = (this.variables.get(node.text) ?? []).filter(
        (init) => !isFunctionLike(unwrap(init)),
      );
      const bound = (this.bindings.get(node.text) ?? []).flatMap((element) =>
        this.bindingValues(element, b),
      );
      return [...declared, ...bound];
    }
    if (ts.isPropertyAccessExpression(node)) {
      return this.memberValues([node.expression], node.name.text, b);
    }
    if (ts.isElementAccessExpression(node)) {
      const argument = unwrap(node.argumentExpression);
      const name = ts.isStringLiteralLike(argument) ? argument.text : undefined;
      return this.memberValues([node.expression], name, b);
    }
    if (ts.isCallExpression(node) && ts.isIdentifier(node.expression)) {
      if (b.hops >= MAX_HOPS) return [];
      const callee = node.expression.text;
      const declared = this.functions.get(callee) ?? [];
      const initialisers = (this.variables.get(callee) ?? [])
        .map(unwrap)
        .filter(isFunctionLike);
      return [...declared, ...initialisers].flatMap((fn) => this.returnsOf(fn));
    }
    return [];
  }

  // Every string-like node of `node`, resolving in-file identifiers (at most
  // MAX_HOPS hops, each declaration once). Conditions and comparison operands
  // decide a value, they are never one; object keys are class tokens only when
  // the position is a class position.
  private strings(
    node: ts.Node,
    mode: "class" | "value",
    b: Budget,
    emit: (at: ts.Node, text: string) => void,
  ) {
    const follow = (expression: ts.Node) => {
      if (b.hops >= MAX_HOPS) return;
      for (const resolved of this.resolve(expression, b)) {
        if (b.visited.has(resolved)) continue;
        b.visited.add(resolved);
        b.hops++;
        this.strings(resolved, mode, b, emit);
        b.hops--;
        b.visited.delete(resolved);
      }
    };
    const walk = (n: ts.Node): void => {
      if (ts.isStringLiteralLike(n)) return emit(n, n.text);
      if (ts.isTemplateExpression(n)) {
        if (mode === "class") {
          emit(n.head, n.head.text);
          for (const span of n.templateSpans) {
            walk(span.expression);
            emit(span.literal, span.literal.text);
          }
        } else {
          emit(
            n,
            [n.head.text, ...n.templateSpans.map((s) => s.literal.text)].join(
              " ",
            ),
          );
          for (const span of n.templateSpans) walk(span.expression);
        }
        return;
      }
      if (ts.isTypeNode(n)) return;
      if (ts.isConditionalExpression(n)) {
        walk(n.whenTrue);
        return walk(n.whenFalse);
      }
      if (ts.isBinaryExpression(n)) {
        const op = n.operatorToken.kind;
        if (COMPARISONS.has(op)) return;
        if (op === ts.SyntaxKind.AmpersandAmpersandToken) return walk(n.right);
      }
      if (ts.isPropertyAssignment(n)) {
        if (mode === "class" && ts.isStringLiteralLike(n.name))
          emit(n.name, n.name.text);
        return walk(n.initializer);
      }
      if (ts.isShorthandPropertyAssignment(n)) return follow(n.name);
      if (ts.isPropertyAccessExpression(n) || ts.isElementAccessExpression(n))
        return follow(n);
      if (ts.isIdentifier(n)) return follow(n);
      if (ts.isCallExpression(n)) {
        const callee = unwrap(n.expression);
        if (ts.isIdentifier(callee)) follow(n);
        else if (ts.isPropertyAccessExpression(callee)) walk(callee.expression);
        else walk(callee);
        for (const argument of n.arguments) walk(argument);
        return;
      }
      if (isFunctionLike(n)) {
        if (n.body) walk(n.body);
        return;
      }
      ts.forEachChild(n, walk);
    };
    walk(node);
  }
}
