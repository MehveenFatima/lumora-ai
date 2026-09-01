import { Upload, Sparkles, TrendingUp } from 'lucide-react'
import { Badge } from '@/components/ui/badge'

const steps = [
  {
    icon: Upload,
    step: '01',
    title: 'Upload your material',
    desc: 'Drop in PDFs, lecture notes, or past papers. LumoraAI indexes everything into a private, searchable workspace.',
  },
  {
    icon: Sparkles,
    step: '02',
    title: 'Let the AI build your plan',
    desc: 'It generates flashcards, quizzes, and a roadmap tailored to your goal, timeline, and current level.',
  },
  {
    icon: TrendingUp,
    step: '03',
    title: 'Learn and watch mastery grow',
    desc: 'Study, get grounded answers, and let adaptive review target weak spots until concepts truly stick.',
  },
]

export function HowItWorks() {
  return (
    <section
      id="how-it-works"
      className="mx-auto w-full max-w-[1200px] scroll-mt-20 px-4 py-16 md:px-6 md:py-24"
    >
      <div className="mx-auto max-w-2xl text-center">
        <Badge variant="default" size="md">
          How it works
        </Badge>
        <h2 className="mt-4 text-balance font-display text-3xl font-semibold tracking-tight text-foreground md:text-4xl">
          From documents to mastery in three steps
        </h2>
        <p className="mt-4 text-pretty text-base leading-relaxed text-muted-foreground">
          Set up in minutes. LumoraAI handles the heavy lifting so you can focus on
          learning.
        </p>
      </div>

      <div className="relative mt-14 grid gap-4 md:grid-cols-3 md:gap-6">
        {/* connecting line */}
        <div
          className="pointer-events-none absolute left-0 right-0 top-[52px] hidden h-px bg-gradient-to-r from-transparent via-border to-transparent md:block"
          aria-hidden
        />
        {steps.map((s) => (
          <article
            key={s.step}
            className="relative flex flex-col rounded-2xl border border-border bg-card p-6 shadow-soft"
          >
            <div className="flex items-center justify-between">
              <span className="flex size-12 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-[var(--shadow-glow)]">
                <s.icon className="size-5" strokeWidth={2} />
              </span>
              <span className="font-display text-3xl font-semibold text-border">{s.step}</span>
            </div>
            <h3 className="mt-5 font-display text-[17px] font-semibold text-foreground">
              {s.title}
            </h3>
            <p className="mt-2 text-[14px] leading-relaxed text-muted-foreground">{s.desc}</p>
          </article>
        ))}
      </div>
    </section>
  )
}
