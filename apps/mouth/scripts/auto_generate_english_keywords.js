const fs = require("fs");
const path = require("path");

// Enhanced translation dictionary for comprehensive KBLI coverage
const translations = {
  // Food & Beverage
  makanan: ["food", "meal", "cuisine"],
  minuman: ["beverage", "drink", "drinks"],
  restaurant: ["restaurant", "dining"],
  restoran: ["restaurant", "dining", "eatery"],
  hotel: ["hotel", "accommodation", "lodging"],
  kafe: ["cafe", "coffee shop"],
  bar: ["bar", "pub", "lounge"],
  katering: ["catering", "food service"],
  pangan: ["food", "foodstuff", "staple"],
  minum: ["beverage", "drink"],
  kopi: ["coffee"],
  teh: ["tea"],
  roti: ["bread", "bakery"],
  kue: ["cake", "pastry", "bakery"],

  // Technology & IT
  komputer: ["computer", "computing", "IT"],
  "perangkat lunak": ["software", "application", "app"],
  pemrograman: ["programming", "coding", "development"],
  "teknologi informasi": ["information technology", "IT", "tech"],
  internet: ["internet", "web", "online"],
  data: ["data", "database", "information"],
  sistem: ["system", "systems"],
  aplikasi: ["application", "app", "software"],
  jaringan: ["network", "networking"],
  elektronik: ["electronic", "electronics"],
  telekomunikasi: ["telecommunication", "telecom", "communication"],
  informasi: ["information", "data"],

  // Construction & Real Estate
  bangunan: ["building", "construction", "structure"],
  gedung: ["building", "edifice", "structure"],
  konstruksi: ["construction", "building"],
  properti: ["property", "real estate", "realty"],
  rumah: ["house", "housing", "residential"],
  jalan: ["road", "street", "highway"],
  jembatan: ["bridge"],
  infrastruktur: ["infrastructure"],
  sipil: ["civil", "civil engineering"],

  // Retail & Commerce
  perdagangan: ["trading", "commerce", "trade"],
  eceran: ["retail", "shop", "store"],
  toko: ["shop", "store", "outlet"],
  pasar: ["market", "marketplace"],
  besar: ["wholesale", "bulk", "large"],
  grosir: ["wholesale"],
  penjualan: ["sales", "selling"],
  distribusi: ["distribution"],
  ekspor: ["export", "exporting"],
  impor: ["import", "importing"],

  // Healthcare & Medical
  kesehatan: ["health", "healthcare", "medical"],
  "rumah sakit": ["hospital", "medical center"],
  klinik: ["clinic", "medical clinic"],
  dokter: ["doctor", "physician", "medical"],
  farmasi: ["pharmacy", "drugstore"],
  medis: ["medical", "medicine"],
  perawatan: ["care", "treatment", "nursing"],
  sosial: ["social", "welfare"],

  // Education & Training
  pendidikan: ["education", "educational", "learning"],
  sekolah: ["school", "academy"],
  pelatihan: ["training", "course"],
  universitas: ["university", "college"],
  kursus: ["course", "training", "class"],
  bimbingan: ["tutoring", "guidance", "coaching"],

  // Transportation & Logistics
  transportasi: ["transportation", "transport"],
  angkutan: ["transport", "transportation", "freight"],
  logistik: ["logistics", "distribution"],
  pengiriman: ["shipping", "delivery"],
  kendaraan: ["vehicle", "automotive"],
  mobil: ["car", "automobile", "vehicle"],
  motor: ["motorcycle", "motor"],
  kapal: ["ship", "vessel", "marine"],
  pesawat: ["aircraft", "airplane", "aviation"],
  kereta: ["train", "railway"],
  laut: ["sea", "marine", "maritime"],
  udara: ["air", "aviation", "airline"],

  // Professional Services
  konsultan: ["consulting", "consultant", "advisory"],
  jasa: ["service", "services"],
  profesional: ["professional"],
  hukum: ["legal", "law"],
  akuntansi: ["accounting", "accountancy"],
  audit: ["audit", "auditing"],
  manajemen: ["management", "managing"],
  teknik: ["engineering", "technical"],
  arsitektur: ["architecture", "architectural"],
  desain: ["design", "designer"],
  iklan: ["advertising", "advertisement"],
  riset: ["research"],
  penelitian: ["research", "study"],

  // Manufacturing & Industry
  industri: ["industry", "industrial", "manufacturing"],
  pabrik: ["factory", "plant", "manufacturing"],
  produksi: ["production", "manufacturing"],
  pengolahan: ["processing", "treatment"],
  pembuatan: ["manufacturing", "production", "making"],
  tekstil: ["textile", "fabric"],
  pakaian: ["clothing", "garment", "apparel"],
  kayu: ["wood", "timber", "lumber"],
  kertas: ["paper"],
  kimia: ["chemical", "chemistry"],
  logam: ["metal", "metallic"],
  mesin: ["machine", "machinery", "mechanical"],
  otomotif: ["automotive", "automobile"],

  // Agriculture & Natural Resources
  pertanian: ["agriculture", "farming", "agricultural"],
  perkebunan: ["plantation", "estate", "farming"],
  perikanan: ["fishery", "fishing", "aquaculture"],
  kehutanan: ["forestry", "forest"],
  tanaman: ["plant", "crop", "vegetation"],
  hewan: ["animal", "livestock"],
  ternak: ["livestock", "cattle", "animal husbandry"],
  sayur: ["vegetable", "vegetables"],
  buah: ["fruit", "fruits"],
  padi: ["rice", "paddy"],
  jagung: ["corn", "maize"],

  // Finance & Insurance
  keuangan: ["finance", "financial"],
  bank: ["bank", "banking"],
  asuransi: ["insurance", "assurance"],
  investasi: ["investment", "investing"],
  modal: ["capital", "equity"],
  kredit: ["credit", "loan"],
  pembiayaan: ["financing", "funding"],

  // Arts, Entertainment & Recreation
  seni: ["art", "arts", "artistic"],
  hiburan: ["entertainment", "recreation"],
  olahraga: ["sports", "athletic"],
  pariwisata: ["tourism", "travel"],
  rekreasi: ["recreation", "leisure"],
  budaya: ["culture", "cultural"],
  museum: ["museum"],
  galeri: ["gallery"],
  pertunjukan: ["performance", "show"],
  musik: ["music", "musical"],
  film: ["film", "movie", "cinema"],
  video: ["video"],

  // Energy & Utilities
  listrik: ["electricity", "electric", "power"],
  energi: ["energy", "power"],
  gas: ["gas"],
  air: ["water"],
  limbah: ["waste"],
  sampah: ["waste", "garbage", "trash"],

  // Other Services
  reparasi: ["repair", "maintenance"],
  perbaikan: ["repair", "fixing"],
  pemeliharaan: ["maintenance"],
  persewaan: ["rental", "renting", "lease"],
  penyimpanan: ["storage", "warehousing"],
  keamanan: ["security", "safety"],
  kebersihan: ["cleaning", "sanitation"],
  laundry: ["laundry", "cleaning"],
  salon: ["salon", "beauty"],
  potong: ["cut", "cutting", "barber"],
  rambut: ["hair", "hairdressing"],
};

// Load reference data
const REFERENCE_FILE = path.join(
  __dirname,
  "../../../source_documents/KBLI_2025_FINAL_CLEAN.json",
);
const referenceData = JSON.parse(fs.readFileSync(REFERENCE_FILE, "utf8"));

// Load existing English keywords
const KEYWORDS_FILE = path.join(__dirname, "kbli_english_keywords.json");
const existingKeywords = JSON.parse(fs.readFileSync(KEYWORDS_FILE, "utf8"));

console.log("🔍 Analyzing KBLI data to generate English keywords...\n");

let generated = 0;
let skipped = 0;

const enhancedKeywords = { ...existingKeywords };

referenceData.data.forEach((code) => {
  const kbliCode = code.kode_kbli_2025;

  // Skip if already has English keywords
  if (enhancedKeywords[kbliCode]) {
    skipped++;
    return;
  }

  const title = code.judul.toLowerCase();
  const description = (code.uraian || "").toLowerCase();
  const allText = title + " " + description;

  const englishTerms = [];
  const categories = new Set();

  // Match against translation dictionary
  for (const [indonesian, english] of Object.entries(translations)) {
    if (allText.includes(indonesian)) {
      englishTerms.push(...english);

      // Infer category
      if (indonesian.includes("makanan") || indonesian.includes("restoran"))
        categories.add("Food Service");
      else if (
        indonesian.includes("komputer") ||
        indonesian.includes("teknologi")
      )
        categories.add("Technology");
      else if (
        indonesian.includes("bangunan") ||
        indonesian.includes("konstruksi")
      )
        categories.add("Construction");
      else if (
        indonesian.includes("perdagangan") ||
        indonesian.includes("eceran")
      )
        categories.add("Retail");
      else if (
        indonesian.includes("kesehatan") ||
        indonesian.includes("dokter")
      )
        categories.add("Healthcare");
      else if (indonesian.includes("pendidikan")) categories.add("Education");
      else if (indonesian.includes("transportasi"))
        categories.add("Transportation");
      else if (indonesian.includes("pertanian")) categories.add("Agriculture");
    }
  }

  // Remove duplicates
  const uniqueTerms = [...new Set(englishTerms)];

  // Only add if we found at least 1 English term
  if (uniqueTerms.length >= 1) {
    enhancedKeywords[kbliCode] = {
      english: uniqueTerms,
      category: Array.from(categories)[0] || "General",
    };
    generated++;

    if (generated <= 10) {
      console.log(`✓ ${kbliCode}: ${code.judul}`);
      console.log(`  → ${uniqueTerms.join(", ")}\n`);
    }
  }
});

// Write enhanced keywords
fs.writeFileSync(KEYWORDS_FILE, JSON.stringify(enhancedKeywords, null, 2));

console.log(`\n📊 Results:`);
console.log(`  Existing: ${skipped}`);
console.log(`  Generated: ${generated}`);
console.log(`  Total: ${Object.keys(enhancedKeywords).length}`);
console.log(
  `  Coverage: ${((Object.keys(enhancedKeywords).length / 1562) * 100).toFixed(1)}%`,
);
console.log(`\n✅ Enhanced keywords saved to: ${KEYWORDS_FILE}`);
console.log(
  "\n💡 Next step: Run generate_kbli_data.js to apply these keywords",
);
