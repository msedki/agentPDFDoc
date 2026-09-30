/** Export statique : FastAPI sert le répertoire out/ après le build. */
const nextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
};
export default nextConfig;
