import nextCoreWebVitals from 'eslint-config-next/core-web-vitals';

/** @type {import("eslint").Linter.Config[]} */
const config = [
  {
    ignores: [
      'node_modules/',
      '.next/',
      'out/',
      'scripts/',
      'e2e/',
      'src/test/',
      'src/**/*.test.{ts,tsx}',
      'src/**/__tests__/',
      'src/lib/api/schema.d.ts',
      'src/app/**/*.backup.{ts,tsx}',
      'src/app/**/*.v1-backup.{ts,tsx}',
      'src/app/**/*.editorial-backup.{ts,tsx}',
    ],
  },
  ...nextCoreWebVitals,
  {
    rules: {
      '@next/next/no-html-link-for-pages': 'warn',
      'react/no-unescaped-entities': 'warn',
      'react/display-name': 'warn',
      'react/no-children-prop': 'warn',
      'react-hooks/immutability': 'off',
      'react-hooks/incompatible-library': 'off',
      'react-hooks/purity': 'off',
      'react-hooks/refs': 'off',
      'react-hooks/set-state-in-effect': 'off',
      'react-hooks/static-components': 'off',
      'react-hooks/use-memo': 'off',
    },
  },
];

export default config;
