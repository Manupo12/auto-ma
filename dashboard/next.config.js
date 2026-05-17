/** @type {import('next').NextConfig} */
const nextConfig = {
  // Conectar con el backend FastAPI en puerto 8000.
  // Next.js route handlers (app/api/**) take priority over rewrites,
  // so /api/chat and /api/upload-audio still use their file-based routes.
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/api/:path*',
      },
    ];
  },
};

module.exports = nextConfig;
