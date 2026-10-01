import Link from 'next/link'
import Image from 'next/image'
import { GraduationCap, Sparkles } from 'lucide-react'

const highlights = [
  'Adaptive quizzes that target your weak spots',
  'Chat with your documents using RAG',
  'Personalized roadmaps and mastery analytics',
]

export function AuthShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen bg-background">
      {/* Illustration panel */}
      <aside className="relative hidden w-[46%] max-w-[620px] shrink-0 overflow-hidden border-r border-border lg:block">
        <Image
          src="/images/auth-panel.png"
          alt=""
          fill
          priority
          sizes="46vw"
          className="object-cover"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-background via-background/40 to-background/10" />

        <div className="relative flex h-full flex-col justify-between p-10">
          <Link href="/" className="flex items-center gap-2.5">
            <span className="flex size-9 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-[var(--shadow-glow)]">
              <GraduationCap className="size-5" strokeWidth={2.25} />
            </span>
            <span className="font-display text-[16px] font-semibold tracking-tight text-foreground">
              Lumora<span className="text-primary">AI</span>
            </span>
          </Link>

          <div className="max-w-sm">
            <div className="mb-5 inline-flex items-center gap-1.5 rounded-full border border-border bg-card/70 px-3 py-1 text-xs font-medium text-muted-foreground backdrop-blur">
              <Sparkles className="size-3.5 text-primary" />
              AI-powered learning
            </div>
            <h2 className="font-display text-3xl font-semibold leading-tight tracking-tight text-balance text-foreground">
              Learn smarter, adapt faster.
            </h2>
            <ul className="mt-6 flex flex-col gap-3">
              {highlights.map((h) => (
                <li key={h} className="flex items-start gap-2.5 text-sm text-muted-foreground">
                  <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-primary" />
                  {h}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </aside>

      {/* Form panel */}
      <main className="flex flex-1 flex-col">
        <div className="flex items-center justify-between p-5 lg:hidden">
          <Link href="/" className="flex items-center gap-2.5">
            <span className="flex size-9 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-[var(--shadow-glow)]">
              <GraduationCap className="size-5" strokeWidth={2.25} />
            </span>
            <span className="font-display text-[16px] font-semibold tracking-tight text-foreground">
              Lumora<span className="text-primary">AI</span>
            </span>
          </Link>
        </div>
        <div className="flex flex-1 items-center justify-center px-5 pb-12 lg:p-8">
          <div className="w-full max-w-[400px]">
            {children}
            <p className="mt-6 rounded-xl border border-border bg-card/60 px-3 py-2 text-center text-[11px] leading-relaxed text-muted-foreground">
              Preview: accounts are not connected yet. LumoraAI currently runs as a single local
              learner, and these forms only validate input.
            </p>
          </div>
        </div>
      </main>
    </div>
  )
}
