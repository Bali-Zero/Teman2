const { test, expect } = require("@playwright/test");

test("SSR Smoke Test: Googlebot Verification", async ({ request }) => {
  // 1. Fetch RAW HTML (no browser hydration)
  const response = await request.get(
    "http://localhost:3000/services/investor-kitas",
  );
  expect(response.ok()).toBeTruthy();

  const html = await response.text();

  // 2. Critical SEO Check: Price in Raw HTML
  // If this fails, the page is Client-Side Rendered (Bad for SEO)
  if (!html.includes("15.000.000")) {
    throw new Error("FATAL: Price not found in raw HTML. SSR is broken.");
  }
  // ✅ Price (15.000.000) found in server response.

  // 3. Critical SEO Check: JSON-LD Schema
  // Verify Script tag format
  if (!html.includes('<script type="application/ld+json">')) {
    // We expect native tag now
    throw new Error("FATAL: JSON-LD script tag not found.");
  }

  // Verify Schema Content (Organization)
  if (
    !html.includes('"@type":"GovernmentService"') &&
    !html.includes('"@type":"ProfessionalService"')
  ) {
    throw new Error("FATAL: Service Schema type not found in JSON-LD.");
  }
  // ✅ JSON-LD Schema found and correctly formatted.

  // 4. Verify AI Summary Block
  if (
    !html.includes(
      '<dl class="sr-only" itemscope itemtype="https://schema.org/GovernmentService">',
    )
  ) {
    // ⚠️ WARNING: AI Summary Block (dl.sr-only) not found or class mismatch.
  } else {
    // ✅ AI Summary Block found.
  }
});
