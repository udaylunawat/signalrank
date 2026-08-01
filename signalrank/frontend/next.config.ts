import type { NextConfig } from "next";

const desktopBuild =
  process.env.SIGNALRANK_MODE === "desktop" ||
  process.env.NEXT_PUBLIC_SIGNALRANK_MODE === "desktop";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["127.0.0.1"],
  ...(desktopBuild ? { output: "standalone" as const } : {}),
};

export default nextConfig;
