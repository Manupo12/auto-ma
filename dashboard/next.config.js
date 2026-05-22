/** @type {import('next').NextConfig} */
const nextConfig = {
  transpilePackages: [
    "react-markdown",
    "remark-gfm",
    "micromark-extension-gfm",
    "mdast-util-gfm",
  ],

  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/api/:path*',
      },
    ];
  },

  experimental: {
    serverActions: {
      bodySizeLimit: '50mb',
    },
  },
};

module.exports = nextConfig;
