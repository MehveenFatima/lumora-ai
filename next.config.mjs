/** @type {import('next').NextConfig} */
const nextConfig = {
  // Self-contained server bundle for the Docker image (ignored by Vercel)
  output: 'standalone',
  // The dev server only accepts its live-reload connection from allowed hosts. GitHub
  // Codespaces serves the app on *.app.github.dev, so allow it; without this the browser
  // keeps reloading the page.
  allowedDevOrigins: ['*.app.github.dev', '127.0.0.1'],
  images: {
    unoptimized: true,
  },
}

export default nextConfig
