/** @type {import('next').NextConfig} */
const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  'http://localhost:8000';

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return {
      beforeFiles: [
        { source: '/api/:path*', destination: `${apiBaseUrl}/:path*` },
        { source: '/forge/:path*', destination: `${apiBaseUrl}/forge/:path*` },
        { source: '/observer/:path*', destination: `${apiBaseUrl}/observer/:path*` },
        { source: '/signals', destination: `${apiBaseUrl}/signals` },
        { source: '/signals/:path*', destination: `${apiBaseUrl}/signals/:path*` },
        { source: '/patterns', destination: `${apiBaseUrl}/patterns` },
        { source: '/patterns/:path*', destination: `${apiBaseUrl}/patterns/:path*` },
        { source: '/opportunities', destination: `${apiBaseUrl}/opportunities` },
        { source: '/opportunities/:path*', destination: `${apiBaseUrl}/opportunities/:path*` },
        { source: '/earn/:path*', destination: `${apiBaseUrl}/earn/:path*` },
        { source: '/orchestrate/:path*', destination: `${apiBaseUrl}/orchestrate/:path*` },
        { source: '/repair-shop/:path*', destination: `${apiBaseUrl}/repair-shop/:path*` },
        { source: '/world/:path*', destination: `${apiBaseUrl}/world/:path*` },
        { source: '/goals/:path*', destination: `${apiBaseUrl}/goals/:path*` },
        { source: '/money/:path*', destination: `${apiBaseUrl}/money/:path*` },
        { source: '/execution/:path*', destination: `${apiBaseUrl}/execution/:path*` },
      ],
    };
  },
};

module.exports = nextConfig;
