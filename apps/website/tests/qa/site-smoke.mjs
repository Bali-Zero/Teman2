#!/usr/bin/env node

const DEFAULT_BASE_URL = "http://127.0.0.1:3105";
const REQUIRED_ROUTES = [
  "/",
  "/services",
  "/services/immigration",
  "/services/company-setup",
  "/services/tax",
  "/services/property",
  "/journal",
];

const REQUIRED_HOME_COPY = [
  "Consultancy for immigration, company setup, tax and property in Indonesia.",
  "Sign in to My Bali Zero",
  "Surya",
  "Ari",
  "Tax Compliance Calendar",
  "Read our reviews on Google",
];

const EXCLUDED_STALE_HOME_COPY = [
  "Tax Intelligence",
  "693 reviews",
  "14 August 2026",
];

function unique(values) {
  return [...new Set(values)];
}

function attributes(html, attribute) {
  const pattern = new RegExp(`${attribute}=["']([^"']+)["']`, "g");
  return [...html.matchAll(pattern)].map((match) => match[1]);
}

async function fetchPreview(url) {
  return fetch(url, {
    redirect: "manual",
    signal: AbortSignal.timeout(10_000),
  });
}

async function main() {
  const baseUrl = new URL(process.argv[2] ?? DEFAULT_BASE_URL);
  const report = {
    baseUrl: baseUrl.origin,
    checkedAt: new Date().toISOString(),
    routes: [],
    fragments: [],
    assets: [],
    content: [],
    destinations: [],
    failures: [],
  };

  let homeHtml = "";
  for (const route of REQUIRED_ROUTES) {
    const url = new URL(route, baseUrl);
    const response = await fetchPreview(url);
    const contentType = response.headers.get("content-type") ?? "";
    const routeResult = {
      route,
      status: response.status,
      contentType,
      location: response.headers.get("location"),
    };
    report.routes.push(routeResult);
    if (response.status !== 200 || !contentType.includes("text/html")) {
      report.failures.push({
        check: "required-route",
        route,
        expected: "HTTP 200 text/html",
        actual: `HTTP ${response.status} ${contentType || "without content-type"}`,
      });
    }
    if (route === "/") homeHtml = await response.text();
  }

  if (homeHtml) {
    const homeHrefs = attributes(homeHtml, "href");
    const fragmentLinks = unique(
      homeHrefs
        .filter((href) => href.startsWith("#") && href.length > 1)
        .map((href) => href.slice(1)),
    );
    const ids = new Set(attributes(homeHtml, "id"));
    report.fragments = fragmentLinks.map((fragment) => ({
      fragment,
      targetExists: ids.has(fragment),
    }));
    for (const result of report.fragments) {
      if (!result.targetExists) {
        report.failures.push({
          check: "fragment-target",
          fragment: result.fragment,
          expected: "matching element id",
          actual: "missing",
        });
      }
    }

    const assetPaths = unique(
      attributes(homeHtml, "src").filter((src) => src.startsWith("/assets/")),
    );
    for (const assetPath of assetPaths) {
      const response = await fetchPreview(new URL(assetPath, baseUrl));
      const result = {
        assetPath,
        status: response.status,
        contentType: response.headers.get("content-type") ?? "",
      };
      report.assets.push(result);
      if (response.status !== 200) {
        report.failures.push({
          check: "home-asset",
          assetPath,
          expected: "HTTP 200",
          actual: `HTTP ${response.status}`,
        });
      }
    }

    for (const copy of REQUIRED_HOME_COPY) {
      const present = homeHtml.includes(copy);
      report.content.push({ copy, present });
      if (!present) {
        report.failures.push({
          check: "required-home-copy",
          copy,
          expected: "present",
          actual: "missing",
        });
      }
    }

    for (const excludedName of [
      "Faysha",
      "Sahira",
      ...EXCLUDED_STALE_HOME_COPY,
    ]) {
      const absent = !homeHtml.includes(excludedName);
      report.content.push({ copy: excludedName, absent });
      if (!absent) {
        report.failures.push({
          check: "excluded-home-copy",
          copy: excludedName,
          expected: "absent",
          actual: "present",
        });
      }
    }

    const unsupportedNewsFilters = unique(
      homeHrefs.filter((href) => href.startsWith("https://balizero.com/news?")),
    );
    report.destinations.push({
      check: "unsupported-public-news-filter",
      matchingHrefs: unsupportedNewsFilters,
    });
    for (const href of unsupportedNewsFilters) {
      report.failures.push({
        check: "unsupported-public-news-filter",
        href,
        expected: "plain /news destination or non-filter control",
        actual: "unsupported public query/filter URL",
      });
    }
  }

  report.summary = {
    requiredRoutes: REQUIRED_ROUTES.length,
    passingRoutes: report.routes.filter((route) => route.status === 200).length,
    fragmentTargets: report.fragments.length,
    passingFragmentTargets: report.fragments.filter((item) => item.targetExists)
      .length,
    homeAssets: report.assets.length,
    passingHomeAssets: report.assets.filter((asset) => asset.status === 200)
      .length,
    unsupportedPublicNewsFilters:
      report.destinations[0]?.matchingHrefs.length ?? 0,
    failures: report.failures.length,
  };

  console.log(JSON.stringify(report, null, 2));
  if (report.failures.length > 0) process.exitCode = 1;
}

main().catch((error) => {
  console.error(
    JSON.stringify(
      {
        failures: [
          {
            check: "preview-availability",
            expected: "reachable preview",
            actual: error instanceof Error ? error.message : String(error),
          },
        ],
      },
      null,
      2,
    ),
  );
  process.exitCode = 1;
});
