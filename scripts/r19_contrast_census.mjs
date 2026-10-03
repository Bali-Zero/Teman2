#!/usr/bin/env node
// R4 contrast census for the R19 paper wrapper (docs/specs/2026-09-27-r19-wrapper-token-contract-spec.md).
// node scripts/r19_contrast_census.mjs --candidate <origin> [--reference https://balizero.com]
//   --route /kbli [--route '/kbli|click=<css>'] [--control '<css>'] [--viewports 1440,390] [--json <file>]
// Exit 0: self-test PASS and new_failures == 0. Exit 1: new_failures > 0. Exit 2: self-test FAIL or usage.
// VERCEL_AUTOMATION_BYPASS_SECRET, when set, is sent only to the candidate origin and is never printed.
import { chromium } from "playwright";
import { writeFileSync } from "node:fs";

const argv = process.argv.slice(2);
const opt = (k) => argv.flatMap((a, i) => (a === k ? [argv[i + 1]] : []));
const out = (s) => process.stdout.write(`${s}\n`);
const candidate = opt("--candidate")[0];
const reference = opt("--reference")[0] ?? "https://balizero.com";
const routes = opt("--route");
const controls = opt("--control");
const viewports = (opt("--viewports")[0] ?? "1440,390").split(",").map(Number);
const secret = process.env.VERCEL_AUTOMATION_BYPASS_SECRET;
if (!candidate || routes.length === 0) {
  out(
    "usage: --candidate <origin> --route <path> [--route ...] [--control <css>] [--reference <origin>]",
  );
  process.exit(2);
}

// Runs in the page. Colours go through a 1x1 canvas, so oklch()/lab()/color-mix() become sRGB bytes.
function census({ controls, selftest }) {
  const cv = document.createElement("canvas");
  cv.width = cv.height = 1;
  const cx = cv.getContext("2d", { willReadFrequently: true });
  const rgba = (c) => {
    cx.clearRect(0, 0, 1, 1);
    cx.fillStyle = "#000";
    cx.fillStyle = c;
    cx.fillRect(0, 0, 1, 1);
    const d = cx.getImageData(0, 0, 1, 1).data;
    return [d[0], d[1], d[2], d[3] / 255];
  };
  const over = (f, b) =>
    [0, 1, 2].map((i) => f[i] * f[3] + b[i] * (1 - f[3])).concat(1);
  const lum = (c) => {
    const [r, g, b] = c.slice(0, 3).map((v) => {
      const s = v / 255;
      return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const ratio = (a, b) => {
    const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
    return (hi + 0.05) / (lo + 0.05);
  };
  const opacity = (el) => {
    let o = 1;
    for (let n = el; n; n = n.parentElement)
      o *= Number(getComputedStyle(n).opacity);
    return o;
  };
  const background = (el) => {
    const layers = [];
    for (let n = el; n; n = n.parentElement) {
      const s = getComputedStyle(n);
      if (s.backgroundImage !== "none") return null;
      const c = rgba(s.backgroundColor);
      if (c[3] > 0) layers.push(c);
      if (c[3] >= 1) break;
    }
    return layers
      .reverse()
      .reduce((acc, c) => over(c, acc), [255, 255, 255, 1]);
  };
  const run = () => {
    const res = { fail: [], checked: 0, imageBacked: 0 };
    const judge = (el, key, min) => {
      const bg = background(el);
      if (!bg) return void res.imageBacked++;
      const fg = rgba(getComputedStyle(el).color);
      fg[3] *= opacity(el);
      const r = ratio(over(fg, bg), bg);
      res.checked++;
      if (r < min)
        res.fail.push({ key, ratio: Math.round(r * 100) / 100, min });
    };
    for (const el of document.querySelectorAll("body *")) {
      const s = getComputedStyle(el);
      if (
        s.visibility === "hidden" ||
        el.getClientRects().length === 0 ||
        opacity(el) === 0
      )
        continue;
      const text = [...el.childNodes]
        .filter((n) => n.nodeType === 3)
        .map((n) => n.textContent)
        .join("")
        .trim();
      if (!text) continue;
      const px = parseFloat(s.fontSize);
      const large = px >= 24 || (px >= 18.66 && Number(s.fontWeight) >= 700);
      judge(
        el,
        `${el.tagName} ${text.replace(/\s+/g, " ").slice(0, 80)}`,
        large ? 3 : 4.5,
      );
    }
    for (const sel of controls) {
      for (const el of document.querySelectorAll(sel)) {
        if (el.getClientRects().length === 0) continue;
        const name = (el.getAttribute("aria-label") || el.textContent || "")
          .trim()
          .slice(0, 80);
        judge(el, `${el.tagName} [control] ${name}`, 3);
      }
    }
    return res;
  };
  if (!selftest) return run();
  const span = document.createElement("span");
  span.textContent = "R19SELFTEST";
  span.style.cssText =
    "position:fixed;top:0;left:0;z-index:2147483647;color:oklch(1 0 0);background:#F7F4EE";
  document.body.append(span);
  const planted = run().fail.some((f) => f.key === "SPAN R19SELFTEST");
  span.remove();
  const paper = [247, 244, 238, 1];
  return {
    oklch: rgba("oklch(0.984 0.003 247.858)").slice(0, 3),
    label:
      Math.round(ratio(over([255, 255, 255, 0.68], paper), paper) * 100) / 100,
    planted,
  };
}

const browser = await chromium.launch();
const report = { candidate, reference, selftest: [], pages: [] };
let newFailures = 0;
try {
  for (const vp of viewports) {
    const ctx = await browser.newContext({
      viewport: { width: vp, height: 900 },
      reducedMotion: "reduce",
    });
    if (secret) {
      const origin = new URL(candidate).origin;
      await ctx.route("**/*", (r) =>
        new URL(r.request().url()).origin === origin
          ? r.continue({
              headers: {
                ...r.request().headers(),
                "x-vercel-protection-bypass": secret,
              },
            })
          : r.continue(),
      );
    }
    const page = await ctx.newPage();
    // Settle: trigger scroll reveals, jump finite animations to their end, freeze infinite ones at 0.
    const settle = () =>
      page.evaluate(async () => {
        const wait = (ms) => new Promise((r) => setTimeout(r, ms));
        for (
          let y = 0;
          y < document.documentElement.scrollHeight;
          y += innerHeight
        ) {
          scrollTo(0, y);
          await wait(60);
        }
        scrollTo(0, 0);
        await wait(300);
        for (const a of document.getAnimations()) {
          if (a.effect?.getComputedTiming().endTime !== Infinity) a.finish();
          else {
            a.pause();
            a.currentTime = 0;
          }
        }
        await document.fonts.ready;
      });
    const measure = async (origin, path, click) => {
      const resp = await page.goto(origin + path, {
        waitUntil: "networkidle",
        timeout: 60000,
      });
      await settle();
      if (click) {
        await page.click(click);
        await page.waitForTimeout(1000);
        await settle();
      }
      return {
        status: resp ? resp.status() : 0,
        ...(await page.evaluate(census, { controls, selftest: false })),
      };
    };
    await page.goto(candidate + routes[0].split("|click=")[0], {
      waitUntil: "networkidle",
      timeout: 60000,
    });
    const st = await page.evaluate(census, { controls: [], selftest: true });
    const pass =
      st.oklch.every((v, i) => Math.abs(v - [248, 250, 252][i]) <= 1) &&
      st.label >= 1.05 &&
      st.label <= 1.08 &&
      st.planted;
    report.selftest.push({ vp, ...st, pass });
    out(
      `selftest vp=${vp} oklch=${st.oklch.join(",")} label=${st.label} planted=${st.planted} ${pass ? "PASS" : "FAIL"}`,
    );
    if (!pass) process.exit(2);
    for (const spec of routes) {
      const [path, click] = spec.split("|click=");
      const cand = await measure(candidate, path, click);
      const ref = await measure(reference, path, click);
      const refKeys = new Set(ref.fail.map((f) => f.key));
      const fresh = cand.fail.filter((f) => !refKeys.has(f.key));
      newFailures += fresh.length;
      report.pages.push({
        vp,
        route: spec,
        candidate: cand,
        reference: ref,
        new: fresh,
      });
      out(
        `census vp=${vp} route=${spec} status=${cand.status}/${ref.status} checked=${cand.checked} ` +
          `candidate_fail=${cand.fail.length} reference_fail=${ref.fail.length} image_backed=${cand.imageBacked} new=${fresh.length}`,
      );
      for (const f of fresh) out(`  NEW ${f.ratio}:1 < ${f.min} ${f.key}`);
    }
    await ctx.close();
  }
} finally {
  await browser.close();
}
const json = JSON.stringify(report, null, 2);
if (secret && json.includes(secret))
  throw new Error("output guard: bypass value reached the report");
if (opt("--json")[0]) writeFileSync(opt("--json")[0], json);
out(`new_failures=${newFailures}`);
process.exit(newFailures ? 1 : 0);
