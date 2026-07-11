/** @type {import('next').NextConfig} */
const backendOrigin = (process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:5001').replace(/\/$/, '');

const nextConfig = {
  turbopack: {
    root: process.cwd(),
  },
  reactStrictMode: true,
  allowedDevOrigins: ['127.0.2.2', '127.0.0.1', '0.0.0.0', '192.168.178.50', '192.168.178.52', 'localhost'],
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${backendOrigin}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
