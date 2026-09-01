import { CheckCircle2, Gauge, ShieldCheck, Infinity as InfinityIcon } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'

const points = [
  {
    icon: Gauge,
    title: 'Learns how you learn',
    desc: 'Every session refines a model of your strengths and gaps — no two learners get the same plan.',
  },
  {
    icon: ShieldCheck,
    title: 'Grounded, not guessing',
    desc: 'Answers cite your own sources, so you can trust what you study and where it came from.',
  },
  {
    icon: InfinityIcon,
    title: 'One place, no context-switching',
    desc: 'Reading, testing, reviewing, and tracking all live together in a single, calm workspace.',
  },
]

const bars = [
  { label: 'System Design', value: 88 },
  { label: 'Data Structures', value: 74 },
  { label: 'Operating Systems', value: 61 },
]

export function Why() {
  return (
    <section className="relative border-y border-border bg-card/30">
      <div className="mx-auto grid w-full max-w-[1200px] items-center gap-12 px-4 py-16 md:px-6 md:py-24 lg:grid-cols-2 lg:gap-16">
        <div>
          <Badge variant="default" size="md">
            Why LumoraAI
          </Badge>
          <h2 className="mt-4 text-balance font-display text-3xl font-semibold tracking-tight text-foreground md:text-4xl">
            Study less. Understand more. Forget nothing.
          </h2>
          <p className="mt-4 text-pretty text-base leading-relaxed text-muted-foreground">
            Most tools give you content. LumoraAI gives you a tutor that pays attention —
            adapting to your pace and protecting the concepts you&apos;re about to lose.
          </p>

          <ul className="mt-8 flex flex-col gap-6">
            {points.map((p) => (
              <li key={p.title} className="flex gap-4">
                <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-accent text-accent-foreground">
                  <p.icon className="size-5" strokeWidth={2} />
                </span>
                <div>
                  <h3 className="font-display text-[15px] font-semibold text-foreground">
                    {p.title}
                  </h3>
                  <p className="mt-1 text-[14px] leading-relaxed text-muted-foreground">
                    {p.desc}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </div>

        {/* Visual mastery panel */}
        <div className="relative">
          <div className="rounded-3xl border border-border bg-card p-6 shadow-card md:p-8">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[13px] text-muted-foreground">Overall mastery</p>
                <p className="font-display text-4xl font-semibold tracking-tight text-foreground">
                  76%
                </p>
              </div>
              <Badge variant="success" size="md" className="gap-1">
                <CheckCircle2 className="size-3.5" />
                +18% this month
              </Badge>
            </div>

            <div className="mt-8 flex flex-col gap-5">
              {bars.map((b) => (
                <div key={b.label}>
                  <div className="mb-1.5 flex items-center justify-between text-[13px]">
                    <span className="text-muted-foreground">{b.label}</span>
                    <span className="font-medium tabular-nums text-foreground">{b.value}%</span>
                  </div>
                  <Progress value={b.value} />
                </div>
              ))}
            </div>

            <div className="mt-8 rounded-2xl border border-border bg-accent/40 p-4">
              <p className="text-[13px] leading-relaxed text-foreground">
                <span className="font-semibold text-primary">AI insight:</span> You retain
                System Design concepts best in the morning. I&apos;ve scheduled 3 review cards
                for 9:00 AM tomorrow.
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
