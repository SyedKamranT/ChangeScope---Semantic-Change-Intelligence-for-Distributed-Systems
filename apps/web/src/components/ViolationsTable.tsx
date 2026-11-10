import React from 'react'
import { AlertCircle, AlertTriangle, Info, Code } from 'lucide-react'

export interface ViolationItem {
  id: string
  rule_code: string
  severity: 'BLOCKING' | 'WARNING' | 'INFO'
  file_path: string
  start_line: number
  end_line: number
  message: string
  impacted_service?: string
}

interface ViolationsTableProps {
  violations: ViolationItem[]
}

export const ViolationsTable: React.FC<ViolationsTableProps> = ({ violations }) => {
  if (violations.length === 0) {
    return (
      <div className="bg-card border border-border rounded-xl p-8 text-center">
        <div className="w-12 h-12 rounded-full bg-emerald-500/10 text-emerald-400 mx-auto flex items-center justify-center mb-3">
          <Info className="w-6 h-6" />
        </div>
        <h3 className="text-sm font-semibold text-white">No Semantic Violations Detected</h3>
        <p className="text-xs text-slate-400 mt-1 max-w-sm mx-auto">
          All changed contracts and database migrations are 100% backward-compatible with active consumers.
        </p>
      </div>
    )
  }

  return (
    <div className="bg-card border border-border rounded-xl overflow-hidden">
      <div className="px-5 py-4 border-b border-border flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            Semantic Contract & Database Violations
            <span className="bg-red-500/10 text-red-400 text-xs px-2 py-0.5 rounded-full border border-red-500/20">
              {violations.length} Detected
            </span>
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Structurally compatible changes that will trigger runtime contract breaches
          </p>
        </div>
      </div>

      <div className="divide-y divide-border overflow-x-auto">
        {violations.map((v) => (
          <div key={v.id} className="p-4 hover:bg-slate-800/20 transition-colors">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                {v.severity === 'BLOCKING' ? (
                  <div className="p-1.5 rounded bg-red-500/10 text-red-400 border border-red-500/20 mt-0.5">
                    <AlertCircle className="w-4 h-4" />
                  </div>
                ) : (
                  <div className="p-1.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 mt-0.5">
                    <AlertTriangle className="w-4 h-4" />
                  </div>
                )}

                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono text-xs font-semibold text-white">{v.rule_code}</span>
                    <span
                      className={`text-[10px] font-bold px-1.5 py-0.5 rounded uppercase ${
                        v.severity === 'BLOCKING'
                          ? 'bg-red-500/10 text-red-400 border border-red-500/20'
                          : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                      }`}
                    >
                      {v.severity}
                    </span>
                    {v.impacted_service && (
                      <span className="text-[11px] text-slate-400 bg-slate-800/80 px-2 py-0.5 rounded border border-slate-700">
                        Breaks: <strong className="text-slate-200">{v.impacted_service}</strong>
                      </span>
                    )}
                  </div>

                  <p className="text-xs text-slate-300 mt-1.5 leading-relaxed">{v.message}</p>

                  <div className="flex items-center gap-2 mt-2 text-[11px] text-slate-400 font-mono">
                    <Code className="w-3.5 h-3.5 text-slate-500" />
                    <span className="text-blue-400 hover:underline cursor-pointer">
                      {v.file_path}:{v.start_line}-{v.end_line}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
