import Link from 'next/link'
import { GraduationCap } from 'lucide-react'

function GithubIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden {...props}>
      <path d="M12 .5A11.5 11.5 0 0 0 .5 12a11.5 11.5 0 0 0 7.86 10.92c.575.106.785-.25.785-.556 0-.274-.01-1-.015-1.965-3.196.695-3.87-1.54-3.87-1.54-.523-1.33-1.277-1.684-1.277-1.684-1.044-.714.08-.699.08-.699 1.155.082 1.763 1.186 1.763 1.186 1.026 1.758 2.693 1.25 3.35.955.104-.744.401-1.25.73-1.538-2.553-.29-5.236-1.276-5.236-5.68 0-1.255.448-2.28 1.183-3.084-.119-.29-.513-1.46.112-3.043 0 0 .966-.31 3.165 1.178a11 11 0 0 1 2.88-.388c.977.004 1.96.132 2.88.388 2.197-1.488 3.162-1.178 3.162-1.178.626 1.583.232 2.753.114 3.043.736.804 1.18 1.829 1.18 3.084 0 4.415-2.687 5.386-5.248 5.67.412.355.78 1.056.78 2.128 0 1.537-.014 2.777-.014 3.155 0 .308.207.667.79.554A11.5 11.5 0 0 0 23.5 12 11.5 11.5 0 0 0 12 .5Z" />
    </svg>
  )
}

const REPO_URL = 'https://github.com/MehveenFatima/lumora-ai'

const columns: { title: string; links: { label: string; href: string; external?: boolean }[] }[] = [
  {
    title: 'Product',
    links: [
      { label: 'Features', href: '#features' },
      { label: 'How it works', href: '#learning-loop' },
      { label: 'Technology', href: '#technology' },
    ],
  },
  {
    title: 'App',
    links: [
      { label: 'Dashboard', href: '/dashboard' },
      { label: 'Sign in', href: '/login' },
      { label: 'Create account', href: '/register' },
    ],
  },
  {
    title: 'Project',
    links: [
      { label: 'Source code', href: REPO_URL, external: true },
      { label: 'Documentation', href: `${REPO_URL}#readme`, external: true },
    ],
  },
]

export function Footer() {
  return (
    <footer className="border-t border-border bg-card/30">
      <div className="mx-auto w-full max-w-[1200px] px-4 py-14 md:px-6 md:py-16">
        <div className="grid gap-10 lg:grid-cols-[1.5fr_1fr_1fr_1fr]">
          <div>
            <Link href="/" className="flex items-center gap-2.5">
              <span className="flex size-9 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-[var(--shadow-glow)]">
                <GraduationCap className="size-5" strokeWidth={2.25} />
              </span>
              <span className="font-display text-[16px] font-semibold tracking-tight text-foreground">
                Lumora<span className="text-primary">AI</span>
              </span>
            </Link>
            <p className="mt-4 max-w-xs text-[13px] leading-relaxed text-muted-foreground">
              A RAG-based adaptive learning platform that explains your own study material and
              tracks mastery concept by concept.
            </p>
            <a
              href={REPO_URL}
              target="_blank"
              rel="noopener noreferrer"
              aria-label="LumoraAI on GitHub"
              className="mt-5 inline-flex size-9 items-center justify-center rounded-lg border border-border bg-card text-muted-foreground transition-colors hover:text-foreground"
            >
              <GithubIcon className="size-4" />
            </a>
          </div>

          {columns.map((col) => (
            <div key={col.title}>
              <h3 className="text-[13px] font-semibold text-foreground">{col.title}</h3>
              <ul className="mt-4 flex flex-col gap-2.5">
                {col.links.map((link) => (
                  <li key={link.label}>
                    <a
                      href={link.href}
                      {...(link.external ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
                      className="text-[13px] text-muted-foreground transition-colors hover:text-foreground"
                    >
                      {link.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-12 flex flex-col items-center justify-between gap-4 border-t border-border pt-8 sm:flex-row">
          <p className="text-[13px] text-muted-foreground">
            © {new Date().getFullYear()} LumoraAI
          </p>
          <p className="text-[13px] text-muted-foreground">
            Next.js · FastAPI · PostgreSQL + pgvector · Gemini
          </p>
        </div>
      </div>
    </footer>
  )
}
