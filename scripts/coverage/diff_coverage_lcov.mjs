#!/usr/bin/env node
/**
 * Frontend Diff Coverage Calculator
 * 
 * Computes coverage percentage for only the lines changed in git diff.
 * Uses Jest LCOV coverage report format.
 * 
 * Usage:
 *     node scripts/coverage/diff_coverage_lcov.mjs [--threshold=80] [--base=main] [--lcov-file=coverage/lcov.info]
 */

import { readFileSync, existsSync } from 'fs';
import { execSync } from 'child_process';
import { fileURLToPath } from 'url';
import { dirname, resolve } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

/**
 * Get changed line numbers per file from git diff.
 * @param {string} baseBranch - Base branch for diff
 * @returns {Map<string, Set<number>>} Map of file paths to changed line numbers
 */
function getChangedLines(baseBranch = 'main') {
    const changedLines = new Map();
    
    let diffOutput = '';
    try {
        // Try remote branch first
        diffOutput = execSync(
            `git diff origin/${baseBranch}...HEAD --unified=0`,
            { encoding: 'utf-8', stdio: 'pipe' }
        );
    } catch (e) {
        // Fallback to local branch
        try {
            diffOutput = execSync(
                `git diff ${baseBranch} --unified=0`,
                { encoding: 'utf-8', stdio: 'pipe' }
            );
        } catch (e2) {
            // Fallback to staged changes
            try {
                diffOutput = execSync(
                    'git diff --cached --unified=0',
                    { encoding: 'utf-8', stdio: 'pipe' }
                );
            } catch (e3) {
                console.error('❌ Error: No git diff available. Are you in a git repository?');
                return changedLines;
            }
        }
    }
    
    let currentFile = null;
    const lines = diffOutput.split('\n');
    
    for (const line of lines) {
        // Look for file header: @@ -start,count +start,count @@
        if (line.startsWith('@@') && line.includes('@@', 2)) {
            const parts = line.split('@@');
            if (parts.length >= 2) {
                const hunkInfo = parts[1].trim();
                // Parse +new_start,new_count
                const newPartMatch = hunkInfo.match(/\+(\d+)(?:,(\d+))?/);
                if (newPartMatch) {
                    const start = parseInt(newPartMatch[1], 10);
                    const count = parseInt(newPartMatch[2] || '1', 10);
                    // Add all lines in this hunk
                    if (currentFile) {
                        if (!changedLines.has(currentFile)) {
                            changedLines.set(currentFile, new Set());
                        }
                        for (let lineNum = start; lineNum < start + count; lineNum++) {
                            changedLines.get(currentFile).add(lineNum);
                        }
                    }
                }
            }
        }
        // Look for file path: +++ b/path
        else if (line.startsWith('+++ b/')) {
            let filePath = line.substring(6); // Remove "+++ b/"
            // Normalize path (remove apps/mouth/ prefix if present)
            if (filePath.startsWith('apps/mouth/')) {
                filePath = filePath.substring('apps/mouth/'.length);
            }
            // Only track TypeScript/JavaScript files
            if ((filePath.endsWith('.ts') || filePath.endsWith('.tsx') || filePath.endsWith('.js') || filePath.endsWith('.jsx')) 
                && !filePath.includes('/test') 
                && !filePath.includes('/__tests__')
                && !filePath.endsWith('.test.ts')
                && !filePath.endsWith('.test.tsx')
                && !filePath.endsWith('.spec.ts')
                && !filePath.endsWith('.spec.tsx')) {
                currentFile = filePath;
                if (!changedLines.has(currentFile)) {
                    changedLines.set(currentFile, new Set());
                }
            }
        }
        else if (line.startsWith('--- a/')) {
            // Reset current file on old file header
            currentFile = null;
        }
    }
    
    return changedLines;
}

/**
 * Parse LCOV coverage file.
 * @param {string} lcovFile - Path to lcov.info file
 * @returns {Map<string, Map<number, boolean>>} Map of file paths to line coverage (line number -> covered)
 */
function parseLcov(lcovFile) {
    const coverage = new Map();
    
    if (!existsSync(lcovFile)) {
        console.error(`❌ LCOV file not found: ${lcovFile}`);
        console.error(`   Run: npm run test:coverage`);
        process.exit(1);
    }
    
    const content = readFileSync(lcovFile, 'utf-8');
    const records = content.split('end_of_record\n');
    
    let currentFile = null;
    const fileCoverage = new Map();
    
    for (const record of records) {
        const lines = record.split('\n');
        
        for (const line of lines) {
            // SF: Source file
            if (line.startsWith('SF:')) {
                if (currentFile && fileCoverage.size > 0) {
                    coverage.set(currentFile, new Map(fileCoverage));
                }
                currentFile = line.substring(3).trim();
                // Normalize path
                if (currentFile.includes('apps/mouth/')) {
                    currentFile = currentFile.substring(currentFile.indexOf('apps/mouth/') + 'apps/mouth/'.length);
                }
                fileCoverage.clear();
            }
            // DA: Line data (line_number,execution_count)
            else if (line.startsWith('DA:')) {
                const match = line.match(/DA:(\d+),(\d+)/);
                if (match) {
                    const lineNum = parseInt(match[1], 10);
                    const execCount = parseInt(match[2], 10);
                    fileCoverage.set(lineNum, execCount > 0);
                }
            }
        }
    }
    
    // Don't forget the last file
    if (currentFile && fileCoverage.size > 0) {
        coverage.set(currentFile, new Map(fileCoverage));
    }
    
    return coverage;
}

/**
 * Calculate diff coverage percentage.
 * @param {Map<string, Set<number>>} changedLines - Changed lines per file
 * @param {Map<string, Map<number, boolean>>} lcovCoverage - LCOV coverage data
 * @returns {{coverage: number, details: Object}}
 */
function calculateDiffCoverage(changedLines, lcovCoverage) {
    let totalChanged = 0;
    let totalCovered = 0;
    const fileDetails = {};
    
    for (const [filePath, changedLineNums] of changedLines.entries()) {
        if (changedLineNums.size === 0) {
            continue;
        }
        
        // Find matching coverage entry
        let fileCoverage = null;
        for (const [covPath, covData] of lcovCoverage.entries()) {
            // Match by filename (handle different path prefixes)
            if (covPath.endsWith(filePath) || filePath.endsWith(covPath) || covPath === filePath) {
                fileCoverage = covData;
                break;
            }
        }
        
        if (!fileCoverage) {
            // File not in coverage (new file, not tested)
            fileDetails[filePath] = {
                changedLines: changedLineNums.size,
                coveredLines: 0,
                coverage: 0.0,
                missingLines: Array.from(changedLineNums).sort((a, b) => a - b)
            };
            totalChanged += changedLineNums.size;
            continue;
        }
        
        // Count coverage for changed lines only
        let fileCovered = 0;
        const missingLines = [];
        
        for (const lineNum of changedLineNums) {
            if (fileCoverage.get(lineNum) === true) {
                fileCovered++;
            } else {
                missingLines.push(lineNum);
            }
        }
        
        const fileChanged = changedLineNums.size;
        totalChanged += fileChanged;
        totalCovered += fileCovered;
        
        fileDetails[filePath] = {
            changedLines: fileChanged,
            coveredLines: fileCovered,
            coverage: fileChanged > 0 ? (fileCovered / fileChanged * 100) : 100.0,
            missingLines: missingLines.sort((a, b) => a - b)
        };
    }
    
    const diffCoverage = totalChanged > 0 ? (totalCovered / totalChanged * 100) : 100.0;
    
    return { coverage: diffCoverage, details: fileDetails };
}

/**
 * Print formatted coverage report.
 */
function printReport(diffCoverage, fileDetails, threshold) {
    console.log('\n' + '='.repeat(80));
    console.log('FRONTEND DIFF COVERAGE REPORT');
    console.log('='.repeat(80));
    console.log(`\nDiff Coverage: ${diffCoverage.toFixed(2)}%`);
    console.log(`Threshold: ${threshold.toFixed(1)}%`);
    
    if (diffCoverage >= threshold) {
        console.log('✅ PASSED');
    } else {
        console.log(`❌ FAILED (below threshold by ${(threshold - diffCoverage).toFixed(2)}%)`);
    }
    
    if (Object.keys(fileDetails).length > 0) {
        console.log('\nFile Details:');
        console.log('-'.repeat(80));
        const sortedFiles = Object.entries(fileDetails)
            .sort((a, b) => a[1].coverage - b[1].coverage);
        
        for (const [filePath, details] of sortedFiles) {
            const status = details.coverage >= threshold ? '✅' : '❌';
            console.log(
                `${status} ${details.coverage.toFixed(1).padStart(5)}% | ` +
                `${details.coveredLines.toString().padStart(3)}/${details.changedLines.toString().padStart(3)} lines | ` +
                `${filePath}`
            );
            if (details.missingLines.length > 0) {
                const missingPreview = details.missingLines.slice(0, 5);
                let missingStr = missingPreview.join(', ');
                if (details.missingLines.length > 5) {
                    missingStr += ` ... (+${details.missingLines.length - 5} more)`;
                }
                console.log(`      Missing lines: ${missingStr}`);
            }
        }
    }
    
    console.log('='.repeat(80) + '\n');
}

function main() {
    const args = process.argv.slice(2);
    let threshold = 80.0;
    let baseBranch = 'main';
    let lcovFile = 'coverage/lcov.info';
    let generateCoverage = false;
    
    // Parse arguments
    for (const arg of args) {
        if (arg.startsWith('--threshold=')) {
            threshold = parseFloat(arg.substring('--threshold='.length));
        } else if (arg.startsWith('--base=')) {
            baseBranch = arg.substring('--base='.length);
        } else if (arg.startsWith('--lcov-file=')) {
            lcovFile = arg.substring('--lcov-file='.length);
        } else if (arg === '--generate-coverage') {
            generateCoverage = true;
        }
    }
    
    // Generate coverage if requested or missing
    if (generateCoverage || !existsSync(lcovFile)) {
        console.log('📊 Generating coverage report...');
        try {
            execSync('npm run test:coverage', { 
                stdio: 'inherit',
                cwd: resolve(__dirname, '../..')
            });
        } catch (e) {
            console.error('⚠️  Warning: Coverage generation had failures, but continuing...');
            if (!existsSync(lcovFile)) {
                console.error('❌ Failed to generate coverage file');
                process.exit(1);
            }
        }
    }
    
    // Get changed lines
    console.log('🔍 Analyzing git diff...');
    const changedLines = getChangedLines(baseBranch);
    
    if (changedLines.size === 0) {
        console.log('ℹ️  No changed TypeScript/JavaScript files found in diff.');
        console.log('   This might mean:');
        console.log('   - No changes compared to base branch');
        console.log('   - Only test files were changed');
        console.log('   - Only non-source files were changed');
        console.log('\n✅ Diff coverage check passed (no production code changes)');
        process.exit(0);
    }
    
    // Load coverage data
    console.log(`📖 Loading coverage data from ${lcovFile}...`);
    const lcovCoverage = parseLcov(lcovFile);
    
    // Calculate diff coverage
    console.log('🧮 Calculating diff coverage...');
    const { coverage: diffCoverage, details: fileDetails } = calculateDiffCoverage(changedLines, lcovCoverage);
    
    // Print report
    printReport(diffCoverage, fileDetails, threshold);
    
    // Exit with appropriate code
    process.exit(diffCoverage >= threshold ? 0 : 1);
}

main();

