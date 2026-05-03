import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  reactStrictMode: true,
  typescript: { ignoreBuildErrors: false },
  poweredByHeader: false,
  turbopack: {
    root: __dirname,
  },
};

export default nextConfig;
