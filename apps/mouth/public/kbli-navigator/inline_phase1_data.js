#!/usr/bin/env node

const fs = require("fs");
const path = require("path");

// Read index.html
const htmlPath = path.join(__dirname, "index.html");
const htmlContent = fs.readFileSync(htmlPath, "utf8");

// Read bilingual data
const dataPath = path.join(__dirname, "kbli_data_with_english.js");
const dataContent = fs.readFileSync(dataPath, "utf8");

// Create backup
const backupPath =
  htmlPath +
  `.backup_before_inline_${new Date().toISOString().replace(/[:.]/g, "-")}`;
fs.writeFileSync(backupPath, htmlContent, "utf8");

// Replace the script src tag with inline content
const updatedHtml = htmlContent.replace(
  /<script src="kbli_data_with_english\.js"><\/script>/,
  `<script>\n${dataContent}\n</script>`,
);

// Write updated HTML
fs.writeFileSync(htmlPath, updatedHtml, "utf8");
