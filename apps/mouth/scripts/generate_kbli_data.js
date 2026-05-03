const fs = require("fs");
const path = require("path");

console.log("🚀 KBLI Data Generation Script - Phase 1: English Keywords");
console.log("=".repeat(70));

// ============================================================================
// STEP 1: Load Reference Data
// ============================================================================

const REFERENCE_FILE = path.join(
  __dirname,
  "../../../source_documents/KBLI_2025_FINAL_CLEAN.json",
);

console.log("\n📂 Loading reference data...");
const referenceRaw = fs.readFileSync(REFERENCE_FILE, "utf8");
const referenceData = JSON.parse(referenceRaw);
console.log(`✅ Loaded ${referenceData.data.length} codes from reference file`);

// ============================================================================
// STEP 2: Load English Keywords Mapping
// ============================================================================

const KEYWORDS_FILE = path.join(__dirname, "kbli_english_keywords.json");

console.log("\n📂 Loading English keywords mapping...");
let englishKeywords = {};

if (fs.existsSync(KEYWORDS_FILE)) {
  englishKeywords = JSON.parse(fs.readFileSync(KEYWORDS_FILE, "utf8"));
  console.log(
    `✅ Loaded English keywords for ${Object.keys(englishKeywords).length} codes`,
  );
} else {
  console.log("⚠️  English keywords file not found. Creating template...");
  englishKeywords = {};
  fs.writeFileSync(KEYWORDS_FILE, JSON.stringify(englishKeywords, null, 2));
  console.log(`✅ Created template at ${KEYWORDS_FILE}`);
}

// ============================================================================
// STEP 3: Helper Functions
// ============================================================================

/**
 * Extract section letter from KBLI code
 */
function getSectionLetter(code) {
  const sectionMap = {
    "01": "A",
    "02": "A",
    "03": "A",
    "05": "B",
    "06": "B",
    "07": "B",
    "08": "B",
    "09": "B",
    10: "C",
    11: "C",
    12: "C",
    13: "C",
    14: "C",
    15: "C",
    16: "C",
    17: "C",
    18: "C",
    19: "C",
    20: "C",
    21: "C",
    22: "C",
    23: "C",
    24: "C",
    25: "C",
    26: "C",
    27: "C",
    28: "C",
    29: "C",
    30: "C",
    31: "C",
    32: "C",
    33: "C",
    35: "D",
    36: "E",
    37: "E",
    38: "E",
    39: "E",
    41: "F",
    42: "F",
    43: "F",
    45: "G",
    46: "G",
    47: "G",
    49: "H",
    50: "H",
    51: "H",
    52: "H",
    53: "H",
    55: "I",
    56: "I",
    58: "J",
    59: "J",
    60: "J",
    61: "J",
    62: "J",
    63: "J",
    64: "K",
    65: "K",
    66: "K",
    68: "L",
    69: "M",
    70: "M",
    71: "M",
    72: "M",
    73: "M",
    74: "M",
    75: "M",
    77: "N",
    78: "N",
    79: "N",
    80: "N",
    81: "N",
    82: "N",
    84: "O",
    85: "P",
    86: "Q",
    87: "Q",
    88: "Q",
    90: "R",
    91: "R",
    92: "R",
    93: "R",
    94: "S",
    95: "S",
    96: "S",
    97: "T",
    98: "T",
    99: "U",
  };

  const prefix = code.kode_kbli_2025.substring(0, 2);
  return sectionMap[prefix] || "A";
}

/**
 * Get PMA status from code data
 */
function getPMAStatus(code) {
  const pma = code.pma_status || code.status_pma;

  if (!pma) return "O"; // Default: Open

  if (pma === "TERBUKA" || pma === "Open" || pma === "O") return "O";
  if (pma === "TERBATAS" || pma === "Restricted" || pma === "R") return "R";
  if (pma === "TERTUTUP" || pma === "Closed" || pma === "C") return "C";

  return "O"; // Default
}

/**
 * Get max foreign ownership percentage
 */
function getMaxForeignOwnership(code) {
  const pmaStatus = getPMAStatus(code);

  if (pmaStatus === "C") return 0; // Closed = 0%
  if (pmaStatus === "R") return 49; // Restricted = typically 49%
  return 100; // Open = 100%
}

/**
 * Get risk level from per_skala data
 */
function getRiskLevel(code) {
  if (!code.per_skala || code.per_skala.length === 0) {
    return "ML"; // Default: Medium-Low
  }

  // Get highest risk level from all scales
  const riskMap = {
    Rendah: "L",
    "Menengah Rendah": "ML",
    "Menengah Tinggi": "MH",
    Tinggi: "H",
  };

  let highestRisk = "L";
  const riskOrder = ["L", "ML", "MH", "H"];

  code.per_skala.forEach((skala) => {
    const risk = riskMap[skala.kategori_risiko] || "ML";
    if (riskOrder.indexOf(risk) > riskOrder.indexOf(highestRisk)) {
      highestRisk = risk;
    }
  });

  return highestRisk;
}

/**
 * Extract Indonesian keywords from code data
 */
function extractIndonesianKeywords(code) {
  const keywords = [];

  // Add title words
  if (code.judul) {
    const titleWords = code.judul
      .toLowerCase()
      .replace(/[^a-z\s]/gi, " ")
      .split(/\s+/)
      .filter((word) => word.length > 2);
    keywords.push(...titleWords);
  }

  // Add description words (first 200 chars)
  if (code.uraian) {
    const descWords = code.uraian
      .substring(0, 200)
      .toLowerCase()
      .replace(/[^a-z\s]/gi, " ")
      .split(/\s+/)
      .filter((word) => word.length > 3);
    keywords.push(...descWords.slice(0, 10)); // Max 10 words from description
  }

  // Remove duplicates
  return [...new Set(keywords)];
}

/**
 * Merge English and Indonesian keywords
 */
function mergeKeywords(kbliCode, indonesianKeywords) {
  const english = englishKeywords[kbliCode]?.english || [];

  // English first, then Indonesian
  const allKeywords = [...english, ...indonesianKeywords];

  // Remove duplicates, lowercase, join with spaces
  const uniqueKeywords = [...new Set(allKeywords.map((k) => k.toLowerCase()))];

  return uniqueKeywords.join(" ");
}

// ============================================================================
// STEP 4: Generate K Array
// ============================================================================

console.log("\n🔨 Generating K array with English keywords...");

const K = referenceData.data.map((code, index) => {
  const kbliCode = code.kode_kbli_2025;

  // Extract Indonesian keywords
  const indonesianKeywords = extractIndonesianKeywords(code);

  // Merge with English keywords
  const allKeywords = mergeKeywords(kbliCode, indonesianKeywords);

  // Progress indicator
  if ((index + 1) % 100 === 0) {
    console.log(
      `  Processed ${index + 1}/${referenceData.data.length} codes...`,
    );
  }

  return [
    kbliCode, // [0] Code
    code.judul, // [1] Title
    getSectionLetter(code), // [2] Section
    getPMAStatus(code), // [3] PMA Status
    getMaxForeignOwnership(code), // [4] Max Foreign %
    getRiskLevel(code), // [5] Risk Level
    "", // [6] Kondisi (empty)
    allKeywords, // [7] ENHANCED Keywords
  ];
});

console.log(`✅ Generated ${K.length} codes`);

// ============================================================================
// STEP 5: Statistics
// ============================================================================

console.log("\n📊 Statistics:");

const stats = {
  total: K.length,
  withEnglish: K.filter((row) => {
    const code = row[0];
    return englishKeywords[code] && englishKeywords[code].english.length > 0;
  }).length,
  withoutEnglish: 0,
};

stats.withoutEnglish = stats.total - stats.withEnglish;

console.log(`  Total codes: ${stats.total}`);
console.log(
  `  With English keywords: ${stats.withEnglish} (${((stats.withEnglish / stats.total) * 100).toFixed(1)}%)`,
);
console.log(
  `  Without English keywords: ${stats.withoutEnglish} (${((stats.withoutEnglish / stats.total) * 100).toFixed(1)}%)`,
);

// ============================================================================
// STEP 6: Write Output Files
// ============================================================================

console.log("\n💾 Writing output files...");

// Output 1: JavaScript array (for index.html)
const jsOutput = `const K = ${JSON.stringify(K, null, 0)};`;
const jsFile = path.join(
  __dirname,
  "../public/kbli-navigator/kbli_data_with_english.js",
);
fs.writeFileSync(jsFile, jsOutput);
console.log(`✅ JavaScript array: ${jsFile}`);
console.log(
  `   File size: ${(fs.statSync(jsFile).size / 1024 / 1024).toFixed(2)} MB`,
);

// Output 2: JSON backup
const jsonFile = path.join(__dirname, "kbli_data_backup.json");
fs.writeFileSync(jsonFile, JSON.stringify(K, null, 2));
console.log(`✅ JSON backup: ${jsonFile}`);

// Output 3: Report
const report = `
KBLI Data Generation Report - Phase 1
======================================
Date: ${new Date().toISOString()}
Total Codes: ${stats.total}
With English Keywords: ${stats.withEnglish} (${((stats.withEnglish / stats.total) * 100).toFixed(1)}%)
Without English Keywords: ${stats.withoutEnglish} (${((stats.withoutEnglish / stats.total) * 100).toFixed(1)}%)

Sample Codes with English Keywords:
`;

const sampleCodes = K.filter((row) => {
  const code = row[0];
  return englishKeywords[code] && englishKeywords[code].english.length > 0;
}).slice(0, 10);

const reportWithSamples =
  report +
  sampleCodes
    .map((row) => {
      return `\n${row[0]} - ${row[1]}\nKeywords: ${row[7]}\n`;
    })
    .join("\n");

const reportFile = path.join(__dirname, "generation_report.txt");
fs.writeFileSync(reportFile, reportWithSamples);
console.log(`✅ Report: ${reportFile}`);

// ============================================================================
// STEP 7: Next Steps
// ============================================================================

console.log("\n✅ Generation complete!");
console.log("\n📋 Next steps:");
console.log("1. Review generated file: " + jsFile);
console.log("2. Copy K array to: /apps/mouth/public/kbli-navigator/index.html");
console.log("3. Test search functionality");
console.log("4. Run test suite to measure improvements");
console.log("\n" + "=".repeat(70));
