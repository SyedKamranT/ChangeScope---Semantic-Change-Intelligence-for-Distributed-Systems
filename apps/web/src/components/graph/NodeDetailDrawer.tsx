import React from 'react'
import { Drawer } from '../ui/Drawer'
import { Badge } from '../ui/Badge'
import { Server, Activity, FileCode, ArrowDownRight, ArrowUpRight, ShieldCheck } from 'lucide-react'

export interface SelectedNodeDetail {
  id: string
  name: string
  urn: string
  type: string
  tier: string
  isTarget: boolean
  riskScore: number
  riskLevel: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
  rpm: number
  p95LatencyMs: number
  callers: { name: string; protocol: string; rpm: number }[]
  consumers: { name: string; protocol: string; rpm: number }[]
  evidenceCitations: { identifier: string; path: string; lines: string }[]
}

export interface NodeDetailDrawerProps {
  node: SelectedNodeDetail | null
  onClose: () => void
}

export const NodeDetailDrawer: React.FC<NodeDetailDrawerProps> = ({ node, onClose }) => {
  if (!node) return null

  return (
    <Drawer
      isOpen={Boolean(node)}
      onClose={onClose}
      title={node.name}
      subtitle={node.urn}
      width="md"
    >
      {/* Risk and Origin Header */}
      <div className="bg-slate-50 border border-slate-200/90 rounded-xl p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Server className="w-4 h-4 text-slate-700" />
            <span className="text-xs font-bold text-slate-900">{node.type}</span>
          </div>
          <Badge
            variant={
              node.riskLevel === 'CRITICAL'
                ? 'danger'
                : node.riskLevel === 'HIGH'
                ? 'warning'
                : 'success'
            }
          >
            {node.riskLevel} RISK ({node.riskScore}/100)
          </Badge>
        </div>

        <div className="grid grid-cols-2 gap-3 text-xs pt-2 border-t border-slate-200/80">
          <div>
            <span className="text-slate-500 text-[11px] font-medium">Role in PR:</span>
            <div className="font-semibold text-slate-800 mt-0.5">
              {node.isTarget ? 'Direct Change Target (Origin)' : 'Downstream Dependent Consumer'}
            </div>
          </div>
          <div>
            <span className="text-slate-500 text-[11px] font-medium">Criticality Tier:</span>
            <div className="font-semibold text-slate-800 mt-0.5">{node.tier}</div>
          </div>
        </div>
      </div>

      {/* Observed Runtime Telemetry */}
      <div className="space-y-2.5">
        <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-1.5">
          <Activity className="w-3.5 h-3.5 text-emerald-600" />
          <span>OpenTelemetry Observed Traffic</span>
        </h4>
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-xs">
            <div className="text-[11px] text-slate-500 font-medium">7-Day Observed Volume</div>
            <div className="text-lg font-bold text-slate-900 mt-1 tabular-nums font-mono">
              {node.rpm.toLocaleString()} RPM
            </div>
          </div>
          <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-xs">
            <div className="text-[11px] text-slate-500 font-medium">p95 Latency SLA</div>
            <div className="text-lg font-bold text-slate-900 mt-1 tabular-nums font-mono">
              {node.p95LatencyMs} ms
            </div>
          </div>
        </div>
      </div>

      {/* Upstream Direct Callers */}
      <div className="space-y-2.5">
        <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-1.5">
          <ArrowDownRight className="w-3.5 h-3.5 text-blue-600" />
          <span>Upstream Callers ({node.callers.length})</span>
        </h4>
        {node.callers.length === 0 ? (
          <p className="text-xs text-slate-400 italic">No incoming calls in observed topology.</p>
        ) : (
          <div className="space-y-1.5">
            {node.callers.map((c, i) => (
              <div
                key={i}
                className="bg-white border border-slate-200 rounded-lg p-2.5 flex items-center justify-between text-xs shadow-xs"
              >
                <span className="font-mono text-slate-800 font-medium">{c.name}</span>
                <div className="flex items-center gap-2">
                  <Badge variant="neutral" size="sm">
                    {c.protocol}
                  </Badge>
                  <span className="font-mono text-emerald-700 text-[11px] tabular-nums font-semibold">
                    {c.rpm.toLocaleString()} RPM
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Downstream Consumers */}
      <div className="space-y-2.5">
        <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-1.5">
          <ArrowUpRight className="w-3.5 h-3.5 text-amber-600" />
          <span>Downstream Consumers ({node.consumers.length})</span>
        </h4>
        {node.consumers.length === 0 ? (
          <p className="text-xs text-slate-400 italic">No downstream consumers.</p>
        ) : (
          <div className="space-y-1.5">
            {node.consumers.map((c, i) => (
              <div
                key={i}
                className="bg-white border border-slate-200 rounded-lg p-2.5 flex items-center justify-between text-xs shadow-xs"
              >
                <span className="font-mono text-slate-800 font-medium">{c.name}</span>
                <div className="flex items-center gap-2">
                  <Badge variant="neutral" size="sm">
                    {c.protocol}
                  </Badge>
                  <span className="font-mono text-emerald-700 text-[11px] tabular-nums font-semibold">
                    {c.rpm.toLocaleString()} RPM
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Evidence Citations */}
      <div className="space-y-2.5 pt-2 border-t border-slate-200">
        <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-1.5">
          <FileCode className="w-3.5 h-3.5 text-slate-700" />
          <span>Verified Evidence Grounding</span>
        </h4>
        <div className="space-y-2">
          {node.evidenceCitations.map((evi, i) => (
            <div
              key={i}
              className="bg-white border border-slate-200 rounded-lg p-3 text-xs space-y-1 shadow-xs"
            >
              <div className="flex items-center justify-between">
                <span className="font-semibold text-slate-800">{evi.identifier}</span>
                <span className="flex items-center gap-1 text-[10px] text-emerald-700 font-medium">
                  <ShieldCheck className="w-3 h-3 text-emerald-600" />
                  Grounded
                </span>
              </div>
              <div className="text-[11px] text-blue-700 font-mono">
                {evi.path}:{evi.lines}
              </div>
            </div>
          ))}
        </div>
      </div>
    </Drawer>
  )
}
