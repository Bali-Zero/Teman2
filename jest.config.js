/**
 * Jest configuration for ES Modules support
 *
 * The repository uses "type": "module" in package.json, so we need to
 * configure Jest to handle ES modules correctly.
 *
 * Run Jest with: node --experimental-vm-modules node_modules/jest/bin/jest.js
 * Or update package.json test script to use NODE_OPTIONS
 */

export default {
  preset: 'ts-jest/presets/default-esm',
  extensionsToTreatAsEsm: ['.ts'],
  testEnvironment: 'node',
  moduleNameMapper: {
    '^(\\.{1,2}/.*)\\.js$': '$1',
  },
  transform: {
    '^.+\\.ts$': [
      'ts-jest',
      {
        useESM: true,
      },
    ],
  },
  moduleFileExtensions: ['ts', 'js', 'json'],
  testMatch: ['**/__tests__/**/*.ts', '**/?(*.)+(spec|test).ts', '**/?(*.)+(spec|test).js'],
  collectCoverageFrom: [
    'apps/**/*.{ts,js}',
    '!apps/**/*.d.ts',
    '!apps/**/node_modules/**',
    '!apps/**/dist/**',
    '!apps/**/build/**',
  ],
  // Run tests with ES modules support
  testEnvironmentOptions: {
    customExportConditions: [''],
  },
};
