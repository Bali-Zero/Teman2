const fs = require("fs");
const path = require("path");

const INDEX_FILE = path.join(__dirname, "../public/kbli-navigator/index.html");
const NEW_DATA_FILE = path.join(
  __dirname,
  "../public/kbli-navigator/kbli_data_with_english.js",
);

console.log("📝 Updating index.html with new K array...");

// Backup first
const backupFile =
  INDEX_FILE +
  ".backup_phase1_" +
  new Date().toISOString().replace(/[:.]/g, "-").substring(0, 19);
fs.copyFileSync(INDEX_FILE, backupFile);
console.log(`✅ Backup created: ${backupFile}`);

// Read files
const indexContent = fs.readFileSync(INDEX_FILE, "utf8");
const newKArray = fs.readFileSync(NEW_DATA_FILE, "utf8");

// Find K array in index.html by looking for the pattern
// We'll search for lines containing KBLI codes
const lines = indexContent.split("\n");
let startLine = -1;
let endLine = -1;

// Find start of K array (look for pattern like ["01111" or similar)
for (let i = 0; i < lines.length; i++) {
  if (lines[i].includes('["01111"') || lines[i].includes('[  "01111"')) {
    // Go back to find the actual const K declaration
    for (let j = i; j >= Math.max(0, i - 20); j--) {
      if (
        lines[j].includes("const K") ||
        lines[j].includes("let K") ||
        lines[j].includes("var K")
      ) {
        startLine = j;
        break;
      }
    }
    if (startLine === -1) {
      startLine = i - 1; // K array starts just before first element
    }
    break;
  }
}

// Find end of K array (look for closing ];)
if (startLine !== -1) {
  for (let i = startLine; i < lines.length; i++) {
    if (lines[i].trim() === "];" && i > startLine + 10) {
      endLine = i;
      break;
    }
  }
}

if (startLine === -1 || endLine === -1) {
  console.log("❌ ERROR: Could not find K array boundaries");
  console.log(`   Start line: ${startLine}, End line: ${endLine}`);
  console.log("\n🔍 Trying alternative approach...");

  // Alternative: Look for specific pattern
  const kPattern = /const K\s*=\s*\[[\s\S]*?\];/;
  const match = indexContent.match(kPattern);

  if (match) {
    const updatedContent = indexContent.replace(kPattern, newKArray);
    fs.writeFileSync(INDEX_FILE, updatedContent);
    console.log("✅ index.html updated successfully using regex replacement!");
    console.log(
      `📊 File size: ${(fs.statSync(INDEX_FILE).size / 1024).toFixed(2)} KB`,
    );
  } else {
    console.log("❌ ERROR: K array not found with regex either");
    process.exit(1);
  }
} else {
  console.log(`✅ Found K array: lines ${startLine} to ${endLine}`);

  // Replace the K array
  const beforeK = lines.slice(0, startLine).join("\n");
  const afterK = lines.slice(endLine + 1).join("\n");

  const updatedContent = beforeK + "\n" + newKArray + "\n" + afterK;

  // Write back
  fs.writeFileSync(INDEX_FILE, updatedContent);

  console.log("✅ index.html updated successfully!");
  console.log(
    `📊 File size: ${(fs.statSync(INDEX_FILE).size / 1024).toFixed(2)} KB`,
  );
}

console.log("\n🎉 Done! Now test the search functionality.");
console.log("   Try searching for: restaurant, software, hotel, construction");
