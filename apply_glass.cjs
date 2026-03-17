const fs = require('fs');
const path = require('path');

function walkDir(dir, callback) {
  fs.readdirSync(dir).forEach(f => {
    let dirPath = path.join(dir, f);
    let isDirectory = fs.statSync(dirPath).isDirectory();
    isDirectory ? 
      walkDir(dirPath, callback) : callback(path.join(dir, f));
  });
}

const targets = [
  '/Users/nuzantara/Desktop/nuzantara/apps/mouth/src/app/(workspace)',
  '/Users/nuzantara/Desktop/nuzantara/apps/mouth/src/components/workspace',
  '/Users/nuzantara/Desktop/nuzantara/apps/mouth/src/components/dashboard'
];

let filesChanged = 0;

targets.forEach(target => {
  if (!fs.existsSync(target)) return;
  walkDir(target, function(filePath) {
    if (filePath.endsWith('.tsx') || filePath.endsWith('.ts')) {
      let content = fs.readFileSync(filePath, 'utf8');
      
      let newContent = content
        // Replace base background classes with glass-base
        .replace(/bg-\[var\(--background-elevated\)\]/g, 'glass-base')
        .replace(/bg-\[var\(--background-secondary\)\]/g, 'glass-base')
        .replace(/bg-\[#2a2a2a\]/g, 'glass-base')
        // Clean up redundant solid borders next to glass-base
        .replace(/border-\[var\(--border\)\] glass-base/g, 'glass-base')
        .replace(/glass-base border-\[var\(--border\)\]/g, 'glass-base')
        .replace(/border border-\[var\(--border\)\] glass-base/g, 'glass-base')
        .replace(/glass-base border border-\[var\(--border\)\]/g, 'glass-base')
        // General text color replacements for better contrast on glass
        .replace(/text-\[var\(--foreground-muted\)\]/g, 'text-white/60')
        .replace(/text-\[var\(--foreground\)\]/g, 'text-white');

      if (content !== newContent) {
        fs.writeFileSync(filePath, newContent, 'utf8');
        console.log('Updated:', filePath);
        filesChanged++;
      }
    }
  });
});

console.log(`\nFinished! Changed ${filesChanged} files.`);
