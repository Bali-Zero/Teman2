#!/usr/bin/env node

const fs = require("fs");
const path = require("path");

const htmlPath = path.join(__dirname, "index.html");
let htmlContent = fs.readFileSync(htmlPath, "utf8");

// Find all occurrences of "const K = ["
const regex = /const K = \[/g;
const matches = [];
let match;
while ((match = regex.exec(htmlContent)) !== null) {
  matches.push(match.index);
}

if (matches.length === 2) {
  // Replace only the SECOND occurrence (the inlined bilingual data) with "K = ["
  const before = htmlContent.substring(0, matches[1]);
  const after = htmlContent.substring(matches[1]);
  const updatedAfter = after.replace(/^const K = \[/, "K = [");
  htmlContent = before + updatedAfter;

  fs.writeFileSync(htmlPath, htmlContent, "utf8");
} else {
}
