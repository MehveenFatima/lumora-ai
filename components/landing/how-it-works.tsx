import {
  Upload,
  MessagesSquare,
  Zap,
  BarChart3,
  AlertTriangle,
  Sparkles,
  Map,
  RotateCcw,
  Target,
  ArrowRight,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'

const loopSteps = [
  {
    step: '01',
    title: 'YOUR MATERIAL',
    desc: 'Upload PDFs, Word documents, slides or text notes into an isolated subject workspace.',
    icon: Upload,
  },
  {
    step: '02',
    title: 'AI TUTOR',
    desc: 'Learn through interactive dialogues grounded strictly in your uploaded notes with page citations.',
    icon: MessagesSquare,
  },
  {
    step: '03',
    title: 'ASSESSMENT',
    desc: 'Take adaptive quizzes where each batch’s score sets the difficulty of the next batch.',
    icon: Zap,
  },
  {
    step: '04',
    title: 'KNOWLEDGE ANALYSIS',
    desc: 'Bayesian Knowledge Tracing updates your mastery probability for each concept after every answer.',
    icon: BarChart3,
  },
  {
    step: '05',
    title: 'KNOWLEDGE GAPS',
    desc: 'Concepts with low mastery or repeated mistakes are flagged as gaps, ranked by severity.',
    icon: AlertTriangle,
  },
  {
    step: '06',
    title: 'RECOMMENDATION',
    desc: 'Receive transparent "next best actions" explaining exactly WHY a specific drill is prioritized.',
    icon: Sparkles,
  },
  {
    step: '07',
    title: 'ADAPTIVE ROADMAP',
    desc: 'Your roadmap reflects topic mastery and points to weak concepts before advanced topics.',
    icon: Map,
  },
  {
    step: '08',
    title: 'REVISION & MASTERY',
    desc: 'Review spaced-repetition flashcards and retake quizzes until your critical gaps are closed.',
    icon: Target,
  },
]

export function HowItWorks() {
  return (
    <section
      id="learning-loop"
      className="mx-auto w-full max-w-[1280px] scroll-mt-20 px-4 py-16 md:px-6 md:py-24"
    >
      <div className="mx-auto max-w-2xl text-center">
        <Badge variant="default" size="md" className="text-xs">
          The Core Engine
        </Badge>
        <h2 className="mt-4 text-balance font-display text-3xl font-bold tracking-tight text-foreground md:text-4xl">
          The Closed-Loop Adaptive Learning Cycle
        </h2>
        <p className="mt-3 text-pretty text-xs leading-relaxed text-muted-foreground md:text-sm">
          LumoraAI isn&apos;t a static reader or a generic chatbot. It is a continuous feedback loop that
          actively analyzes your strengths and adapts every study session to your cognitive state.
        </p>
      </div>

      {/* Grid of Loop Stages */}
      <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {loopSteps.map((s, idx) => {
          const Icon = s.icon
          return (
            <article
              key={s.step}
              className="group relative flex flex-col justify-between rounded-3xl border border-border bg-card p-6 shadow-soft transition-all duration-200 hover:-translate-y-1 hover:border-primary/40 hover:shadow-card"
            >
              <div>
                <div className="flex items-center justify-between">
                  <span className="flex size-11 items-center justify-center rounded-2xl bg-primary/10 text-primary shadow-soft">
                    <Icon className="size-5" />
                  </span>
                  <span className="font-mono text-xs font-bold text-muted-foreground">
                    STEP {s.step}
                  </span>
                </div>

                <h3 className="mt-5 font-display text-sm font-bold tracking-wider text-foreground">
                  {s.title}
                </h3>
                <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{s.desc}</p>
              </div>

              {idx < loopSteps.length - 1 && (
                <div className="mt-4 flex items-center gap-1 text-[10px] font-semibold uppercase text-primary">
                  <span>Leads to next step</span>
                  <ArrowRight className="size-3" />
                </div>
              )}
            </article>
          )
        })}
      </div>
    </section>
  )
}
