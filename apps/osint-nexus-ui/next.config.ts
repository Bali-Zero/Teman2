import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  reactStrictMode: true,
  typescript: { ignoreBuildErrors: false },
  poweredByHeader: false,
  experimental: {
    turbo: {
      root: __dirname,
    },
  },
};

export default nextConfig;
