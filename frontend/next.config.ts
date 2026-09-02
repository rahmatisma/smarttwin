import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Dev server RunPod diakses lewat domain proxy publik (bukan localhost),
  // jadi Next.js menganggapnya cross-origin dan memblokir HMR/chunk JS
  // secara default. Wildcard *.proxy.runpod.net supaya tetap jalan walau
  // pod di-redeploy dan ID pod-nya berubah. HANYA untuk `next dev` --
  // build production (`next build`/`next start`) tidak terpengaruh.
  allowedDevOrigins: ["*.proxy.runpod.net"],
};

export default nextConfig;
