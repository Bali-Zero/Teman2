import nextCoreWebVitals from 'eslint-config-next/core-web-vitals';

/** @type {import("eslint").Linter.Config[]} */
const config = [
  ...nextCoreWebVitals,
  {
    ignores: ['node_modules/', '.next/', 'out/', 'scripts/'],
  },
];

export default config;
