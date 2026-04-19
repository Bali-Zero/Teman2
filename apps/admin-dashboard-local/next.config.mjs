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
  output: "standalone",
};

export default nextConfig;
