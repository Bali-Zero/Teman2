import { chromium } from 'playwright';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const slides = [
  'slide-01-cover.html',
  'slide-02-backstory.html',
  'slide-03-rules.html',
  'slide-04-reactions.html',
  'slide-05-working.html',
  'slide-06-survive.html',
  'slide-07-bigger-picture.html',
  'slide-08-cta.html'
];

async function generateScreenshots() {
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1080, height: 1350 },
    deviceScaleFactor: 2 // Retina quality
  });

  const outputDir = path.join(__dirname, 'output');
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  console.log('Generating screenshots...\n');

  for (let i = 0; i < slides.length; i++) {
    const slide = slides[i];
    const page = await context.newPage();
    const filePath = path.join(__dirname, slide);

    await page.goto(`file://${filePath}`);
    await page.waitForLoadState('networkidle');

    // Wait for fonts to load
    await page.waitForTimeout(500);

    const outputName = slide.replace('.html', '.png');
    const outputPath = path.join(outputDir, outputName);

    await page.screenshot({
      path: outputPath,
      type: 'png',
      fullPage: false
    });

    console.log(`✓ ${i + 1}/8: ${outputName}`);
    await page.close();
  }

  await browser.close();
  console.log(`\n✅ Done! Screenshots saved to: ${outputDir}`);
}

generateScreenshots().catch(console.error);
