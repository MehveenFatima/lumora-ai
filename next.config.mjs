/** @type {import('next').NextConfig} */
const nextConfig = {
  // Self-contained server bundle for the Docker image (ignored by Vercel)
  output: 'standalone',
  images: {
    unoptimized: true,
  },
}

export default nextConfig
