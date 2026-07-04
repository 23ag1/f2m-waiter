import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow loading dev assets / HMR when the app is opened via the host IP.
  allowedDevOrigins: ["62.238.0.62"],
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: "http://195.225.110.250:8000/api/v1/:path*",
      },
    ];
  },
};

export default nextConfig;
