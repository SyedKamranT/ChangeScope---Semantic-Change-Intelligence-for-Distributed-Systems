import React from 'react'
import { AppHeader } from './AppHeader'
import { AppSidebar, NavViewKey } from './AppSidebar'
import { WorkspaceItem, UserProfile } from '../../api/types'

export interface AppShellProps {
  workspaces: WorkspaceItem[]
  currentWorkspace: WorkspaceItem
  onWorkspaceChange: (ws: WorkspaceItem) => void
  currentUser: UserProfile
  activeView: NavViewKey
  onSelectView: (view: NavViewKey) => void
  onTriggerScan: () => void
  children: React.ReactNode
}

export const AppShell: React.FC<AppShellProps> = ({
  workspaces,
  currentWorkspace,
  onWorkspaceChange,
  currentUser,
  activeView,
  onSelectView,
  onTriggerScan,
  children,
}) => {
  return (
    <div className="min-h-screen bg-[#fafafa] text-slate-900 flex flex-col font-sans selection:bg-blue-100 selection:text-blue-900">
      <AppHeader
        workspaces={workspaces}
        currentWorkspace={currentWorkspace}
        onWorkspaceChange={onWorkspaceChange}
        currentUser={currentUser}
        onTriggerScan={onTriggerScan}
      />

      <div className="flex-1 flex overflow-hidden">
        <AppSidebar activeView={activeView} onSelectView={onSelectView} />

        <main className="flex-1 overflow-y-auto p-6 space-y-6">
          <div className="max-w-7xl mx-auto space-y-6">{children}</div>
        </main>
      </div>
    </div>
  )
}
