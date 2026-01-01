// eslint.config.mjs
import js from '@eslint/js';
import tseslint from 'typescript-eslint';
import globals from 'globals';

export default tseslint.config(
  {
    ignores: [
      '**/node_modules/**',
      '**/.next/**',
      '**/dist/**',
      '**/build/**',
      '**/coverage*/**',
      '**/htmlcov*/**',
      '**/coverage_html_client_scoring/**',
      '**/htmlcov_memory_vector/**',
      '**/coverage_report/**',
      '**/out/**'
    ]
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.node,
        ...globals.es2021
      }
    },
    // Mock Next.js & React Hooks rules to prevent 'Definition not found' errors
    plugins: {
      '@next/next': {
        rules: {
          'no-img-element': {}
        }
      },
      'react-hooks': {
        rules: {
          'rules-of-hooks': {},
          'exhaustive-deps': {}
        }
      }
    },
    rules: {
      '@typescript-eslint/no-explicit-any': 'warn',
      '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
      'no-console': ['warn', { allow: ['warn', 'error', 'info'] }],
      'no-constant-binary-expression': 'error'
    }
  }
);
