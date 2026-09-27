// R19 guard: renders every element the article-body MDX renderer maps
// (MDXContent.tsx / MDXContentRSC.tsx share the same `mdxComponents`) and
// fails if a className carries a pre-R19 hardcoded color: `text-white*`,
// `bg-white*`/`bg-black`, a Tailwind palette-family color utility, a
// `bg-gradient-*`/literal-hex arbitrary class, or `font-black`/
// `font-extrabold` on a heading. Must be RED on origin/main's version of
// MDXContent.tsx, GREEN after the R19 restyle.
import { renderToString } from "react-dom/server";
import remarkGfm from "remark-gfm";
import { compileMDX } from "next-mdx-remote/rsc";
import { describe, expect, it } from "vitest";

import { mdxComponents } from "./MDXContent";

const GUARD_SOURCE = `
# Guard H1

## Guard H2

### Guard H3

#### Guard H4

##### Guard H5

###### Guard H6

Paragraph text with **bold** and *italic* and an [external link](https://example.com/x) and an [internal link](/visas/example).

- item one
- item two

1. first
2. second

> A guard blockquote line.

Inline \`code()\` sample.

\`\`\`js
const x = 1;
\`\`\`

| Col A | Col B |
| --- | --- |
| 1 | 2 |

---

![alt text](https://example.com/img.png)
`;

const PALETTE_FAMILIES =
  "sky|blue|cyan|teal|emerald|green|lime|amber|orange|red|rose|pink|fuchsia|purple|violet|indigo";

const FORBIDDEN_CLASS_PATTERNS: Array<[string, RegExp]> = [
  ["text-white", /\btext-white(\/\d+)?\b/],
  ["bg-white", /\bbg-white(\/\d+)?\b/],
  ["border-white", /\bborder-white(\/\d+)?\b/],
  ["divide-white", /\bdivide-white(\/\d+)?\b/],
  ["bg-black", /\bbg-black(\/\d+)?\b/],
  ["gradient", /bg-gradient-|linear-gradient/],
  [
    "palette-color-utility",
    new RegExp(
      `\\b(?:bg|text|border|from|to|via|divide|ring|fill|stroke)-(?:${PALETTE_FAMILIES})-\\d{2,3}\\b`,
    ),
  ],
  [
    "literal-hex-class",
    /\b(?:bg|text|border|from|to|via)-\[#[0-9a-fA-F]{3,8}\]/,
  ],
  ["font-black", /\bfont-black\b/],
  ["font-extrabold", /\bfont-extrabold\b/],
];

function classAttributesIn(html: string): string[] {
  return [...html.matchAll(/class="([^"]*)"/g)].map((m) => m[1]);
}

describe("MDXContent R19 guard — no pre-R19 hardcoded colors", () => {
  it("renders every mapped element with no forbidden className", async () => {
    const { content } = await compileMDX({
      source: GUARD_SOURCE,
      components: mdxComponents,
      options: {
        mdxOptions: { remarkPlugins: [remarkGfm], development: false },
      },
    });
    const html = renderToString(<>{content}</>);

    // Sanity: the guard source actually rendered every element it claims to
    // (a silently-empty render would make every forbidden-class check a
    // false pass).
    expect(html).toContain("Guard H1");
    expect(html).toContain("Guard H6");
    expect(html).toContain("<table");
    expect(html).toContain("<blockquote");
    expect(html).toContain("<pre");
    expect(html).toContain("<img");

    const classes = classAttributesIn(html);
    expect(classes.length).toBeGreaterThan(0);

    for (const cls of classes) {
      for (const [name, pattern] of FORBIDDEN_CLASS_PATTERNS) {
        expect(
          cls,
          `className "${cls}" matched forbidden pattern "${name}"`,
        ).not.toMatch(pattern);
      }
    }
  });
});
