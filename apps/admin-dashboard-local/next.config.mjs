/** @type {import('next').NextConfig} */

// LOCAL_ONLY guard: refuse to start unless explicitly invoked as the local
// Pro dev tool. Prevents accidental Vercel/Fly deployment.
if (process.env.LOCAL_ONLY !== "1") {
  throw new Error(
    "admin-dashboard-local is a Pro-only dev tool. Set LOCAL_ONLY=1 to run " +
      "(use scripts/start-cost-dashboard.sh).",
  );
}

const nextConfig = {
  reactStrictMode: true,
  // `output: "standalone"` was removed: this app only runs locally via
  // `next start -p 3100` (see scripts/start-cost-dashboard.sh). Standalone
  // is for minimal Docker images, which we explicitly don't need — and it
  // triggers a runtime warning ("next start does not work with output:
  // standalone configuration").
};

export default nextConfig;
