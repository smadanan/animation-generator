
/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    const configured =
      process.env.BACKEND_URL ||
      'https://chai-animation-api.onrender.com';

    const backend =
      configured.startsWith('http://') ||
      configured.startsWith('https://')
        ? configured
        : `https://${configured}`;

    return [
      {
        source: '/backend/:path*',
        destination: `${backend}/:path*`,
      },
    ];
  },
};

export default nextConfig;
