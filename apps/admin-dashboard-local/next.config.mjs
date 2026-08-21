/** @type {import('next').NextConfig} */

// LOCAL_ONLY guard: refuse to start unless explicitly invoked as the local
// Pro dev tool. Prevents accidental Vercel/Fly deployment.
if (process.env.LOCAL_ONLY !== "1") {
  throw new Error(
    "admin-dashboard-local is a Pro-only dev tool. Set LOCAL_ONLY=1 to run " +
      "(use scripts/start-cockpit.sh).",
  );
}

const nextConfig = {
  reactStrictMode: true,
  async headers() {
    const privateHeaders = [
      { key: "Cache-Control", value: "no-store, max-age=0" },
      { key: "X-Robots-Tag", value: "noindex, nofollow, noarchive" },
      { key: "Referrer-Policy", value: "no-referrer" },
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "X-Frame-Options", value: "DENY" },
    ];
    return [
      { source: "/garuda-voa", headers: privateHeaders },
      { source: "/garuda-voa/:path*", headers: privateHeaders },
      { source: "/api/garuda-voa/:path*", headers: privateHeaders },
    ];
  },
  // `output: "standalone"` was removed: this app only runs locally through
  // scripts/start-cockpit.sh. Standalone is for minimal Docker images, which
  // this loopback-only operator tool does not need.
};

export default nextConfig;
