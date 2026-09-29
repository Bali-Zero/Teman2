// Entity: a colour or depth effect decided by a LITERAL, in a position that
// carries colour, instead of an R19 CSS custom property. Positions that do not
// carry colour are never judged; positions that do are judged whatever the
// spelling. Pure functions, shared by every R19 per-page guard.

import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

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

// Read from the installed Tailwind theme so a moved file is loud and an
// upgrade that adds a palette is covered without an edit.
function readPalette(): string[] {
  const theme = createRequire(import.meta.url).resolve("tailwindcss/theme.css");
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
  return [...names].sort();
}

export const PALETTE = readPalette();

const WORD = "a-z0-9-";
const GRADIENT_FUNCTION = /(?:linear|radial|conic)-gradient\(/i;
const COLOUR_FUNCTION = new RegExp(
  `(?<![${WORD}])(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color|color-mix|light-dark)\\(`,
  "i",
);
const HEX = /#[0-9a-f]{3,8}(?![0-9a-z_-])/i;
const NAMED_COLOUR = new RegExp(
  `(?<![${WORD}])(?:${[...NAMED_COLOURS, ...SYSTEM_COLOURS].join("|")})(?![${WORD}])`,
  "i",
);

// Removes every `var(...)` reference, fallback included, with balanced
// parentheses. An unbalanced one is removed only to the end of the value.
function stripVar(text: string): string {
  let out = "";
  for (let i = 0; i < text.length;) {
    if (
      /^var\(/i.test(text.slice(i, i + 4)) &&
      !/[\w-]/.test(text[i - 1] ?? "")
    ) {
      let depth = 0;
      let j = i + 3;
      for (; j < text.length; j++) {
        if (text[j] === "(") depth++;
        else if (text[j] === ")" && --depth === 0) break;
      }
      i = j + 1;
    } else {
      out += text[i++];
    }
  }
  return out;
}

export function colourLiteralIn(value: string): string | null {
  const gradient = value.match(GRADIENT_FUNCTION);
  if (gradient) return gradient[0];
  const bare = stripVar(value);
  return (
    (bare.match(COLOUR_FUNCTION) ??
      bare.match(HEX) ??
      bare.match(NAMED_COLOUR))?.[0] ?? null
  );
}

// Splits on `separator` only when outside (...) and [...].
function splitOutside(text: string, separator: string): string[] {
  const parts: string[] = [];
  let depth = 0;
  let current = "";
  for (const ch of text) {
    if (ch === "(" || ch === "[") depth++;
    else if (ch === ")" || ch === "]") depth = Math.max(0, depth - 1);
    if (ch === separator && depth === 0) {
      parts.push(current);
      current = "";
    } else {
      current += ch;
    }
  }
  parts.push(current);
  return parts;
}

// Contents of every top-level `[...]` / `(...)` group of a class token.
function arbitraryParts(token: string): string[] {
  const parts: string[] = [];
  let depth = 0;
  let start = 0;
  for (let i = 0; i < token.length; i++) {
    const ch = token[i];
    if (ch === "[" || ch === "(") {
      if (depth++ === 0) start = i + 1;
    } else if ((ch === "]" || ch === ")") && depth > 0 && --depth === 0) {
      parts.push(token.slice(start, i));
    }
  }
  if (depth > 0) parts.push(token.slice(start));
  return parts;
}

const COLOUR_PREFIXES = [
  "bg",
  "text",
  "border",
  "border-x",
  "border-y",
  "border-t",
  "border-r",
  "border-b",
  "border-l",
  "border-s",
  "border-e",
  "divide",
  "outline",
  "ring",
  "ring-offset",
  "inset-ring",
  "fill",
  "stroke",
  "decoration",
  "accent",
  "caret",
  "placeholder",
  "shadow",
  "inset-shadow",
  "drop-shadow",
  "text-shadow",
].sort((a, b) => b.length - a.length);
const PALETTE_VALUE = new RegExp(
  `^(?:${PALETTE.join("|")})(?:-\\d+)?(?:/.*)?$`,
);
const GRADIENT_UTILITY =
  /^(?:bg-gradient-|bg-linear-|bg-radial|bg-conic|from-|via-|to-)/;
const ARBITRARY_PROPERTY = /^\[([a-z-]+):(.*)\]$/;

export function forbiddenClassToken(token: string): boolean {
  const last = splitOutside(token, ":").pop() ?? "";
  const base = last
    .replace(/^!|!$/g, "")
    .replace(/^-/, "")
    .replaceAll("_", " ");
  if (base.startsWith("backdrop-")) return true;
  if (GRADIENT_UTILITY.test(base)) return true;
  if (/^font-(?:black|extrabold)$/.test(base)) return true;

  const property = base.match(ARBITRARY_PROPERTY);
  if (property) {
    return forbiddenInlineStyle(`${property[1]}: ${property[2]}`) !== null;
  }

  const prefix = COLOUR_PREFIXES.find((p) => base.startsWith(`${p}-`));
  if (prefix && PALETTE_VALUE.test(base.slice(prefix.length + 1))) return true;

  return arbitraryParts(base).some((part) => colourLiteralIn(part) !== null);
}

export function forbiddenInlineStyle(style: string): string | null {
  for (const declaration of splitOutside(style, ";")) {
    const at = declaration.indexOf(":");
    if (at < 0) continue;
    const property = declaration.slice(0, at).trim();
    const value = declaration.slice(at + 1);
    if (/backdrop/i.test(property) || colourLiteralIn(value) !== null) {
      return declaration.trim();
    }
  }
  return null;
}

// Blanks `//` and `/* */` comments that sit OUTSIDE string and template
// literals, so the `//` of "https://..." survives.
function stripComments(src: string): string {
  let out = "";
  let i = 0;

  const template = () => {
    while (i < src.length) {
      const ch = src[i];
      if (ch === "\\") {
        out += src.slice(i, i + 2);
        i += 2;
      } else if (ch === "`") {
        out += ch;
        i++;
        return;
      } else if (ch === "$" && src[i + 1] === "{") {
        out += "${";
        i += 2;
        code(true);
      } else {
        out += ch;
        i++;
      }
    }
  };

  const code = (inExpression: boolean) => {
    let depth = 0;
    while (i < src.length) {
      const ch = src[i];
      const next = src[i + 1];
      if (ch === "/" && next === "/") {
        while (i < src.length && src[i] !== "\n") i++;
      } else if (ch === "/" && next === "*") {
        const end = src.indexOf("*/", i + 2);
        const stop = end < 0 ? src.length : end + 2;
        out += src.slice(i, stop).replace(/[^\n]/g, " ");
        i = stop;
      } else if (ch === '"' || ch === "'") {
        // An apostrophe in JSX text never closes: stop at the line end.
        let j = i + 1;
        while (j < src.length && src[j] !== ch && src[j] !== "\n") {
          j += src[j] === "\\" ? 2 : 1;
        }
        const stop = src[j] === ch ? j + 1 : Math.min(j, src.length);
        out += src.slice(i, stop);
        i = stop;
      } else if (ch === "`") {
        out += ch;
        i++;
        template();
      } else if (ch === "{") {
        depth++;
        out += ch;
        i++;
      } else if (ch === "}") {
        out += ch;
        i++;
        if (depth === 0 && inExpression) return;
        depth = Math.max(0, depth - 1);
      } else {
        out += ch;
        i++;
      }
    }
  };

  code(false);
  return out;
}

// Index just past the group opened at `open` (`(` or `{`), string-aware.
function closeOf(text: string, open: number): number {
  const pairs: Record<string, string> = { "(": ")", "{": "}" };
  const opener = text[open];
  const closer = pairs[opener];
  let depth = 0;
  for (let i = open; i < text.length; i++) {
    const ch = text[i];
    if (ch === '"' || ch === "'" || ch === "`") {
      const end = text.indexOf(ch, i + 1);
      if (end < 0) return text.length;
      i = end;
    } else if (ch === opener) {
      depth++;
    } else if (ch === closer && --depth === 0) {
      return i + 1;
    }
  }
  return text.length;
}

const STRING_LITERAL =
  /"((?:\\.|[^"\\\n])*)"|'((?:\\.|[^'\\\n])*)'|`((?:\\.|[^`\\])*)`/g;

// Static text of every string / template literal in `text`, expressions of
// a template included as their own literals.
function stringLiteralsIn(text: string): string[] {
  const found: string[] = [];
  for (const match of text.matchAll(STRING_LITERAL)) {
    const template = match[3];
    if (template === undefined) {
      found.push(match[1] ?? match[2]);
      continue;
    }
    found.push(template.replace(/\$\{[^}]*\}/g, " "));
    for (const expression of template.matchAll(/\$\{([^}]*)\}/g)) {
      found.push(...stringLiteralsIn(expression[1]));
    }
  }
  return found;
}

function forbiddenClassText(text: string): string | null {
  for (const token of text.split(/\s+/).filter(Boolean)) {
    if (forbiddenClassToken(token)) return token;
  }
  return null;
}

const COLOUR_KEY =
  /(?:^|-)(?:color|colour|background|border|outline|shadow|fill|stroke|filter|mask|image|decoration|caret|accent|rule|theme)(?:-|$)/;

function colourBearingKey(key: string): boolean {
  if (key.startsWith("--")) return true;
  const kebab = key
    .replace(/[A-Z]/g, (c) => `-${c.toLowerCase()}`)
    .replace(/^-?(?:webkit|moz|ms|o)-/, "");
  return COLOUR_KEY.test(kebab);
}

const ENTRY_START = "(?<=(?:^|[{,])\\s*)";
const OBJECT_KEY = `(?:"([^"\\n]+)"|'([^'\\n]+)'|([\\w$-]+))`;
const OBJECT_ENTRY = new RegExp(
  `${ENTRY_START}${OBJECT_KEY}\\s*:\\s*(?:"([^"\\n]*)"|'([^'\\n]*)'|\`([^\`$]*)\`)`,
  "g",
);
const BACKDROP_KEY = new RegExp(`${ENTRY_START}${OBJECT_KEY}\\s*:`, "g");
const COLOUR_ATTRIBUTE =
  /(?<![\w$-])(?:fill|stroke|color|stopColor|stop-color|floodColor|flood-color|lightingColor|bgcolor)\s*=\s*(?:"([^"]*)"|'([^']*)'|\{\s*(?:"([^"]*)"|'([^']*)'|`([^`$]*)`)\s*\})/g;
const CLASS_ATTRIBUTE = /(?<![\w$-])(?:className|class)\s*=\s*/g;
const CLASS_HELPER = /(?<![\w$.])(?:cn|clsx|cva|twMerge)\s*\(/g;

export function forbiddenSourceColour(source: string): string | null {
  const text = stripComments(source);

  for (const attribute of text.matchAll(CLASS_ATTRIBUTE)) {
    const at = attribute.index + attribute[0].length;
    const opener = text[at];
    const literals =
      opener === "{"
        ? stringLiteralsIn(text.slice(at, closeOf(text, at)))
        : opener === '"' || opener === "'"
          ? stringLiteralsIn(text.slice(at, text.indexOf(opener, at + 1) + 1))
          : [];
    for (const literal of literals) {
      const hit = forbiddenClassText(literal);
      if (hit) return hit;
    }
  }

  for (const helper of text.matchAll(CLASS_HELPER)) {
    const at = helper.index + helper[0].length - 1;
    for (const literal of stringLiteralsIn(text.slice(at, closeOf(text, at)))) {
      const hit = forbiddenClassText(literal);
      if (hit) return hit;
    }
  }

  for (const entry of text.matchAll(BACKDROP_KEY)) {
    const key = entry[1] ?? entry[2] ?? entry[3];
    if (/backdrop/i.test(key)) return key;
  }

  for (const entry of text.matchAll(OBJECT_ENTRY)) {
    const key = entry[1] ?? entry[2] ?? entry[3];
    if (!colourBearingKey(key)) continue;
    const value = entry[4] ?? entry[5] ?? entry[6];
    if (colourLiteralIn(value) !== null) return entry[0];
  }

  for (const attribute of text.matchAll(COLOUR_ATTRIBUTE)) {
    const value = attribute.slice(1).find((v) => v !== undefined) ?? "";
    if (colourLiteralIn(value) !== null) return attribute[0];
  }

  return null;
}
