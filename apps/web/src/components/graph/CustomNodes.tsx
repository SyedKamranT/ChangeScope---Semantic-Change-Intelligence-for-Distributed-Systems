import { memo } from 'react'
import { Handle, Position } from '@xyflow/react'
import { Server, Database, Radio } from 'lucide-react'
import { clsx } from 'clsx'

export interface ServiceNodeData {
  label: string
  serviceName: string
  tier: string
  is_origin?: boolean
  riskLevel?: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
  rpm?: number
  hop?: number
}

export const ServiceNode = memo(({ data, selected }: { data: ServiceNodeData; selected?: boolean }) => {
  const isOrigin = data.is_origin
  const riskBorder =
    data.riskLevel === 'CRITICAL' || isOrigin
      ? 'border-red-500 shadow-sm shadow-red-500/10'
      : data.riskLevel === 'HIGH'
      ? 'border-amber-400'
      : 'border-slate-200'

  return (
    <div
      className={clsx(
        'px-3.5 py-2.5 rounded-xl bg-white border text-xs text-slate-900 min-w-[190px]',
        'transition-all duration-140 shadow-premium',
        selected && 'ring-2 ring-slate-900 ring-offset-2 ring-offset-white',
        riskBorder
      )}
    >
      <Handle type="target" position={Position.Top} className="!bg-slate-800 !w-2 !h-2" />

      <div className="flex items-center justify-between gap-2 mb-1.5">
        <div className="flex items-center gap-1.5 text-slate-800">
          <Server className="w-3.5 h-3.5 text-slate-700" />
          <span className="font-mono font-semibold text-[11px] truncate">{data.serviceName}</span>
        </div>
        {isOrigin ? (
          <span className="text-[9px] font-bold px-1.5 py-0.2 rounded bg-red-50 text-red-700 border border-red-200">
            TARGET
          </span>
        ) : (
          data.hop !== undefined && (
            <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-slate-100 text-slate-700 border border-slate-200">
              HOP {data.hop}
            </span>
          )
        )}
      </div>

      <div className="text-[10px] text-slate-500 flex items-center justify-between pt-1 border-t border-slate-100">
        <span>{data.tier}</span>
        {data.rpm !== undefined && (
          <span className="font-mono text-emerald-700 tabular-nums font-semibold">
            {data.rpm.toLocaleString()} RPM
          </span>
        )}
      </div>

      <Handle type="source" position={Position.Bottom} className="!bg-slate-800 !w-2 !h-2" />
    </div>
  )
})
ServiceNode.displayName = 'ServiceNode'

export const DatabaseNode = memo(({ data, selected }: { data: { label: string; tableCount?: number }; selected?: boolean }) => {
  return (
    <div
      className={clsx(
        'px-3.5 py-2.5 rounded-xl bg-white border border-sky-300 text-xs text-slate-900 min-w-[170px] shadow-premium',
        selected && 'ring-2 ring-sky-500 ring-offset-2 ring-offset-white'
      )}
    >
      <Handle type="target" position={Position.Top} className="!bg-sky-600 !w-2 !h-2" />
      <div className="flex items-center gap-2">
        <Database className="w-3.5 h-3.5 text-sky-600" />
        <div>
          <div className="font-mono font-semibold text-[11px] text-slate-900">{data.label}</div>
          <div className="text-[10px] text-slate-500">PostgreSQL Relational DB</div>
        </div>
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-sky-600 !w-2 !h-2" />
    </div>
  )
})
DatabaseNode.displayName = 'DatabaseNode'

export const EndpointNode = memo(({ data }: { data: { method: string; path: string } }) => {
  return (
    <div className="px-3 py-1.5 rounded-lg bg-white border border-blue-200 text-[11px] text-slate-800 flex items-center gap-2 shadow-xs">
      <Handle type="target" position={Position.Left} className="!bg-blue-600" />
      <span className="font-bold text-[9px] px-1 rounded bg-blue-50 text-blue-700 border border-blue-200">
        {data.method}
      </span>
      <span className="font-mono text-slate-700">{data.path}</span>
      <Handle type="source" position={Position.Right} className="!bg-blue-600" />
    </div>
  )
})
EndpointNode.displayName = 'EndpointNode'

export const EventNode = memo(({ data }: { data: { topic: string; broker: string } }) => {
  return (
    <div className="px-3 py-1.5 rounded-lg bg-white border border-amber-300 text-[11px] text-slate-800 flex items-center gap-2 shadow-xs">
      <Handle type="target" position={Position.Left} className="!bg-amber-600" />
      <Radio className="w-3 h-3 text-amber-600" />
      <span className="font-mono text-slate-800 font-medium">{data.topic}</span>
      <Handle type="source" position={Position.Right} className="!bg-amber-600" />
    </div>
  )
})
EventNode.displayName = 'EventNode'
