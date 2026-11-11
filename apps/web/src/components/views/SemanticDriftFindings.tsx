import React, { useState, useEffect } from 'react'
import { Card, CardHeader, CardContent } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { GitCompare, AlertTriangle, ShieldCheck, Network } from 'lucide-react'
import { api } from '../../api/client'
import { SemanticDriftItem } from '../../api/types'

export const SemanticDriftFindings: React.FC = () => {
  const [drifts, setDrifts] = useState<SemanticDriftItem[]>([])

  useEffect(() => {
    async function loadData() {
      const data = await api.fetchSemanticDrift()
      setDrifts(data)
    }
    loadData()
  }, [])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2">
          <h1 className="text-xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
            <GitCompare className="w-5 h-5 text-amber-600" />
            Semantic Drift & Meaning Collisions
          </h1>
          <Badge variant="warning" size="sm">
            NVIDIA Auto-Ontology + Static Rule Engine
          </Badge>
        </div>
        <p className="text-xs text-slate-500 mt-1">
          Detecting subtle behavioral and business concept shifts that pass strict syntactic schema parsers.
        </p>
      </div>

      {/* Drift Findings List */}
      <div className="space-y-4">
        {drifts.map((item) => (
          <Card key={item.id} hoverEffect className="space-y-4">
            <CardHeader className="bg-slate-50/70">
              <div className="flex items-center gap-2.5 flex-wrap">
                <span className="font-mono text-xs font-bold text-slate-900">{item.entity_urn}</span>
                <Badge
                  variant={
                    item.difference_type === 'ENUM_NARROWED'
                      ? 'danger'
                      : item.difference_type === 'UNIT_SHIFT'
                      ? 'warning'
                      : 'info'
                  }
                >
                  {item.difference_type}
                </Badge>
              </div>

              <div className="flex items-center gap-2 text-xs">
                <span className="text-slate-500 font-medium">Concept:</span>
                <Badge variant="purple" size="sm" className="flex items-center gap-1 font-semibold">
                  <Network className="w-3 h-3" />
                  {item.business_concept}
                </Badge>
                <span className="text-emerald-700 font-mono text-[11px] tabular-nums font-bold">
                  {(item.confidence * 100).toFixed(0)}% Confidence
                </span>
              </div>
            </CardHeader>

            <CardContent className="space-y-4 pt-0">
              {/* Impact summary */}
              <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-900 flex items-start gap-2.5">
                <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                <span className="leading-relaxed font-medium">{item.impact_summary}</span>
              </div>

              {/* Side-by-side Before & After comparison */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-slate-400" />
                    <span>Before (Base Contract)</span>
                  </div>
                  <div className="bg-slate-50 border border-slate-200/90 rounded-xl p-3 text-xs font-mono text-slate-800 shadow-xs">
                    <pre className="whitespace-pre-wrap">{item.before_definition}</pre>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <div className="text-[11px] font-semibold text-red-600 uppercase tracking-wider flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-red-500" />
                    <span>After (Proposed Drift)</span>
                  </div>
                  <div className="bg-red-50/70 border border-red-200 rounded-xl p-3 text-xs font-mono text-red-800 shadow-xs">
                    <pre className="whitespace-pre-wrap">{item.after_definition}</pre>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between pt-2 border-t border-slate-100 text-[11px] text-slate-500 font-medium">
                <span>Observed: {new Date(item.detected_at).toLocaleString()}</span>
                <span className="flex items-center gap-1 text-emerald-700 font-semibold">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                  Grounded with AST Symbol Citation
                </span>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
