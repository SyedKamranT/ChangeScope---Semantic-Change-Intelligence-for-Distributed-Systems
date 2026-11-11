import React from 'react'
import { ShieldCheck, Database, Activity, Plus, Shield } from 'lucide-react'
import { Button } from '../ui/Button'
import { Badge } from '../ui/Badge'
import { WorkspaceItem, UserProfile } from '../../api/types'

export interface AppHeaderProps {
  workspaces: WorkspaceItem[]
  currentWorkspace: WorkspaceItem
  onWorkspaceChange: (ws: WorkspaceItem) => void
  currentUser: UserProfile
  onTriggerScan: () => void
}

export const AppHeader: React.FC<AppHeaderProps> = ({
  workspaces,
  currentWorkspace,
  onWorkspaceChange,
  currentUser,
  onTriggerScan,
}) => {
  return (
    <header className="border-b border-slate-200 bg-white/95 backdrop-blur-md sticky top-0 z-40 px-5 py-3 flex items-center justify-between shadow-xs transition-colors">
      {/* Left: Brand & Workspace Switcher */}
      <div className="flex items-center gap-5">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-[#09090b] flex items-center justify-center shadow-xs text-white font-bold">
            <ShieldCheck className="w-4 h-4 text-white" />
          </div>
          <div>
            <div className="font-bold text-sm tracking-tight text-slate-900 flex items-center gap-2">
              ChangeScope
              <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-slate-100 text-slate-700 border border-slate-200 font-medium">
                v1.0.0
              </span>
            </div>
            <div className="text-[10px] text-slate-500 font-medium">Semantic Change Intelligence</div>
          </div>
        </div>

        <div className="h-5 w-px bg-slate-200" />

        {/* Workspace Dropdown */}
        <div className="flex items-center gap-2 text-xs">
          <Database className="w-3.5 h-3.5 text-slate-500" />
          <span className="text-slate-500 font-medium">Workspace:</span>
          <select
            value={currentWorkspace.id}
            onChange={(e) => {
              const selected = workspaces.find((w) => w.id === e.target.value)
              if (selected) onWorkspaceChange(selected)
            }}
            className="bg-slate-50 hover:bg-slate-100/70 border border-slate-200 rounded-md px-2.5 py-1 text-xs text-slate-900 font-semibold focus:outline-none focus:border-slate-900 cursor-pointer shadow-2xs transition-colors"
          >
            {workspaces.map((ws) => (
              <option key={ws.id} value={ws.id} className="bg-white text-slate-900">
                {ws.name}
              </option>
            ))}
          </select>
        </div>

        <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-emerald-50 border border-emerald-200/90 text-[11px] text-emerald-800 font-medium">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          <span>PostgreSQL 17 + Neo4j Synced</span>
        </div>
      </div>

      {/* Right: Telemetry Ingest, Quick PR Scan CTA, User Pill */}
      <div className="flex items-center gap-4">
        <div className="hidden md:flex items-center gap-2 text-xs text-slate-500">
          <Activity className="w-3.5 h-3.5 text-emerald-600" />
          <span>
            OTel Ingestion: <strong className="text-slate-900 tabular-nums font-semibold">12.5k spans/min</strong>
          </span>
        </div>

        <Button
          size="sm"
          variant="primary"
          onClick={onTriggerScan}
          icon={<Plus className="w-3.5 h-3.5" />}
        >
          Simulate PR Scan
        </Button>

        <div className="h-5 w-px bg-slate-200 hidden sm:block" />

        <div className="flex items-center gap-2">
          <div className="text-right hidden sm:block">
            <div className="text-xs font-semibold text-slate-900">{currentUser.username}</div>
            <div className="text-[10px] text-slate-500 font-mono">{currentUser.tenant_id}</div>
          </div>
          <Badge variant="purple" size="sm" className="flex items-center gap-1 font-semibold">
            <Shield className="w-2.5 h-2.5" />
            {currentUser.roles[0] || 'ADMIN'}
          </Badge>
        </div>
      </div>
    </header>
  )
}
