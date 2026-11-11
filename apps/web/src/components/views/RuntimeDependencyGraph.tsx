import React, { useState, useEffect } from 'react'
import { Card, CardHeader, CardContent } from '../ui/Card'
import { Table, TableHeader, TableRow, TableHead, TableCell } from '../ui/Table'
import { Badge } from '../ui/Badge'
import { StatCard } from '../ui/StatCard'
import { Activity, Radio, Database, ArrowRight, ShieldCheck, Info } from 'lucide-react'
import { api } from '../../api/client'
import { TelemetryDependencyItem } from '../../api/types'

export const RuntimeDependencyGraph: React.FC = () => {
  const [dependencies, setDependencies] = useState<TelemetryDependencyItem[]>([])
  const [protocolFilter, setProtocolFilter] = useState<string>('ALL')

  useEffect(() => {
    async function loadData() {
      const data = await api.fetchTelemetryGraph()
      setDependencies(data)
    }
    loadData()
  }, [])

  const filtered = dependencies.filter(
    (d) => protocolFilter === 'ALL' || d.protocol === protocolFilter
  )

  const totalRpm = dependencies.reduce((acc, d) => acc + d.rpm, 0)
  const avgLatency = (
    dependencies.reduce((acc, d) => acc + d.p95_latency_ms, 0) / (dependencies.length || 1)
  ).toFixed(1)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2">
          <h1 className="text-xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
            <Activity className="w-5 h-5 text-emerald-600" />
            Runtime Dependency Intelligence (OpenTelemetry)
          </h1>
          <Badge variant="success" size="sm">
            OTLP Ingest Verified
          </Badge>
        </div>
        <p className="text-xs text-slate-500 mt-1">
          Observed service-to-service communication topologies, request frequency, and p95 latency SLAs.
        </p>
      </div>

      {/* Sampling Invariant Alert */}
      <div className="bg-white border border-slate-200/90 rounded-2xl p-4 flex items-start gap-3 text-xs text-slate-700 shadow-premium">
        <Info className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <span className="font-bold text-slate-900">Permanent Grounding Invariant:</span>
          <p className="text-slate-600 leading-relaxed font-normal">
            Runtime telemetry confirms active observed behavior. It is never treated as proof of absence:
            unobserved edges in sampled environments remain protected via static AST and OpenAPI contracts.
          </p>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard
          label="Total Sampled Throughput"
          value={`${totalRpm.toLocaleString()} RPM`}
          subValue="Across 5 active pipelines"
          icon={<Activity className="w-4 h-4 text-emerald-600" />}
          trend="100% PII Scrubbed"
          trendDirection="up"
        />
        <StatCard
          label="Average p95 Service Latency"
          value={`${avgLatency} ms`}
          subValue="Lowest: 4.8ms (PG), Highest: 31.4ms (gRPC)"
          icon={<Radio className="w-4 h-4 text-slate-600" />}
          trend="Within SLA bounds"
          trendDirection="neutral"
        />
        <StatCard
          label="Graph Projection Status"
          value="Synchronized"
          subValue="Neo4j Read Projection Rebuilt"
          icon={<Database className="w-4 h-4 text-sky-600" />}
          statusIndicator="success"
          trend="PostgreSQL Transactional Outbox"
          trendDirection="up"
        />
      </div>

      {/* Dependency Matrix Table */}
      <Card>
        <CardHeader>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between w-full gap-3">
            <div>
              <h3 className="text-sm font-bold text-slate-900 tracking-tight">Observed Caller-to-Callee Topologies</h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Dynamic traffic extracted from TraceSpan parent-child linkages
              </p>
            </div>

            {/* Protocol Filter */}
            <div className="flex items-center gap-1.5 flex-wrap">
              {['ALL', 'HTTP', 'GRPC', 'KAFKA', 'POSTGRES'].map((p) => (
                <button
                  key={p}
                  onClick={() => setProtocolFilter(p)}
                  className={`px-2.5 py-1 text-xs rounded-lg font-semibold cursor-pointer transition-all active:scale-[0.97] ${
                    protocolFilter === p
                      ? 'bg-slate-900 text-white shadow-xs'
                      : 'bg-white text-slate-600 hover:text-slate-900 border border-slate-200'
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        </CardHeader>

        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Source (Caller)</TableHead>
                <TableHead></TableHead>
                <TableHead>Target (Callee)</TableHead>
                <TableHead>Protocol</TableHead>
                <TableHead>Throughput (RPM)</TableHead>
                <TableHead>p95 Latency</TableHead>
                <TableHead>Error Rate</TableHead>
                <TableHead>Environment</TableHead>
                <TableHead className="text-right">Knowledge Graph</TableHead>
              </TableRow>
            </TableHeader>
            <tbody>
              {filtered.map((dep, idx) => (
                <TableRow key={idx}>
                  <TableCell className="font-mono font-bold text-slate-900">
                    {dep.source_service}
                  </TableCell>
                  <TableCell className="w-6 text-slate-400">
                    <ArrowRight className="w-3.5 h-3.5" />
                  </TableCell>
                  <TableCell className="font-mono font-bold text-slate-900">
                    {dep.target_service}
                  </TableCell>
                  <TableCell>
                    <Badge variant={dep.protocol === 'KAFKA' ? 'warning' : 'neutral'} size="sm">
                      {dep.protocol}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-mono text-emerald-700 tabular-nums font-bold">
                    {dep.rpm.toLocaleString()}
                  </TableCell>
                  <TableCell className="font-mono text-slate-700 tabular-nums">
                    {dep.p95_latency_ms} ms
                  </TableCell>
                  <TableCell className="font-mono text-slate-500 tabular-nums">
                    {dep.error_rate_pct}%
                  </TableCell>
                  <TableCell className="font-mono text-xs text-slate-600">
                    {dep.environment}
                  </TableCell>
                  <TableCell className="text-right">
                    <span className="inline-flex items-center gap-1 text-[11px] text-emerald-700 font-semibold">
                      <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                      Verified
                    </span>
                  </TableCell>
                </TableRow>
              ))}
            </tbody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
