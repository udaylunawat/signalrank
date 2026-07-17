import type { NextConfig } from "next";

const desktopBuild =
  process.env.SIGNALRANK_MODE === "desktop" ||
  process.env.NEXT_PUBLIC_SIGNALRANK_MODE === "desktop";

const nextConfig: NextConfig = {
  ...(desktopBuild ? { output: "standalone" as const } : {}),
};

export default nextConfig;
