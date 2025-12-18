import js from '@eslint/js';
import tseslint from 'typescript-eslint';
import prettier from 'eslint-config-prettier';
import globals from 'globals';

export default tseslint.config(
  // Base configuration for all files
  js.configs.recommended,
  ...tseslint.configs.recommended,
  prettier,

  // Configuration for TypeScript files (backend)
  {
    files: ['**/*.ts'],
    languageOptions: {
      parser: tseslint.parser,
      parserOptions: {
        ecmaVersion: 'latest',
        sourceType: 'module',
      },
      globals: {
        ...globals.node,
      },
    },
    rules: {
      // TypeScript-specific rules can go here
    },
  },

  // Configuration for JavaScript files in mouth app (browser environment)
  {
    files: ['apps/mouth/**/*.js', 'apps/mouth/**/*.jsx'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: {
        ...globals.browser,
      },
    },
    rules: {
      'no-undef': 'error',
    },
  },

  // Configuration for test files (browser + Jest environment)
  {
    files: ['apps/mouth/**/*.test.js', 'apps/mouth/**/*.test.ts', 'apps/mouth/**/tests/**/*.js'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: {
        ...globals.browser,
        ...globals.jest,
      },
    },
    rules: {
      'no-undef': 'error',
    },
  },

  // Configuration for other JavaScript files (Node.js environment)
  {
    files: ['**/*.js'],
    ignores: ['apps/mouth/**/*.js', 'node_modules/**', 'dist/**', 'coverage/**'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: {
        ...globals.node,
      },
    },
  },

  // Ignore patterns
  {
    ignores: [
      'node_modules/**',
      'dist/**',
      'coverage/**',
      '*.config.js',
      '*.config.mjs',
      '*.config.cjs',
      'build/**',
      '.next/**',
      '.turbo/**',
    ],
  }
);
