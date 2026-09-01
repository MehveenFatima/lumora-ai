import { BrainCircuit, Database, Network, ScanText, Waypoints, Gauge } from 'lucide-react'
import { Badge } from '@/components/ui/badge'

const tech = [
  {
    icon: BrainCircuit,
    title: 'Large Language Models',
    desc: 'Frontier reasoning models generate explanations, quizzes, and summaries tuned to your level.',
  },
  {
    icon: Database,
    title: 'Vector embeddings',
    desc: 'Your documents are embedded into a semantic index for fast, meaning-aware retrieval.',
  },
  {
    icon: Network,
    title: 'Retrieval-augmented generation',
    desc: 'Answers are grounded in your sources with citations — reducing hallucination.',
  },
  {
    icon: ScanText,
    title: 'Document understanding',
    desc: 'OCR and layout parsing extract structure from PDFs, slides, and handwritten notes.',
  },
  {
    icon: Waypoints,
    title: 'Adaptive algorithms',
    desc: 'Spaced repetition and item-response theory decide what to show you, and when.',
  },
  {
    icon: Gauge,
    title: 'Mastery modeling',
    desc: 'A live knowledge model estimates retention per concept to guide every session.',
  },
]

export function Technology() {
  return (
    <section
      id="technology"
      className="relative scroll-mt-20 border-y border-border bg-card/30"
    >
      <div className="mx-auto w-full max-w-[1200px] px-4 py-16 md:px-6 md:py-24">
        <div className="mx-auto max-w-2xl text-center">
          <Badge variant="default" size="md">
            AI technology
          </Badge>
          <h2 className="mt-4 text-balance font-display text-3xl font-semibold tracking-tight text-foreground md:text-4xl">
            Serious AI under a calm surface
          </h2>
          <p className="mt-4 text-pretty text-base leading-relaxed text-muted-foreground">
            The complexity stays behind the scenes. You just get answers that are fast,
            accurate, and grounded in your own material.
          </p>
        </div>

        <div className="mt-14 grid gap-px overflow-hidden rounded-2xl border border-border bg-border sm:grid-cols-2 lg:grid-cols-3">
          {tech.map((t) => (
            <div key={t.title} className="flex flex-col bg-card p-6 transition-colors hover:bg-accent/20">
              <span className="flex size-10 items-center justify-center rounded-lg bg-accent text-accent-foreground">
                <t.icon className="size-5" strokeWidth={2} />
              </span>
              <h3 className="mt-4 font-display text-[15px] font-semibold text-foreground">
                {t.title}
              </h3>
              <p className="mt-1.5 text-[13px] leading-relaxed text-muted-foreground">{t.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
