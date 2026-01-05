const sharp = require('sharp');
const fs = require('fs');
const path = require('path');

const avatarsDir = path.join(__dirname, '../public/avatars/team');
const files = fs.readdirSync(avatarsDir);

async function optimizeAvatar(filename) {
  const inputPath = path.join(avatarsDir, filename);
  const outputPath = path.join(avatarsDir, filename);

  try {
    await sharp(inputPath)
      .resize(200, 200, {
        fit: 'cover',
        position: 'center'
      })
      .png({ quality: 80, compressionLevel: 9 })
      .toFile(outputPath + '.tmp');

    fs.renameSync(outputPath + '.tmp', outputPath);
    console.log(`✓ Optimized ${filename}`);
  } catch (error) {
    console.error(`✗ Failed to optimize ${filename}:`, error.message);
  }
}

async function main() {
  console.log('Optimizing team avatars...\n');

  for (const file of files) {
    if (file.endsWith('.png')) {
      await optimizeAvatar(file);
    }
  }

  console.log('\nDone!');
}

main();
