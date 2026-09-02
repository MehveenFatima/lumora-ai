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
    currentWorkspace = {
      id: workspaceId,
      name: 'Workspace',
      goal: 'Learning Track',
      level: 'intermediate',
      targetDate: '2026-12-31',
      dailyTargetMinutes: 45,
      description: 'Workspace grounded in your uploaded resources.',
      overallMastery: 0,
      masteryDelta: 0,
      status: 'active',
      iconName: 'FolderKanban',
      documentCount: 0,
      topicsCount: 0,
      flashcardsDueCount: 0,
      lastActive: 'Just now',
      createdAt: new Date().toISOString().split('T')[0],
    }
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
