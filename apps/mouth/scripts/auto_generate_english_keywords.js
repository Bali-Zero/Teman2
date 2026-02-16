const fs = require('fs');
const path = require('path');

// Simple translation dictionary for common KBLI terms
const translations = {
  // Food & Beverage
  'makanan': ['food', 'meal', 'cuisine'],
  'minuman': ['beverage', 'drink', 'drinks'],
  'restaurant': ['restaurant', 'dining'],
  'restoran': ['restaurant', 'dining', 'eatery'],
  'hotel': ['hotel', 'accommodation', 'lodging'],
  'kafe': ['cafe', 'coffee shop'],
  'bar': ['bar', 'pub', 'lounge'],
  'katering': ['catering', 'food service'],
  
  // Technology
  'komputer': ['computer', 'computing', 'IT'],
  'perangkat lunak': ['software', 'application', 'app'],
  'pemrograman': ['programming', 'coding', 'development'],
  'teknologi informasi': ['information technology', 'IT', 'tech'],
  'internet': ['internet', 'web', 'online'],
  'data': ['data', 'database', 'information'],
  
  // Construction & Real Estate
  'bangunan': ['building', 'construction', 'structure'],
  'gedung': ['building', 'edifice', 'structure'],
  'konstruksi': ['construction', 'building'],
  'properti': ['property', 'real estate', 'realty'],
  
  // Retail
  'perdagangan': ['trading', 'commerce', 'trade'],
  'eceran': ['retail', 'shop', 'store'],
  'toko': ['shop', 'store', 'outlet'],
  'pasar': ['market', 'marketplace'],
  
  // Healthcare
  'kesehatan': ['health', 'healthcare', 'medical'],
  'rumah sakit': ['hospital', 'medical center'],
  'klinik': ['clinic', 'medical clinic'],
  'dokter': ['doctor', 'physician', 'medical'],
  'farmasi': ['pharmacy', 'drugstore'],
  
  // Education
  'pendidikan': ['education', 'educational', 'learning'],
  'sekolah': ['school', 'academy'],
  'pelatihan': ['training', 'course'],
  
  // Transportation
  'transportasi': ['transportation', 'transport'],
  'angkutan': ['transport', 'transportation', 'freight'],
  'logistik': ['logistics', 'distribution'],
  
  // Professional Services
  'konsultan': ['consulting', 'consultant', 'advisory'],
  'jasa': ['service', 'services'],
  'profesional': ['professional'],
  
  // Manufacturing
  'industri': ['industry', 'industrial', 'manufacturing'],
  'pabrik': ['factory', 'plant', 'manufacturing'],
  'produksi': ['production', 'manufacturing'],
  
  // Agriculture
  'pertanian': ['agriculture', 'farming', 'agricultural'],
  'perkebunan': ['plantation', 'estate', 'farming'],
  'perikanan': ['fishery', 'fishing', 'aquaculture'],
  
  // Finance
  'keuangan': ['finance', 'financial'],
  'bank': ['bank', 'banking'],
  'asuransi': ['insurance', 'assurance'],
  
  // Arts & Recreation
  'seni': ['art', 'arts', 'artistic'],
  'hiburan': ['entertainment', 'recreation'],
  'olahraga': ['sports', 'athletic'],
  'pariwisata': ['tourism', 'travel'],
};

// Load reference data
const REFERENCE_FILE = path.join(__dirname, '../../../source_documents/KBLI_2025_FINAL_CLEAN.json');
const referenceData = JSON.parse(fs.readFileSync(REFERENCE_FILE, 'utf8'));

// Load existing English keywords
const KEYWORDS_FILE = path.join(__dirname, 'kbli_english_keywords.json');
const existingKeywords = JSON.parse(fs.readFileSync(KEYWORDS_FILE, 'utf8'));

console.log('🔍 Analyzing KBLI data to generate English keywords...\n');

let generated = 0;
let skipped = 0;

const enhancedKeywords = { ...existingKeywords };

referenceData.data.forEach(code => {
  const kbliCode = code.kode_kbli_2025;
  
  // Skip if already has English keywords
  if (enhancedKeywords[kbliCode]) {
    skipped++;
    return;
  }
  
  const title = code.judul.toLowerCase();
  const description = (code.uraian || '').toLowerCase();
  const allText = title + ' ' + description;
  
  const englishTerms = [];
  const categories = new Set();
  
  // Match against translation dictionary
  for (const [indonesian, english] of Object.entries(translations)) {
    if (allText.includes(indonesian)) {
      englishTerms.push(...english);
      
      // Infer category
      if (indonesian.includes('makanan') || indonesian.includes('restoran')) categories.add('Food Service');
      else if (indonesian.includes('komputer') || indonesian.includes('teknologi')) categories.add('Technology');
      else if (indonesian.includes('bangunan') || indonesian.includes('konstruksi')) categories.add('Construction');
      else if (indonesian.includes('perdagangan') || indonesian.includes('eceran')) categories.add('Retail');
      else if (indonesian.includes('kesehatan') || indonesian.includes('dokter')) categories.add('Healthcare');
      else if (indonesian.includes('pendidikan')) categories.add('Education');
      else if (indonesian.includes('transportasi')) categories.add('Transportation');
      else if (indonesian.includes('pertanian')) categories.add('Agriculture');
    }
  }
  
  // Remove duplicates
  const uniqueTerms = [...new Set(englishTerms)];
  
  // Only add if we found at least 2 English terms
  if (uniqueTerms.length >= 2) {
    enhancedKeywords[kbliCode] = {
      english: uniqueTerms,
      category: Array.from(categories)[0] || 'General'
    };
    generated++;
    
    if (generated <= 10) {
      console.log(`✓ ${kbliCode}: ${code.judul}`);
      console.log(`  → ${uniqueTerms.join(', ')}\n`);
    }
  }
});

// Write enhanced keywords
fs.writeFileSync(KEYWORDS_FILE, JSON.stringify(enhancedKeywords, null, 2));

console.log(`\n📊 Results:`);
console.log(`  Existing: ${skipped}`);
console.log(`  Generated: ${generated}`);
console.log(`  Total: ${Object.keys(enhancedKeywords).length}`);
console.log(`  Coverage: ${((Object.keys(enhancedKeywords).length / 1562) * 100).toFixed(1)}%`);
console.log(`\n✅ Enhanced keywords saved to: ${KEYWORDS_FILE}`);
console.log('\n💡 Next step: Run generate_kbli_data.js to apply these keywords');
