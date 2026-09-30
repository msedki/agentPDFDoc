/** @type {import('next').NextConfig} */
const config = {
  output: "export",
  trailingSlash: true,
  poweredByHeader: false,
  productionBrowserSourceMaps: false,
  images: { unoptimized: true },
  experimental: { cpus: 1 },
};
export default config;
