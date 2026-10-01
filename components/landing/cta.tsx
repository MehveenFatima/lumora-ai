import Link from 'next/link'
import { ArrowRight, Sparkles } from 'lucide-react'

export function CTA() {
  return (
    <section className="mx-auto w-full max-w-[1200px] px-4 py-16 md:px-6 md:py-24">
      <div className="relative overflow-hidden rounded-3xl border border-border bg-card px-6 py-14 text-center shadow-card md:px-12 md:py-20">
        {/* ambient glow */}
        <div
          className="pointer-events-none absolute inset-0 -z-0 opacity-80"
          style={{
            background:
              'radial-gradient(50% 80% at 50% 0%, oklch(0.64 0.19 264 / 0.22) 0%, transparent 70%)',
          }}
          aria-hidden
        />
        <div className="relative z-10 mx-auto max-w-2xl">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-background/60 px-3 py-1 text-[12px] font-medium text-muted-foreground backdrop-blur">
            <Sparkles className="size-3.5 text-primary" />
            Built on your own study material
          </span>
          <h2 className="mt-6 text-balance font-display text-3xl font-semibold tracking-tight text-foreground md:text-5xl">
            Your smartest study session starts now
          </h2>
          <p className="mt-4 text-pretty text-base leading-relaxed text-muted-foreground md:text-lg">
            Create a workspace, upload your notes, and let LumoraAI explain them with citations,
            quiz you adaptively, and track your mastery concept by concept.
          </p>
          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link
              href="/dashboard"
              className="inline-flex items-center gap-2 rounded-xl bg-primary px-6 py-3 text-sm font-semibold text-primary-foreground shadow-[var(--shadow-glow)] transition-opacity hover:opacity-90"
            >
              Open the dashboard
              <ArrowRight className="size-4" />
            </Link>
            <Link
              href="#learning-loop"
              className="inline-flex items-center gap-2 rounded-xl border border-border bg-background/50 px-6 py-3 text-sm font-semibold text-foreground backdrop-blur transition-colors hover:bg-accent/50"
            >
              See how it works
            </Link>
          </div>
        </div>
      </div>
    </section>
  )
}
