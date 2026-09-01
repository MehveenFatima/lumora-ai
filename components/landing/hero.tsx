import Link from 'next/link'
import {
  ArrowRight,
  Sparkles,
  Play,
  FileText,
  Layers,
  Target,
  Zap,
  CheckCircle2,
  Map,
  MessagesSquare,
  BookOpen,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'

export function Hero() {
  return (
    <section className="relative overflow-hidden pt-28 md:pt-36">
      {/* Ambient background grid & glow */}
      <div
        className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[600px] opacity-60"
        style={{
          background:
            'radial-gradient(60% 60% at 50% 0%, rgba(59, 130, 246, 0.22) 0%, transparent 70%)',
        }}
        aria-hidden
      />

      <div className="mx-auto w-full max-w-[1280px] px-4 md:px-6">
        <div className="mx-auto flex max-w-3xl flex-col items-center text-center">
          <Badge
            variant="outline"
            size="md"
            className="gap-1.5 border-border bg-card/60 backdrop-blur text-xs"
          >
            <Sparkles className="size-3.5 text-primary" />
            RAG-Based Adaptive Learning Platform
          </Badge>

          <h1 className="mt-6 text-balance font-display text-4xl font-bold leading-[1.08] tracking-tight text-foreground sm:text-5xl md:text-6xl">
            Learn smarter. Adapt faster.{' '}
            <span className="text-primary">Master what matters.</span>
          </h1>

          <p className="mt-6 max-w-2xl text-pretty text-sm leading-relaxed text-muted-foreground md:text-base">
            Turn your own learning resources into a personalized AI learning system that understands what you know,
            identifies knowledge gaps, and continuously adapts your learning path.
          </p>

          <div className="mt-8 flex flex-col items-center gap-3 sm:flex-row">
            <Link
              href="/dashboard/workspace/dsa"
              className="inline-flex items-center gap-2 rounded-xl bg-primary px-6 py-3.5 text-xs font-semibold text-primary-foreground shadow-glow transition-opacity hover:opacity-90"
            >
              Start Learning Free
              <ArrowRight className="size-4" />
            </Link>
            <Link
              href="/dashboard"
              className="inline-flex items-center gap-2 rounded-xl border border-border bg-card px-6 py-3.5 text-xs font-semibold text-foreground shadow-soft transition-colors hover:bg-accent/50"
            >
              Explore LumoraAI
            </Link>
          </div>

          <p className="mt-4 text-[11px] text-muted-foreground">
            No fake promises · Grounded citations in your sources · Adaptive mastery modeling
          </p>
        </div>

        {/* UI-Grounded Interactive Workspace Preview Card */}
        <div className="relative mx-auto mt-12 max-w-5xl md:mt-16">
          <div className="overflow-hidden rounded-3xl border border-border bg-card shadow-card">
            {/* Mock Topbar */}
            <div className="flex items-center justify-between border-b border-border bg-background/60 px-5 py-3 text-xs">
              <div className="flex items-center gap-2">
                <span className="size-2.5 rounded-full bg-destructive/60" />
                <span className="size-2.5 rounded-full bg-warning/60" />
                <span className="size-2.5 rounded-full bg-success/60" />
                <span className="ml-2 font-mono text-[11px] text-muted-foreground">
                  lumora.ai/workspace/data-structures-and-algorithms
                </span>
              </div>
              <Badge variant="success" size="sm" className="text-[10px]">
                74% Overall Mastery
              </Badge>
            </div>

            {/* Mock Workspace Content */}
            <div className="grid gap-6 p-6 md:grid-cols-12 md:p-8 bg-card">
              {/* Left mock col: AI Recommendation & Knowledge Gaps */}
              <div className="space-y-4 md:col-span-7">
                <div className="rounded-2xl border border-primary/30 bg-primary/5 p-4 text-xs">
                  <div className="flex items-center gap-2 font-semibold text-primary">
                    <Sparkles className="size-4" />
                    <span>AI Recommendation: Graph Traversal & Disconnected DFS</span>
                  </div>
                  <p className="mt-1 text-[11px] text-muted-foreground leading-relaxed">
                    &ldquo;Recent assessments show that BFS is solid (91%), but accuracy drops to 46% on DFS questions involving disconnected subgraphs.&rdquo;
                  </p>
                  <div className="mt-3 flex items-center gap-2">
                    <span className="rounded-lg bg-primary px-2.5 py-1 text-[10px] font-semibold text-primary-foreground">
                      High Priority • 25 min
                    </span>
                    <span className="text-[11px] text-muted-foreground">
                      Prerequisites: Arrays (92%), Recursion (84%)
                    </span>
                  </div>
                </div>

                <div className="rounded-2xl border border-border bg-background/60 p-4 text-xs">
                  <span className="font-semibold text-foreground">Knowledge Gap Diagnostics</span>
                  <div className="mt-2.5 space-y-2">
                    <div className="flex items-center justify-between rounded-xl border border-border bg-card p-2 text-[11px]">
                      <span className="font-medium text-foreground">DFS on Disconnected Graphs</span>
                      <span className="font-bold text-destructive">46% Mastery</span>
                    </div>
                    <div className="flex items-center justify-between rounded-xl border border-border bg-card p-2 text-[11px]">
                      <span className="font-medium text-foreground">Directed Cycle Detection (3-Color)</span>
                      <span className="font-bold text-destructive">41% Mastery</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Right mock col: AI Tutor snippet & Grounded Citation */}
              <div className="space-y-4 md:col-span-5">
                <div className="rounded-2xl border border-border bg-background p-4 text-xs space-y-2.5">
                  <div className="flex items-center justify-between border-b border-border pb-2">
                    <span className="font-semibold text-foreground flex items-center gap-1.5">
                      <MessagesSquare className="size-3.5 text-primary" /> Grounded AI Tutor
                    </span>
                    <span className="text-[10px] text-muted-foreground">24 Sources</span>
                  </div>
                  <div className="rounded-xl bg-card p-2.5 text-[11px] leading-relaxed text-foreground border border-border/60">
                    &ldquo;In directed cycle detection, a back-edge points to an ancestor currently active in the recursion stack (Gray node).&rdquo;
                  </div>
                  <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
                    <FileText className="size-3 text-primary" />
                    <span>Cited: <strong>DSA_Core_Notes.pdf</strong> (Page 42)</span>
                  </div>
                </div>

                <div className="rounded-2xl border border-border bg-background p-4 text-xs">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-semibold text-foreground">Adaptive Roadmap Splicing</span>
                    <Badge variant="warning" size="sm" className="text-[9px]">AI Adapted</Badge>
                  </div>
                  <p className="text-[11px] text-muted-foreground">
                    Graph Fundamentals → <strong>Disconnected DFS Practice</strong> → Advanced Graphs
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
