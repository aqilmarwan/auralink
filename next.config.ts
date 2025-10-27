import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  output: 'export',
  images: {
    unoptimized: true,
  },
  // Environment variables for gRPC
  env: {
    GRPC_ENDPOINT: 'localhost:50051',
  },
  // Transpile Tauri API
  transpilePackages: ['@tauri-apps/api'],
  // Webpack configuration for Tauri
  webpack: (config, { isServer }) => {
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
};

export default nextConfig;