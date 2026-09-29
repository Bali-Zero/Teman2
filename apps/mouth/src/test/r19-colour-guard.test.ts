import { describe, expect, it } from "vitest";
import {
  NAMED_COLOUR_COUNT,
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
];

describe("r19 colour guard", () => {
  it("knows the 148 CSS named colours", () => {
    expect(NAMED_COLOUR_COUNT).toBe(148);
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
