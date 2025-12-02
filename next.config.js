// Converted to JS module format supported by Next 16
/** @type {import('next').NextConfig} */
const nextConfig = {
  // No auth redirects in local mode
  images: {
    domains: ['lh3.googleusercontent.com'],
  },
  // Environment variables for gRPC
  env: {
    GRPC_ENDPOINT: 'localhost:50051',
  },
  // Transpile Tauri API
  transpilePackages: ['@tauri-apps/api'],
  // Webpack configuration for Tauri
  webpack: (config, { isServer }) => {
    // requested aliases
    config.resolve.alias = {
      ...(config.resolve.alias || {}),
      canvas: false,
      encoding: false,
    };
    if (!isServer) {
      config.resolve.fallback = {
        ...config.resolve.fallback,
        fs: false,
        net: false,
        tls: false,
      };
    }
    return config;
  },
  turbopack: {
    root: "./", 
  },
};

module.exports = nextConfig;

