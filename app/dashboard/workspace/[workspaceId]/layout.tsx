import { workspaceService } from '@/lib/services/workspace-service'
import { WorkspaceShell } from '@/components/workspace/workspace-shell'
import { Workspace } from '@/lib/types/domain'

interface WorkspaceLayoutProps {
  children: React.ReactNode
  params: Promise<{ workspaceId: string }>
}

export default async function WorkspaceLayout({ children, params }: WorkspaceLayoutProps) {
  const { workspaceId } = await params
  const workspaces = await workspaceService.getWorkspaces()
  let currentWorkspace = await workspaceService.getWorkspaceById(workspaceId)
  const notifications = await workspaceService.getNotifications()

  if (!currentWorkspace) {
    return (
      <div className="flex min-h-dvh flex-col items-center justify-center p-6 text-center bg-background text-foreground">
        <div className="max-w-md rounded-3xl border border-border bg-card p-8 shadow-card">
          <div className="mx-auto flex size-12 items-center justify-center rounded-2xl bg-destructive/10 text-destructive mb-4">
            <span className="text-xl font-bold">!</span>
          </div>
          <h2 className="font-display text-lg font-semibold text-foreground">Workspace Not Found</h2>
          <p className="mt-2 text-xs text-muted-foreground leading-relaxed">
            The workspace <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-[11px] text-foreground">{workspaceId}</code> does not exist in the database. It may have been deleted or created prior to database migration.
          </p>
          <div className="mt-6 flex justify-center gap-3">
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
