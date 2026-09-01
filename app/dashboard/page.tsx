'use client'

import { useState } from 'react'
import { FolderKanban, FileText, Flame, Target, X } from 'lucide-react'
import { Sidebar } from '@/components/dashboard/sidebar'
import { Topbar } from '@/components/dashboard/topbar'
import { StatCard } from '@/components/dashboard/stat-card'
import { MasteryChart } from '@/components/dashboard/mastery-chart'
import { Workspaces } from '@/components/dashboard/workspaces'
import { AiAssistant } from '@/components/dashboard/ai-assistant'
import { QuizCard } from '@/components/dashboard/quiz-card'
import { Roadmap, Recommendations } from '@/components/dashboard/roadmap'

const stats = [
  { label: 'Active workspaces', value: '6', delta: 20, hint: '2 added this month', icon: FolderKanban },
  { label: 'Documents indexed', value: '84', delta: 12, hint: 'Ready for RAG chat', icon: FileText },
  { label: 'Day streak', value: '23', delta: 8, hint: 'Personal best: 31 days', icon: Flame },
  { label: 'Avg. mastery', value: '76%', delta: 18, hint: 'Across all subjects', icon: Target },
]

export default function DashboardPage() {
  const [active, setActive] = useState('Overview')
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="flex h-dvh overflow-hidden bg-background">
      {/* Desktop sidebar */}
      <div className="hidden lg:block">
        <Sidebar active={active} onNavigate={setActive} />
      </div>

      {/* Mobile sidebar */}
      {sidebarOpen ? (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            className="absolute inset-0 bg-foreground/40 backdrop-blur-sm"
            onClick={() => setSidebarOpen(false)}
            aria-hidden
          />
          <div className="absolute left-0 top-0 h-full">
            <Sidebar
              active={active}
              onNavigate={(l) => {
                setActive(l)
                setSidebarOpen(false)
              }}
            />
            <button
              onClick={() => setSidebarOpen(false)}
              className="absolute -right-11 top-3 flex size-9 items-center justify-center rounded-lg bg-card text-foreground"
              aria-label="Close sidebar"
            >
              <X className="size-5" />
            </button>
          </div>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar onToggleSidebar={() => setSidebarOpen(true)} />

        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-[1400px] px-4 py-6 md:px-6 md:py-8">
            {/* Greeting */}
            <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
              <div>
                <h1 className="font-display text-2xl font-semibold tracking-tight text-foreground md:text-[28px]">
                  Good evening, Mehveen
                </h1>
                <p className="mt-1 text-sm text-muted-foreground">
                  You&apos;re on a 23-day streak. Here&apos;s what your AI tutor suggests today.
                </p>
              </div>
              <div className="flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1.5 text-[12px] text-muted-foreground">
                <span className="size-2 rounded-full bg-success" />
                All documents synced
              </div>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
              {stats.map((s) => (
                <StatCard key={s.label} {...s} />
              ))}
            </div>

            {/* Analytics */}
            <div className="mt-6">
              <MasteryChart />
            </div>

            {/* Main grid */}
            <div className="mt-6 grid gap-6 xl:grid-cols-3">
              <div className="flex flex-col gap-6 xl:col-span-2">
                <Workspaces />
                <QuizCard />
              </div>

              <div className="flex flex-col gap-6">
                <div className="h-[520px]">
                  <AiAssistant />
                </div>
                <Roadmap />
                <Recommendations />
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}
