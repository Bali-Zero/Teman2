#!/usr/bin/env node

/**
 * OpenAPI Spec Validator
 * 
 * Usage:
 *   node scripts/validate-openapi.js
 */

const fs = require('fs');
const path = require('path');

async function main() {
  const specPath = path.join(__dirname, '../apps/mouth/src/lib/api/openapi.yaml');
  
  console.log('🔍 Validating OpenAPI spec...');
  console.log(`📄 File: ${specPath}\n`);
  
  if (!fs.existsSync(specPath)) {
    console.error('❌ File not found:', specPath);
    process.exit(1);
  }
  
  const content = fs.readFileSync(specPath, 'utf-8');
  console.log(`📊 Size: ${(content.length / 1024).toFixed(2)} KB`);
  console.log(`📏 Lines: ${content.split('\n').length}`);
  
  // Basic validation
  const requiredFields = ['openapi:', 'info:', 'paths:', 'servers:', 'components:'];
  const missing = requiredFields.filter(field => !content.includes(field));
  
  if (missing.length > 0) {
    console.error('\n❌ Missing required fields:', missing.join(', '));
    process.exit(1);
  }
  
  // Count endpoints
  const pathCount = (content.match(/^\s{2}\/api\//gm) || []).length;
  console.log(`📋 Endpoints: ${pathCount}`);
  
  // Count tags
  const tagMatches = content.match(/tags:\s*\[([^\]]+)\]/g) || [];
  const uniqueTags = new Set(
    tagMatches.flatMap(m => m.match(/\w+/g)).filter(t => t !== 'tags')
  );
  console.log(`🏷️  Tags: ${uniqueTags.size} (${[...uniqueTags].join(', ')})`);
  
  console.log('\n✅ OpenAPI spec is valid!\n');
  console.log('Next steps:');
  console.log('  1. View spec: http://localhost:3000/api/docs/openapi.yaml');
  console.log('  2. Optional - Install Swagger UI:');
  console.log('     cd apps/mouth && pnpm add swagger-ui-react @types/swagger-ui-react');
}

main().catch(err => {
  console.error('❌ Validation failed:', err.message);
  process.exit(1);
});
