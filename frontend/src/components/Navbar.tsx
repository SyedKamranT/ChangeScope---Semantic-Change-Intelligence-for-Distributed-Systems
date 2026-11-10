import React from 'react'
import { ShieldCheck, Database, Activity, Plus } from 'lucide-react'

interface NavbarProps {
  onOpenTriggerModal: () => void
}

export const Navbar: React.FC<NavbarProps> = ({ onOpenTriggerModal }) => {
  return (
    <header className="border-b border-border bg-[#090d16]/90 backdrop-blur-md sticky top-0 z-50 px-6 py-3.5 flex items-center justify-between">
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center shadow-lg shadow-blue-500/20">
            <ShieldCheck className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="font-bold text-base tracking-tight text-white flex items-center gap-2">
              ChangeScope
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">
                v0.1.0
              </span>
            </div>
            <div className="text-[11px] text-slate-400 font-medium">Semantic Change Intelligence</div>
          </div>
        </div>

        <div className="hidden md:flex items-center gap-2 px-3 py-1 bg-card rounded-md border border-border text-xs text-slate-300">
          <Database className="w-3.5 h-3.5 text-blue-400" />
          <span>Workspace: <strong className="text-white">Core Platform</strong></span>
          <span className="text-slate-500">•</span>
          <span className="text-emerald-400 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 inline-block" />
            Postgres + Neo4j Synced
          </span>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="hidden sm:flex items-center gap-2 text-xs text-slate-400 mr-2">
          <Activity className="w-3.5 h-3.5 text-emerald-400" />
          <span>OTel Ingest: <strong className="text-slate-200">12.5k spans/min</strong></span>
        </div>

        <button
          onClick={onOpenTriggerModal}
          className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold px-3.5 py-2 rounded-lg transition-colors shadow-md shadow-blue-600/20 cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          <span>Simulate PR Scan</span>
        </button>
      </div>
    </header>
  )
}
