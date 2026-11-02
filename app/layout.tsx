import { Analytics } from '@vercel/analytics/next'
import type { Metadata, Viewport } from 'next'
import { Inter, Space_Grotesk } from 'next/font/google'
import { ThemeProvider } from '@/lib/theme-provider'
import './globals.css'

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
})

const spaceGrotesk = Space_Grotesk({
  subsets: ['latin'],
  variable: '--font-space-grotesk',
  display: 'swap',
})

const siteUrl =
  process.env.NEXT_PUBLIC_SITE_URL ||
  (process.env.VERCEL_PROJECT_PRODUCTION_URL ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}` : 'http://localhost:3000')
const description =
  'LumoraAI is a RAG-based adaptive learning and knowledge-gap prediction platform. Build workspace knowledge bases, converse with AI tutors grounded in your sources, test mastery with adaptive quizzes, and follow self-adapting roadmaps.'

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: 'LumoraAI — Adaptive Learning, Reimagined',
  description,
  generator: 'LumoraAI',
  applicationName: 'LumoraAI',
  // Link previews on WhatsApp, LinkedIn, Slack and X (image from app/opengraph-image.tsx)
  openGraph: {
    type: 'website',
    siteName: 'LumoraAI',
    title: 'LumoraAI — Adaptive Learning, Reimagined',
    description:
      'Upload your notes and get an AI tutor grounded in them, adaptive quizzes, flashcards and a study plan built from your knowledge gaps.',
    url: '/',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'LumoraAI — Adaptive Learning, Reimagined',
    description: 'An AI tutor, adaptive quizzes and flashcards built from your own notes.',
  },
}

export const viewport: Viewport = {
  colorScheme: 'dark light',
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#F7F8FA' },
    { media: '(prefers-color-scheme: dark)', color: '#080B12' },
  ],
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" className={`dark ${inter.variable} ${spaceGrotesk.variable}`} suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              try {
                const stored = localStorage.getItem('lumora_theme_preference');
                const dark = stored === 'dark' || (!stored && window.matchMedia('(prefers-color-scheme: dark)').matches) || stored === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches;
                if (stored === 'light' || (!dark && stored !== 'dark')) {
                  document.documentElement.classList.remove('dark');
                  document.documentElement.classList.add('light');
                } else {
                  document.documentElement.classList.add('dark');
                }
              } catch (e) {}
            `,
          }}
        />
      </head>
      <body className="font-sans antialiased bg-background text-foreground min-h-dvh selection:bg-primary/20 selection:text-primary">
        <ThemeProvider>
          {children}
        </ThemeProvider>
        {process.env.NODE_ENV === 'production' && <Analytics />}
      </body>
    </html>
  )
}

