import Link from 'next/link'
import { GraduationCap, ArrowLeft } from 'lucide-react'

export const metadata = { title: 'Page not found — LumoraAI' }

export default function NotFound() {
  return (
    <main className="flex min-h-dvh items-center justify-center bg-background px-4">
      <div className="w-full max-w-md rounded-3xl border border-border bg-card/60 p-8 text-center shadow-soft">
        <span className="mx-auto flex size-12 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-glow">
          <GraduationCap className="size-6" strokeWidth={2.25} />
        </span>
        <p className="mt-5 text-xs font-semibold uppercase tracking-wider text-primary">Error 404</p>
        <h1 className="mt-1 font-display text-2xl font-semibold text-foreground">This page doesn&apos;t exist</h1>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          The link may be broken, or the page may have been moved. Your workspaces and progress are safe.
        </p>
        <div className="mt-6 flex flex-col gap-2.5 sm:flex-row sm:justify-center">
          <Link
            href="/dashboard"
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground shadow-glow transition-opacity hover:opacity-90"
          >
            Go to my workspaces
          </Link>
          <Link
            href="/"
            className="inline-flex items-center justify-center gap-2 rounded-xl border border-border bg-card px-5 py-2.5 text-sm font-medium text-foreground transition-colors hover:bg-accent/40"
          >
            <ArrowLeft className="size-4" />
            Home
          </Link>
        </div>
      </div>
    </main>
  )
}
