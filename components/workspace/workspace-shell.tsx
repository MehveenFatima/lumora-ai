'use client'

import { useState } from 'react'
import { X } from 'lucide-react'
import { Workspace, NotificationItem } from '@/lib/types/domain'
import { WorkspaceSidebar } from './workspace-sidebar'
import { WorkspaceHeader } from './workspace-header'
import { CreateWorkspaceModal } from './create-workspace-modal'

interface WorkspaceShellProps {
  workspaces: Workspace[]
  currentWorkspace: Workspace
  notifications?: NotificationItem[]
  children: React.ReactNode
}

export function WorkspaceShell({
  workspaces,
  currentWorkspace,
  notifications = [],
  children,
}: WorkspaceShellProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [createModalOpen, setCreateModalOpen] = useState(false)

  return (
    <div className="flex h-dvh w-full overflow-hidden bg-background">
      {/* Desktop Sidebar */}
      <div className="hidden lg:block h-full">
        <WorkspaceSidebar workspace={currentWorkspace} />
      </div>

      {/* Mobile Drawer */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            className="absolute inset-0 bg-background/80 backdrop-blur-sm"
            onClick={() => setSidebarOpen(false)}
            aria-hidden
          />
          <div className="absolute left-0 top-0 h-full w-72 max-w-[85vw] shadow-card">
            <WorkspaceSidebar
              workspace={currentWorkspace}
              onNavigate={() => setSidebarOpen(false)}
            />
            <button
              onClick={() => setSidebarOpen(false)}
              className="absolute -right-11 top-3.5 flex size-9 items-center justify-center rounded-xl border border-border bg-card text-foreground"
              aria-label="Close sidebar"
            >
              <X className="size-4" />
            </button>
          </div>
        </div>
      )}

      {/* Main Workspace Frame */}
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <WorkspaceHeader
          workspaces={workspaces}
          currentWorkspace={currentWorkspace}
          notifications={notifications}
          onToggleSidebar={() => setSidebarOpen(true)}
          onCreateWorkspaceClick={() => setCreateModalOpen(true)}
        />

        <main className="flex-1 overflow-y-auto">
          {children}
        </main>
      </div>

      {/* Create Workspace Modal */}
      <CreateWorkspaceModal
        isOpen={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
      />
    </div>
  )
}
