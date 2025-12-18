/* eslint-disable no-undef, @typescript-eslint/no-require-imports */
const fs = require('fs');
const path = require('path');

const outputFile = 'FULL_CODEBASE_CONTEXT.md';
const fileList = fs.readFileSync('files_to_include.txt', 'utf8').split('\n').filter(Boolean);

let output = '# ZANTARA FULL CODEBASE CONTEXT\n\n';
output += '> Auto-generated codebase digest for AI analysis.\n\n';

// Add Architecture doc first if exists
if (fs.existsSync('ARCHITECTURE.md')) {
    output += '## ARCHITECTURE.md\n```markdown\n' + fs.readFileSync('ARCHITECTURE.md', 'utf8') + '\n```\n\n';
}

fileList.forEach(filePath => {
    try {
        // Skip very large files (> 100KB) to save tokens
        const stats = fs.statSync(filePath);
        if (stats.size > 100 * 1024) {
            console.log(`Skipping large file: ${filePath} (${Math.round(stats.size/1024)}KB)`);
            output += `### File: ${filePath} (SKIPPED - TOO LARGE)\n\n`;
            return;
        }

        const content = fs.readFileSync(filePath, 'utf8');
        const ext = path.extname(filePath).substring(1);

        output += `### File: ${filePath}\n`;
        output += '```' + ext + '\n';
        output += content;
        output += '\n```\n\n';
    } catch (e) {
        console.error(`Error reading ${filePath}: ${e.message}`);
    }
});

fs.writeFileSync(outputFile, output);
console.log(`Successfully created ${outputFile}`);
