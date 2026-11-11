import React from 'react'
import {
  LayoutDashboard,
  GitFork,
  GitBranch,
  GitPullRequest,
  History,
  Layers,
  GitCompare,
  Activity,
  Network,
  Workflow,
  FileCode,
  TestTube,
  Key,
  Users,
  ScrollText,
} from 'lucide-react'
import { clsx } from 'clsx'

export type NavViewKey =
  | 'overview'
  | 'repositories'
  | 'repo_detail'
  | 'pull_requests'
  | 'history'
  | 'impact_explorer'
  | 'semantic_drift'
  | 'runtime_graph'
  | 'ontology'
  | 'workflow_impact'
  | 'evidence'
  | 'test_recommendations'
  | 'integrations'
  | 'team_settings'
  | 'audit_logs'

interface NavItem {
  key: NavViewKey
  label: string
  icon: React.ReactNode
  badge?: string
}

interface NavSection {
  title: string
  items: NavItem[]
}

const NAV_SECTIONS: NavSection[] = [
  {
    title: 'CORE PLATFORM',
    items: [
      { key: 'overview', label: 'Overview Dashboard', icon: <LayoutDashboard className="w-4 h-4" /> },
      { key: 'repositories', label: 'Repositories', icon: <GitFork className="w-4 h-4" /> },
      { key: 'repo_detail', label: 'Repository Detail', icon: <GitBranch className="w-4 h-4" /> },
      { key: 'pull_requests', label: 'Pull Request Review', icon: <GitPullRequest className="w-4 h-4" />, badge: 'PR #142' },
      { key: 'history', label: 'Analysis History', icon: <History className="w-4 h-4" /> },
    ],
  },
  {
    title: 'SEMANTIC INTELLIGENCE',
    items: [
      { key: 'impact_explorer', label: 'Change Impact Explorer', icon: <Layers className="w-4 h-4" />, badge: 'Graph' },
      { key: 'semantic_drift', label: 'Semantic Drift Findings', icon: <GitCompare className="w-4 h-4" /> },
      { key: 'runtime_graph', label: 'Runtime Topology (OTel)', icon: <Activity className="w-4 h-4" /> },
      { key: 'ontology', label: 'Ontology Explorer', icon: <Network className="w-4 h-4" /> },
      { key: 'workflow_impact', label: 'Workflow Impact View', icon: <Workflow className="w-4 h-4" /> },
      { key: 'evidence', label: 'Evidence Explorer', icon: <FileCode className="w-4 h-4" /> },
      { key: 'test_recommendations', label: 'Test Recommendations', icon: <TestTube className="w-4 h-4" />, badge: 'AI' },
    ],
  },
  {
    title: 'GOVERNANCE & ADMIN',
    items: [
      { key: 'integrations', label: 'Integrations', icon: <Key className="w-4 h-4" /> },
      { key: 'team_settings', label: 'Workspaces & RBAC', icon: <Users className="w-4 h-4" /> },
      { key: 'audit_logs', label: 'Security Audit Logs', icon: <ScrollText className="w-4 h-4" /> },
    ],
  },
]

export interface AppSidebarProps {
  activeView: NavViewKey
  onSelectView: (view: NavViewKey) => void
}

export const AppSidebar: React.FC<AppSidebarProps> = ({ activeView, onSelectView }) => {
  return (
    <aside className="w-64 bg-[#fbfbfd] border-r border-slate-200 flex flex-col shrink-0 select-none shadow-2xs">
      <div className="flex-1 overflow-y-auto py-4 px-3 space-y-6">
        {NAV_SECTIONS.map((section) => (
          <div key={section.title} className="space-y-1">
            <div className="px-3 py-1 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
              {section.title}
            </div>
            {section.items.map((item) => {
              const isActive = activeView === item.key
              return (
                <button
                  key={item.key}
                  onClick={() => onSelectView(item.key)}
                  className={clsx(
                    'w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium cursor-pointer',
                    'transition-all duration-140 ease-[cubic-bezier(0.16,1,0.3,1)] active:scale-[0.98]',
                    isActive
                      ? 'bg-white text-slate-900 border border-slate-200 shadow-xs font-semibold'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100/60 border border-transparent'
                  )}
                >
                  <div className="flex items-center gap-2.5 truncate">
                    <span className={clsx(isActive ? 'text-slate-900' : 'text-slate-400')}>
                      {item.icon}
                    </span>
                    <span className="truncate">{item.label}</span>
                  </div>
                  {item.badge && (
                    <span
                      className={clsx(
                        'text-[10px] px-1.5 py-0.2 rounded font-mono font-medium',
                        item.badge === 'PR #142'
                          ? 'bg-red-50 text-red-700 border border-red-200'
                          : 'bg-slate-100 text-slate-700 border border-slate-200'
                      )}
                    >
                      {item.badge}
                    </span>
                  )}
                </button>
              )
            })}
          </div>
        ))}
      </div>

      {/* Footer / Tenant Environment Status */}
      <div className="p-3.5 border-t border-slate-200 bg-white text-[11px] text-slate-500">
        <div className="flex items-center justify-between">
          <span>Env: <strong className="text-slate-900 font-semibold">Production</strong></span>
          <span className="text-emerald-700 flex items-center gap-1.5 font-mono text-[10px] font-semibold">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            Operational
          </span>
        </div>
      </div>
    </aside>
  )
}
