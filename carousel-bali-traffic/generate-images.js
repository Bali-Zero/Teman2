import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const IMAGINART_API_KEY = 'vk-3zVt3g8xJ7dSg6KZ3pbpPRUPDwtSAQDlJssPQrKZTp7Kp';

// Prompts ottimizzati per Bali, ultra-realistici, con più luce
const imagePrompts = [
  {
    name: 'cover-traffic',
    prompt: 'Ultra realistic photo of massive traffic jam in Kerobokan Bali Indonesia, hundreds of scooters motorcycles and cars gridlocked on narrow street, traditional Balinese temples in background, palm trees, bright daylight, high saturation colors, photojournalism style, 8K quality, sharp focus, vibrant'
  },
  {
    name: 'backstory-flood',
    prompt: 'Ultra realistic photo of flooded street in Seminyak Bali Indonesia after tropical storm, local riders on scooters wading through water, Balinese shop houses, dramatic clouds breaking with sunlight, bright wet reflections, photojournalism style, 8K quality, vivid colors'
  },
  {
    name: 'rules-map',
    prompt: 'Ultra realistic aerial drone photo of busy intersection in Kerobokan Bali, view from above showing traffic flow, one-way street signs visible, tropical palm trees, Balinese architecture, bright sunny day, high contrast, sharp details, 8K quality'
  },
  {
    name: 'bigger-picture',
    prompt: 'Ultra realistic photo of new highway road construction in Bali Indonesia, modern infrastructure project, construction equipment, Balinese landscape with rice terraces in background, blue sky with white clouds, bright daylight, progress and development, 8K quality, vibrant colors'
  }
];

async function generateImage(prompt, name) {
  console.log(`\nGenerating: ${name}...`);
  console.log(`Prompt: ${prompt.substring(0, 80)}...`);

  try {
    const formData = new FormData();
    formData.append('prompt', prompt);
    formData.append('style_id', '122'); // Photographic/Realistic
    formData.append('aspect_ratio', '4:5'); // Instagram portrait
    formData.append('high_res_results', '1');

    const response = await fetch('https://api.vyro.ai/v1/imagine/api/generations', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${IMAGINART_API_KEY}`
      },
      body: formData
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error(`API Error for ${name}:`, response.status, errorText);
      return null;
    }

    const contentType = response.headers.get('content-type');

    if (contentType?.includes('image')) {
      const buffer = await response.arrayBuffer();
      const outputPath = path.join(__dirname, 'images', `${name}.png`);
      fs.writeFileSync(outputPath, Buffer.from(buffer));
      console.log(`✓ Saved: ${name}.png`);
      return outputPath;
    } else {
      const data = await response.json();
      const imageUrl = data.image_url || data.url || data[0]?.url || data.data?.[0]?.url;
      if (imageUrl) {
        const imageResponse = await fetch(imageUrl);
        const buffer = await imageResponse.arrayBuffer();
        const outputPath = path.join(__dirname, 'images', `${name}.png`);
        fs.writeFileSync(outputPath, Buffer.from(buffer));
        console.log(`✓ Saved: ${name}.png`);
        return outputPath;
      }
    }

    return null;
  } catch (error) {
    console.error(`Error generating ${name}:`, error.message);
    return null;
  }
}

async function main() {
  const imagesDir = path.join(__dirname, 'images');
  if (!fs.existsSync(imagesDir)) {
    fs.mkdirSync(imagesDir, { recursive: true });
  }

  console.log('='.repeat(60));
  console.log('GENERATING ULTRA-REALISTIC BALI IMAGES');
  console.log('='.repeat(60));

  for (const img of imagePrompts) {
    await generateImage(img.prompt, img.name);
    // Rate limiting
    await new Promise(r => setTimeout(r, 3000));
  }

  console.log('\n' + '='.repeat(60));
  console.log('DONE! All images generated.');
  console.log('='.repeat(60));
}

main().catch(console.error);
