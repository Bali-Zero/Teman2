/* eslint-disable @typescript-eslint/no-require-imports */
const puppeteer = require("puppeteer");

(async () => {
  console.log("🚀 Starting Puppeteer X-RAY Debug...");
  const browser = await puppeteer.launch({
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
    headless: "new",
  });
  const page = await browser.newPage();

  // 1. Capture Browser Console & Errors
  page.on("console", (msg) => console.log("🔹 BROWSER LOG:", msg.text()));
  page.on("pageerror", (err) =>
    console.error("🔴 BROWSER JS ERROR:", err.message),
  );
  page.on("requestfailed", (req) =>
    console.error(`❌ NETWORK FAIL: ${req.url()} - ${req.failure().errorText}`),
  );

  try {
    console.log("🌐 Navigating to http://localhost:3000/login ...");
    await page.goto("http://localhost:3000/login", {
      waitUntil: "networkidle2",
      timeout: 30000,
    });

    console.log("✍️ Filling credentials (test1@example.com)...");
    await page.type('input[type="email"]', "test1@example.com");
    await page.type('input[type="password"]', "123456");

    console.log("🖱️ Clicking Submit...");

    // Promise.all per gestire la navigazione in modo robusto
    await Promise.all([
      page.click('button[type="submit"]'),
      page.waitForFunction(
        () => {
          // Aspetta o il redirect alla chat o un messaggio di errore visibile
          return (
            window.location.href.includes("/chat") ||
            document.body.innerText.includes("Invalid")
          );
        },
        { timeout: 15000 },
      ),
    ]);

    const url = page.url();
    console.log(`📍 Current URL: ${url}`);

    if (url.includes("/chat")) {
      console.log("🎉 SUCCESS: Reached Chat Page!");
      // Optional: Check if input exists
      await page.waitForSelector('input[placeholder*="message"]', {
        timeout: 5000,
      });
      console.log("✅ Chat Interface Loaded.");
    } else {
      console.error("❌ FAILED: Still on Login page or Error.");
      const content = await page.content();
      if (content.includes("Invalid"))
        console.log("Reason: Invalid Credentials shown on UI");
    }
  } catch (error) {
    console.error("💥 SCRIPT CRASH:", error.message);
  } finally {
    await browser.close();
  }
})();
