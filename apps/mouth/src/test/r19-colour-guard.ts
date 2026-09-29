// Entity: a colour or depth effect decided by a LITERAL instead of an R19 CSS
// custom property. Pure functions, shared by every R19 per-page guard.

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

export const NAMED_COLOUR_COUNT = NAMED_COLOURS.length;

const HEX = /#[0-9a-f]{3,8}\b/i;
const COLOUR_FUNCTION =
  /(?<![\w-])(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color|color-mix)\(/i;
const GRADIENT_FUNCTION = /(?:linear|radial|conic)-gradient\(/i;
const NAMED_COLOUR = new RegExp(
  `(?<![\\w-])(?:${NAMED_COLOURS.join("|")})(?![\\w-])`,
  "i",
);

// Removes every `var(...)` reference, including nested parentheses in a fallback.
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

function hasColourLiteral(text: string): boolean {
  return (
    HEX.test(text) || COLOUR_FUNCTION.test(text) || NAMED_COLOUR.test(text)
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

const PALETTES =
  "slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose";
const COLOUR_PREFIXES =
  "bg|text|border(?:-[xytrblse])?|divide|outline|ring-offset|ring|inset-ring|fill|stroke|decoration|accent|caret|placeholder|inset-shadow|drop-shadow|text-shadow|shadow";
const COLOUR_UTILITY = new RegExp(
  `^(?:${COLOUR_PREFIXES})-(?:(?:${PALETTES})-\\d+|white|black)(?:/.*)?$`,
);
const GRADIENT_UTILITY =
  /^(?:bg-gradient-|bg-linear-|bg-radial|bg-conic|from-|via-|to-)/;

export function forbiddenClassToken(token: string): boolean {
  const last = splitOutside(token, ":").pop() ?? "";
  const base = last.replace(/^!|!$/g, "").replace(/^-/, "");
  if (base.startsWith("backdrop-")) return true;
  if (GRADIENT_UTILITY.test(base)) return true;
  if (COLOUR_UTILITY.test(base)) return true;
  if (/^(?:font-black|font-extrabold)$/.test(base)) return true;
  const arbitrary = stripVar(base).match(/\[[^\]]*\]|\([^)]*\)/g) ?? [];
  return arbitrary.some(hasColourLiteral);
}

export function forbiddenInlineStyle(style: string): string | null {
  for (const declaration of splitOutside(style, ";")) {
    const at = declaration.indexOf(":");
    if (at < 0) continue;
    const property = declaration.slice(0, at).trim();
    const value = stripVar(declaration.slice(at + 1));
    if (
      /backdrop/i.test(property) ||
      hasColourLiteral(value) ||
      GRADIENT_FUNCTION.test(value)
    ) {
      return declaration.trim();
    }
  }
  return null;
}

export function forbiddenSourceColour(source: string): string | null {
  const text = stripVar(source)
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(?<!:)\/\/[^\n]*/g, "");

  const backdrop = text.match(/backdrop/i);
  if (backdrop) return backdrop[0];

  const scannable = text
    .replace(/\b(?:href|id)\s*=\s*(?:\{\s*)?(?:"[^"]*"|'[^']*')(?:\s*\})?/g, "")
    .replace(/&#/g, "&");
  const literal =
    scannable.match(GRADIENT_FUNCTION) ??
    scannable.match(COLOUR_FUNCTION) ??
    scannable.match(HEX);
  if (literal) return literal[0];

  for (const property of scannable.matchAll(
    /[\w$-]+\s*:\s*(["'])([^"'\n]*)\1/g,
  )) {
    if (hasColourLiteral(property[2])) return property[0];
  }
  return null;
}
