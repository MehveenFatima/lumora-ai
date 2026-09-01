import {
  MessagesSquare,
  Layers,
  Target,
  Map,
  BarChart3,
  FolderKanban,
  ArrowUpRight,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'

const features = [
  {
    icon: MessagesSquare,
    title: 'Chat with your documents',
    desc: 'Upload PDFs, notes, and papers. Ask anything and get grounded answers with citations powered by retrieval-augmented generation.',
    tag: 'RAG',
  },
  {
    icon: Layers,
    title: 'Auto-generated flashcards',
    desc: 'LumoraAI extracts key concepts and builds spaced-repetition decks tuned to how you actually forget.',
    tag: 'Memory',
  },
  {
    icon: Target,
    title: 'Adaptive quizzes',
    desc: 'Questions adjust in real time to your performance, targeting weak spots before they cost you.',
    tag: 'Adaptive',
  },
  {
    icon: Map,
    title: 'Personalized roadmaps',
    desc: 'Turn any goal into a step-by-step learning path with milestones the AI keeps up to date.',
    tag: 'Planning',
  },
  {
    icon: BarChart3,
    title: 'Mastery analytics',
    desc: 'Track retention, streaks, and subject-level mastery with clarity — no vanity metrics.',
    tag: 'Insight',
  },
  {
    icon: FolderKanban,
    title: 'Isolated workspaces',
    desc: 'Each subject gets its own memory and context, so answers stay relevant and focused.',
    tag: 'Focus',
  },
]

export function Features() {
  return (
    <section id="features" className="mx-auto w-full max-w-[1200px] scroll-mt-20 px-4 py-16 md:px-6 md:py-24">
      <div className="mx-auto max-w-2xl text-center">
        <Badge variant="default" size="md">
          Feature highlights
        </Badge>
        <h2 className="mt-4 text-balance font-display text-3xl font-semibold tracking-tight text-foreground md:text-4xl">
          Everything you need to actually learn it
        </h2>
        <p className="mt-4 text-pretty text-base leading-relaxed text-muted-foreground">
          One platform that reads your material, tests your understanding, and adapts to
          the way your mind works.
        </p>
      </div>

      <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {features.map((f) => (
          <article
            key={f.title}
            className="group flex flex-col rounded-2xl border border-border bg-card p-6 shadow-soft transition-all hover:-translate-y-0.5 hover:shadow-card"
          >
            <div className="flex items-start justify-between">
              <span className="flex size-11 items-center justify-center rounded-xl bg-accent text-accent-foreground">
                <f.icon className="size-5" strokeWidth={2} />
              </span>
              <Badge variant="neutral" size="sm">
                {f.tag}
              </Badge>
            </div>
            <h3 className="mt-5 flex items-center gap-1 font-display text-[17px] font-semibold text-foreground">
              {f.title}
              <ArrowUpRight className="size-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
            </h3>
            <p className="mt-2 text-[14px] leading-relaxed text-muted-foreground">{f.desc}</p>
          </article>
        ))}
      </div>
    </section>
  )
}
