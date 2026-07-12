/** @type {import('next').NextConfig} */
const nextConfig = {
  output: process.env.NODE_ENV === 'production' ? 'export' : undefined,
  reactStrictMode: true,
  images: { unoptimized: true },
  turbopack: { root: import.meta.dirname },
};

export default nextConfig;
