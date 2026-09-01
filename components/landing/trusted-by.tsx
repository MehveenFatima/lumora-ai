const logos = [
  'Stanford',
  'MIT Media Lab',
  'Coursera',
  'Y Combinator',
  'Notion',
  'DeepMind',
]

const stats = [
  { value: '250K+', label: 'Active learners' },
  { value: '4.9M', label: 'Documents indexed' },
  { value: '38%', label: 'Faster mastery' },
  { value: '4.9/5', label: 'Average rating' },
]

export function TrustedBy() {
  return (
    <section className="mx-auto w-full max-w-[1200px] px-4 py-16 md:px-6 md:py-24">
      <p className="text-center text-[13px] font-medium uppercase tracking-wider text-muted-foreground">
        Trusted by students & professionals at leading organizations
      </p>

      <div className="mt-8 flex flex-wrap items-center justify-center gap-x-10 gap-y-6 md:gap-x-16">
        {logos.map((logo) => (
          <span
            key={logo}
            className="font-display text-lg font-semibold tracking-tight text-muted-foreground/60 transition-colors hover:text-foreground md:text-xl"
          >
            {logo}
          </span>
        ))}
      </div>

      <div className="mt-14 grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-border bg-border md:grid-cols-4">
        {stats.map((s) => (
          <div key={s.label} className="bg-card px-6 py-8 text-center">
            <p className="font-display text-3xl font-semibold tracking-tight text-foreground md:text-4xl">
              {s.value}
            </p>
            <p className="mt-1.5 text-[13px] text-muted-foreground">{s.label}</p>
          </div>
        ))}
      </div>
    </section>
  )
}
