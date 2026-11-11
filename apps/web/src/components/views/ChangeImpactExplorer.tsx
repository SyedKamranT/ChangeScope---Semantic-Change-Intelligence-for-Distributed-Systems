import React from 'react'
import { ImpactGraphView } from '../graph/ImpactGraphView'
import { Badge } from '../ui/Badge'
import { Layers, AlertCircle, CheckCircle2, ShieldCheck, Cpu } from 'lucide-react'

export interface ChangeImpactExplorerProps {
  selectedPR: number
  setSelectedPR: (pr: number) => void
}

export const ChangeImpactExplorer: React.FC<ChangeImpactExplorerProps> = ({
  selectedPR,
  setSelectedPR,
}) => {
  const isDangerous = selectedPR === 142

  return (
    <div className="space-y-6">
      {/* View Header with Scenario Switcher */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
              <Layers className="w-5 h-5 text-slate-700" />
              Change Impact Explorer
            </h1>
            <Badge variant="purple" size="sm">
              Neo4j Projection
            </Badge>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Topological blast radius reasoning combining Tree-sitter AST, OpenAPI schemas, and OTel runtime traces.
          </p>
        </div>

        {/* PR Scenario Switcher */}
        <div className="flex items-center gap-1.5 bg-slate-100 p-1 rounded-xl border border-slate-200">
          <button
            onClick={() => setSelectedPR(142)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer transition-all active:scale-[0.98] ${
              isDangerous
                ? 'bg-red-50 text-red-700 border border-red-200 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <AlertCircle className="w-3.5 h-3.5" />
            <span>PR #142 (Violations)</span>
          </button>
          <button
            onClick={() => setSelectedPR(143)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer transition-all active:scale-[0.98] ${
              !isDangerous
                ? 'bg-emerald-50 text-emerald-800 border border-emerald-200 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>PR #143 (Safe)</span>
          </button>
        </div>
      </div>

      {/* Engine Invariants Strip */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white border border-slate-200/90 rounded-2xl p-3.5 flex items-center justify-between shadow-premium">
          <div>
            <div className="text-[11px] text-slate-500 font-medium">Blast Radius Risk Score</div>
            <div className="text-xl font-bold text-slate-900 mt-0.5 tabular-nums font-mono">
              {isDangerous ? '85 / 100' : '12 / 100'}
            </div>
          </div>
          <Badge variant={isDangerous ? 'danger' : 'success'}>
            {isDangerous ? 'CRITICAL' : 'LOW'}
          </Badge>
        </div>

        <div className="bg-white border border-slate-200/90 rounded-2xl p-3.5 flex items-center justify-between shadow-premium">
          <div>
            <div className="text-[11px] text-slate-500 font-medium">Deterministic Traversal</div>
            <div className="text-sm font-semibold text-slate-900 mt-0.5 flex items-center gap-1.5">
              <Cpu className="w-3.5 h-3.5 text-slate-600" />
              <span>Multi-Hop BFS + Cycle Check</span>
            </div>
          </div>
          <span className="text-[10px] text-slate-500 font-mono">Max Depth: 5</span>
        </div>

        <div className="bg-white border border-slate-200/90 rounded-2xl p-3.5 flex items-center justify-between shadow-premium">
          <div>
            <div className="text-[11px] text-slate-500 font-medium">Grounding Guarantee</div>
            <div className="text-sm font-semibold text-emerald-700 mt-0.5 flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
              <span>Citation Guard: 100% Verified</span>
            </div>
          </div>
          <span className="text-[10px] text-emerald-700 font-mono font-medium">Zero Hallucinations</span>
        </div>
      </div>

      {/* Graph Visualizer */}
      <ImpactGraphView scenarioPR={selectedPR} />
    </div>
  )
}
