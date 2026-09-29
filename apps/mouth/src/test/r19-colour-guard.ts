// Entity: on an R19 surface, a colour, gradient or backdrop effect decided by a
// LITERAL instead of an R19 custom property. This module judges VALUES, CSS
// declarations and class tokens. A class token is never pattern-matched: it is
// compiled by the installed Tailwind design system (the app's real
// globals.css) and the emitted declarations are judged. Where colour lives in
// a source file is decided by r19-colour-source.ts on the syntax tree.

import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export type Finding = { line: number; position: string; text: string };

const NAMED_COLOURS =
  `aliceblue antiquewhite aqua aquamarine azure beige bisque black blanchedalmond blue
blueviolet brown burlywood cadetblue chartreuse chocolate coral cornflowerblue cornsilk crimson cyan darkblue
darkcyan darkgoldenrod darkgray darkgreen darkgrey darkkhaki darkmagenta darkolivegreen darkorange darkorchid
darkred darksalmon darkseagreen darkslateblue darkslategray darkslategrey darkturquoise darkviolet deeppink
deepskyblue dimgray dimgrey dodgerblue firebrick floralwhite forestgreen fuchsia gainsboro ghostwhite gold
goldenrod gray green greenyellow grey honeydew hotpink indianred indigo ivory khaki lavender lavenderblush
lawngreen lemonchiffon lightblue lightcoral lightcyan lightgoldenrodyellow lightgray lightgreen lightgrey
lightpink lightsalmon lightseagreen lightskyblue lightslategray lightslategrey lightsteelblue lightyellow lime
limegreen linen magenta maroon mediumaquamarine mediumblue mediumorchid mediumpurple mediumseagreen
mediumslateblue mediumspringgreen mediumturquoise mediumvioletred midnightblue mintcream mistyrose moccasin
navajowhite navy oldlace olive olivedrab orange orangered orchid palegoldenrod palegreen paleturquoise
palevioletred papayawhip peachpuff peru pink plum powderblue purple rebeccapurple red rosybrown royalblue
saddlebrown salmon sandybrown seagreen seashell sienna silver skyblue slateblue slategray slategrey snow
springgreen steelblue tan teal thistle tomato turquoise violet wheat white whitesmoke yellow yellowgreen`
    .split(/\s+/)
    .filter(Boolean);

const SYSTEM_COLOURS =
  `canvas canvastext linktext visitedtext activetext buttonface buttontext buttonborder field fieldtext
highlight highlighttext selecteditem selecteditemtext mark marktext graytext accentcolor accentcolortext`
    .split(/\s+/)
    .filter(Boolean);

export const NAMED_COLOUR_COUNT = NAMED_COLOURS.length;

const COLOUR_WORDS = new Set([...NAMED_COLOURS, ...SYSTEM_COLOURS]);

const require = createRequire(import.meta.url);

let paletteNames: Set<string> | null = null;

// The DEFAULT Tailwind palette, read from the installed theme so a moved file
// is loud and an upgrade that adds a colour is covered without an edit.
export function defaultPaletteNames(): Set<string> {
  if (paletteNames) return paletteNames;
  const theme = require.resolve("tailwindcss/theme.css");
  const names = new Set<string>();
  for (const match of readFileSync(theme, "utf8").matchAll(
    /--color-([a-z]+)(?:-\d+)?\s*:/g,
  )) {
    names.add(match[1]);
  }
  if (names.size < 20) {
    throw new Error(
      `r19 colour guard: read ${names.size} palette names from ${theme}, expected at least 20`,
    );
  }
  paletteNames = names;
  return names;
}

// Index of the `)` matching the `(` at `open`, skipping quoted text; -1 when
// unbalanced.
function closeParen(text: string, open: number): number {
  let depth = 0;
  for (let i = open; i < text.length; i++) {
    const ch = text[i];
    if (ch === '"' || ch === "'") {
      const end = text.indexOf(ch, i + 1);
      if (end < 0) return -1;
      i = end;
    } else if (ch === "(") {
      depth++;
    } else if (ch === ")" && --depth === 0) {
      return i;
    }
  }
  return -1;
}

const SVG_COLOUR_ATTRIBUTE =
  /(?:^|[\s<"'])(fill|stroke|stop-color|flood-color|lighting-color|color)\s*=\s*(?:'([^']*)'|"([^"]*)")/gi;

function decodeDataUri(uri: string): string {
  const base64 = uri.match(/;base64,(.*)$/is);
  if (base64) {
    try {
      return Buffer.from(base64[1], "base64").toString("utf8");
    } catch {
      return "";
    }
  }
  try {
    return decodeURIComponent(uri);
  } catch {
    return uri.replace(/%23/gi, "#");
  }
}

// Step 1 + 2: quoted strings and url(...) are not colour positions; a data URI
// is judged only where an SVG attribute carries a colour. Returns the rest of
// the value or, when a data URI is guilty, the fragment.
function withoutQuotesAndUrls(value: string): { rest: string; hit?: string } {
  const noQuotes = value.replace(
    /(url\(\s*)?('(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")/gi,
    (whole, url) => (url ? whole : ""),
  );
  let rest = "";
  let i = 0;
  for (;;) {
    const at = noQuotes.toLowerCase().indexOf("url(", i);
    if (at < 0) {
      rest += noQuotes.slice(i);
      return { rest };
    }
    const end = closeParen(noQuotes, at + 3);
    const inner =
      end < 0 ? noQuotes.slice(at + 4) : noQuotes.slice(at + 4, end);
    const argument = inner.trim().replace(/^['"]|['"]$/g, "");
    if (/^data:/i.test(argument)) {
      const decoded = decodeDataUri(argument);
      for (const attribute of decoded.matchAll(SVG_COLOUR_ATTRIBUTE)) {
        const hit = colourLiteralIn(
          attribute[2] ?? attribute[3] ?? "",
          attribute[1].toLowerCase(),
        );
        if (hit) return { rest: "", hit };
      }
    }
    rest += noQuotes.slice(i, at);
    i = end < 0 ? noQuotes.length : end + 1;
  }
}

// Step 5: var(...) with balanced parentheses, fallback included, becomes a
// space. An unbalanced one is removed to the end of the value only.
function withoutVar(text: string): string {
  let out = text;
  for (;;) {
    const at = out.search(/(?<![a-z0-9-])var\(/i);
    if (at < 0) return out;
    const end = closeParen(out, at + 3);
    out =
      end < 0
        ? `${out.slice(0, at)} `
        : `${out.slice(0, at)} ${out.slice(end + 1)}`;
  }
}

const COLOUR_FUNCTIONS = "rgba?|hsla?|hwb|lab|lch|oklab|oklch|color|light-dark";
const RELATIVE_COLOUR = new RegExp(
  `(?<![a-z0-9-])(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\\(\\s*from\\s+`,
  "i",
);
const COLOUR_FUNCTION = new RegExp(
  `(?<![a-z0-9-])(?:${COLOUR_FUNCTIONS})\\(`,
  "i",
);
const INTERPOLATION =
  /color-mix\(\s*in\s+[a-z0-9-]+(?:\s+(?:shorter|longer|increasing|decreasing)\s+hue)?\s*,/gi;

// Step 6, relative colour syntax: judge ONLY the origin colour, then drop the
// whole function (its channel keywords are not colours).
function relativeOrigins(text: string): { rest: string; origins: string[] } {
  const origins: string[] = [];
  let rest = text;
  for (;;) {
    const match = RELATIVE_COLOUR.exec(rest);
    if (!match) return { rest, origins };
    const open = match.index + match[0].indexOf("(");
    const close = closeParen(rest, open);
    const from = match.index + match[0].length;
    const tail = rest.slice(from);
    const functional = tail.match(/^[a-z-]+\(/i);
    const origin = functional
      ? tail.slice(
          0,
          closeParen(tail, functional[0].length - 1) + 1 || tail.length,
        )
      : (tail.match(/^\S+/)?.[0] ?? "");
    origins.push(origin);
    rest = `${rest.slice(0, match.index)} ${close < 0 ? "" : rest.slice(close + 1)}`;
  }
}

const COLOUR_BEARING = [
  "background",
  "border",
  "outline",
  "shadow",
  "fill",
  "stroke",
  "caret",
  "accent",
  "decoration",
  "column-rule",
  "scrollbar",
  "stop-color",
  "flood-color",
  "lighting-color",
  "mask",
  "filter",
  "text-emphasis",
];

function colourBearing(property: string | undefined): boolean {
  if (property === undefined) return true;
  const p = property.toLowerCase();
  return (
    p === "color" ||
    p.startsWith("--") ||
    COLOUR_BEARING.some((k) => p.includes(k))
  );
}

export function colourLiteralIn(
  value: string,
  property?: string,
): string | null {
  const stripped = withoutQuotesAndUrls(value);
  if (stripped.hit) return stripped.hit;
  let v = stripped.rest;

  const gradient = v.match(
    /(?:repeating-)?(?:linear|radial|conic)-gradient\(/i,
  );
  if (gradient) return gradient[0];

  const theme = v.match(/(?<![a-z0-9-])theme\(/i);
  if (theme) return theme[0];
  const palette = defaultPaletteNames();
  for (const match of v.matchAll(/var\(\s*--color-([a-z]+)/gi)) {
    if (palette.has(match[1].toLowerCase())) return match[0];
  }

  v = withoutVar(v);

  const relative = relativeOrigins(v);
  v = relative.rest;
  for (const origin of relative.origins) {
    const hit = colourLiteralIn(origin, property);
    if (hit) return hit;
  }
  v = v.replace(INTERPOLATION, "(");

  const fn = v.match(COLOUR_FUNCTION);
  if (fn) return fn[0];

  for (const match of v.matchAll(/#([0-9a-f]{3,8})(?![0-9a-z_-])/gi)) {
    const digits = match[1];
    const transparent =
      (digits.length === 4 && digits[3] === "0") ||
      (digits.length === 8 && digits.slice(6) === "00");
    if (!transparent) return match[0];
  }

  if (colourBearing(property)) {
    for (const word of v.split(/[^a-zA-Z0-9-]+/)) {
      if (COLOUR_WORDS.has(word.toLowerCase())) return word;
    }
  }
  return null;
}

export function forbiddenDeclaration(
  prop: string,
  value: string,
): string | null {
  const p = prop.toLowerCase();
  if (p.includes("backdrop")) return prop;
  if (p.startsWith("--tw-gradient-")) return prop;
  return colourLiteralIn(value, prop);
}

// Splits `text` on `separator` outside parentheses and quotes.
function splitOutside(text: string, separator: string): string[] {
  const parts: string[] = [];
  let depth = 0;
  let quote = "";
  let current = "";
  for (const ch of text) {
    if (quote) {
      if (ch === quote) quote = "";
    } else if (ch === '"' || ch === "'") {
      quote = ch;
    } else if (ch === "(") {
      depth++;
    } else if (ch === ")") {
      depth = Math.max(0, depth - 1);
    }
    if (ch === separator && depth === 0 && !quote) {
      parts.push(current);
      current = "";
    } else {
      current += ch;
    }
  }
  parts.push(current);
  return parts;
}

export function forbiddenInlineStyle(style: string): string | null {
  for (const declaration of splitOutside(style, ";")) {
    const at = declaration.indexOf(":");
    if (at < 0) continue;
    const property = declaration.slice(0, at).trim();
    const value = declaration.slice(at + 1).trim();
    if (forbiddenDeclaration(property, value)) return `${property}: ${value}`;
  }
  return null;
}

type Declaration = { offset: number; prop: string; value: string };

// Declarations of a stylesheet: `prop: value` INSIDE a `{...}` block, ended by
// `;` or `}`. Selectors and at-rule preludes are never declarations.
function cssDeclarations(css: string): Declaration[] {
  const text = css.replace(/@property[^{]*\{[^}]*\}/g, (m) =>
    m.replace(/[^\n]/g, " "),
  );
  const found: Declaration[] = [];
  let buffer = "";
  let start = 0;
  let depth = 0;
  let quote = "";
  const flush = () => {
    const raw = buffer;
    buffer = "";
    const trimmed = raw.trim();
    const colon = trimmed.indexOf(":");
    if (colon <= 0 || trimmed.startsWith("@")) return;
    found.push({
      offset: start + raw.indexOf(trimmed),
      prop: trimmed.slice(0, colon).trim(),
      value: trimmed
        .slice(colon + 1)
        .trim()
        .replace(/\s*!important$/i, ""),
    });
  };
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (quote) {
      if (ch === quote) quote = "";
    } else if (ch === '"' || ch === "'") {
      quote = ch;
    } else if (ch === "(") {
      depth++;
    } else if (ch === ")") {
      depth = Math.max(0, depth - 1);
    } else if (depth === 0 && ch === "{") {
      buffer = "";
      start = i + 1;
      continue;
    } else if (depth === 0 && (ch === ";" || ch === "}")) {
      flush();
      start = i + 1;
      continue;
    }
    buffer += ch;
  }
  flush();
  return found;
}

function lineOf(text: string, offset: number): number {
  let line = 1;
  for (let i = 0; i < offset && i < text.length; i++)
    if (text[i] === "\n") line++;
  return line;
}

export function forbiddenCssModule(css: string): Finding[] {
  const clean = css.replace(/\/\*[\s\S]*?\*\//g, (m) =>
    m.replace(/[^\n]/g, " "),
  );
  const findings: Finding[] = [];
  for (const { offset, prop, value } of cssDeclarations(clean)) {
    if (forbiddenDeclaration(prop, value)) {
      findings.push({
        line: lineOf(clean, offset),
        position: "css",
        text: `${prop}: ${value}`,
      });
    }
  }
  return findings;
}

// ---- class tokens -----------------------------------------------------------

type DesignSystem = {
  candidatesToCss(candidates: string[]): (string | null)[];
  parseCandidate(candidate: string): Iterable<{ value?: { kind?: string } }>;
};
type Tailwind = {
  __unstable__loadDesignSystem?: (
    css: string,
    options: {
      base: string;
      loadStylesheet: (
        id: string,
        base: string,
      ) => Promise<{ path: string; base: string; content: string }>;
    },
  ) => Promise<DesignSystem>;
};

let designSystem: DesignSystem | null = null;
const verdicts = new Map<string, boolean>();

const APP_GLOBALS = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "../app/globals.css",
);

async function loadStylesheet(id: string, base: string) {
  const file = id.startsWith(".")
    ? resolve(base, id)
    : id === "tailwindcss"
      ? require.resolve("tailwindcss/index.css")
      : null;
  if (!file)
    throw new Error(
      `r19 colour guard: unexpected stylesheet import "${id}" from ${base}`,
    );
  return {
    path: file,
    base: dirname(file),
    content: readFileSync(file, "utf8"),
  };
}

export async function loadR19ColourGuard(
  tw: Tailwind = require("tailwindcss"),
): Promise<void> {
  designSystem = null;
  verdicts.clear();
  defaultPaletteNames();
  if (typeof tw.__unstable__loadDesignSystem !== "function") {
    throw new Error(
      "r19 colour guard: tailwindcss no longer exports __unstable__loadDesignSystem; the guard cannot compile class tokens",
    );
  }
  const ds = await tw.__unstable__loadDesignSystem(
    readFileSync(APP_GLOBALS, "utf8"),
    {
      base: dirname(APP_GLOBALS),
      loadStylesheet,
    },
  );
  const white = ds.candidatesToCss(["bg-white"])[0];
  if (!white || !white.includes("--color-white")) {
    throw new Error(
      "r19 colour guard: bg-white does not compile to a --color-white declaration",
    );
  }
  if (!ds.candidatesToCss(["bg-surface-base"])[0]) {
    throw new Error(
      "r19 colour guard: bg-surface-base (a packages/core alias) does not compile; globals.css or the theme moved",
    );
  }
  designSystem = ds;
}

// Splits on `:` outside [] and (); the last segment is the utility.
function utilityPart(token: string): string {
  let depth = 0;
  let last = -1;
  for (let i = 0; i < token.length; i++) {
    const ch = token[i];
    if (ch === "[" || ch === "(") depth++;
    else if (ch === "]" || ch === ")") depth = Math.max(0, depth - 1);
    else if (ch === ":" && depth === 0) last = i;
  }
  return token.slice(last + 1).replace(/^!|!$/g, "");
}

// Contents of every top-level [...] / (...) group.
function bracketParts(text: string): string[] {
  const parts: string[] = [];
  let depth = 0;
  let start = 0;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (ch === "[" || ch === "(") {
      if (depth++ === 0) start = i + 1;
    } else if ((ch === "]" || ch === ")") && depth > 0 && --depth === 0) {
      parts.push(text.slice(start, i));
    }
  }
  if (depth > 0) parts.push(text.slice(start));
  return parts;
}

// Tailwind puts every arbitrary shadow colour in `var(--tw-shadow-color, X)`:
// for an arbitrary value the fallback X is the author's literal, so it is
// exposed to the judge.
function exposeTwFallbacks(css: string): string {
  let out = "";
  let i = 0;
  for (;;) {
    const at = css.indexOf("var(--tw-", i);
    if (at < 0) return out + css.slice(i);
    const close = closeParen(css, at + 3);
    if (close < 0) return `${out}${css.slice(i, at)} `;
    let depth = 0;
    let comma = -1;
    for (let j = at + 3; j < close; j++) {
      if (css[j] === "(") depth++;
      else if (css[j] === ")") depth--;
      else if (css[j] === "," && depth === 1) {
        comma = j;
        break;
      }
    }
    out += `${css.slice(i, at)} ${comma < 0 ? "" : exposeTwFallbacks(css.slice(comma + 1, close))} `;
    i = close + 1;
  }
}

function judgeToken(ds: DesignSystem, token: string): boolean {
  const utility = utilityPart(token);
  if (utility === "font-black" || utility === "font-extrabold") return true;
  const css = ds.candidatesToCss([token])[0];
  if (css == null) {
    return bracketParts(utility).some(
      (part) => colourLiteralIn(part.replaceAll("_", " ")) !== null,
    );
  }
  let arbitrary = false;
  for (const candidate of ds.parseCandidate(token)) {
    arbitrary = candidate.value?.kind === "arbitrary";
    break;
  }
  return cssDeclarations(css).some(({ prop, value }) =>
    forbiddenDeclaration(prop, arbitrary ? exposeTwFallbacks(value) : value),
  );
}

export function forbiddenClassToken(token: string): boolean {
  if (!designSystem) {
    throw new Error(
      "r19 colour guard: call loadR19ColourGuard() (beforeAll) before forbiddenClassToken()",
    );
  }
  const cached = verdicts.get(token);
  if (cached !== undefined) return cached;
  const verdict = judgeToken(designSystem, token);
  verdicts.set(token, verdict);
  return verdict;
}

// ---- rendered DOM -----------------------------------------------------------

// Class tokens and inline styles of a rendered tree. The whole style attribute
// of the element carrying data-presentation="r19" is exempt: R19Presentation
// applies the token definitions (R19_VARS, literals by design) there.
export function forbiddenRenderedColour(root: Element): Finding[] {
  const findings: Finding[] = [];
  for (const element of [root, ...root.querySelectorAll("*")]) {
    const tag = element.tagName.toLowerCase();
    for (const token of (element.getAttribute("class") ?? "")
      .split(/\s+/)
      .filter(Boolean)) {
      if (forbiddenClassToken(token))
        findings.push({
          line: 0,
          position: "class",
          text: `<${tag}> ${token}`,
        });
    }
    if (element.getAttribute("data-presentation") === "r19") continue;
    const hit = forbiddenInlineStyle(element.getAttribute("style") ?? "");
    if (hit)
      findings.push({ line: 0, position: "style", text: `<${tag}> ${hit}` });
  }
  return findings;
}
