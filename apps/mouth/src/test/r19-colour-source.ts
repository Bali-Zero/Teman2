// Where colour lives in a source file is decided by the TypeScript syntax
// tree, never by a regex over text. The resolver below is a single-file
// abstract evaluator: it uses the TypeScript checker for lexical bindings and
// memoizes every (operation, node, member-name) result.

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
const ELEMENT_OF = new Set(["find", "findLast", "at", "pop", "shift"]);
const SAME_CONTAINER = new Set([
  "filter",
  "slice",
  "sort",
  "toSorted",
  "reverse",
  "toReversed",
  "flat",
]);
const STRING_TRANSFORMS = new Set([
  "join",
  "trim",
  "toString",
  "toLowerCase",
  "toUpperCase",
]);
const CALLBACK_METHODS = new Set([
  "map",
  "forEach",
  "filter",
  "find",
  "findLast",
  "some",
  "every",
  "flatMap",
]);
const TOKEN_DEFINITIONS = "/src/components/r19/presentation.ts";
const MAX_EVALUATION_DEPTH = 256;
const MAX_GUARD_WORK = 20000;

type SyntheticContainer = {
  synthetic: "container";
  owner: ts.Node;
  values: SourceSet;
};
type ContextualString = {
  synthetic: "contextual-string";
  node: ts.Node;
  text: string;
};
type Source = ts.Node | SyntheticContainer | ContextualString;
type SourceSet = Set<Source>;
type OperationMemo = Map<string, SourceSet>;
type Memo = Map<ts.Node, OperationMemo>;
type Shared = {
  namedCallbackSites?: Map<ts.Node, ts.Expression[]>;
};

function scriptKind(path: string): ts.ScriptKind {
  if (path.endsWith(".tsx")) return ts.ScriptKind.TSX;
  if (path.endsWith(".jsx")) return ts.ScriptKind.JSX;
  if (path.endsWith(".js")) return ts.ScriptKind.JS;
  return ts.ScriptKind.TS;
}

function programFor(
  path: string,
  source: string,
): { checker: ts.TypeChecker; sourceFile: ts.SourceFile } {
  const options: ts.CompilerOptions = {
    noLib: true,
    noResolve: true,
    types: [],
    jsx: ts.JsxEmit.Preserve,
    allowJs: true,
    target: ts.ScriptTarget.Latest,
    noEmit: true,
  };
  let sourceFile: ts.SourceFile | undefined;
  const host: ts.CompilerHost = {
    getSourceFile(fileName) {
      if (fileName !== path) return undefined;
      sourceFile ??= ts.createSourceFile(
        path,
        source,
        ts.ScriptTarget.Latest,
        true,
        scriptKind(path),
      );
      return sourceFile;
    },
    getDefaultLibFileName: () => "/__nolib.d.ts",
    writeFile: () => undefined,
    getCurrentDirectory: () => "/",
    getDirectories: () => [],
    fileExists: (fileName) => fileName === path,
    readFile: (fileName) => (fileName === path ? source : undefined),
    getCanonicalFileName: (fileName) => fileName,
    useCaseSensitiveFileNames: () => true,
    getNewLine: () => "\n",
  };
  const program = ts.createProgram({ rootNames: [path], options, host });
  const sf = program.getSourceFile(path);
  if (!sf) throw new Error(`r19 colour guard: TypeScript did not load ${path}`);
  return { checker: program.getTypeChecker(), sourceFile: sf };
}

function unwrap(node: ts.Node): ts.Node {
  let current = node;
  while (
    ts.isParenthesizedExpression(current) ||
    ts.isAsExpression(current) ||
    ts.isSatisfiesExpression(current) ||
    ts.isNonNullExpression(current) ||
    ts.isTypeAssertionExpression(current)
  ) {
    current = current.expression;
  }
  return current;
}

function isFunctionLike(node: ts.Node): node is ts.FunctionLikeDeclaration {
  return (
    ts.isFunctionDeclaration(node) ||
    ts.isFunctionExpression(node) ||
    ts.isArrowFunction(node) ||
    ts.isMethodDeclaration(node)
  );
}

function isCallableFunction(
  node: ts.Node,
): node is ts.FunctionDeclaration | ts.FunctionExpression | ts.ArrowFunction {
  return (
    ts.isFunctionDeclaration(node) ||
    ts.isFunctionExpression(node) ||
    ts.isArrowFunction(node)
  );
}

function isCssProperties(type: ts.TypeNode | undefined): boolean {
  if (!type || !ts.isTypeReferenceNode(type)) return false;
  return ts.isIdentifier(type.typeName)
    ? type.typeName.text === "CSSProperties"
    : type.typeName.right.text === "CSSProperties";
}

function isCssPropertiesRecord(type: ts.TypeNode | undefined): boolean {
  return (
    !!type &&
    ts.isTypeReferenceNode(type) &&
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
    : key.replace(/[A-Z]/g, (character) => `-${character.toLowerCase()}`);
}

function returnsOf(fn: ts.FunctionLikeDeclaration): ts.Expression[] {
  if (!fn.body) return [];
  if (!ts.isBlock(fn.body)) return [fn.body];
  const returns: ts.Expression[] = [];
  const visit = (node: ts.Node) => {
    if (isFunctionLike(node)) return;
    if (ts.isReturnStatement(node) && node.expression)
      returns.push(node.expression);
    ts.forEachChild(node, visit);
  };
  visit(fn.body);
  return returns;
}

function isSyntheticContainer(source: Source): source is SyntheticContainer {
  return !("getSourceFile" in source) && source.synthetic === "container";
}

function isContextualString(source: Source): source is ContextualString {
  return (
    !("getSourceFile" in source) && source.synthetic === "contextual-string"
  );
}

function isAstNode(source: Source): source is ts.Node {
  return "getSourceFile" in source;
}

function isStringNode(
  source: Source,
): source is
  | ts.StringLiteral
  | ts.NoSubstitutionTemplateLiteral
  | ts.TemplateExpression
  | ContextualString {
  return (
    isContextualString(source) ||
    (isAstNode(source) &&
      (ts.isStringLiteral(source) ||
        ts.isNoSubstitutionTemplateLiteral(source) ||
        ts.isTemplateExpression(source)))
  );
}

class Evaluator {
  private readonly memo: Memo = new Map();
  private readonly inProgress = new Map<ts.Node, Set<string>>();
  readonly synthetic = new Map<ts.Node, SyntheticContainer>();
  private work = 0;
  private workExceeded = false;
  private depth = 0;

  constructor(
    private checker: ts.TypeChecker,
    private sourceFile: ts.SourceFile,
    private shared: Shared,
    private onDepthExceeded: () => void,
    private onCut: (node: ts.Node) => void,
    private onWorkExceeded: () => void,
  ) {}

  charge(): boolean {
    if (this.work >= MAX_GUARD_WORK) {
      if (!this.workExceeded) this.onWorkExceeded();
      this.workExceeded = true;
      return false;
    }
    this.work++;
    return true;
  }

  private run(
    operation: string,
    node: ts.Node,
    name: string | undefined,
    compute: () => SourceSet,
  ): SourceSet {
    const key = name === undefined ? operation : `${operation}\u0000${name}`;
    let operations = this.memo.get(node);
    if (!operations) {
      operations = new Map();
      this.memo.set(node, operations);
    }
    const cached = operations.get(key);
    if (cached) return cached;

    let active = this.inProgress.get(node);
    if (!active) {
      active = new Set();
      this.inProgress.set(node, active);
    }
    if (active.has(key)) {
      this.onCut(node);
      return new Set();
    }
    if (this.depth >= MAX_EVALUATION_DEPTH) {
      this.onDepthExceeded();
      return new Set();
    }

    active.add(key);
    this.depth++;
    try {
      const value = compute();
      operations.set(key, value);
      return value;
    } finally {
      this.depth--;
      active.delete(key);
    }
  }

  private declarations(identifier: ts.Identifier): ts.Declaration[] {
    const parent = identifier.parent;
    const symbol =
      ts.isShorthandPropertyAssignment(parent) && parent.name === identifier
        ? this.checker.getShorthandAssignmentValueSymbol(parent)
        : this.checker.getSymbolAtLocation(identifier);
    return (symbol?.declarations ?? []).filter(
      (declaration) =>
        declaration.getSourceFile() === this.sourceFile &&
        (ts.isVariableDeclaration(declaration) ||
          ts.isBindingElement(declaration) ||
          ts.isParameter(declaration) ||
          ts.isFunctionDeclaration(declaration) ||
          ts.isFunctionExpression(declaration) ||
          ts.isArrowFunction(declaration)),
    );
  }

  sources(expression: ts.Node): SourceSet {
    return this.run("sources", expression, undefined, () => {
      const node = expression;
      const out: SourceSet = new Set();
      const add = (values: SourceSet) => {
        for (const value of values) out.add(value);
      };

      if (
        ts.isStringLiteral(node) ||
        ts.isNoSubstitutionTemplateLiteral(node)
      ) {
        out.add(node);
      } else if (ts.isTemplateExpression(node)) {
        out.add(node);
        node.templateSpans.forEach((span, index) => {
          for (const source of this.stringSources(
            this.sources(span.expression),
          )) {
            if (!this.charge()) break;
            out.add(this.contextual(node, index, source));
          }
        });
      } else if (
        ts.isObjectLiteralExpression(node) ||
        ts.isArrayLiteralExpression(node)
      ) {
        out.add(node);
      } else if (
        ts.isParenthesizedExpression(node) ||
        ts.isAsExpression(node) ||
        ts.isSatisfiesExpression(node) ||
        ts.isNonNullExpression(node) ||
        ts.isTypeAssertionExpression(node)
      ) {
        add(this.sources(node.expression));
      } else if (ts.isConditionalExpression(node)) {
        add(this.sources(node.whenTrue));
        add(this.sources(node.whenFalse));
      } else if (ts.isBinaryExpression(node)) {
        const operator = node.operatorToken.kind;
        if (operator === ts.SyntaxKind.AmpersandAmpersandToken) {
          add(this.sources(node.right));
        } else if (
          operator === ts.SyntaxKind.BarBarToken ||
          operator === ts.SyntaxKind.QuestionQuestionToken
        ) {
          add(this.sources(node.left));
          add(this.sources(node.right));
        } else if (operator === ts.SyntaxKind.PlusToken) {
          add(this.stringSources(this.sources(node.left)));
          add(this.stringSources(this.sources(node.right)));
        }
      } else if (ts.isIdentifier(node)) {
        for (const declaration of this.declarations(node))
          add(this.declarationValue(declaration));
      } else if (ts.isPropertyAccessExpression(node)) {
        add(this.member(this.sources(node.expression), node.name.text));
      } else if (ts.isElementAccessExpression(node)) {
        const argument = unwrap(node.argumentExpression);
        const receivers = this.sources(node.expression);
        if (ts.isStringLiteralLike(argument)) {
          add(this.member(receivers, argument.text));
        } else {
          add(this.allMembers(receivers));
          add(this.elements(receivers));
        }
      } else if (ts.isCallExpression(node)) {
        add(this.callValue(node));
      }
      return out;
    });
  }

  private contextual(
    template: ts.TemplateExpression,
    index: number,
    source: Source,
  ): ContextualString {
    return {
      synthetic: "contextual-string",
      node: this.sourceNode(source),
      text: this.renderTemplate(template, index, this.stringText(source)),
    };
  }

  private namedCallbackReceivers(fn: ts.Node): ts.Expression[] {
    if (!this.shared.namedCallbackSites) {
      const sites = new Map<ts.Node, ts.Expression[]>();
      const visit = (node: ts.Node) => {
        if (ts.isCallExpression(node) && node.arguments[0]) {
          const callee = unwrap(node.expression);
          const callback = unwrap(node.arguments[0]);
          if (
            ts.isPropertyAccessExpression(callee) &&
            CALLBACK_METHODS.has(callee.name.text) &&
            ts.isIdentifier(callback)
          ) {
            for (const target of this.functionsOf(callback)) {
              const receivers = sites.get(target) ?? [];
              receivers.push(callee.expression);
              sites.set(target, receivers);
            }
          }
        }
        ts.forEachChild(node, visit);
      };
      visit(this.sourceFile);
      this.shared.namedCallbackSites = sites;
    }
    return this.shared.namedCallbackSites.get(fn) ?? [];
  }

  private declarationValue(declaration: ts.Declaration): SourceSet {
    return this.run("declaration", declaration, undefined, () => {
      if (ts.isVariableDeclaration(declaration)) {
        const container = declaration.parent;
        const statement = ts.isVariableDeclarationList(container)
          ? container.parent
          : container;
        if (statement && ts.isForOfStatement(statement))
          return this.elements(this.sources(statement.expression));
        if (
          statement &&
          ts.isCatchClause(statement) &&
          statement.variableDeclaration === declaration
        ) {
          return new Set();
        }
        if (ts.isIdentifier(declaration.name) && declaration.initializer) {
          return this.sources(declaration.initializer);
        }
        return new Set();
      }
      if (ts.isBindingElement(declaration))
        return this.bindingValue(declaration);
      if (ts.isParameter(declaration)) return this.parameterValue(declaration);
      return new Set();
    });
  }

  private bindingValue(binding: ts.BindingElement): SourceSet {
    const out: SourceSet = new Set();
    const add = (values: SourceSet) => {
      for (const value of values) out.add(value);
    };
    if (binding.initializer) add(this.sources(binding.initializer));
    const pattern = binding.parent;
    const whole = this.patternValue(pattern);
    if (binding.dotDotDotToken) {
      add(whole);
    } else if (ts.isArrayBindingPattern(pattern)) {
      add(this.elements(whole));
    } else {
      const named = binding.propertyName ?? binding.name;
      const key =
        ts.isIdentifier(named) || ts.isStringLiteralLike(named)
          ? named.text
          : ts.isComputedPropertyName(named)
            ? keyText(named)
            : undefined;
      if (key !== undefined) add(this.member(whole, key));
    }
    return out;
  }

  private patternValue(pattern: ts.BindingPattern): SourceSet {
    const owner = pattern.parent;
    if (ts.isVariableDeclaration(owner)) {
      const statement = owner.parent?.parent;
      if (statement && ts.isForOfStatement(statement))
        return this.elements(this.sources(statement.expression));
      return owner.initializer ? this.sources(owner.initializer) : new Set();
    }
    if (ts.isParameter(owner)) return this.parameterValue(owner);
    if (ts.isBindingElement(owner)) return this.declarationValue(owner);
    return new Set();
  }

  private parameterValue(parameter: ts.ParameterDeclaration): SourceSet {
    return this.run("parameter", parameter, undefined, () => {
      const out: SourceSet = new Set();
      const add = (values: SourceSet) => {
        for (const value of values) out.add(value);
      };
      const fn = parameter.parent;
      const call = fn.parent;
      if (
        (ts.isArrowFunction(fn) || ts.isFunctionExpression(fn)) &&
        fn.parameters[0] === parameter &&
        call &&
        ts.isCallExpression(call) &&
        call.arguments[0] === fn
      ) {
        const callee = unwrap(call.expression);
        if (
          ts.isPropertyAccessExpression(callee) &&
          CALLBACK_METHODS.has(callee.name.text)
        ) {
          add(this.elements(this.sources(callee.expression)));
        }
      }
      if (isCallableFunction(fn) && fn.parameters[0] === parameter) {
        for (const receiver of this.namedCallbackReceivers(fn))
          add(this.elements(this.sources(receiver)));
      }
      if (parameter.initializer) add(this.sources(parameter.initializer));
      return out;
    });
  }

  private functionsOf(identifier: ts.Identifier): ts.FunctionLikeDeclaration[] {
    const functions: ts.FunctionLikeDeclaration[] = [];
    for (const declaration of this.declarations(identifier)) {
      if (isCallableFunction(declaration)) {
        functions.push(declaration);
      } else if (
        ts.isVariableDeclaration(declaration) &&
        declaration.initializer
      ) {
        const initializer = unwrap(declaration.initializer);
        if (isCallableFunction(initializer)) {
          functions.push(initializer);
        } else if (ts.isCallExpression(initializer)) {
          const callee = unwrap(initializer.expression);
          const callback = initializer.arguments[0]
            ? unwrap(initializer.arguments[0])
            : undefined;
          if (
            ts.isIdentifier(callee) &&
            callee.text === "useCallback" &&
            callback &&
            isCallableFunction(callback)
          ) {
            functions.push(callback);
          }
        }
      }
    }
    return functions;
  }

  private callbackFunctions(
    expression: ts.Expression | undefined,
  ): ts.FunctionLikeDeclaration[] {
    if (!expression) return [];
    const node = unwrap(expression);
    if (isCallableFunction(node)) return [node];
    if (ts.isIdentifier(node)) return this.functionsOf(node);
    return [];
  }

  private callValue(call: ts.CallExpression): SourceSet {
    const out: SourceSet = new Set();
    const add = (values: SourceSet) => {
      for (const value of values) out.add(value);
    };
    const callee = unwrap(call.expression);

    if (ts.isIdentifier(callee)) {
      const callback = call.arguments[0]
        ? unwrap(call.arguments[0])
        : undefined;
      if (
        callee.text === "useMemo" &&
        callback &&
        isCallableFunction(callback)
      ) {
        for (const returned of returnsOf(callback)) add(this.sources(returned));
        return out;
      }
      if (callee.text === "useCallback") return out;
      if (callee.text === "String" && call.arguments[0])
        return this.stringSources(this.sources(call.arguments[0]));
      for (const fn of this.functionsOf(callee))
        for (const returned of returnsOf(fn)) add(this.sources(returned));
      return out;
    }

    if (!ts.isPropertyAccessExpression(callee)) return out;
    const method = callee.name.text;
    const receiver = callee.expression;
    if (
      ts.isIdentifier(receiver) &&
      receiver.text === "Object" &&
      method === "values" &&
      call.arguments[0]
    ) {
      return new Set([
        this.container(call, this.allMembers(this.sources(call.arguments[0]))),
      ]);
    }
    if (
      ts.isIdentifier(receiver) &&
      receiver.text === "Object" &&
      method === "assign"
    ) {
      for (const argument of call.arguments) add(this.sources(argument));
      return out;
    }
    if (ELEMENT_OF.has(method)) return this.elements(this.sources(receiver));
    if (SAME_CONTAINER.has(method)) return this.sources(receiver);
    if (method === "concat") {
      add(this.sources(receiver));
      for (const argument of call.arguments) add(this.sources(argument));
      return out;
    }
    if (method === "map" || method === "flatMap") {
      const values: SourceSet = new Set();
      for (const fn of this.callbackFunctions(call.arguments[0])) {
        for (const returned of returnsOf(fn)) {
          const sources = this.sources(returned);
          if (method === "flatMap") {
            for (const value of sources) {
              if (isAstNode(value) && ts.isArrayLiteralExpression(value)) {
                for (const item of this.elements(new Set([value])))
                  values.add(item);
              } else {
                values.add(value);
              }
            }
          } else {
            for (const value of sources) values.add(value);
          }
        }
      }
      return new Set([this.container(call, values)]);
    }
    if (STRING_TRANSFORMS.has(method)) {
      const strings = this.stringSources(this.sources(receiver));
      if (method === "join") {
        for (const source of this.stringSources(
          this.elements(this.sources(receiver)),
        )) {
          strings.add(source);
        }
      }
      return strings;
    }
    return out;
  }

  private container(owner: ts.Node, values: SourceSet): SyntheticContainer {
    let container = this.synthetic.get(owner);
    if (!container) {
      container = { synthetic: "container", owner, values };
      this.synthetic.set(owner, container);
    }
    return container;
  }

  member(sources: SourceSet, name: string): SourceSet {
    const out: SourceSet = new Set();
    for (const source of sources) {
      for (const value of this.memberOf(source, name)) out.add(value);
    }
    return out;
  }

  private memberOf(source: Source, name: string): SourceSet {
    if (!isAstNode(source) || !ts.isObjectLiteralExpression(source)) {
      return new Set();
    }
    return this.run("member", source, name, () => {
      const out: SourceSet = new Set();
      const add = (values: SourceSet) => {
        for (const value of values) out.add(value);
      };
      for (const property of source.properties) {
        if (
          ts.isPropertyAssignment(property) &&
          keyText(property.name) === name
        ) {
          add(this.sources(property.initializer));
        } else if (
          ts.isShorthandPropertyAssignment(property) &&
          property.name.text === name
        ) {
          add(this.sources(property.name));
        } else if (ts.isSpreadAssignment(property)) {
          add(this.member(this.sources(property.expression), name));
        }
      }
      return out;
    });
  }

  allMembers(sources: SourceSet): SourceSet {
    const out: SourceSet = new Set();
    const add = (values: SourceSet) => {
      for (const value of values) out.add(value);
    };
    for (const source of sources) {
      if (isSyntheticContainer(source)) {
        add(source.values);
      } else if (isAstNode(source) && ts.isObjectLiteralExpression(source)) {
        add(
          this.run("all-members", source, undefined, () => {
            const values: SourceSet = new Set();
            const addValue = (items: SourceSet) => {
              for (const item of items) values.add(item);
            };
            for (const property of source.properties) {
              if (ts.isPropertyAssignment(property))
                addValue(this.sources(property.initializer));
              else if (ts.isShorthandPropertyAssignment(property))
                addValue(this.sources(property.name));
              else if (ts.isSpreadAssignment(property))
                addValue(this.allMembers(this.sources(property.expression)));
            }
            return values;
          }),
        );
      }
    }
    return out;
  }

  elements(sources: SourceSet): SourceSet {
    const out: SourceSet = new Set();
    const add = (values: SourceSet) => {
      for (const value of values) out.add(value);
    };
    for (const source of sources) {
      if (isSyntheticContainer(source)) {
        add(source.values);
      } else if (isAstNode(source) && ts.isArrayLiteralExpression(source)) {
        add(
          this.run("elements", source, undefined, () => {
            const values: SourceSet = new Set();
            const addValue = (items: SourceSet) => {
              for (const item of items) values.add(item);
            };
            for (const element of source.elements) {
              if (ts.isSpreadElement(element))
                addValue(this.elements(this.sources(element.expression)));
              else addValue(this.sources(element));
            }
            return values;
          }),
        );
      }
    }
    return out;
  }

  stringSources(sources: SourceSet): SourceSet {
    const strings: SourceSet = new Set();
    for (const source of sources) if (isStringNode(source)) strings.add(source);
    return strings;
  }

  sourceNode(source: Source): ts.Node {
    if (isContextualString(source)) return source.node;
    if (isSyntheticContainer(source)) return source.owner;
    return source;
  }

  stringText(source: Source): string {
    if (isContextualString(source)) return source.text;
    if (
      isAstNode(source) &&
      (ts.isStringLiteral(source) || ts.isNoSubstitutionTemplateLiteral(source))
    ) {
      return source.text;
    }
    if (isAstNode(source) && ts.isTemplateExpression(source))
      return this.renderTemplate(source);
    return "";
  }

  private renderTemplate(
    template: ts.TemplateExpression,
    replacementIndex?: number,
    replacement = "",
  ): string {
    let text = template.head.text;
    template.templateSpans.forEach((span, index) => {
      text += index === replacementIndex ? replacement : "var(--r19-x)";
      text += span.literal.text;
    });
    return text;
  }
}

class Scanner {
  private findings: Finding[] = [];
  private seen = new Set<string>();
  private evaluator: Evaluator;
  private activeUse: ts.Node;
  private firstCut: { use: ts.Node; node: ts.Node } | undefined;

  constructor(
    private sourceFile: ts.SourceFile,
    checker: ts.TypeChecker,
  ) {
    this.activeUse = sourceFile;
    this.evaluator = new Evaluator(
      checker,
      sourceFile,
      {},
      () => this.reportUnresolved("resolution deeper than 256"),
      (node) => {
        this.firstCut ??= { use: this.activeUse, node };
      },
      () =>
        this.reportUnresolved(`too much work to judge (>${MAX_GUARD_WORK})`),
    );
  }

  run(): Finding[] {
    this.visit(this.sourceFile);
    if (this.firstCut) {
      this.findings.push({
        line: this.lineOf(this.firstCut.use),
        position: "unresolved",
        text: `cycle: a value depends on itself (cut at line ${this.lineOf(this.firstCut.node)})`,
      });
    }
    return this.findings;
  }

  private lineOf(node: ts.Node): number {
    return (
      this.sourceFile.getLineAndCharacterOfPosition(
        node.getStart(this.sourceFile),
      ).line + 1
    );
  }

  private report(
    source: ts.Node,
    position: string,
    text: string,
    use?: ts.Node,
  ) {
    const line =
      this.sourceFile.getLineAndCharacterOfPosition(
        source.getStart(this.sourceFile),
      ).line + 1;
    const key = `${line}|${position}|${text}`;
    if (this.seen.has(key)) return;
    this.seen.add(key);
    const useLine = use
      ? this.sourceFile.getLineAndCharacterOfPosition(
          use.getStart(this.sourceFile),
        ).line + 1
      : undefined;
    this.findings.push({
      line,
      ...(useLine !== undefined && useLine !== line ? { use: useLine } : {}),
      position,
      text,
    });
  }

  private reportUnresolved(text: string) {
    const line = this.lineOf(this.activeUse);
    const key = `${line}|unresolved|${text}`;
    if (this.seen.has(key)) return;
    this.seen.add(key);
    this.findings.push({ line, position: "unresolved", text });
  }

  private withUse<T>(use: ts.Node, evaluate: () => T): T {
    const before = this.activeUse;
    this.activeUse = use;
    try {
      return evaluate();
    } finally {
      this.activeUse = before;
    }
  }

  private sources(expression: ts.Node, use: ts.Node): SourceSet {
    return this.withUse(use, () => this.evaluator.sources(expression));
  }

  private visit(node: ts.Node) {
    if (ts.isJsxAttribute(node)) {
      this.jsxAttribute(node);
    } else if (ts.isCallExpression(node)) {
      this.classHelperCall(node);
    } else if (ts.isVariableDeclaration(node) && node.initializer) {
      if (isCssProperties(node.type)) this.styleRoot(node.initializer);
      else if (isCssPropertiesRecord(node.type))
        this.styleMap(node.initializer);
    } else if (
      (ts.isAsExpression(node) ||
        ts.isSatisfiesExpression(node) ||
        ts.isTypeAssertionExpression(node)) &&
      isCssProperties(node.type)
    ) {
      this.styleRoot(node.expression);
    } else if (isFunctionLike(node) && isCssProperties(node.type)) {
      for (const expression of returnsOf(node)) this.styleRoot(expression);
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
    } else if (
      name === "style" &&
      ts.isJsxExpression(value) &&
      value.expression
    ) {
      this.styleRoot(value.expression);
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
    const named = attributes.find(
      (attribute) => attributeName(attribute) === "name",
    );
    if (
      !named?.initializer ||
      !ts.isStringLiteral(named.initializer) ||
      named.initializer.text !== "theme-color"
    ) {
      return;
    }
    const content = attributes.find(
      (attribute) => attributeName(attribute) === "content",
    );
    if (content?.initializer)
      this.colourValue(content.initializer, "theme-color");
  }

  private classPosition(node: ts.Node) {
    this.strings(node, "class", node, (source, text, use) => {
      for (const token of text.split(/\s+/).filter(Boolean)) {
        if (forbiddenClassToken(token))
          this.report(source, "class", token, use);
      }
    });
  }

  private colourValue(node: ts.Node, attribute: string) {
    this.strings(node, "value", node, (source, text, use) => {
      if (colourLiteralIn(text, "color"))
        this.report(source, "colour attribute", `${attribute}: ${text}`, use);
    });
  }

  private styleRoot(expression: ts.Node) {
    const visited = new Set<ts.ObjectLiteralExpression>();
    for (const source of this.sources(expression, expression)) {
      if (isAstNode(source) && ts.isObjectLiteralExpression(source))
        this.styleObject(source, visited, expression);
    }
  }

  private styleMap(expression: ts.Node) {
    const node = unwrap(expression);
    if (!ts.isObjectLiteralExpression(node)) return;
    for (const property of node.properties) {
      if (ts.isPropertyAssignment(property))
        this.styleRoot(property.initializer);
    }
  }

  private styleObject(
    object: ts.ObjectLiteralExpression,
    visited: Set<ts.ObjectLiteralExpression>,
    use: ts.Node,
  ) {
    if (visited.has(object)) return;
    visited.add(object);
    for (const property of object.properties) {
      if (ts.isSpreadAssignment(property)) {
        for (const source of this.sources(property.expression, use)) {
          if (isAstNode(source) && ts.isObjectLiteralExpression(source))
            this.styleObject(source, visited, use);
        }
        continue;
      }
      if (
        !ts.isPropertyAssignment(property) &&
        !ts.isShorthandPropertyAssignment(property)
      ) {
        continue;
      }
      const key = ts.isPropertyAssignment(property)
        ? keyText(property.name)
        : property.name.text;
      const css = key === undefined ? undefined : cssProperty(key);
      if (css?.includes("backdrop")) this.report(property, "style", css, use);
      const value = ts.isPropertyAssignment(property)
        ? property.initializer
        : property.name;
      this.strings(value, "value", use, (source, text, useSite) => {
        const hit =
          css === undefined
            ? colourLiteralIn(text)
            : forbiddenDeclaration(css, text);
        if (hit)
          this.report(source, "style", `${css ?? "?"}: ${text}`, useSite);
      });
    }
  }

  private strings(
    node: ts.Node,
    mode: "class" | "value",
    use: ts.Node,
    emit: (source: ts.Node, text: string, use?: ts.Node) => void,
  ) {
    const descended = new Set<ts.Node>();
    const emitSource = (source: Source, resolvedUse: ts.Node) => {
      if (!this.withUse(resolvedUse, () => this.evaluator.charge())) return;
      if (isStringNode(source)) {
        emit(
          this.evaluator.sourceNode(source),
          this.evaluator.stringText(source),
          resolvedUse,
        );
        return;
      }
      if (mode !== "class" || !isAstNode(source)) return;
      if (ts.isObjectLiteralExpression(source)) {
        for (const property of source.properties) {
          if (
            (ts.isPropertyAssignment(property) ||
              ts.isMethodDeclaration(property)) &&
            ts.isStringLiteralLike(property.name)
          ) {
            emit(property.name, property.name.text, resolvedUse);
          }
        }
      } else if (ts.isArrayLiteralExpression(source)) {
        if (descended.has(source)) return;
        descended.add(source);
        const elements = this.withUse(resolvedUse, () =>
          this.evaluator.elements(new Set([source])),
        );
        for (const element of elements) emitSource(element, resolvedUse);
      }
    };

    const emitResolved = (expression: ts.Node) => {
      for (const source of this.sources(expression, use))
        emitSource(source, use);
    };

    const walk = (current: ts.Node): void => {
      if (
        ts.isStringLiteral(current) ||
        ts.isNoSubstitutionTemplateLiteral(current)
      ) {
        emit(current, current.text);
        return;
      }
      if (ts.isTemplateExpression(current)) {
        emitResolved(current);
        return;
      }
      if (ts.isTypeNode(current)) return;
      if (ts.isConditionalExpression(current)) {
        walk(current.whenTrue);
        walk(current.whenFalse);
        return;
      }
      if (ts.isBinaryExpression(current)) {
        const operator = current.operatorToken.kind;
        if (COMPARISONS.has(operator)) return;
        if (operator === ts.SyntaxKind.AmpersandAmpersandToken) {
          walk(current.right);
          return;
        }
      }
      if (ts.isPropertyAssignment(current)) {
        if (mode === "class" && ts.isStringLiteralLike(current.name))
          emit(current.name, current.name.text);
        walk(current.initializer);
        return;
      }
      if (ts.isShorthandPropertyAssignment(current)) {
        emitResolved(current.name);
        return;
      }
      if (
        ts.isPropertyAccessExpression(current) ||
        ts.isElementAccessExpression(current) ||
        ts.isIdentifier(current)
      ) {
        emitResolved(current);
        return;
      }
      if (ts.isCallExpression(current)) {
        emitResolved(current);
        const callee = unwrap(current.expression);
        if (ts.isPropertyAccessExpression(callee)) walk(callee.expression);
        else if (!ts.isIdentifier(callee)) walk(callee);
        for (const argument of current.arguments) walk(argument);
        return;
      }
      if (isFunctionLike(current)) {
        if (current.body) walk(current.body);
        return;
      }
      ts.forEachChild(current, walk);
    };
    walk(node);
  }
}

export function forbiddenSourceColour(path: string, source: string): Finding[] {
  if (`/${path.replaceAll("\\", "/")}`.endsWith(TOKEN_DEFINITIONS)) return [];
  const { checker, sourceFile } = programFor(path, source);
  return new Scanner(sourceFile, checker).run();
}
