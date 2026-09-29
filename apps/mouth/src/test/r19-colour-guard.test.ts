import { describe, expect, it } from "vitest";
import {
  NAMED_COLOUR_COUNT,
  PALETTE,
  colourLiteralIn,
  forbiddenClassToken,
  forbiddenInlineStyle,
  forbiddenSourceColour,
} from "./r19-colour-guard";

const guiltyClasses = [
  "text-white/60",
  "bg-[rgba(10,37,64,0.3)]",
  "bg-slate-900/80",
  "!text-white",
  "text-[color:#fff]",
  "hover:bg-white/10",
  "font-extrabold",
  "font-black",
  "bg-slate-900/[0.8]",
  "border-t-slate-200",
  "border-l-white/10",
  "border-s-sky-300",
  "backdrop-blur-md",
  "dark:text-white",
  "md:!bg-white/5",
  "text-white!",
  "ring-white/10",
  "bg-gradient-to-r",
  "from-sky-400",
  "hover:!bg-blue-600/50",
  "-from-white",
  "shadow-black/20",
  "caret-rose-500",
  "decoration-[#abc]",
  "bg-[whitesmoke]",
  "text-[hsl(0_0%_100%)]",
  "bg-linear-to-b",
  "bg-radial-[at_top]",
  "bg-conic-180",
  "via-slate-500",
  "to-black",
  "inset-ring-white/5",
  "ring-offset-slate-900",
  "divide-gray-200",
  "outline-red-500",
  "drop-shadow-black/25",
  // gate-7648c probe
  "shadow-[0_1px_2px_rgba(0,0,0,0.2)]",
  "shadow-[0_0_0_1px_black]",
  "[box-shadow:0_1px_2px_rgba(0,0,0,.2)]",
  "[box-shadow:0_0_0_1px_#0A2540]",
  "bg-mauve-500",
  "text-mist-700",
  "border-taupe-200",
  "bg-olive-100",
  "[&_a]:text-white",
  "bg-white/(--r19-alpha)",
  "outline-white/40",
  "bg-[radial-gradient(circle,var(--r19-wash),transparent)]",
  "bg-[linear-gradient(to_right,var(--a),var(--b))]",
  "text-shadow-black/30",
  "[background:white]",
  "[backdrop-filter:blur(4px)]",
  "bg-[Red]",
  "supports-[backdrop-filter]:bg-white/60",
  "data-[state=open]:bg-white",
  "fill-white",
  "stroke-black",
  "accent-pink-500",
  "placeholder-gray-400",
  "bg-[hsl(from_var(--r19-ink)_h_s_40%)]",
  "text-[canvastext]",
  "bg-white/[0.8]",
  "border-x-white",
  "decoration-white/50",
  "inset-shadow-black/10",
  "bg-[rgb(var(--x))]",
];

const innocentClasses = [
  "whitespace-nowrap",
  "text-balance",
  "text-sm",
  "border-2",
  "ring-2",
  "shadow-md",
  "outline-none",
  "bg-transparent",
  "text-current",
  "bg-[var(--r19-wash)]",
  "bg-(--r19-wash)",
  "text-[var(--r19-ink,#1d2c3b)]",
  "font-medium",
  "hover:bg-[var(--r19-wash)]",
  "border-t-2",
  // gate-7648c probe
  "bg-[color:var(--r19-ink,white)]",
  "underline-offset-4",
  "decoration-2",
  "text-[13px]",
  "border-[1.5px]",
  "bg-[url(/img/paper.png)]",
  "rounded-[8px]",
  "grid-cols-[auto_1fr_auto]",
  "shadow-[0_0_0_1px_var(--r19-line)]",
  "text-(length:--r19-size)",
  "bg-(image:--r19-grain)",
  "ring-(--r19-line)",
  "outline-hidden",
  "text-inherit",
  "fill-current",
  "stroke-2",
  "shadow-none",
  "inset-shadow-2xs",
  "drop-shadow-md",
  "text-shadow-sm",
  "border-x-2",
  "divide-y",
  "ring-inset",
  "tabular-nums",
  "whitespace-pre-wrap",
  "mix-blend-multiply",
  "[white-space:nowrap]",
  "peer-checked:text-(--r19-ink)",
  "text-[var(--r19-ink)]/80",
  "min-h-screen",
  "max-w-6xl",
  "sm:px-6",
];

const guiltyStyles = [
  "backdrop-filter: blur(12px)",
  "-webkit-backdrop-filter: blur(12px)",
  "border: 1px solid white",
  "background: #0A2540",
  "color: rgba(255,255,255,.68)",
  "background-image: linear-gradient(90deg, var(--r19-ink), var(--r19-slate))",
  "color: whitesmoke",
  "background: ghostwhite",
  "color: hsl(0 0% 100%)",
  "border-color: rgb(255 255 255 / 0.1)",
  "color: BLACK",
  "color: oklch(0.5 0.1 30)",
  "background: color-mix(in srgb, red 50%, blue)",
  "background: repeating-linear-gradient(red, blue)",
  "font-family: var(--font-sans); box-shadow: 0 1px 2px rgba(0,0,0,.2)",
  // gate-7648c probe
  "--state-danger: red",
  "outline: 2px solid Canvas",
  "color: hsl(from var(--r19-ink) h s 40%)",
  "box-shadow: inset 0 0 0 1px lab(50% 0 0)",
  "background: rebeccapurple",
  "filter: drop-shadow(0 2px 4px black)",
  "mask-image: linear-gradient(black, transparent)",
  "color: #FFF",
  "background-color: WHITE",
  "border-color: color(display-p3 1 1 1)",
  "background: url(\"data:image/svg+xml;utf8,<svg fill='white'/>\")",
];

const innocentStyles = [
  "white-space: pre-wrap",
  "white-space: nowrap",
  "color: var(--r19-ink)",
  "border: 1px solid var(--r19-line)",
  "background: var(--x, #fff)",
  "color: var(--x, rgb(1 2 3))",
  "background: transparent; color: currentColor",
  "--state-danger: var(--r19-copper); font-family: var(--font-sans)",
  // gate-7648c probe
  "box-shadow: 0 0 0 1px var(--r19-line)",
  "color: inherit",
  "color: currentcolor",
  "background: none",
  "text-decoration-color: var(--r19-copper)",
  "white-space: pre-line",
  "transition: background-color .2s, border-color .2s",
  "font-family: var(--font-serif), Georgia, serif",
  "grid-template-columns: auto 1fr auto",
];

const guiltySources = [
  'style={{ backdropFilter: "blur(12px)" }}',
  'style={{ WebkitBackdropFilter: "blur(4px)" }}',
  'style={{ boxShadow: "0 1px 2px rgba(0,0,0,.2)" }}',
  'style={{ color: "rgba(255,255,255,.9)" }}',
  'style={{ background: "#0A2540" }}',
  'style={{ color: "white" }}',
  "style={{ color: 'whitesmoke' }}",
  'style={{ backgroundImage: "repeating-linear-gradient(red, blue)" }}',
  'className="backdrop-blur-md"',
  'style={{ color: "hsl(0 0% 100%)" }}',
  // gate-7648c probe
  'style={{ "--r19-ink": "white" } as CSSProperties}',
  'other: { "theme-color": "navy" }',
  "style={{ color: `white` }}",
  '<svg aria-hidden="true" fill="white" />',
  '<header className="bg-slate-900">',
  '<h1 className="shadow-[0_1px_2px_rgba(0,0,0,.2)]">',
  'export const viewport = { themeColor: "#0A2540" };',
  'style={{ backgroundColor: "ivory" }}',
  '<h1 className="text-[white]">',
  'style={{ background: "conic-gradient(var(--a), var(--b))" }}',
  'style={{ textShadow: "0 1px 0 hsl(0 0% 0% / .2)" }}',
  // reclassified: the comment is stripped first, then P2 flags the colour
  '// see var(--r19-ink\nexport const x = { color: "white" };',
  // position rule
  'className={cn("p-4", "bg-mauve-500")}',
  '<stop stopColor="#fff" />',
  "{ borderColor: 'navy' }",
  "<rect fill='Canvas' />",
];

const innocentSources = [
  '<a href="#faq">FAQ</a>',
  '<a href="#add">Add</a>',
  "<p>Read our white paper on tax.</p>",
  'style={{ color: "var(--r19-ink, #1d2c3b)" }}',
  "<p>&#169; Bali Zero</p>",
  "// color: white in a comment\nconst a = 1;",
  "/* backdrop-filter note */ const b = 2;",
  'const url = "https://wa.me/628213454721?text=Delega%20Bali%20Zero%20SPT";',
  'style={{ whiteSpace: "nowrap", fontFamily: "var(--font-sans)" }}',
  // gate-7648c probe
  '<a href="/tax-calendar#faq">FAQ</a>',
  'router.push("#add");',
  'title: "Tax Compliance Calendar",',
  'description: "Deadlines, reminders and compliance for businesses in Bali.",',
  'label: "Orange County office",',
  "<p>Pay before the red deadline</p>",
  '<img aria-label="White paper" />',
  'alt: "Tan beach at dusk",',
  'const ics = "BEGIN:VCALENDAR";',
  // position rule
  "<p>against the backdrop of Bali</p>",
  'title: "Black Friday",',
  'const u = "https://x.com/#fff";',
  'className="text-balance whitespace-nowrap"',
];

const guiltyValues = [
  "0 0 0 1px black",
  "linear-gradient(var(--a), var(--b))",
  "repeating-conic-gradient(var(--a), var(--b))",
  "0 1px 2px rgba(0,0,0,.2)",
  "rgb(var(--x))",
  "#fff",
  "Canvas",
  "url(\"data:image/svg+xml;utf8,<svg fill='white'/>\")",
];

const innocentValues = [
  "white-space",
  "var(--r19-ink, white)",
  "var(--a, rgb(1 2 3))",
  "transparent",
  "currentcolor",
  "inherit",
  "none",
  "0 0 0 1px var(--r19-line)",
  "8px",
  "var(--unbalanced, white",
];

describe("r19 colour guard", () => {
  it("knows the 148 CSS named colours", () => {
    expect(NAMED_COLOUR_COUNT).toBe(148);
  });

  it("reads the palette from the installed Tailwind theme", () => {
    for (const name of [
      "mauve",
      "mist",
      "olive",
      "taupe",
      "slate",
      "white",
      "black",
    ]) {
      expect(PALETTE).toContain(name);
    }
    expect(PALETTE.length).toBeGreaterThanOrEqual(26);
  });

  it.each(guiltyValues)("flags value %s", (value) => {
    expect(colourLiteralIn(value)).not.toBeNull();
  });

  it.each(innocentValues)("passes value %s", (value) => {
    expect(colourLiteralIn(value)).toBeNull();
  });

  it.each(guiltyClasses)("flags class %s", (token) => {
    expect(forbiddenClassToken(token)).toBe(true);
  });

  it.each(innocentClasses)("passes class %s", (token) => {
    expect(forbiddenClassToken(token)).toBe(false);
  });

  it.each(guiltyStyles)("flags style %s", (style) => {
    expect(forbiddenInlineStyle(style)).not.toBeNull();
  });

  it.each(innocentStyles)("passes style %s", (style) => {
    expect(forbiddenInlineStyle(style)).toBeNull();
  });

  it.each(guiltySources)("flags source %s", (source) => {
    expect(forbiddenSourceColour(source)).not.toBeNull();
  });

  it.each(innocentSources)("passes source %s", (source) => {
    expect(forbiddenSourceColour(source)).toBeNull();
  });
});
