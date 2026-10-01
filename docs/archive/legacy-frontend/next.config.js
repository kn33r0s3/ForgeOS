/** @type {import('next').NextConfig} */
const path = require('path');

const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  '';

const nextConfig = {
  reactStrictMode: true,
  distDir: process.env.FORGE_NEXT_DIST_DIR || '.next',
  // The repo root also has a lockfile. Pin tracing to this app so Next
  // does not treat the parent TanStack project as the workspace root.
  outputFileTracingRoot: path.join(__dirname),
  async rewrites() {
    // Same-origin /api is the public FastAPI service. A localhost
    // destination is a private host, and Vercel rejects it.
    if (!apiBaseUrl) return [];
    return [
      { source: '/api/:path*', destination: `${apiBaseUrl}/:path*` },
    ];
  },
};

module.exports = nextConfig;
