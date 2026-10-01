import { BrainCircuit, Database, Network, ScanText, Waypoints, Gauge } from 'lucide-react'
import { Badge } from '@/components/ui/badge'

const tech = [
  {
    icon: BrainCircuit,
    title: 'Large Language Models',
    desc: 'Gemini 3.8 Flash writes explanations and questions, with automatic failover to Qwen via OpenRouter.',
  },
  {
    icon: Database,
    title: 'Vector embeddings',
    desc: 'Chunks are embedded with Gemini Embedding 001 (768 dimensions) and searched with pgvector.',
  },
  {
    icon: Network,
    title: 'Retrieval-augmented generation',
    desc: 'Hybrid keyword and vector retrieval with a relevance threshold, so answers come with page citations or not at all.',
  },
  {
    icon: ScanText,
    title: 'Document understanding',
    desc: 'PDF, DOCX, PPTX and TXT parsing that keeps page, slide, heading and table metadata on every chunk.',
  },
  {
    icon: Waypoints,
    title: 'Adaptive algorithms',
    desc: 'Score bands (80% and 60%) pick the next batch’s difficulty and concepts from a validated question bank.',
  },
  {
    icon: Gauge,
    title: 'Mastery modeling',
    desc: 'Bayesian Knowledge Tracing keeps an interpretable mastery estimate per concept, rolled up to topics.',
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
