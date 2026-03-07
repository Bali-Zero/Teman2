import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Rewrite /api/* to the backend on Fly.io
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.BACKEND_URL || "https://nuzantara-rag.fly.dev"}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
