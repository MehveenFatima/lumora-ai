'use client'

import { useEffect } from 'react'
import Link from 'next/link'
import { AlertTriangle, RotateCcw } from 'lucide-react'

/** Shown when a page fails to render; the rest of the app keeps working. */
export default function Error({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error('Page error:', error)
  }, [error])

  return (
    <main className="flex min-h-[70dvh] items-center justify-center bg-background px-4">
      <div className="w-full max-w-md rounded-3xl border border-border bg-card/60 p-8 text-center shadow-soft">
        <span className="mx-auto flex size-12 items-center justify-center rounded-2xl bg-warning/15 text-warning">
          <AlertTriangle className="size-6" />
        </span>
        <h1 className="mt-5 font-display text-xl font-semibold text-foreground">Something went wrong on this page</h1>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          Please try again. If the server was asleep it can take up to a minute to start.
        </p>
        <div className="mt-6 flex flex-col gap-2.5 sm:flex-row sm:justify-center">
          <button
            onClick={reset}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground shadow-glow transition-opacity hover:opacity-90"
          >
            <RotateCcw className="size-4" />
            Try again
          </button>
          <Link
            href="/dashboard"
            className="inline-flex items-center justify-center rounded-xl border border-border bg-card px-5 py-2.5 text-sm font-medium text-foreground transition-colors hover:bg-accent/40"
          >
            Go to my workspaces
          </Link>
        </div>
        {error.digest && <p className="mt-4 text-[11px] text-muted-foreground">Reference: {error.digest}</p>}
      </div>
    </main>
  )
}
