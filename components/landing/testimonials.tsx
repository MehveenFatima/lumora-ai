import { Star } from 'lucide-react'
import { Badge } from '@/components/ui/badge'

const testimonials = [
  {
    quote:
      'LumoraAI replaced four different apps for me. I upload my lecture slides and it just knows what I need to review before an exam.',
    name: 'Aisha Rahman',
    role: 'CS Undergrad, Stanford',
    initials: 'AR',
  },
  {
    quote:
      'The adaptive quizzes are eerily good at finding my weak spots. My retention on system design concepts jumped noticeably in weeks.',
    name: 'Marcus Lee',
    role: 'Software Engineer',
    initials: 'ML',
  },
  {
    quote:
      'Grounded answers with citations mean I actually trust it while studying for the bar. This is what AI in education should feel like.',
    name: 'Elena Fischer',
    role: 'Law Student',
    initials: 'EF',
  },
  {
    quote:
      'I onboarded my whole study group. Each subject has its own workspace, so the answers never bleed across topics.',
    name: 'David Osei',
    role: 'PhD Candidate',
    initials: 'DO',
  },
  {
    quote:
      'The roadmap feature took my vague goal of "learn ML" and turned it into a plan I could actually follow. Game changer.',
    name: 'Priya Nair',
    role: 'Data Analyst',
    initials: 'PN',
  },
  {
    quote:
      'It feels less like a tool and more like a tutor that remembers everything. The mastery analytics keep me honest.',
    name: 'Tom Bradley',
    role: 'Bootcamp Grad',
    initials: 'TB',
  },
]

export function Testimonials() {
  return (
    <section
      id="testimonials"
      className="mx-auto w-full max-w-[1200px] scroll-mt-20 px-4 py-16 md:px-6 md:py-24"
    >
      <div className="mx-auto max-w-2xl text-center">
        <Badge variant="default" size="md">
          Testimonials
        </Badge>
        <h2 className="mt-4 text-balance font-display text-3xl font-semibold tracking-tight text-foreground md:text-4xl">
          Loved by learners who ship results
        </h2>
        <p className="mt-4 text-pretty text-base leading-relaxed text-muted-foreground">
          From university students to working professionals, LumoraAI is how ambitious
          people learn faster.
        </p>
      </div>

      <div className="mt-14 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {testimonials.map((t) => (
          <figure
            key={t.name}
            className="flex flex-col rounded-2xl border border-border bg-card p-6 shadow-soft"
          >
            <div className="flex gap-0.5" aria-label="5 out of 5 stars">
              {Array.from({ length: 5 }).map((_, i) => (
                <Star key={i} className="size-4 fill-warning text-warning" />
              ))}
            </div>
            <blockquote className="mt-4 flex-1 text-[14px] leading-relaxed text-foreground">
              &ldquo;{t.quote}&rdquo;
            </blockquote>
            <figcaption className="mt-5 flex items-center gap-3 border-t border-border pt-4">
              <span className="flex size-10 items-center justify-center rounded-full bg-accent text-[13px] font-semibold text-accent-foreground">
                {t.initials}
              </span>
              <div>
                <p className="text-[14px] font-semibold text-foreground">{t.name}</p>
                <p className="text-[12px] text-muted-foreground">{t.role}</p>
              </div>
            </figcaption>
          </figure>
        ))}
      </div>
    </section>
  )
}
