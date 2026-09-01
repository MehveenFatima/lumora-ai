import Image from 'next/image'
import Link from 'next/link'
import { ArrowRight, Sparkles, Play, FileText, Layers, Target } from 'lucide-react'
import { Badge } from '@/components/ui/badge'

const floatingCards = [
  {
    icon: FileText,
    title: 'RAG document chat',
    sub: '84 sources indexed',
    className: 'left-3 top-16 md:-left-6 md:top-24',
  },
  {
    icon: Target,
    title: 'Mastery 76%',
    sub: '+18% this month',
    className: 'right-3 top-10 md:-right-6 md:top-16',
  },
  {
    icon: Layers,
    title: '12 flashcards due',
    sub: 'Adaptive review',
    className: 'bottom-6 left-6 md:-left-4 md:bottom-10',
  },
]

export function Hero() {
  return (
    <section className="relative overflow-hidden pt-28 md:pt-36">
      {/* ambient glow */}
      <div
        className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[600px] opacity-70"
        style={{
          background:
            'radial-gradient(60% 60% at 50% 0%, oklch(0.64 0.19 264 / 0.18) 0%, transparent 70%)',
        }}
        aria-hidden
      />
      <div
        className="pointer-events-none absolute inset-0 -z-10 opacity-[0.35]"
        style={{
          backgroundImage:
            'linear-gradient(to right, oklch(1 0 0 / 0.04) 1px, transparent 1px), linear-gradient(to bottom, oklch(1 0 0 / 0.04) 1px, transparent 1px)',
          backgroundSize: '48px 48px',
          maskImage: 'radial-gradient(70% 55% at 50% 30%, black, transparent)',
          WebkitMaskImage: 'radial-gradient(70% 55% at 50% 30%, black, transparent)',
        }}
        aria-hidden
      />

      <div className="mx-auto w-full max-w-[1200px] px-4 md:px-6">
        <div className="mx-auto flex max-w-3xl flex-col items-center text-center">
          <Badge
            variant="outline"
            size="md"
            className="gap-1.5 border-border bg-card/60 backdrop-blur"
          >
            <Sparkles className="size-3.5 text-primary" />
            Adaptive learning, powered by AI
          </Badge>

          <h1 className="mt-6 text-balance font-display text-4xl font-semibold leading-[1.05] tracking-tight text-foreground sm:text-5xl md:text-6xl lg:text-[68px]">
            Learn smarter. Adapt faster.{' '}
            <span className="text-primary">Powered by AI.</span>
          </h1>

          <p className="mt-6 max-w-2xl text-pretty text-base leading-relaxed text-muted-foreground md:text-lg">
            LumoraAI turns your documents, notes, and goals into a personalized
            learning engine — chat with your material, generate flashcards, take
            adaptive quizzes, and watch your mastery climb in real time.
          </p>

          <div className="mt-8 flex flex-col items-center gap-3 sm:flex-row">
            <Link
              href="/dashboard"
              className="inline-flex items-center gap-2 rounded-xl bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground shadow-[var(--shadow-glow)] transition-opacity hover:opacity-90"
            >
              Start learning free
              <ArrowRight className="size-4" />
            </Link>
            <button className="inline-flex items-center gap-2 rounded-xl border border-border bg-card px-5 py-3 text-sm font-semibold text-foreground shadow-soft transition-colors hover:bg-accent/50">
              <Play className="size-4 text-primary" />
              Watch demo
            </button>
          </div>

          <p className="mt-4 text-[13px] text-muted-foreground">
            No credit card required · Free forever plan
          </p>
        </div>

        {/* Product visual */}
        <div className="relative mx-auto mt-14 max-w-4xl md:mt-20">
          <div className="relative overflow-hidden rounded-3xl border border-border bg-card shadow-card">
            <div
              className="pointer-events-none absolute inset-0 z-10 rounded-3xl ring-1 ring-inset ring-primary/10"
              aria-hidden
            />
            <Image
              src="/images/hero-ai.png"
              alt="LumoraAI knowledge graph visualization showing interconnected AI-powered learning nodes"
              width={1200}
              height={750}
              priority
              className="h-auto w-full object-cover"
            />
          </div>

          {floatingCards.map((c) => (
            <div
              key={c.title}
              className={`absolute hidden items-center gap-2.5 rounded-xl border border-border bg-card/90 px-3.5 py-2.5 shadow-card backdrop-blur-md sm:flex ${c.className}`}
            >
              <span className="flex size-9 items-center justify-center rounded-lg bg-accent text-accent-foreground">
                <c.icon className="size-[18px]" strokeWidth={2} />
              </span>
              <div className="text-left">
                <p className="text-[13px] font-semibold leading-tight text-foreground">
                  {c.title}
                </p>
                <p className="text-[11px] leading-tight text-muted-foreground">{c.sub}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
