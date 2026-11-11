import React, { useState, useEffect } from 'react'
import { Card, CardHeader, CardContent } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { Workflow, AlertTriangle, CheckCircle2, ChevronRight, User } from 'lucide-react'
import { api } from '../../api/client'
import { WorkflowItem } from '../../api/types'

export const WorkflowImpactView: React.FC = () => {
  const [workflows, setWorkflows] = useState<WorkflowItem[]>([])

  useEffect(() => {
    async function loadData() {
      const data = await api.fetchWorkflows()
      setWorkflows(data)
    }
    loadData()
  }, [])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2">
          <h1 className="text-xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
            <Workflow className="w-5 h-5 text-slate-700" />
            Business Workflow Impact Reasoning
          </h1>
          <Badge variant="purple" size="sm">
            Topological Path Mapping
          </Badge>
        </div>
        <p className="text-xs text-slate-500 mt-1">
          Evaluating which end-to-end customer and operational workflows are impacted by proposed contract shifts.
        </p>
      </div>

      {/* Workflows List */}
      <div className="space-y-4">
        {workflows.map((wf) => (
          <Card key={wf.id} hoverEffect className="space-y-4">
            <CardHeader className="bg-slate-50/70">
              <div className="flex items-center gap-3">
                <div
                  className={`p-2 rounded-xl ${
                    wf.disrupted_by_recent_scans
                      ? 'bg-red-50 text-red-700 border border-red-200'
                      : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                  }`}
                >
                  <Workflow className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-900 tracking-tight">{wf.name}</h3>
                  <div className="text-[11px] text-slate-500 flex items-center gap-2 mt-0.5">
                    <span className="font-mono">{wf.id}</span>
                    <span>•</span>
                    <span className="flex items-center gap-1 font-medium">
                      <User className="w-3 h-3 text-slate-400" />
                      Owner: <strong className="text-slate-800 font-mono">{wf.owner}</strong>
                    </span>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <Badge
                  variant={wf.criticality === 'TIER_1_CRITICAL' ? 'danger' : 'neutral'}
                  size="sm"
                >
                  {wf.criticality}
                </Badge>
                {wf.disrupted_by_recent_scans ? (
                  <Badge variant="danger" size="sm" className="flex items-center gap-1 font-semibold">
                    <AlertTriangle className="w-3 h-3" />
                    DISRUPTED BY PR #142
                  </Badge>
                ) : (
                  <Badge variant="success" size="sm" className="flex items-center gap-1 font-semibold">
                    <CheckCircle2 className="w-3 h-3" />
                    OPERATIONAL
                  </Badge>
                )}
              </div>
            </CardHeader>

            <CardContent className="space-y-4 pt-0">
              {wf.disruption_reason && (
                <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-xs text-red-800 flex items-start gap-2.5">
                  <AlertTriangle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
                  <span className="font-medium leading-relaxed">{wf.disruption_reason}</span>
                </div>
              )}

              {/* Step by step pipeline visualization */}
              <div className="space-y-1.5">
                <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-2">
                  Workflow Execution Pipeline
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  {wf.steps.map((step, idx) => {
                    const isDisruptedStep =
                      wf.disrupted_by_recent_scans &&
                      (step.service === 'inventory-service' || step.service === 'checkout-service')

                    return (
                      <React.Fragment key={step.step_index}>
                        <div
                          className={`p-3 rounded-xl border text-xs min-w-[150px] shadow-xs ${
                            isDisruptedStep
                              ? 'bg-red-50/80 border-red-300 text-red-900'
                              : 'bg-slate-50 border-slate-200 text-slate-800'
                          }`}
                        >
                          <div className="flex items-center justify-between text-[10px] text-slate-500 font-mono mb-1 font-semibold">
                            <span>STEP 0{step.step_index}</span>
                            {isDisruptedStep && (
                              <span className="text-red-700 font-bold">BREACH</span>
                            )}
                          </div>
                          <div className="font-mono font-bold truncate text-slate-900">{step.service}</div>
                          <div className="text-[10px] text-slate-500 truncate mt-0.5 font-mono">
                            {step.operation}
                          </div>
                        </div>

                        {idx < wf.steps.length - 1 && (
                          <ChevronRight className="w-4 h-4 text-slate-400 shrink-0" />
                        )}
                      </React.Fragment>
                    )
                  })}
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
