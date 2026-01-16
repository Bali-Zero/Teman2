#!/usr/bin/env node
/**
 * Image Optimization Script
 * Compresses images to max 300KB while maintaining quality
 */

const sharp = require('sharp');
const fs = require('fs');
const path = require('path');

const IMAGE_DIR = path.join(__dirname, '../apps/mouth/public/static/news');
const MAX_SIZE_KB = 300;
const TARGET_WIDTH = 1200;

// Images to optimize
const IMAGES_TO_OPTIMIZE = [
  'dengue-alert.jpg',
  'maritime-chaos.jpg',
  'indonesia-zero-tax-expat.jpg',
  'gemini-3-ai.jpg',
  'gemini-3-multimodal.jpg'
];

async function getFileSize(filePath) {
  const stats = fs.statSync(filePath);
  return (stats.size / 1024).toFixed(2); // KB
}

async function optimizeImage(filename) {
  const inputPath = path.join(IMAGE_DIR, filename);
  const outputPath = path.join(IMAGE_DIR, filename);
  const backupPath = path.join(IMAGE_DIR, `${filename}.backup`);

  if (!fs.existsSync(inputPath)) {
    console.log(`⏭️  ${filename} - Not found, skipping`);
    return;
  }

  const originalSize = await getFileSize(inputPath);

  // Skip if already optimized
  if (originalSize < MAX_SIZE_KB) {
    console.log(`✅ ${filename} - Already optimized (${originalSize} KB)`);
    return;
  }

  // Backup original
  fs.copyFileSync(inputPath, backupPath);

  try {
    // Progressive optimization with quality adjustment
    let quality = 85;
    let optimized = false;
    let finalSize = 0;

    while (!optimized && quality >= 60) {
      await sharp(inputPath)
        .resize(TARGET_WIDTH, null, {
          fit: 'inside',
          withoutEnlargement: true
        })
        .jpeg({
          quality,
          progressive: true,
          mozjpeg: true
        })
        .toFile(outputPath + '.tmp');

      finalSize = await getFileSize(outputPath + '.tmp');

      if (finalSize <= MAX_SIZE_KB || quality <= 60) {
        optimized = true;
        fs.renameSync(outputPath + '.tmp', outputPath);
      } else {
        quality -= 5;
        fs.unlinkSync(outputPath + '.tmp');
      }
    }

    const reduction = ((1 - finalSize / originalSize) * 100).toFixed(1);
    console.log(`✅ ${filename}`);
    console.log(`   ${originalSize} KB → ${finalSize} KB (${reduction}% reduction, quality: ${quality})`);

  } catch (error) {
    // Restore backup on error
    fs.copyFileSync(backupPath, outputPath);
    console.error(`❌ ${filename} - Error: ${error.message}`);
  }
}

async function main() {
  console.log('🖼️  Image Optimization Script\n');
  console.log(`Target: Max ${MAX_SIZE_KB} KB per image`);
  console.log(`Width: ${TARGET_WIDTH}px\n`);

  for (const img of IMAGES_TO_OPTIMIZE) {
    await optimizeImage(img);
  }

  console.log('\n✅ Optimization complete!');
  console.log('\nBackup files saved as *.backup (delete when satisfied with results)');
}

main().catch(console.error);
