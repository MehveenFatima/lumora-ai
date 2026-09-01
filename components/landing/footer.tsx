import Link from 'next/link'
import { GraduationCap } from 'lucide-react'

function XIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden {...props}>
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24h-6.66l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231 5.451-6.231Zm-1.161 17.52h1.833L7.084 4.126H5.117L17.083 19.77Z" />
    </svg>
  )
}

function GithubIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden {...props}>
      <path d="M12 .5A11.5 11.5 0 0 0 .5 12a11.5 11.5 0 0 0 7.86 10.92c.575.106.785-.25.785-.556 0-.274-.01-1-.015-1.965-3.196.695-3.87-1.54-3.87-1.54-.523-1.33-1.277-1.684-1.277-1.684-1.044-.714.08-.699.08-.699 1.155.082 1.763 1.186 1.763 1.186 1.026 1.758 2.693 1.25 3.35.955.104-.744.401-1.25.73-1.538-2.553-.29-5.236-1.276-5.236-5.68 0-1.255.448-2.28 1.183-3.084-.119-.29-.513-1.46.112-3.043 0 0 .966-.31 3.165 1.178a11 11 0 0 1 2.88-.388c.977.004 1.96.132 2.88.388 2.197-1.488 3.162-1.178 3.162-1.178.626 1.583.232 2.753.114 3.043.736.804 1.18 1.829 1.18 3.084 0 4.415-2.687 5.386-5.248 5.67.412.355.78 1.056.78 2.128 0 1.537-.014 2.777-.014 3.155 0 .308.207.667.79.554A11.5 11.5 0 0 0 23.5 12 11.5 11.5 0 0 0 12 .5Z" />
    </svg>
  )
}

function LinkedinIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden {...props}>
      <path d="M20.45 20.45h-3.56v-5.57c0-1.33-.02-3.04-1.85-3.04-1.85 0-2.14 1.45-2.14 2.94v5.67H9.34V9h3.42v1.56h.05c.48-.9 1.64-1.85 3.37-1.85 3.6 0 4.27 2.37 4.27 5.46v6.28ZM5.34 7.43a2.06 2.06 0 1 1 0-4.13 2.06 2.06 0 0 1 0 4.13ZM7.12 20.45H3.55V9h3.57v11.45ZM22.22 0H1.77C.79 0 0 .77 0 1.73v20.54C0 23.23.79 24 1.77 24h20.45c.98 0 1.78-.77 1.78-1.73V1.73C24 .77 23.2 0 22.22 0Z" />
    </svg>
  )
}

const columns = [
  {
    title: 'Product',
    links: ['Features', 'How it works', 'Technology', 'Pricing', 'Changelog'],
  },
  {
    title: 'Company',
    links: ['About', 'Careers', 'Blog', 'Press', 'Contact'],
  },
  {
    title: 'Resources',
    links: ['Documentation', 'Help center', 'Community', 'API', 'Status'],
  },
  {
    title: 'Legal',
    links: ['Privacy', 'Terms', 'Security', 'Cookies'],
  },
]

const socials = [
  { icon: XIcon, label: 'X' },
  { icon: GithubIcon, label: 'GitHub' },
  { icon: LinkedinIcon, label: 'LinkedIn' },
]

export function Footer() {
  return (
    <footer className="border-t border-border bg-card/30">
      <div className="mx-auto w-full max-w-[1200px] px-4 py-14 md:px-6 md:py-16">
        <div className="grid gap-10 lg:grid-cols-[1.5fr_1fr_1fr_1fr_1fr]">
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
              The AI-powered adaptive learning platform that turns your material into
              mastery.
            </p>
            <div className="mt-5 flex items-center gap-2">
              {socials.map((s) => (
                <a
                  key={s.label}
                  href="#"
                  aria-label={s.label}
                  className="flex size-9 items-center justify-center rounded-lg border border-border bg-card text-muted-foreground transition-colors hover:text-foreground"
                >
                  <s.icon className="size-4" />
                </a>
              ))}
            </div>
          </div>

          {columns.map((col) => (
            <div key={col.title}>
              <h3 className="text-[13px] font-semibold text-foreground">{col.title}</h3>
              <ul className="mt-4 flex flex-col gap-2.5">
                {col.links.map((link) => (
                  <li key={link}>
                    <a
                      href="#"
                      className="text-[13px] text-muted-foreground transition-colors hover:text-foreground"
                    >
                      {link}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-12 flex flex-col items-center justify-between gap-4 border-t border-border pt-8 sm:flex-row">
          <p className="text-[13px] text-muted-foreground">
            © {new Date().getFullYear()} LumoraAI. All rights reserved.
          </p>
          <p className="flex items-center gap-1.5 text-[13px] text-muted-foreground">
            <span className="size-2 rounded-full bg-success" />
            All systems operational
          </p>
        </div>
      </div>
    </footer>
  )
}
