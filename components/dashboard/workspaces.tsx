import type { LucideIcon } from 'lucide-react'
import {
  Cpu,
  Network,
  Braces,
  BrainCircuit,
  FileText,
  MoreHorizontal,
  Plus,
  ArrowRight,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'

type Workspace = {
  title: string
  desc: string
  icon: LucideIcon
  docs: number
  progress: number
  status: 'Active' | 'On track' | 'Needs review'
  updated: string
}

const workspaces: Workspace[] = [
  {
    title: 'Placement Prep 2026',
    desc: 'DSA, CS fundamentals & mock interviews',
    icon: Braces,
    docs: 24,
    progress: 82,
    status: 'On track',
    updated: '2h ago',
  },
  {
    title: 'Operating Systems',
    desc: 'Semester 5 — notes, PYQs & summaries',
    icon: Cpu,
    docs: 12,
    progress: 64,
    status: 'Active',
    updated: 'Yesterday',
  },
  {
    title: 'System Design',
    desc: 'Scalability patterns & case studies',
    icon: Network,
    docs: 9,
    progress: 41,
    status: 'Needs review',
    updated: '3d ago',
  },
  {
    title: 'Machine Learning',
    desc: 'Certification track — Andrew Ng notes',
    icon: BrainCircuit,
    docs: 18,
    progress: 57,
    status: 'Active',
    updated: '5h ago',
  },
]

const statusVariant = {
  Active: 'default',
  'On track': 'success',
  'Needs review': 'warning',
} as const

function WorkspaceCard({ ws }: { ws: Workspace }) {
  return (
    <article className="group flex flex-col rounded-2xl border border-border bg-card p-5 shadow-soft transition-all hover:-translate-y-0.5 hover:shadow-card">
      <div className="flex items-start justify-between">
        <span className="flex size-11 items-center justify-center rounded-xl bg-accent text-accent-foreground">
          <ws.icon className="size-5" strokeWidth={2} />
        </span>
        <button
          className="flex size-8 items-center justify-center rounded-lg text-muted-foreground opacity-0 transition-opacity hover:bg-accent group-hover:opacity-100"
          aria-label="Workspace options"
        >
          <MoreHorizontal className="size-4" />
        </button>
      </div>

      <h3 className="mt-4 font-display text-[15px] font-semibold text-foreground">{ws.title}</h3>
      <p className="mt-1 line-clamp-1 text-[13px] text-muted-foreground">{ws.desc}</p>

      <div className="mt-4 flex items-center gap-2">
        <Badge variant={statusVariant[ws.status]} size="sm">
          {ws.status}
        </Badge>
        <span className="inline-flex items-center gap-1 text-[12px] text-muted-foreground">
          <FileText className="size-3.5" />
          {ws.docs} docs
        </span>
      </div>

      <div className="mt-4">
        <div className="mb-1.5 flex items-center justify-between text-[13px]">
          <span className="text-muted-foreground">Progress</span>
          <span className="font-medium tabular-nums text-foreground">{ws.progress}%</span>
        </div>
        <Progress value={ws.progress} />
      </div>

      <div className="mt-4 flex items-center justify-between border-t border-border pt-3">
        <span className="text-[12px] text-muted-foreground">Updated {ws.updated}</span>
        <span className="inline-flex items-center gap-1 text-[13px] font-medium text-primary opacity-0 transition-opacity group-hover:opacity-100">
          Open <ArrowRight className="size-3.5" />
        </span>
      </div>
    </article>
  )
}

export function Workspaces() {
  return (
    <section>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="font-display text-lg font-semibold text-foreground">Your workspaces</h2>
          <p className="mt-0.5 text-[13px] text-muted-foreground">Independent learning journeys, each with its own memory</p>
        </div>
        <button className="hidden items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-accent/50 sm:inline-flex">
          View all
          <ArrowRight className="size-4" />
        </button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {workspaces.map((ws) => (
          <WorkspaceCard key={ws.title} ws={ws} />
        ))}

        <button className="flex min-h-[220px] flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-border bg-card/40 p-5 text-center transition-colors hover:border-primary/50 hover:bg-accent/30">
          <span className="flex size-11 items-center justify-center rounded-xl border border-border bg-card text-primary">
            <Plus className="size-5" />
          </span>
          <span className="text-sm font-medium text-foreground">Create workspace</span>
          <span className="max-w-[200px] text-[12px] text-muted-foreground">
            Upload PDFs, notes or question papers to start a new journey
          </span>
        </button>
      </div>
    </section>
  )
}
