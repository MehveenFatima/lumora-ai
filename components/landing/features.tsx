import {
  FolderKanban,
  MessagesSquare,
  Zap,
  Layers,
  Map,
  BarChart3,
  FileText,
  Target,
  ArrowUpRight,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'

const features = [
  {
    icon: FolderKanban,
    title: 'Isolated Learning Workspaces',
    desc: 'Each subject keeps its own documents, vector index, quiz history and mastery model, so retrieval never mixes subjects.',
    tag: 'Core Architecture',
  },
  {
    icon: MessagesSquare,
    title: 'Grounded AI Tutor',
    desc: 'Answers are generated only from passages retrieved from your uploads and cite the document and page. Off-topic questions are declined.',
    tag: 'RAG Grounding',
  },
  {
    icon: Zap,
    title: 'Adaptive Diagnostic Quizzes',
    desc: 'Questions arrive in batches. Your batch score raises, holds or lowers the difficulty of the next batch and decides which concepts it targets.',
    tag: 'Adaptive Testing',
  },
  {
    icon: Target,
    title: 'Knowledge Gap Prediction',
    desc: 'Bayesian Knowledge Tracing updates a mastery probability for every concept after each answer and flags gaps with a severity and next action.',
    tag: 'Diagnostics',
  },
  {
    icon: Map,
    title: 'Self-Adapting Roadmaps',
    desc: 'A roadmap built from your topic mastery that highlights weak concepts to revisit before moving on.',
    tag: 'Dynamic Planning',
  },
  {
    icon: Layers,
    title: 'Flashcards From Your Sources',
    desc: 'Concept cards from your documents, rescheduled with SM-2 spaced repetition from your Again / Hard / Good / Easy ratings.',
    tag: 'Spaced Repetition',
  },
]

export function Features() {
  return (
    <section id="features" className="mx-auto w-full max-w-[1280px] scroll-mt-20 px-4 py-16 md:px-6 md:py-24">
      <div className="mx-auto max-w-2xl text-center">
        <Badge variant="default" size="md" className="text-xs">
          Capabilities
        </Badge>
        <h2 className="mt-4 text-balance font-display text-3xl font-bold tracking-tight text-foreground md:text-4xl">
          Everything You Need to Master Any Subject
        </h2>
        <p className="mt-3 text-pretty text-xs leading-relaxed text-muted-foreground md:text-sm">
          A premium, source-centric adaptive workspace built to replace disconnected flashcards, static notes, and generic chatbots.
        </p>
      </div>

      <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {features.map((f) => {
          const Icon = f.icon
          return (
            <article
              key={f.title}
              className="group flex flex-col justify-between rounded-3xl border border-border bg-card p-6 shadow-soft transition-all duration-200 hover:-translate-y-1 hover:border-primary/40 hover:shadow-card"
            >
              <div>
                <div className="flex items-start justify-between">
                  <span className="flex size-11 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                    <Icon className="size-5" />
                  </span>
                  <Badge variant="neutral" size="sm" className="text-[10px]">
                    {f.tag}
                  </Badge>
                </div>
                <h3 className="mt-5 font-display text-base font-semibold text-foreground">
                  {f.title}
                </h3>
                <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{f.desc}</p>
              </div>
            </article>
          )
        })}
      </div>
    </section>
  )
}
