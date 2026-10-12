// Lot W1 (mission kbli-nav-design-loop): arms the R19 wrapper token census.
// Drives the W0 probe (read via `--export`, never copied) over /kbli* in the
// six measure.py states, judges it with W0's own `--replay`, and adds the
// palette rule: inside [data-presentation=r19] every computed colour is
// Direction A or the PMA triad. Two fixtures prove guilt red, innocence green.
// Starts `next dev --webpack` and a browser, so it runs only when asked
// (`npm test -- r19-wrapper` or R19_WRAPPER_LIVE=1, decided in vitest.config.ts).
// Palette scope is the r19 root alone: until W2 mounts it, SKIPPED, never green.
import { execFileSync, spawn, type ChildProcess } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium, type Browser, type Page } from "playwright-core";
import { afterAll, beforeAll, describe, expect, inject, test } from "vitest";

declare module "vitest" {
  export interface ProvidedContext {
    r19WrapperLive: boolean;
  }
}

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MOUTH = path.resolve(HERE, "../..");
const ROOT = path.resolve(MOUTH, "../..");
const CENSUS = path.join(ROOT, "scripts/mouth/r19_wrapper_token_census.py");
const TSCONFIG = path.join(MOUTH, "tsconfig.json");
const PYTHON = process.env.PYTHON ?? "python3";
const R19 = "[data-presentation=r19]";
const LIVE = inject("r19WrapperLive");
const NOT_ASKED =
  "not requested: run `npm test -- r19-wrapper` or set R19_WRAPPER_LIVE=1 (CI: r19-wrapper-census-tests / wrapper-census-live)";

const RANK: Record<string, number> = { wrapper: 0, above: 1, nowhere: 2 };
const rank = (d: string | null) => RANK[d ?? ""] ?? -1;
const rgb = (hex: string) => hex.slice(0, 7); // PROBE_JS uppercases; drops "/alpha"
const say = (...l: string[]) => process.stdout.write(l.join("\n") + "\n");
const sleep = (ms: number) => new Promise((ok) => setTimeout(ok, ms));

type Dict<T> = Record<string, T>;
type Hit = { selector: string; count: number };
type Read = Hit & { kind: string; token: string; defined: string | null };
type Colour = Hit & { hex: string; prop: string };
type Offender = Colour & { tokens: string[] };
type Probe = { root: string; reads: Read[]; colors: Colour[] } & Record<
  "elements" | "rules" | "skipped",
  unknown
>;
type Cap = Probe & { page: string; state: string; offenders: Offender[] };
type Dim = { width: number; height: number };
type State = Dim & {
  name: string;
  forced: string | null;
  scheme: "light" | "dark";
};
type Exported = {
  probe: string;
  pages: string[];
  core: string[];
  states: State[];
  direction_a: Dict<string>;
  semantic: Dict<string>;
  semantic_on_paper: Dict<number>;
};

// W1-owned page function: which wrapper tokens resolve to each offending hex.
function attribute({ tokens, hexes }: { tokens: string[]; hexes: string[] }) {
  const root = document.querySelector('[data-presentation="r19"]');
  const px = document.createElement("canvas").getContext("2d")!;
  const hexOf = (v: string) => {
    px.clearRect(0, 0, 1, 1);
    px.fillStyle = "#000";
    px.fillStyle = v;
    px.fillRect(0, 0, 1, 1);
    const d = px.getImageData(0, 0, 1, 1).data;
    const h = [d[0], d[1], d[2]].map((n) => n.toString(16).padStart(2, "0"));
    return "#" + h.join("").toUpperCase();
  };
  const cache = new Map<string, string>();
  const out: Dict<Set<string>> = {};
  for (const el of root ? [root, ...root.querySelectorAll("*")] : []) {
    for (const t of tokens) {
      const v = getComputedStyle(el).getPropertyValue(t).trim();
      if (!v || !CSS.supports("color", v)) continue;
      if (!cache.has(v)) cache.set(v, hexOf(v));
      const hex = cache.get(v)!;
      if (hexes.includes(hex)) (out[hex] ??= new Set()).add(t);
    }
  }
  return Object.fromEntries(
    Object.entries(out).map(([h, s]) => [h, [...s].sort()]),
  );
}

let ex: Exported;
let allowed: Set<string>;
let browser: Browser;

async function capture(page: Page, name: string, state: string): Promise<Cap> {
  const call = `(${ex.probe})(${JSON.stringify(ex.core)})`;
  const res = (await page.evaluate(call)) as Probe;
  if (!res.root) throw new Error("wrapper root not found");
  const bad =
    res.root === R19 ? res.colors.filter((c) => !allowed.has(rgb(c.hex))) : [];
  const tokens = res.reads.filter((r) => r.kind === "var").map((r) => r.token);
  const hexes = bad.map((c) => rgb(c.hex));
  const by = bad.length
    ? await page.evaluate(attribute, { tokens, hexes })
    : {};
  const offenders = bad.map((c) => ({ ...c, tokens: by[rgb(c.hex)] ?? [] }));
  return { ...res, page: name, state, offenders };
}

// The W0 census shape, merged exactly as Python live() merges it.
function censusOf(
  pages: string[],
  states: string[],
  caps: Cap[],
  failed: string[],
) {
  const reads: Dict<Read & { page: string; state: string }> = {};
  const colors: Dict<Colour & { page: string; state: string }> = {};
  for (const { page, state, reads: rs, colors: cs } of caps) {
    for (const r of rs) {
      const key = `${r.kind} ${r.token}`;
      const prev = reads[key];
      if (!prev || rank(r.defined) > rank(prev.defined))
        reads[key] = { ...r, page, state, count: (prev?.count ?? 0) + r.count };
      else prev.count += r.count;
    }
    for (const c of cs) {
      if (colors[c.hex]) colors[c.hex].count += c.count;
      else colors[c.hex] = { ...c, page, state };
    }
  }
  const captures = caps.map(
    ({ page, state, root, elements, rules, skipped }) => ({
      ...{ page, state, root, elements, rules },
      skipped_sheets: skipped,
    }),
  );
  return { schema: 1, pages, states, captures, failed, reads, colors };
}

// Judge a census with W0's own `--replay`; returns its tail split into parts.
function replay({ reads, colors, ...head }: ReturnType<typeof censusOf>) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "r19-wrapper-"));
  const file = path.join(dir, "census.jsonl");
  try {
    const rows = [
      head,
      ...Object.entries(reads).map(([read, v]) => ({ read, ...v })),
      ...Object.entries(colors).map(([color, v]) => ({ color, ...v })),
    ];
    fs.writeFileSync(
      file,
      rows.map((r) => JSON.stringify(r)).join("\n") + "\n",
    );
    const out = execFileSync(PYTHON, [CENSUS, "--replay", file], {
      encoding: "utf8",
    });
    const lines = out.trimEnd().split("\n");
    const at = lines.findIndex((l) => l.startsWith("read-but-undefined:"));
    const end = lines.findIndex((l) => l.startsWith("colors-outside-"));
    const named = lines.slice(at + 1, end).filter((l) => l.startsWith("  "));
    return {
      lines,
      undefinedLine: lines[at],
      named: named.map((l) => l.trim()),
      colorsLine: lines[end],
    };
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

// The W1 palette verdict over the r19-scope captures it is given.
function paletteLines(caps: Cap[], total = caps.length) {
  const seen = new Map<string, Offender & { page: string; state: string }>();
  for (const { page, state, offenders } of caps)
    for (const o of offenders) {
      const prev = seen.get(rgb(o.hex));
      if (prev) prev.count += o.count;
      else seen.set(rgb(o.hex), { ...o, hex: rgb(o.hex), page, state });
    }
  const head = `palette-outside-direction-a (r19 scope, ${caps.length}/${total} captures): ${seen.size}`;
  return [
    head,
    ...[...seen.values()].map((o) => {
      const via = o.tokens.join(", ") || "(no wrapper token: literal or class)";
      return `  colour ${o.hex} x${o.count} ${o.prop} via ${via} e.g. ${o.selector} on ${o.page} ${o.state}`;
    }),
  ];
}

describe("R19 wrapper census (lot W1)", () => {
  beforeAll(async () => {
    if (!LIVE) return;
    ex = JSON.parse(
      execFileSync(PYTHON, [CENSUS, "--export"], { encoding: "utf8" }),
    );
    allowed = new Set([
      ...Object.values(ex.direction_a),
      ...Object.values(ex.semantic),
    ]);
    browser = await chromium.launch({
      executablePath: process.env.CHROME_HEADLESS || undefined,
    });
  }, 60_000);
  afterAll(async () => {
    if (LIVE) await browser?.close();
  });

  describe("fixtures: guilt goes red, innocence stays green", () => {
    const html = (n: string) =>
      fs.readFileSync(
        path.join(HERE, `fixtures/r19-wrapper-${n}.html`),
        "utf8",
      );
    async function fixture(content: string, name: string) {
      const ctx = await browser.newContext({
        viewport: { width: 1440, height: 900 },
        colorScheme: "light",
      });
      try {
        const page = await ctx.newPage();
        await page.setContent(content, { waitUntil: "load" });
        return await capture(page, `fixture:${name}`, "desktop/light");
      } finally {
        await ctx.close();
      }
    }
    const judge = (c: Cap) => replay(censusOf([c.page], [c.state], [c], []));

    test("the guilt fixture differs from innocence by one token line", (ctx) => {
      if (!LIVE) ctx.skip(NOT_ASKED);
      const [a, b] = [html("innocence").split("\n"), html("guilt").split("\n")];
      expect(b).toHaveLength(a.length);
      const diff = a.map((_, i) => i).filter((i) => a[i] !== b[i]);
      expect(diff).toHaveLength(1);
      expect(a[diff[0]]).toMatch(/--kbli-bg-base:\s*#F7F4EE/);
      expect(b[diff[0]]).toMatch(/--kbli-bg-base:\s*#0F172A/);
    });

    test("innocence: Direction-A paint stays green", async (ctx) => {
      if (!LIVE) ctx.skip(NOT_ASKED);
      for (const x of Object.values(ex.semantic_on_paper))
        expect(x).toBeGreaterThanOrEqual(4.5);
      const cap = await fixture(html("innocence"), "innocence");
      const r = judge(cap);
      const head = paletteLines([cap])[0];
      say(`innocence fixture: GREEN — ${head}`);
      say(`  W0 replay: ${r.undefinedLine} / ${r.colorsLine}`);
      expect(cap.root).toBe(R19);
      expect(cap.offenders).toEqual([]);
      const hexes = cap.colors.map((c) => rgb(c.hex));
      expect(hexes).toContain("#2E5E4E");
      expect(hexes).toContain("#F7F4EE");
      expect(r.undefinedLine).toBe("read-but-undefined: 0");
      expect(r.colorsLine).toBe("colors-outside-direction-a: 0");
    });

    test("guilt: one dark --kbli-bg-base is named with its hex", async (ctx) => {
      if (!LIVE) ctx.skip(NOT_ASKED);
      const cap = await fixture(html("guilt"), "guilt");
      const r = judge(cap);
      say(`guilt fixture: RED (expected) — ${paletteLines([cap]).join("\n")}`);
      say(`  W0 replay: ${r.colorsLine}`);
      expect(cap.root).toBe(R19);
      expect(cap.offenders).toHaveLength(1);
      expect(rgb(cap.offenders[0].hex)).toBe("#0F172A");
      expect(cap.offenders[0].tokens).toContain("--kbli-bg-base");
      expect(r.colorsLine).toBe("colors-outside-direction-a: 1");
    });

    test("a read the contract lacks is named through the replay", async (ctx) => {
      if (!LIVE) ctx.skip(NOT_ASKED);
      const [from, to] = [
        "--kbli-text-muted)",
        "--kbli-w1-undeclared, #58626B)",
      ];
      const content = html("innocence").replace(from, to);
      expect(content).not.toBe(html("innocence"));
      const r = judge(await fixture(content, "undeclared"));
      say(`undeclared-read fixture: ${r.undefinedLine}`, ...r.named);
      expect(r.undefinedLine).toBe("read-but-undefined: 1");
      expect(r.named).toHaveLength(1);
      expect(r.named[0]).toMatch(/^var --kbli-w1-undeclared/);
    });
  });

  describe("live: /kbli* in the six measure.py states", () => {
    let child: ChildProcess | undefined;
    let exit: number | undefined;
    let tsconfig: Buffer | undefined;
    const caps: Cap[] = [];
    const failed: string[] = [];

    // node:http, not fetch: setup.tsx stubs the global fetch under jsdom.
    const status = (url: string) =>
      new Promise<number>((ok) => {
        const req = http.get(
          url,
          (res) => (res.resume(), ok(res.statusCode ?? 599)),
        );
        req.on("error", () => ok(599));
      });
    async function wait(url: string) {
      const end = Date.now() + 300_000;
      while (Date.now() < end) {
        if (child && exit !== undefined)
          throw new Error(`next dev exited ${exit}`);
        if ((await status(url)) < 400) return;
        await sleep(2000);
      }
      throw new Error(`dev server never answered ${url}`);
    }

    async function shoot(url: string, p: string, s: State) {
      const ctx = await browser.newContext({
        viewport: s,
        colorScheme: s.scheme,
      });
      try {
        const page = await ctx.newPage();
        const resp = await page.goto(url, {
          waitUntil: "load",
          timeout: 180_000,
        });
        if (!resp || resp.status() >= 400)
          throw new Error(`HTTP ${resp?.status() ?? "none"}`);
        await page.waitForTimeout(250);
        if (s.forced)
          await page.evaluate(
            (t) => document.documentElement.setAttribute("data-theme", t),
            s.forced,
          );
        await page.waitForFunction(
          () => document.readyState === "complete",
          null,
          { timeout: 60_000 },
        );
        await page.waitForTimeout(1500);
        caps.push(await capture(page, p, s.name));
      } catch (e) {
        failed.push(
          `${p} ${s.name}: ${String((e as Error).message).split("\n")[0]}`.slice(
            0,
            200,
          ),
        );
      } finally {
        await ctx.close();
      }
    }

    beforeAll(async () => {
      if (!LIVE) return;
      let base = process.env.R19_WRAPPER_BASE_URL;
      if (!base) {
        const srv = net.createServer();
        await new Promise<void>((ok) => srv.listen(0, "127.0.0.1", ok));
        const { port } = srv.address() as net.AddressInfo;
        await new Promise((ok) => srv.close(ok));
        tsconfig = fs.readFileSync(TSCONFIG); // next dev rewrites it; afterAll puts it back
        const next = path.join(ROOT, "node_modules/.bin/next");
        const env = { ...process.env, NEXT_TELEMETRY_DISABLED: "1" };
        child = spawn(next, ["dev", "--webpack", "-p", `${port}`], {
          cwd: MOUTH,
          detached: true,
          stdio: "ignore",
          env,
        });
        child.on("exit", (code) => (exit = code ?? -1));
        base = `http://localhost:${port}`;
      }
      for (const p of ex.pages) await wait(base + p);
      for (const p of ex.pages)
        for (const s of ex.states) await shoot(base + p, p, s);
    }, 900_000);

    afterAll(async () => {
      if (!child?.pid) return;
      try {
        if (exit === undefined) {
          const gone = new Promise((ok) => child!.once("exit", ok));
          process.kill(-child.pid, "SIGTERM");
          const late = await Promise.race([
            gone,
            sleep(15_000).then(() => "late"),
          ]);
          if (late === "late") process.kill(-child.pid, "SIGKILL");
        }
      } catch (e) {
        if ((e as NodeJS.ErrnoException).code !== "ESRCH") throw e;
      }
      if (tsconfig && !fs.readFileSync(TSCONFIG).equals(tsconfig))
        fs.writeFileSync(TSCONFIG, tsconfig);
    });

    test("read-but-undefined: 0 on 5 pages x 6 states", (ctx) => {
      if (!LIVE) ctx.skip(NOT_ASKED);
      const census = censusOf(
        ex.pages,
        ex.states.map((s) => s.name),
        caps,
        failed,
      );
      const r = replay(census);
      say("census (W0 judge on this run):", ...r.lines);
      expect(failed).toEqual([]);
      expect(caps).toHaveLength(ex.pages.length * ex.states.length);
      expect(Object.keys(census.reads).length).toBeGreaterThan(0);
      expect(r.undefinedLine).toBe("read-but-undefined: 0");
      expect(r.named).toEqual([]);
    }, 60_000);

    test("palette: every computed colour on r19 surfaces is in Direction A + the PMA triad", (ctx) => {
      if (!LIVE) ctx.skip(NOT_ASKED);
      if (failed.length || !caps.length)
        throw new Error(
          `incomplete census: ${failed.length} failed, ${caps.length} captured`,
        );
      const scope = caps.filter((c) => c.root === R19);
      if (!scope.length) {
        const why = `0 r19 surfaces under /kbli* (0 of ${caps.length} captures carry ${R19}) — W2 pending`;
        say(`palette-outside-direction-a: SKIPPED — ${why}`);
        ctx.skip(why);
      }
      const lines = paletteLines(scope, caps.length);
      say(...lines);
      expect(lines).toEqual([lines[0].replace(/: \d+$/, ": 0")]);
    }, 60_000);
  });
});
