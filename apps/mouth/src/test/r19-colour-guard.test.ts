import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { beforeAll, describe, expect, it, vi } from "vitest";
import {
  NAMED_COLOUR_COUNT,
  colourLiteralIn,
  defaultPaletteNames,
  forbiddenClassToken,
  forbiddenCssModule,
  forbiddenDeclaration,
  forbiddenInlineStyle,
  forbiddenRenderedColour,
  loadR19ColourGuard,
} from "./r19-colour-guard";
import { forbiddenSourceColour } from "./r19-colour-source";

type Row = [expected: "G" | "I", input: string];
type ValueRow = [expected: "G" | "I", value: string, property?: string];

beforeAll(async () => {
  await loadR19ColourGuard();
});

// ---- §1 values ---------------------------------------------------------------

const valueRows: ValueRow[] = [
  // v2 rows
  ["G", "0 0 0 1px black"],
  ["G", "linear-gradient(var(--a), var(--b))"],
  ["G", "repeating-conic-gradient(var(--a), var(--b))"],
  ["G", "0 1px 2px rgba(0,0,0,.2)"],
  ["G", "rgb(var(--x))"],
  ["G", "#fff"],
  ["G", "Canvas"],
  ["G", "url(\"data:image/svg+xml;utf8,<svg fill='white'/>\")"],
  ["I", "white-space"],
  ["I", "var(--r19-ink, white)"],
  ["I", "var(--a, rgb(1 2 3))"],
  ["I", "transparent"],
  ["I", "currentcolor"],
  ["I", "inherit"],
  ["I", "none"],
  ["I", "0 0 0 1px var(--r19-line)"],
  ["I", "8px"],
  ["I", "var(--unbalanced, white"],
  // step 1: quoted strings
  ["I", '"Mark Pro", sans-serif', "font-family"],
  ["I", "'Mark'", "content"],
  ["I", '"white"'],
  // step 2: url()
  ["I", "url(#fade)"],
  ["I", "url(/brand/white.svg) no-repeat"],
  ["I", "url(https://cdn.balizero.com/og/white.png)"],
  ["G", "url(\"data:image/svg+xml,%3Csvg fill='%23fff'/%3E\")"],
  ["G", 'url("data:image/svg+xml,%3Csvg%20stroke=%22red%22/%3E")'],
  [
    "G",
    `url(data:image/svg+xml;base64,${Buffer.from("<svg fill='white'/>").toString("base64")})`,
  ],
  ["I", "url(\"data:image/svg+xml,%3Csvg fill='none'/%3E\")"],
  ["I", "url(\"data:image/svg+xml,%3Csvg fill='currentColor'/%3E\")"],
  // step 3: gradients, judged before var()
  ["G", "var(--r19-wash, linear-gradient(red, blue))"],
  ["G", "-webkit-linear-gradient(top, var(--a), var(--b))"],
  ["G", "RADIAL-GRADIENT(circle, var(--a), var(--b))"],
  // step 4: theme() and default-palette var(--color-*)
  ["G", "theme(colors.white)"],
  ["G", "theme(--color-slate-900)"],
  ["G", "theme(colors.slate.900)"],
  ["G", "var(--color-white)"],
  ["G", "var(--color-slate-900)"],
  ["G", "color-mix(in oklab, var(--color-white) 60%, transparent)"],
  ["I", "var(--color-text-primary, #fff)"],
  ["I", "var(--color-border-subtle)"],
  ["I", "var(--color-surface-base)"],
  ["I", "var(--color-accent-gold-muted)"],
  // step 5: var() with fallback
  ["I", "var(--r19-ink, var(--fallback, #1d2c3b))"],
  ["I", "var(--x, rgb(1 2 3)) var(--y, red)"],
  // step 6: color-mix and relative colour syntax
  ["I", "color-mix(in srgb, var(--r19-ink) 8%, transparent)"],
  ["I", "color-mix(in oklch shorter hue, var(--a), currentColor)"],
  ["I", "color-mix(in oklab, var(--r19-ink) 10%, transparent)"],
  ["G", "color-mix(in srgb, white 20%, var(--r19-ink))"],
  ["G", "color-mix(in srgb, #fff 20%, transparent)"],
  ["G", "color-mix(in srgb, rgb(0 0 0) 10%, transparent)"],
  ["G", "color-mix(in srgb, var(--a), color-mix(in srgb, red, var(--b)))"],
  ["I", "oklab(from var(--r19-line) l a b / 50%)"],
  ["I", "rgb(from var(--r19-ink) r g b)"],
  ["G", "oklab(from red l a b)"],
  ["G", "rgb(from #fff r g b)"],
  ["G", "hsl(from rgb(0 0 0) h s l)"],
  ["G", "light-dark(var(--a), var(--b))"],
  ["G", "light-dark(black, white)"],
  // step 7: colour functions
  ["G", "rgba(255,255,255,.68)"],
  ["G", "RGB(0 0 0)"],
  ["G", "hsl(0 0% 100%)"],
  ["G", "hwb(0 0% 0%)"],
  ["G", "lab(50% 0 0)"],
  ["G", "lch(50% 0 0)"],
  ["G", "oklab(0.5 0 0)"],
  ["G", "oklch(0.5 0.1 30)"],
  ["G", "color(display-p3 1 1 1)"],
  ["G", "0_0_0_1px_rgb(0_0_0)"],
  ["I", "calc(1px + 2px)"],
  ["I", "my-color(1)"],
  // step 8: hex
  ["G", "#FFF"],
  ["G", "#0a254033"],
  ["G", "#abcd"],
  ["G", "#fff!important"],
  ["I", "#0000"],
  ["I", "0 0 #00000000"],
  ["I", "#fff0"],
  ["I", "#abcg"],
  ["I", "#faqx"],
  // step 9: named and system colours, only in a colour-bearing property
  ["G", "red", "color"],
  ["G", "WHITE", "background-color"],
  ["G", "1px solid silver", "border"],
  ["G", "2px solid Highlight", "outline"],
  ["G", "0 1px black", "box-shadow"],
  ["G", "gray transparent", "scrollbar-color"],
  ["G", "hotpink", "caret-color"],
  ["G", "wavy red", "text-decoration"],
  ["G", "white", "fill"],
  ["G", "red", "--anything"],
  ["G", "drop-shadow(0 0 2px black)", "filter"],
  ["G", "black", undefined],
  ["G", "0_0_0_1px_red"],
  ["I", "Mark Pro", "font-family"],
  ["I", "highlight 1s", "animation"],
  ["I", "canvas", "grid-area"],
  ["I", "canvas side", "grid-template-areas"],
  ["I", "color 150ms", "transition"],
  ["I", "color", "will-change"],
  ["I", "red-500", "color"],
  ["I", "white-space", "color"],
  ["I", "blur(2px)", "filter"],
  ["I", "Georgia", "font-family"],
];

// ---- §3 class tokens ---------------------------------------------------------

const classRows: Row[] = [
  // v2 guilty
  ...[
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
    "text-[canvastext]",
    "bg-white/[0.8]",
    "border-x-white",
    "decoration-white/50",
    "inset-shadow-black/10",
    "bg-[rgb(var(--x))]",
  ].map((token): Row => ["G", token]),
  // v2 guilty, verdict changed by spec §1.6 (relative colour syntax judges only its origin)
  ["I", "bg-[hsl(from_var(--r19-ink)_h_s_40%)]"],
  ["G", "bg-[hsl(from_red_h_s_40%)]"],
  // v2 innocent
  ...[
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
  ].map((token): Row => ["I", token]),
  // spec §3 "Expected consequences"
  ["G", "bg-white"],
  ["I", "bg-(--r19-ink)/10"],
  ["G", "hover:bg-slate-900/[0.8]"],
  ["I", "shadow-md"],
  ["I", "ring-2"],
  ["G", "text-[#fff]"],
  ["G", "scrollbar-thumb-red-500"],
  ["G", "border-bs-slate-200"],
  ["G", "mask-t-from-white"],
  ["G", "backdrop-blur-md"],
  ["G", "bg-linear-to-r"],
  ["I", "content-['Mark']"],
  ["I", "text-sm"],
  ["I", "bg-[var(--r19-wash)]"],
  ["I", "shadow-[0_0_0_1px_var(--r19-line)]/50"],
  ["G", "shadow-[0_0_0_1px_red]/50"],
  ["I", "bg-surface-base/50"],
  ["G", "bg-white/50"],
  ["G", "bg-[light-dark(var(--a),var(--b))]"],
  ["G", "text-red-500!"],
  ["I", "pill"],
  ["I", "shadow-none"],
  ["I", "inset-shadow-none"],
  ["G", "shadow-[0_0_0_1px_red]"],
  ["G", "shadow-[0_1px_2px_rgba(0,0,0,.2)]"],
  ["G", "text-shadow-[0_1px_0_#000]"],
  ["G", "drop-shadow-[0_1px_2px_rgb(0_0_0/0.3)]"],
  ["I", "shadow-[0_0_0_1px_var(--r19-line)]"],
  ["I", "bg-surface-base"],
  ["I", "text-text-primary"],
  ["I", "group-data-[tone=red]:pill"],
  ["I", "-from-white"],
  // gate-7691 witness W1
  ["G", "shadow-[#000_0_1px_2px]"],
  // §3 rules the list does not spell out
  ["G", "hover:font-black"],
  ["G", "font-extrabold!"],
  ["I", "font-bold"],
  ["G", "placeholder-white"],
  ["I", "bg-[--color-red-500]"],
  ["I", "r19-funnel-frame"],
  ["I", "scope"],
  ["G", "[--r19-ink:white]"],
  ["I", "[--r19-gap:8px]"],
  ["I", "text-[length:var(--x)]"],
  ["I", "shadow-lg/20"],
  ["G", "hover:bg-white"],
  ["I", "hover:bg-(--r19-wash)"],
  ["G", "text-[13px]/[#fff]"],
  ["I", "data-[tone=red]:p-2"],
  ["I", "aria-[current=page]:underline"],
  ["G", "peer-data-[x=y]:bg-white"],
  ["G", "bg-(--color-slate-900)"],
  ["G", "bg-[theme(--color-slate-900)]"],
  ["G", "ring-offset-[3px]/50 bg-white"],
  // not a Tailwind utility: only its own bracket part is judged
  ["G", "unknown-[#fff]"],
  ["G", "[&_a]:unknown-[red]"],
  ["I", "unknown-[8px]"],
  ["I", "[&_.white]:unknown"],
];

// ---- §2 inline styles --------------------------------------------------------

const styleRows: Row[] = [
  // v2 guilty
  ["G", "backdrop-filter: blur(12px)"],
  ["G", "-webkit-backdrop-filter: blur(12px)"],
  ["G", "border: 1px solid white"],
  ["G", "background: #0A2540"],
  ["G", "color: rgba(255,255,255,.68)"],
  [
    "G",
    "background-image: linear-gradient(90deg, var(--r19-ink), var(--r19-slate))",
  ],
  ["G", "color: whitesmoke"],
  ["G", "background: ghostwhite"],
  ["G", "color: hsl(0 0% 100%)"],
  ["G", "border-color: rgb(255 255 255 / 0.1)"],
  ["G", "color: BLACK"],
  ["G", "color: oklch(0.5 0.1 30)"],
  ["G", "background: color-mix(in srgb, red 50%, blue)"],
  ["G", "background: repeating-linear-gradient(red, blue)"],
  ["G", "font-family: var(--font-sans); box-shadow: 0 1px 2px rgba(0,0,0,.2)"],
  ["G", "--state-danger: red"],
  ["G", "outline: 2px solid Canvas"],
  ["G", "color: hsl(from rgb(0 0 0) h s 40%)"],
  // v2 guilty, verdict changed by spec §1.6 (relative colour syntax judges only its origin)
  ["I", "color: hsl(from var(--r19-ink) h s 40%)"],
  ["G", "box-shadow: inset 0 0 0 1px lab(50% 0 0)"],
  ["G", "background: rebeccapurple"],
  ["G", "filter: drop-shadow(0 2px 4px black)"],
  ["G", "mask-image: linear-gradient(black, transparent)"],
  ["G", "color: #FFF"],
  ["G", "background-color: WHITE"],
  ["G", "border-color: color(display-p3 1 1 1)"],
  ["G", "background: url(\"data:image/svg+xml;utf8,<svg fill='white'/>\")"],
  // v2 innocent
  ["I", "white-space: pre-wrap"],
  ["I", "white-space: nowrap"],
  ["I", "color: var(--r19-ink)"],
  ["I", "border: 1px solid var(--r19-line)"],
  ["I", "background: var(--x, #fff)"],
  ["I", "color: var(--x, rgb(1 2 3))"],
  ["I", "background: transparent; color: currentColor"],
  ["I", "--state-danger: var(--r19-copper); font-family: var(--font-sans)"],
  ["I", "box-shadow: 0 0 0 1px var(--r19-line)"],
  ["I", "color: inherit"],
  ["I", "color: currentcolor"],
  ["I", "background: none"],
  ["I", "text-decoration-color: var(--r19-copper)"],
  ["I", "white-space: pre-line"],
  ["I", "transition: background-color .2s, border-color .2s"],
  ["I", "font-family: var(--font-serif), Georgia, serif"],
  ["I", "grid-template-columns: auto 1fr auto"],
  // gate-7691 witness W2
  ["G", "background: var(--r19-wash, linear-gradient(red, blue))"],
  // §2 rules
  ["G", "--tw-backdrop-blur: blur(4px)"],
  ["G", "--tw-gradient-from: var(--r19-ink)"],
  ["G", "color: light-dark(black, white)"],
  ["I", "background: color-mix(in oklab, var(--r19-ink) 10%, transparent)"],
  ["I", "font-family: 'Mark Pro', sans-serif"],
  ["I", "background-image: url('/img/fade.svg'); color: var(--r19-ink)"],
  [
    "G",
    "background: url(data:image/svg+xml;utf8,%3Csvg%20fill=%22white%22/%3E)",
  ],
  [
    "I",
    "background: url(data:image/svg+xml;utf8,%3Csvg%20fill=%22none%22/%3E); color: var(--r19-ink)",
  ],
  ["G", "background: url('/img/a;b.svg'); color: red"],
  [
    "I",
    "background-image: url(\"data:image/svg+xml;utf8,<svg fill='none'/>\")",
  ],
];

// gate-7691 probe rows, style
const probeStyleRows: Row[] = [
  ["G", "color: RGB(0 0 0)"],
  ["G", "background: -webkit-linear-gradient(top, var(--a), var(--b))"],
  ["G", "border-bottom: 1px solid #0a254033"],
  ["G", "outline: 2px solid Highlight"],
  ["G", "text-decoration: underline wavy red"],
  ["G", "caret-color: hotpink"],
  ["G", "--r19-wash: rgb(10 37 64 / 5%)"],
  ["G", "fill: white"],
  [
    "G",
    `background: var(--r19-wash) url("data:image/svg+xml,%3Csvg fill='white'/%3E")`,
  ],
  ["G", "scrollbar-color: gray transparent"],
  ["G", "background: var(--x), linear-gradient(red, blue)"],
  ["G", "column-rule: 1px solid silver"],
  ["G", "color:#FFF!important"],
  ["G", "box-shadow: 0 0 0 1px light-dark(black, white)"],
  ["G", "background-color: color-mix(in srgb, white 20%, var(--r19-ink))"],
  ["G", `background: url("data:image/svg+xml,%3Csvg fill='%23fff'/%3E")`],
  ["I", `font-family: "Mark Pro", sans-serif`],
  ["I", "animation: highlight 1s ease-out"],
  ["I", `grid-template-areas: "canvas side"`],
  ["I", "transition: color 150ms, background-color 150ms"],
  ["I", "background: url(/brand/white.svg) no-repeat"],
  ["I", "mask-image: url(/img/fade.svg)"],
  ["I", "color: var(--r19-ink, var(--fallback, #1d2c3b))"],
  ["I", "background: color-mix(in srgb, var(--r19-ink) 8%, transparent)"],
  ["I", "border: 1px solid currentColor"],
  ["I", "content: none"],
  ["I", "will-change: color"],
  ["I", "accent-color: auto"],
  ["I", "color: revert"],
  ["I", "--r19-gap: 8px"],
  ["I", "list-style: none"],
  ["I", "filter: blur(2px)"],
  ["I", "font-variant: small-caps"],
];

const probeClassRows: Row[] = [
  ["G", "bg-[#0A2540]/50"],
  ["G", "text-[rgb(255_255_255/0.7)]"],
  ["G", "border-[color:rgb(0_0_0/.1)]"],
  ["G", "shadow-[inset_0_1px_0_theme(colors.white)]"],
  ["G", "ring-[#fff]"],
  ["G", "outline-[Highlight]"],
  ["G", "fill-[#0A2540]"],
  ["G", "stroke-[white]"],
  ["G", "text-black/[var(--a)]"],
  ["G", "group-hover:[&>svg]:fill-white"],
  ["G", "[--r19-ink:white]"],
  ["G", "[--r19-wash:#fff]"],
  ["G", "[-webkit-backdrop-filter:blur(4px)]"],
  ["G", "[color:rgb(0_0_0)]!"],
  ["G", "max-md:!border-b-red-500/40"],
  ["G", "bg-[light-dark(var(--a),var(--b))]"],
  ["G", "border-y-slate-700"],
  ["G", "border-e-white/10"],
  ["G", "shadow-[0_0_0_1px_color-mix(in_srgb,black_10%,transparent)]"],
  ["G", "text-shadow-[0_1px_0_#000]"],
  ["G", "drop-shadow-[0_2px_4px_rgb(0_0_0/0.3)]"],
  ["G", "from-[#fff]"],
  ["G", "placeholder:text-slate-400"],
  ["G", "selection:bg-white"],
  ["G", "file:bg-slate-100"],
  ["G", "marker:text-red-500"],
  ["G", "inset-ring-[#fff]"],
  ["G", "ring-offset-[#0A2540]"],
  ["G", "bg-linear-[to_right,var(--a),var(--b)]"],
  ["G", "scrollbar-thumb-slate-300"],
  ["G", "scrollbar-track-white"],
  ["G", "border-bs-white"],
  ["G", "mask-linear-from-white"],
  ["G", "mask-b-from-80%"],
  ["G", "bg-[theme(--color-slate-900)]"],
  ["G", "bg-(--color-slate-900)"],
  ["G", `bg-[url("data:image/svg+xml,%3Csvg%20fill='%23fff'%3E")]`],
  ["I", "bg-(--r19-ink)/10"],
  ["I", "text-(color:--r19-ink)"],
  ["I", "border-[var(--r19-line)]/40"],
  ["I", "shadow-[0_1px_0_var(--r19-line)]"],
  ["I", "[&_#faq]:scroll-mt-20"],
  ["I", "after:content-['Mark_as_paid']"],
  ["I", "content-['#add']"],
  ["I", "bg-[url(/brand/white.svg)]"],
  ["I", "bg-[url(/img/white-sand.jpg)]"],
  ["I", "font-[family-name:var(--font-serif)]"],
  ["I", "outline-offset-2"],
  ["I", "border-separate"],
  ["I", "bg-blend-multiply"],
  ["I", "bg-clip-text"],
  ["I", "text-ellipsis"],
  ["I", "decoration-wavy"],
  ["I", "accent-auto"],
  ["I", "caret-transparent"],
  ["I", "stroke-[1.5]"],
  ["I", "fill-none"],
  ["I", "shadow-lg/20"],
  ["I", "ring-offset-2"],
  ["I", "divide-x-2"],
  ["I", "animate-[highlight_1s_ease]"],
  ["I", "bg-[color-mix(in_srgb,var(--r19-ink)_8%,transparent)]"],
  ["I", "text-[length:var(--r19-size)]"],
  ["I", "grid-cols-[repeat(auto-fill,minmax(10rem,1fr))]"],
  ["I", "bg-top"],
  ["I", "text-pretty"],
  ["I", "border-spacing-2"],
  ["I", "[mask-type:alpha]"],
  ["I", "font-[Georgia]"],
  ["I", "scroll-mt-[var(--header)]"],
  ["I", "data-[tone=red]:p-2"],
  ["I", "aria-[current=page]:underline"],
  ["I", "scrollbar-thin"],
  ["I", "border-bs-2"],
];

// ---- §4 source ---------------------------------------------------------------

const attr = (a: string) => `export const C = () => <div ${a} />;`;
const el = (e: string) => `export const C = () => <>${e}</>;`;

const sourceRows: Row[] = [
  // ---- v2 rows re-expressed for v3 (guilty)
  ["G", attr('style={{ backdropFilter: "blur(12px)" }}')],
  ["G", attr('style={{ WebkitBackdropFilter: "blur(4px)" }}')],
  ["G", attr('style={{ boxShadow: "0 1px 2px rgba(0,0,0,.2)" }}')],
  ["G", attr('style={{ color: "rgba(255,255,255,.9)" }}')],
  ["G", attr('style={{ background: "#0A2540" }}')],
  ["G", attr('style={{ color: "white" }}')],
  ["G", attr("style={{ color: 'whitesmoke' }}")],
  [
    "G",
    attr('style={{ backgroundImage: "repeating-linear-gradient(red, blue)" }}'),
  ],
  ["G", attr('className="backdrop-blur-md"')],
  ["G", attr('style={{ color: "hsl(0 0% 100%)" }}')],
  ["G", attr('style={{ "--r19-ink": "white" } as CSSProperties}')],
  ["G", 'export const metadata = { other: { "theme-color": "navy" } };'],
  ["G", attr("style={{ color: `white` }}")],
  ["G", el('<svg aria-hidden="true" fill="white" />')],
  ["G", el('<header className="bg-slate-900" />')],
  ["G", el('<h1 className="shadow-[0_1px_2px_rgba(0,0,0,.2)]" />')],
  ["G", 'export const viewport = { themeColor: "#0A2540" };'],
  ["G", attr('style={{ backgroundColor: "ivory" }}')],
  ["G", el('<h1 className="text-[white]" />')],
  ["G", attr('style={{ background: "conic-gradient(var(--a), var(--b))" }}')],
  ["G", attr('style={{ textShadow: "0 1px 0 hsl(0 0% 0% / .2)" }}')],
  [
    "G",
    '// see var(--r19-ink\nexport const x: CSSProperties = { color: "white" };',
  ],
  ["G", 'const c = cn("p-4", "bg-mauve-500");'],
  ["G", el('<stop stopColor="#fff" />')],
  ["G", "const s: CSSProperties = { borderColor: 'navy' };"],
  ["G", el("<rect fill='Canvas' />")],
  // ---- v2 rows re-expressed for v3 (innocent)
  ["I", el('<a href="#faq">FAQ</a>')],
  ["I", el('<a href="#add">Add</a>')],
  ["I", el("<p>Read our white paper on tax.</p>")],
  ["I", attr('style={{ color: "var(--r19-ink, #1d2c3b)" }}')],
  ["I", el("<p>&#169; Bali Zero</p>")],
  ["I", "// color: white in a comment\nconst a = 1;"],
  ["I", "/* backdrop-filter note */ const b = 2;"],
  [
    "I",
    'const url = "https://wa.me/628213454721?text=Delega%20Bali%20Zero%20SPT";',
  ],
  [
    "I",
    attr('style={{ whiteSpace: "nowrap", fontFamily: "var(--font-sans)" }}'),
  ],
  ["I", el('<a href="/tax-calendar#faq">FAQ</a>')],
  ["I", 'router.push("#add");'],
  ["I", 'export const metadata = { title: "Tax Compliance Calendar" };'],
  [
    "I",
    'export const metadata = { description: "Deadlines, reminders and compliance for businesses in Bali." };',
  ],
  ["I", 'const office = { label: "Orange County office" };'],
  ["I", el("<p>Pay before the red deadline</p>")],
  ["I", el('<img aria-label="White paper" />')],
  ["I", 'const beach = { alt: "Tan beach at dusk" };'],
  ["I", 'const ics = "BEGIN:VCALENDAR";'],
  ["I", el("<p>against the backdrop of Bali</p>")],
  ["I", 'const sale = { title: "Black Friday" };'],
  ["I", 'const u = "https://x.com/#fff";'],
  ["I", attr('className="text-balance whitespace-nowrap"')],
  // ---- v2 rows whose verdict v3 changes: an object no position reaches
  ["I", '// see var(--r19-ink\nexport const x = { color: "white" };'],
  ["I", "const border = { borderColor: 'navy' };"],
  // ---- gate-7691 probe rows, source, guilty
  ["G", 'const card = cn(open && "bg-white/10");'],
  ["G", el('<div className={active ? "text-white" : "text-(--r19-ink)"} />')],
  ["G", el('<div className={`p-4 ${open ? "bg-slate-900" : ""}`} />')],
  ["G", attr('style={{ color: isPast ? "#999" : "var(--r19-ink)" }}')],
  ["G", attr("style={{ background: `rgba(10,37,64,${alpha})` }}")],
  ["G", attr('style={{ ["--r19-ink" as string]: "white" }}')],
  ["G", el('<QRCodeSVG value={url} fgColor="#0A2540" bgColor="#ffffff" />')],
  ["G", el('<Dialog overlayClassName="bg-black/60" />')],
  ["G", el('<meta name="theme-color" content="#0A2540" />')],
  ["G", el('<path fill={done ? "white" : "none"} />')],
  [
    "G",
    'export const viewport: Viewport = { themeColor: [{ media: "(prefers-color-scheme: dark)", color: "#0A2540" }] };',
  ],
  ["G", el('<text fill={"#fff"}>1</text>')],
  ["G", 'twJoin("p-2", "bg-white")'],
  ["G", attr("style={{ outlineColor: 'Highlight' }}")],
  ["G", 'const s: CSSProperties = { borderBottomColor: "rgb(0 0 0 / .1)" };'],
  ["G", attr('style={{ WebkitTextFillColor: "white" }}')],
  ["G", attr('className="x" style={{ filter: "drop-shadow(0 0 2px black)" }}')],
  ["G", attr('className={clsx({ "bg-white": active })}')],
  [
    "G",
    'const v = cva("rounded", { variants: { tone: { dark: "bg-slate-900" } } });',
  ],
  ["G", el('<feFlood floodColor="black" />')],
  [
    "G",
    attr(
      'className={cn(\n  "p-4",\n  // bg-white was here\n  "text-white",\n)}',
    ),
  ],
  ["G", attr("className='bg-[#fff]'")],
  [
    "G",
    el(
      '<><p>See https://balizero.com</p><span className="text-white">x</span></>',
    ),
  ],
  // ---- gate-7691 probe rows whose verdict v3 changes: not reached from a position
  ["I", 'const TONE = { overdue: "bg-red-500 text-white" } as const;'],
  ["I", 'const chart = { stroke: "#0A2540", strokeWidth: 2 };'],
  // ...and the same objects once a position reaches them
  [
    "G",
    'const TONE = { overdue: "bg-red-500 text-white" } as const;\nexport const C = ({ k }: { k: "overdue" }) => <div className={TONE[k]} />;',
  ],
  [
    "G",
    'const chart = { stroke: "#0A2540", strokeWidth: 2 };\nexport const C = () => <path stroke={chart.stroke} />;',
  ],
  // ---- gate-7691 probe rows, source, innocent
  ["I", 'const o = { imageAlt: "Tan beach at dusk" };'],
  ["I", 'const copy = { fillHint: "Fill in the field below" };'],
  ["I", 'const note = { ruleNote: "Pay before the red deadline" };'],
  ["I", 'const og = { imageUrl: "https://cdn.balizero.com/og/white.png" };'],
  ["I", "type Props = { backdropLabel: string };"],
  ["I", "const dialog = { backdrop: false };"],
  ["I", el('<option value="white">White</option>')],
  ["I", el('<span data-color="red">Overdue</span>')],
  ["I", el("<p>Don't miss the red deadline</p>")],
  ["I", el('<a title="Black Friday" href="/tax#fade">Sale</a>')],
  ["I", "const re = /#[0-9a-f]{3}/;"],
  ["I", 'const ics = "X-APPLE-CALENDAR-COLOR:#0A2540";'],
  ["I", el('<button aria-label="Mark as paid">OK</button>')],
  ["I", 'const b = { borderRadius: "8px", borderStyle: "dashed" };'],
  [
    "I",
    attr('style={{ color: "var(--r19-ink)", background: "var(--r19-wash)" }}'),
  ],
  ["I", el('<svg fill="none" stroke="currentColor" />')],
  ["I", el('<div>{/* <div className="bg-white"> */}</div>')],
  ["I", el('<p>Don\'t forget</p>{/* <i className="bg-white" /> */}')],
  ["I", 'const opts = { label: "Highlight", value: "canvas" };'],
  ["I", el('<Badge variant="white">New</Badge>')],
  ["I", 'const t = { theme: "dark", colorScheme: "light dark" };'],
  ["I", el('<rect fill="url(#fade)" />')],
  ["I", attr('style={{ backgroundImage: "url(/img/paper.png)" }}')],
  ["I", 'const f = { fontFamily: "Mark Pro" };'],
  ["I", 'const deadline = { title: "SPT Tahunan", colorLabel: "Red" };'],
  ["I", attr('className={cn("p-4", className)}')],
  // ---- gate-7691 witnesses W5, W13, W18, W22
  ["I", '// <i className="bg-white" />\nconst a = 1;'],
  ["G", 'const c = cn("p-4", "bg-white");'],
  ["G", attr('className={`p-4 ${open ? "bg-slate-900" : ""}`}')],
  ["G", el('<path stroke={"white"} />')],
  // ---- gate-7691 product mutants T1-T5 (TaxCalendarBody) as source rows
  [
    "G",
    el(
      '<button className={k === kind ? "pill pill-active text-[#0A2540]" : "pill"} style={{ border: "1px solid var(--r19-line)" }} />',
    ),
  ],
  [
    "G",
    el(
      '<button className={k === kind ? "pill pill-active" : "pill"} style={{ padding: "var(--space-2) var(--space-4)", border: "1px solid rgb(0 0 0 / .1)" }} />',
    ),
  ],
  [
    "G",
    el('<strong style={{ color: "oklch(0.3 0.05 250)", display: "block" }} />'),
  ],
  [
    "G",
    el(
      '<section style={{ fontFamily: "var(--font-sans)", outlineColor: "Highlight" }} />',
    ),
  ],
  [
    "G",
    el(
      '<strong style={{ color: deadlines.length > 99 ? "#0A2540" : "var(--r19-ink)", display: "block" }} />',
    ),
  ],
  // ---- gate-7691 product mutants Y1-Y5 (MyTaxCalendar) as source rows
  [
    "G",
    el(
      '<label style={{ alignItems: "center", border: "1px solid #0A2540", borderRadius: "8px" }} />',
    ),
  ],
  [
    "G",
    'const cardStyle: CSSProperties = { background: "var(--r19-surface)", border: "1px solid var(--r19-line)", borderRadius: "8px", boxShadow: "0 1px 2px rgba(0,0,0,.2)", padding: "var(--space-6)" };',
  ],
  [
    "G",
    'const cardStyle: CSSProperties = { background: "var(--r19-surface)" };\nexport const C = () => <aside style={{ ...cardStyle, background: "whitesmoke" }} />;',
  ],
  ["G", el('<p className="text-slate-600" style={mutedStyle} />')],
  [
    "G",
    'const cardStyle: CSSProperties = { background: "var(--r19-surface)" };\nexport const C = () => <aside style={{ ...cardStyle, background: count > 999 ? "ivory" : "var(--r19-wash)" }} />;',
  ],
  // ---- the same shapes as they stand on HEAD (innocent)
  [
    "I",
    el(
      '<button className={k === kind ? "pill pill-active" : "pill"} style={{ padding: "var(--space-2) var(--space-4)", borderRadius: "999px", border: "1px solid var(--r19-line)", background: k === kind ? "var(--r19-copper)" : "var(--r19-surface)", color: k === kind ? "var(--r19-cta-ink)" : "var(--r19-ink)", cursor: "pointer" }} />',
    ),
  ],
  [
    "I",
    'const cardStyle: CSSProperties = { background: "var(--r19-surface)", border: "1px solid var(--r19-line)", borderRadius: "8px", padding: "var(--space-6)" };\nexport const C = () => <aside style={{ ...cardStyle, background: "var(--r19-wash)" }} />;',
  ],
  // ---- §4 positions
  [
    "G",
    'export const C = () => <div className="p-2" style={S.card} />;\nconst S = { card: { color: "white" } };',
  ],
  [
    "I",
    'export const C = () => <div style={S.card} />;\nconst S = { card: { color: "var(--r19-ink)" }, other: { color: "white" } };',
  ],
  [
    "G",
    'export const C = ({ k }: { k: string }) => <div style={S[k]} />;\nconst S: Record<string, CSSProperties> = { a: { color: "var(--r19-ink)" }, b: { color: "white" } };',
  ],
  [
    "G",
    'const S: Record<string, React.CSSProperties> = { b: { background: "#fff" } };',
  ],
  [
    "G",
    'function tone(): React.CSSProperties {\n  return { color: "white" };\n}',
  ],
  [
    "G",
    'const tone = (a: boolean): CSSProperties => (a ? { color: "white" } : {});',
  ],
  ["G", 'const style = { color: "red" } satisfies CSSProperties;'],
  ["G", 'const style = { color: "red" } as CSSProperties;'],
  [
    "G",
    'const pill = (a: boolean) => ({ color: a ? "white" : "var(--r19-ink)" });\nexport const C = () => <b style={pill(true)} />;',
  ],
  [
    "I",
    'const pill = (a: boolean) => ({ color: a ? "var(--r19-ink)" : "var(--r19-copper)" });\nexport const C = () => <b style={pill(true)} />;',
  ],
  [
    "G",
    'const TONE = { overdue: "white", soon: "var(--r19-ink)" };\nexport const C = ({ k }: { k: "soon" }) => <b style={{ color: TONE[k] }} />;',
  ],
  [
    "G",
    'const PALETTE = { ink: "#0A2540" };\nexport const C = () => <b style={{ color: PALETTE.ink }} />;',
  ],
  [
    "I",
    'const PALETTE = { ink: "var(--r19-ink)", bad: "#0A2540" };\nexport const C = () => <b style={{ color: PALETTE.ink }} />;',
  ],
  [
    "I",
    'const MAP = { card: "white" };\nexport const C = () => <b style={{ color: "var(--r19-ink)", fontFamily: MAP.card }} />;',
  ],
  [
    "G",
    'const a = { color: "white" };\nconst b = a;\nconst c = b;\nexport const C = () => <i style={c} />;',
  ],
  [
    "I",
    'const a = { color: "white" };\nconst b = a;\nconst c = b;\nconst d = c;\nexport const C = () => <i style={d} />;',
  ],
  [
    "G",
    'const cls = "bg-white";\nexport const C = () => <i className={cls} />;',
  ],
  [
    "G",
    'const tone = (k: string) => (k ? "text-white" : "p-2");\nexport const C = () => <i className={tone("x")} />;',
  ],
  [
    "I",
    'const status = "white";\nexport const C = ({ s }: { s: string }) => <i className={s === status ? "p-2" : "p-4"} />;',
  ],
  [
    "I",
    'export const C = ({ tone }: { tone: string }) => <i style={{ color: tone === "white" ? "var(--r19-ink)" : "var(--r19-copper)" }} />;',
  ],
  [
    "G",
    'export const C = () => <i style={{ color: "var(--r19-ink)", ...(open ? { background: "white" } : {}) }} />;',
  ],
  [
    "G",
    'export const C = () => <i style={open ? { color: "white" } : undefined} />;',
  ],
  ["G", 'export const C = () => <i style={open && { color: "white" }} />;'],
  ["G", 'export const C = () => <i style={base ?? { color: "white" }} />;'],
  [
    "G",
    'export const C = () => <i style={(({ color: "white" }) as CSSProperties)} />;',
  ],
  [
    "G",
    'const c = { color: "white" };\nexport const C = () => <i style={Object.assign({}, c)} />;',
  ],
  ["G", "export const C = () => <i style={{ backdropFilter: false }} />;"],
  [
    "I",
    'export const C = () => <i style={{ color: "var(--r19-ink)", ...props.style }} />;',
  ],
  ["G", 'export const C = () => <i style={{ "--surface-base": "#fff" }} />;'],
  ["G", 'export const C = () => <i style={{ [`--r19-ink`]: "white" }} />;'],
  [
    "G",
    'const key = "x";\nexport const C = () => <i style={{ [key]: "white" }} />;',
  ],
  [
    "G",
    'export const C = () => <i style={{ borderTop: `1px solid ${c ? "#fff" : "var(--r19-line)"}` }} />;',
  ],
  [
    "G",
    "export const C = () => <i style={{ background: `linear-gradient(${a}, ${b})` }} />;",
  ],
  [
    "G",
    'export const C = () => <i style={{ color }} />;\nconst color = "white";',
  ],
  [
    "G",
    'const cardStyle = { background: "white" };\nexport const C = () => <i style={{ ...cardStyle }} />;',
  ],
  ["G", 'export const C = () => <Foo cardClassName="bg-white" />;'],
  ["I", 'export const C = () => <Foo tone="bg-white" label="red" />;'],
  ["G", 'export const C = () => <i className={cx.cn("bg-white")} />;'],
  ["G", 'export const C = () => <i class="text-white" />;'],
  [
    "I",
    'const cn2 = (a: string) => a;\nexport const C = () => <i title={cn2("bg-white")} />;',
  ],
  [
    "G",
    'const x = { color: "white" };\nconst y = { ...x };\nexport const C = () => <i style={y} />;',
  ],
  ["G", "export const C = () => <i className={`bg-white ${x}`} />;"],
  ["G", "export const C = () => <i className={`${x} bg-white ${y}`} />;"],
  ["G", "export const C = () => <i className={`${x} text-white`} />;"],
  [
    "G",
    'export const C = () => <i style={open ? undefined : { color: "white" }} />;',
  ],
  ["I", 'export const C = () => <i style={{ ["fontFamily"]: "Mark Pro" }} />;'],
  [
    "I",
    'export const C = () => <i style={{ color: pick(tone === "white") }} />;',
  ],
  [
    "I",
    'export const C = () => <i style={{ color: hasTone("white") ? "var(--r19-ink)" : "var(--r19-copper)" }} />;',
  ],
  [
    "I",
    'export const C = () => <i style={{ color: hasTone("white") && "var(--r19-ink)" }} />;',
  ],
  [
    "I",
    'export const C = () => <i style={{ color: pick() as "white" | "black" }} />;',
  ],
  [
    "G",
    'const colors = MAP[k];\nconst MAP = { a: { text: "text-white" } };\nexport const C = () => <i className={colors.text} />;',
  ],
  [
    "G",
    "export const C = () => <i style={{ border: `${w}px solid white` }} />;",
  ],
  [
    "I",
    'export const C = () => <i style={{ color: pick({ "white": 1 }) }} />;',
  ],
  // P3 / P4
  ["G", el('<path stroke={active ? "red" : "currentColor"} />')],
  ["G", el('<Chart accentColor="#0A2540" />')],
  ["G", el('<Bar bgcolor="white" />')],
  ["I", el('<Bar fill="none" stroke="currentColor" />')],
  ["I", el('<Bar fill="var(--r19-ink)" stopColor="transparent" />')],
  ["I", el('<Chart colorScheme="red" colour="red" />')],
  ["I", el('<meta name="viewport" content="#fff" />')],
  ["I", el('<meta name="theme-color" content="var(--r19-ink)" />')],
  ["G", el('<meta name="theme-color" content="white" />')],
  [
    "G",
    'export const m = { themeColor: [{ media: "(prefers-color-scheme: light)", color: "white" }] };',
  ],
  ["I", 'export const m = { themeColor: "var(--r19-ink)" };'],
  ["I", 'export const m = { other: { "theme-color": "var(--r19-ink)" } };'],
  ["I", 'export const m = { themeColorLabel: "white" };'],
  // imports are not followed
  [
    "I",
    'import { TONE } from "./tone";\nexport const C = () => <i className={TONE.a} style={{ color: TONE.b }} />;',
  ],
  // binding elements are declarations too (v3.3, gate-7702 D1, F1)
  [
    "G",
    'const config = { draft: { label: "D", style: { background: "#0A2540", color: "white" } }, ok: { label: "O", style: { color: "var(--r19-ink)" } } };\nexport const C = ({ s }: { s: "draft" | "ok" }) => {\n  const { label, style } = config[s] ?? config.draft;\n  return <span style={style}>{label}</span>;\n};',
  ],
  [
    "I",
    'const config = { draft: { label: "D", style: { background: "var(--r19-wash)", color: "var(--r19-ink)" } }, ok: { label: "O", style: { color: "var(--r19-ink)" } } };\nexport const C = ({ s }: { s: "draft" | "ok" }) => {\n  const { label, style } = config[s] ?? config.draft;\n  return <span style={style}>{label}</span>;\n};',
  ],
  [
    "G",
    'const config: Record<string, { color: string; label: string }> = { hot: { color: "text-red-400 bg-red-400/10", label: "H" } };\nconst defaultConf = { color: "text-(--r19-ink)", label: "x" };\nexport const C = ({ e }: { e: string }) => {\n  const { color, label } = config[e] || defaultConf;\n  return <div className={`inline-flex ${color} mb-2`}>{label}</div>;\n};',
  ],
  [
    "I",
    'const config: Record<string, { color: string; label: string }> = { hot: { color: "text-(--r19-ink) bg-(--r19-wash)", label: "H" } };\nconst defaultConf = { color: "text-(--r19-ink)", label: "x" };\nexport const C = ({ e }: { e: string }) => {\n  const { color, label } = config[e] || defaultConf;\n  return <div className={`inline-flex ${color} mb-2`}>{label}</div>;\n};',
  ],
  [
    "G",
    'const defaultConf = { color: "text-blue-400", label: "x" };\nexport const C = ({ e }: { e: string }) => {\n  const { color } = MAP[e] || defaultConf;\n  return <div className={color} />;\n};\nconst MAP: Record<string, { color: string }> = {};',
  ],
  [
    "G",
    'const T = { a: { style: { color: "red" } } };\nexport const C = () => {\n  const { style: st } = T.a;\n  return <i style={st} />;\n};',
  ],
  [
    "G",
    'const T = { a: { inner: { style: { color: "red" } } } };\nexport const C = () => {\n  const { inner: { style } } = T.a;\n  return <i style={style} />;\n};',
  ],
  [
    "G",
    'const T = [{ color: "white" }, { color: "var(--r19-ink)" }];\nexport const C = () => {\n  const [first] = T;\n  return <i style={first} />;\n};',
  ],
  [
    "I",
    'const T = [{ color: "var(--r19-ink)" }, { color: "var(--r19-copper)" }];\nexport const C = () => {\n  const [first] = T;\n  return <i style={first} />;\n};',
  ],
  [
    "G",
    'export const C = (props: P) => {\n  const { color = "#0A2540" } = props;\n  return <i style={{ color }} />;\n};',
  ],
  [
    "I",
    'export const C = (props: P) => {\n  const { color = "var(--r19-ink)" } = props;\n  return <i style={{ color }} />;\n};',
  ],
  [
    "G",
    'export const C = ({ bg = "#0A2540" }: P) => <div style={{ background: bg }} />;',
  ],
  [
    "I",
    'export const C = ({ bg = "var(--r19-wash)" }: P) => <div style={{ background: bg }} />;',
  ],
  [
    "G",
    'export function C({ tone = "text-red-500" }: P) {\n  return <i className={tone} />;\n}',
  ],
  [
    "I",
    'export function C({ tone = "text-(--r19-ink)" }: P) {\n  return <i className={tone} />;\n}',
  ],
  [
    "G",
    'export const C = (bg = "#fff") => <div style={{ background: bg }} />;',
  ],
  [
    "I",
    'export const C = (bg = "var(--r19-wash)") => <div style={{ background: bg }} />;',
  ],
  [
    "I",
    "export const C = ({ label }: P) => { const { style } = label; return <i style={style} />; };",
  ],
  [
    "G",
    'const A = { style: { color: "white" } };\nconst B = { ...A };\nexport const C = () => <i style={B.style} />;',
  ],
  [
    "G",
    'const ONE = { style: { color: "var(--r19-ink)" } };\nconst TWO = { style: { color: "white" } };\nexport const C = ({ ok }: P) => {\n  const { style } = ok ? ONE : TWO;\n  return <i style={style} />;\n};',
  ],
  [
    "G",
    'const M = { style: { color: "white" } };\nconst b = M;\nconst c = b;\nexport const C = () => {\n  const { style } = c;\n  return <i style={style} />;\n};',
  ],
  [
    "I",
    'const M = { style: { color: "white" } };\nconst a = M;\nconst b = a;\nconst c = b;\nexport const C = () => {\n  const { style } = c;\n  return <i style={style} />;\n};',
  ],
  [
    "G",
    'const M = { style: { color: "white" } };\nconst f1 = () => f2();\nconst f2 = () => M;\nexport const C = () => {\n  const { style } = f1();\n  return <i style={style} />;\n};',
  ],
  [
    "I",
    'const M = { style: { color: "white" } };\nconst f1 = () => f2();\nconst f2 = () => f3();\nconst f3 = () => M;\nexport const C = () => {\n  const { style } = f1();\n  return <i style={style} />;\n};',
  ],
  [
    "G",
    'const f1 = () => f2();\nconst f2 = () => f3();\nconst f3 = () => ({ style: { color: "white" } });\nexport const C = () => {\n  const { style } = f1();\n  return <i style={style} />;\n};',
  ],
  [
    "I",
    'const f1 = () => f2();\nconst f2 = () => f3();\nconst f3 = () => f4();\nconst f4 = () => ({ style: { color: "white" } });\nexport const C = () => {\n  const { style } = f1();\n  return <i style={style} />;\n};',
  ],
  // resolution depth and visited are one budget (gate-7702 D2): cycles end as "not resolved"
  [
    "I",
    "function A() {\n  const style = base.style;\n  return <div style={style} />;\n}\nfunction B() {\n  const base = style.base;\n  return <i />;\n}",
  ],
  [
    "G",
    'const base = { style: { color: "white" } };\nfunction A() {\n  const style = base.style;\n  return <div style={style} />;\n}\nfunction B() {\n  const base2 = style.base;\n  const style = base2.style;\n  return <i />;\n}',
  ],
  // never judged
  ["I", el("<p style={{ margin: 0 }}>white red #fff rgba(0,0,0)</p>")],
  [
    "I",
    'export const C = () => <a href="/white" id="red" alt="black" title="navy" aria-label="tan" />;',
  ],
  ["I", "export type T = { color: 'white' | 'red' };"],
  ["I", "export const x = { color: 'white' };"],
];

function findings(source: string, path = "src/components/Sample.tsx") {
  return forbiddenSourceColour(path, source);
}

describe("r19 colour guard values (§1)", () => {
  it("knows the 148 CSS named colours", () => {
    expect(NAMED_COLOUR_COUNT).toBe(148);
  });

  it("reads the default palette from the installed Tailwind theme", () => {
    for (const name of [
      "mauve",
      "mist",
      "olive",
      "taupe",
      "slate",
      "white",
      "black",
    ]) {
      expect(defaultPaletteNames()).toContain(name);
    }
    expect(defaultPaletteNames().size).toBeGreaterThanOrEqual(26);
    expect(defaultPaletteNames().has("text")).toBe(false);
  });

  it.each(valueRows)("%s value %s (%s)", (expected, value, property) => {
    expect(colourLiteralIn(value, property) === null ? "I" : "G").toBe(
      expected,
    );
  });
});

describe("r19 colour guard declarations and styles (§2)", () => {
  it.each(styleRows)("%s style %s", (expected, style) => {
    expect(forbiddenInlineStyle(style) === null ? "I" : "G").toBe(expected);
  });

  it("names the offending declaration", () => {
    expect(
      forbiddenInlineStyle("color: var(--a); border: 1px solid #fff"),
    ).toBe("border: 1px solid #fff");
  });

  it.each([
    ["backdrop-filter", "blur(2px)", true],
    ["-webkit-backdrop-filter", "blur(2px)", true],
    ["--tw-backdrop-blur", "blur(2px)", true],
    ["--tw-gradient-stops", "var(--a)", true],
    ["color", "red", true],
    ["font-family", "Mark Pro", false],
    ["--tw-shadow", "0 0 #0000", false],
  ])("declaration %s: %s -> %s", (prop, value, guilty) => {
    expect(forbiddenDeclaration(prop, value) !== null).toBe(guilty);
  });

  it("never searches property names for colour words", () => {
    expect(
      forbiddenInlineStyle("white-space: nowrap; red-shift: 1"),
    ).toBeNull();
  });
});

describe("r19 colour guard class tokens (§3)", () => {
  it.each(classRows)("%s class %s", (expected, token) => {
    // a class string is split on whitespace, as the source scanner does
    const guilty = token.split(/\s+/).some((t) => forbiddenClassToken(t));
    expect(guilty ? "G" : "I").toBe(expected);
  });
});

describe("gate-7691 probe rows, class and style", () => {
  it.each(probeClassRows)("%s class %s", (expected, token) => {
    expect(forbiddenClassToken(token) ? "G" : "I").toBe(expected);
  });

  it.each(probeStyleRows)("%s style %s", (expected, style) => {
    expect(forbiddenInlineStyle(style) === null ? "I" : "G").toBe(expected);
  });
});

describe("r19 colour guard source (§4)", () => {
  it.each(sourceRows)("%s source %s", (expected, source) => {
    expect(findings(source).length > 0 ? "G" : "I").toBe(expected);
  });
});

describe("r19 colour guard source: findings and paths", () => {
  it("reports line, position and text of every finding", () => {
    const source = [
      "export const C = () => (",
      '  <div className="p-2 bg-white" style={{ color: "red" }}>',
      '    <path fill="#fff" />',
      "  </div>",
      ");",
    ].join("\n");
    expect(findings(source)).toEqual([
      { line: 2, position: "class", text: "bg-white" },
      { line: 2, position: "style", text: "color: red" },
      { line: 3, position: "colour attribute", text: "fill: #fff" },
    ]);
  });

  it("reports a literal once, however many positions reach it", () => {
    const source =
      'const c = { color: "white" };\nexport const C = () => (<><i style={c} /><b style={c} /></>);';
    expect(findings(source)).toHaveLength(1);
  });

  it("reports the line of the literal, wherever it is defined", () => {
    const source =
      '\n\nconst TONE = { a: "text-white" };\n\nexport const C = () => <i className={TONE.a} />;';
    expect(findings(source)[0].line).toBe(3);
  });

  it("exempts the R19 token definitions and nothing else", () => {
    const definitions =
      'export const R19_VARS = { "--surface-base": "#F7F4EE" } as CSSProperties;';
    expect(
      findings(definitions, "apps/mouth/src/components/r19/presentation.ts"),
    ).toEqual([]);
    expect(
      findings(definitions, "/x/apps/mouth/src/components/r19/presentation.ts"),
    ).toEqual([]);
    expect(
      findings(definitions, "apps/mouth/src/components/r19/other.ts"),
    ).not.toEqual([]);
    expect(
      findings(definitions, "apps/mouth/src/components/funnel/presentation.ts"),
    ).not.toEqual([]);
  });

  it("parses each extension as its own language", () => {
    expect(
      findings('const s = <CSSProperties>{ color: "red" };', "a.ts"),
    ).not.toEqual([]);
    expect(
      findings('export const C = () => <i className="bg-white" />;', "a.jsx"),
    ).not.toEqual([]);
    expect(
      findings('export const C = () => <i className="bg-white" />;', "a.js"),
    ).not.toEqual([]);
    expect(findings("export const x = 1;", "a.ts")).toEqual([]);
  });

  it("survives source the parser does not accept", () => {
    expect(() =>
      findings('const = <div className="bg-white" style={{ '),
    ).not.toThrow();
  });
});

describe("r19 colour guard rendered DOM (§6)", () => {
  const mount = (html: string) => {
    const host = document.createElement("div");
    host.innerHTML = html;
    return host;
  };

  it("judges every class token and inline style of the tree", () => {
    const host = mount(
      '<section class="p-2"><b class="text-white" style="color: var(--r19-ink)"></b><i style="border: 1px solid #fff"></i></section>',
    );
    expect(forbiddenRenderedColour(host).map((f) => f.text)).toEqual([
      "<b> text-white",
      "<i> border: 1px solid #fff",
    ]);
  });

  it("exempts the whole style attribute of the data-presentation=r19 root only", () => {
    const host = mount(
      '<div data-presentation="r19" class="r19-root" style="--surface-base: #F7F4EE; color: white"><p style="color: white"></p></div>',
    );
    expect(forbiddenRenderedColour(host).map((f) => f.text)).toEqual([
      "<p> color: white",
    ]);
  });

  it("judges the class of the R19 root and of SVG elements", () => {
    const host = mount(
      '<div data-presentation="r19" class="bg-white"><svg class="fill-white"></svg></div>',
    );
    expect(forbiddenRenderedColour(host).map((f) => f.text)).toEqual([
      "<div> bg-white",
      "<svg> fill-white",
    ]);
  });

  it("passes a clean tree", () => {
    expect(
      forbiddenRenderedColour(
        mount('<p class="text-sm" style="color: var(--r19-ink)"></p>'),
      ),
    ).toEqual([]);
  });
});

describe("r19 colour guard source: resolution budget and real files", () => {
  it("never overflows the stack on cross-referencing member reads", () => {
    const source =
      "function A() {\n  const style = base.style;\n  return <div style={style} />;\n}\nfunction B() {\n  const base = style.base;\n  return <i />;\n}";
    expect(() => findings(source)).not.toThrow();
    expect(findings(source)).toEqual([]);
  });

  it("resolves the destructured config of the real MessageBubble.tsx", () => {
    const file = "src/components/chat/MessageBubble.tsx";
    const seen = findings(
      readFileSync(resolve(process.cwd(), file), "utf8"),
      file,
    );
    const lines = new Set(
      seen.filter((f) => f.position === "class").map((f) => f.line),
    );
    for (const line of [138, 143, 148, 153, 160]) expect(lines).toContain(line);
  });
});

describe("r19 colour guard css modules (§5)", () => {
  it.each([
    ["I", ".scope { color: var(--r19-ink); background: var(--r19-wash); }"],
    ["G", ".scope { color: #fff; }"],
    ["G", ".scope { background: linear-gradient(red, blue) }"],
    ["G", ".scope { backdrop-filter: blur(4px); }"],
    ["G", "@media (min-width: 640px) { .scope { border: 1px solid white } }"],
    ["I", "/* color: white; */ .scope { margin: 0 }"],
    ["I", ".scope { /* background: white; */ margin: 0 }"],
    [
      "I",
      "@property --x { syntax: '<color>'; initial-value: #fff; inherits: false }",
    ],
    ["I", ".scope { font-family: 'Mark Pro'; content: 'Mark' }"],
    ["I", ".scope:hover { color: var(--x, white) }"],
    ["I", '@import "x.css"; .a { margin: 0 }'],
    ["I", '@import url("a.css") supports(background: red); .a { margin: 0 }'],
    [
      "G",
      ".a { background: url(\"data:image/svg+xml;utf8,<svg fill='white'/>\"); }",
    ],
    [
      "I",
      ".a { background: url(\"data:image/svg+xml;utf8,<svg fill='none'/>\"); margin: 0 }",
    ],
  ])("%s css %s", (expected, css) => {
    expect(forbiddenCssModule(css).length > 0 ? "G" : "I").toBe(expected);
  });

  it("reports the line of the declaration", () => {
    const css = ".a {\n  margin: 0;\n  color: red;\n}\n";
    expect(forbiddenCssModule(css)).toEqual([
      { line: 3, position: "css", text: "color: red" },
    ]);
  });
});

describe("r19 colour guard loader tripwires", () => {
  it("loads the app's real stylesheet: a packages/core alias compiles", () => {
    expect(forbiddenClassToken("bg-surface-base")).toBe(false);
    expect(forbiddenClassToken("bg-white")).toBe(true);
  });

  it("throws when Tailwind stops exporting __unstable__loadDesignSystem", async () => {
    await expect(loadR19ColourGuard({} as never)).rejects.toThrow(
      /no longer exports/,
    );
    await loadR19ColourGuard();
  });

  it("throws when bg-white does not compile to --color-white", async () => {
    const fake = {
      __unstable__loadDesignSystem: async () => ({
        candidatesToCss: () => [null],
        parseCandidate: () => [],
      }),
    };
    await expect(loadR19ColourGuard(fake as never)).rejects.toThrow(/bg-white/);
    await loadR19ColourGuard();
  });

  it("throws when a packages/core alias no longer compiles", async () => {
    const fake = {
      __unstable__loadDesignSystem: async () => ({
        candidatesToCss: (tokens: string[]) =>
          tokens.map((t) =>
            t === "bg-white" ? "background-color: var(--color-white)" : null,
          ),
        parseCandidate: () => [],
      }),
    };
    await expect(loadR19ColourGuard(fake as never)).rejects.toThrow(
      /bg-surface-base/,
    );
    await loadR19ColourGuard();
  });

  it("throws before the design system is loaded, never a silent green", async () => {
    vi.resetModules();
    const fresh = await import("./r19-colour-guard");
    expect(() => fresh.forbiddenClassToken("bg-white")).toThrow(
      /loadR19ColourGuard/,
    );
    await fresh.loadR19ColourGuard();
    expect(fresh.forbiddenClassToken("bg-white")).toBe(true);
  });

  it("stays red after a failed reload until a load succeeds", async () => {
    vi.resetModules();
    const fresh = await import("./r19-colour-guard");
    await expect(fresh.loadR19ColourGuard({} as never)).rejects.toThrow();
    expect(() => fresh.forbiddenClassToken("bg-white")).toThrow(
      /loadR19ColourGuard/,
    );
  });

  it("uses the injected tailwind, not the CommonJS one, when given", async () => {
    const real = createRequire(import.meta.url)("tailwindcss");
    let called = 0;
    await loadR19ColourGuard({
      __unstable__loadDesignSystem: (...args: unknown[]) => {
        called++;
        return real.__unstable__loadDesignSystem(...args);
      },
    } as never);
    expect(called).toBe(1);
  });
});
