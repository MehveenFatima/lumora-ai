import { notFound } from 'next/navigation'
import { workspaceService } from '@/lib/services/workspace-service'
import { WorkspaceShell } from '@/components/workspace/workspace-shell'

interface WorkspaceLayoutProps {
  children: React.ReactNode
  params: Promise<{ workspaceId: string }>
}

export default async function WorkspaceLayout({ children, params }: WorkspaceLayoutProps) {
  const { workspaceId } = await params
  const workspaces = await workspaceService.getWorkspaces()
  const currentWorkspace = await workspaceService.getWorkspaceById(workspaceId)
  const notifications = await workspaceService.getNotifications()

  if (!currentWorkspace) {
    // If not found, redirect to first valid workspace or 404
    if (workspaces.length > 0) {
      return (
        <WorkspaceShell
          workspaces={workspaces}
          currentWorkspace={workspaces[0]}
          notifications={notifications}
        >
          {children}
        </WorkspaceShell>
      )
    }
    notFound()
  }

  return (
    <WorkspaceShell
      workspaces={workspaces}
      currentWorkspace={currentWorkspace}
      notifications={notifications}
    >
      {children}
    </WorkspaceShell>
  )
}
