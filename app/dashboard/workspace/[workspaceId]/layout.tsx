import { redirect } from 'next/navigation'
import { tutorApiClient } from '@/lib/api/tutor-api-client'
import { serverAuthInit } from '@/lib/api/server-auth'
import { WorkspaceShell } from '@/components/workspace/workspace-shell'

interface WorkspaceLayoutProps {
  children: React.ReactNode
  params: Promise<{ workspaceId: string }>
}

export default async function WorkspaceLayout({ children, params }: WorkspaceLayoutProps) {
  const { workspaceId } = await params
  const { init, hasSession } = await serverAuthInit()
  if (!hasSession) redirect(`/login?next=${encodeURIComponent(`/dashboard/workspace/${workspaceId}`)}`)

  // Uncached, per-request calls made with this user's own session
  const [workspaces, currentWorkspace] = await Promise.all([
    tutorApiClient.getWorkspaces(init),
    tutorApiClient.getWorkspaceById(workspaceId, init),
  ])
  const notifications: never[] = []

  if (!currentWorkspace) {
    return (
      <div className="flex min-h-dvh flex-col items-center justify-center p-6 text-center bg-background text-foreground">
        <div className="max-w-md rounded-3xl border border-border bg-card p-8 shadow-card">
          <div className="mx-auto flex size-12 items-center justify-center rounded-2xl bg-destructive/10 text-destructive mb-4">
            <span className="text-xl font-bold">!</span>
          </div>
          <h2 className="font-display text-lg font-semibold text-foreground">Workspace Not Found</h2>
          <p className="mt-2 text-xs text-muted-foreground leading-relaxed">
            The workspace <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-[11px] text-foreground">{workspaceId}</code> does not exist, or you don&apos;t have access to it. If your session has expired, sign in again.
          </p>
          <div className="mt-6 flex justify-center gap-3">
            <a
              href="/login"
              className="inline-flex h-10 items-center justify-center rounded-xl border border-border bg-card px-5 text-xs font-semibold text-foreground transition-colors hover:bg-accent/40"
            >
              Sign in again
            </a>
            <a
              href="/dashboard"
              className="inline-flex h-10 items-center justify-center rounded-xl bg-primary px-5 text-xs font-semibold text-primary-foreground shadow-glow transition-opacity hover:opacity-90"
            >
              Return to Dashboard
            </a>
          </div>
        </div>
      </div>
    )
  }

  const allWorkspaces = workspaces.some((w) => w.id === currentWorkspace!.id)
    ? workspaces
    : [currentWorkspace, ...workspaces]

  return (
    <WorkspaceShell
      workspaces={allWorkspaces}
      currentWorkspace={currentWorkspace}
      notifications={notifications}
    >
      {children}
    </WorkspaceShell>
  )
}
