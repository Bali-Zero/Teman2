import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  typescript: {
    ignoreBuildErrors: true,
  },
  basePath: "/kbli-navigator",
  experimental: {
    optimizePackageImports: ["lucide-react"],
  },
};

export default nextConfig;
