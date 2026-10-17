/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    const configured = process.env.BACKEND_URL || 'http://localhost:8080';
    const backend = configured.startsWith('http://') || configured.startsWith('https://')
      ? configured
      : `https://${configured}`;
    return [{ source: '/backend/:path*', destination: `${backend}/:path*` }];
  },
};
export default nextConfig;
