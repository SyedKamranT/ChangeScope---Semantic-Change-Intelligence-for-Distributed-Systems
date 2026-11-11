import React, { useState, useEffect } from 'react'
import { StatCard } from '../ui/StatCard'
import { Card, CardHeader, CardContent } from '../ui/Card'
import { Table, TableHeader, TableRow, TableHead, TableCell } from '../ui/Table'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import {
  AlertTriangle,
  Activity,
  ArrowRight,
  Plus,
  Play,
  FileCheck,
  Server,
} from 'lucide-react'
import { api } from '../../api/client'
import { ScanRunItem, RepositoryItem, TelemetryDependencyItem } from '../../api/types'
import { NavViewKey } from '../layout/AppSidebar'
import { motion } from 'motion/react'

export interface OverviewDashboardProps {
  onNavigate: (view: NavViewKey) => void
  onTriggerScan: () => void
  onRegisterRepo: () => void
}

export const OverviewDashboard: React.FC<OverviewDashboardProps> = ({
  onNavigate,
  onTriggerScan,
  onRegisterRepo,
}) => {
  const [scans, setScans] = useState<ScanRunItem[]>([])
  const [repos, setRepos] = useState<RepositoryItem[]>([])
  const [telemetry, setTelemetry] = useState<TelemetryDependencyItem[]>([])

  useEffect(() => {
    async function loadData() {
      try {
        const [scansData, reposData, telemetryData] = await Promise.all([
          api.fetchScans(),
          api.fetchRepositories(),
          api.fetchTelemetryGraph(),
        ])
        setScans(scansData)
        setRepos(reposData)
        setTelemetry(telemetryData)
      } catch (err) {
        console.error('Error loading dashboard data', err)
      }
    }
    loadData()
  }, [])

  const criticalScans = scans.filter((s) => s.risk_level === 'CRITICAL' || s.risk_level === 'HIGH')
  const totalViolations = scans.reduce(
    (acc, s) => acc + s.blocking_violations_count + s.warning_violations_count,
    0
  )

  return (
    <div className="space-y-6">
      {/* Page Title & Quick Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900">System Intelligence Overview</h1>
          <p className="text-xs text-slate-500 mt-1">
            Real-time semantic contract intelligence and runtime dependency blast radius.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <Button size="sm" variant="outline" onClick={onRegisterRepo} icon={<Plus className="w-3.5 h-3.5" />}>
            Register Repo
          </Button>
          <Button size="sm" variant="primary" onClick={onTriggerScan} icon={<Play className="w-3.5 h-3.5 fill-current" />}>
            Simulate PR Scan
          </Button>
        </div>
      </div>

      {/* High-Risk Finding Alert Banner */}
      {criticalScans.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-red-50/80 border border-red-200 rounded-2xl p-4 flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-xs"
        >
          <div className="flex items-start gap-3">
            <div className="p-2 rounded-xl bg-red-100 text-red-700 shrink-0">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-red-950">
                  High-Risk Semantic Breaking Change Detected in PR #142
                </h3>
                <Badge variant="danger" size="sm">
                  CRITICAL (Score: 85/100)
                </Badge>
              </div>
              <p className="text-xs text-slate-700 mt-1 max-w-2xl leading-relaxed">
                Repository <code className="font-mono text-slate-900 font-semibold">inventory-service</code> removed enum value{' '}
                <code className="text-red-700 font-mono font-semibold">'CANCELLED'</code>. Consumer{' '}
                <code className="font-mono text-slate-900 font-semibold">checkout-service</code> processes 12.5k RPM and will crash on deserialization.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <Button
              size="sm"
              variant="danger"
              onClick={() => onNavigate('impact_explorer')}
              icon={<ArrowRight className="w-3.5 h-3.5" />}
            >
              Inspect Blast Radius
            </Button>
          </div>
        </motion.div>
      )}

      {/* Stat Cards Grid with Staggered Cascades */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Registered Repositories"
          value={repos.length}
          subValue="Active in Core Platform"
          icon={<Server className="w-4 h-4 text-slate-500" />}
          trend="+1 added today"
          trendDirection="up"
        />
        <StatCard
          label="Contract Scans Executed"
          value={scans.length}
          subValue="Across 4 microservices"
          icon={<FileCheck className="w-4 h-4 text-emerald-600" />}
          trend="100% deterministic AST"
          trendDirection="neutral"
        />
        <StatCard
          label="Detected Violations"
          value={totalViolations}
          subValue="3 blocking • 3 warnings"
          icon={<AlertTriangle className="w-4 h-4 text-red-600" />}
          statusIndicator="danger"
          trend="Action required on PR #142"
          trendDirection="down"
        />
        <StatCard
          label="OTel Observed Dependencies"
          value={telemetry.length}
          subValue="5 verified edge protocols"
          icon={<Activity className="w-4 h-4 text-emerald-600" />}
          trend="12.5k spans/min sampled"
          trendDirection="up"
        />
      </div>

      {/* Two-Column Grid: Recent Scans Table & Discovered Runtime Mesh */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Recent Scans */}
        <div className="lg:col-span-8">
          <Card>
            <CardHeader>
              <div>
                <h3 className="text-sm font-bold text-slate-900 tracking-tight">Recent Change Analyses</h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Semantic scans across pull requests and target branches
                </p>
              </div>
              <Button size="sm" variant="ghost" onClick={() => onNavigate('history')}>
                View All Scans
              </Button>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Target Repository</TableHead>
                    <TableHead>Branches / SHA</TableHead>
                    <TableHead>Risk Level</TableHead>
                    <TableHead>Violations</TableHead>
                    <TableHead>Duration</TableHead>
                    <TableHead className="text-right">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <tbody>
                  {scans.slice(0, 5).map((scan) => (
                    <TableRow key={scan.id}>
                      <TableCell className="font-mono font-semibold text-slate-900">
                        {scan.repository_name || scan.repository_id}
                      </TableCell>
                      <TableCell className="font-mono text-[11px] text-slate-500">
                        {scan.source_branch} → {scan.target_branch}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={
                            scan.risk_level === 'CRITICAL'
                              ? 'danger'
                              : scan.risk_level === 'HIGH'
                              ? 'warning'
                              : 'success'
                          }
                        >
                          {scan.risk_level || 'UNKNOWN'} ({scan.risk_score || 0})
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {scan.blocking_violations_count > 0 ? (
                          <span className="text-red-700 font-semibold">
                            {scan.blocking_violations_count} blocking
                          </span>
                        ) : (
                          <span className="text-emerald-700 font-medium">Clean</span>
                        )}
                      </TableCell>
                      <TableCell className="font-mono text-slate-600 tabular-nums">
                        {scan.duration_ms}ms
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => onNavigate('pull_requests')}
                        >
                          Inspect
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </tbody>
              </Table>
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Runtime Dependency Quick Summary */}
        <div className="lg:col-span-4 space-y-4">
          <Card>
            <CardHeader>
              <div>
                <h3 className="text-sm font-bold text-slate-900 tracking-tight">Observed Topology</h3>
                <p className="text-xs text-slate-500 mt-0.5">Live OpenTelemetry service communication</p>
              </div>
              <Button size="sm" variant="ghost" onClick={() => onNavigate('runtime_graph')}>
                Graph
              </Button>
            </CardHeader>
            <CardContent className="space-y-3">
              {telemetry.map((dep, idx) => (
                <div
                  key={idx}
                  className="bg-slate-50 border border-slate-200/90 rounded-xl p-3 text-xs space-y-1.5 shadow-2xs hover:bg-slate-100/60 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-slate-900 font-semibold">
                      {dep.source_service} → {dep.target_service}
                    </span>
                    <Badge variant="neutral" size="sm">
                      {dep.protocol}
                    </Badge>
                  </div>
                  <div className="flex items-center justify-between text-[11px] text-slate-500 font-mono">
                    <span className="text-emerald-700 font-bold tabular-nums">
                      {dep.rpm.toLocaleString()} RPM
                    </span>
                    <span>p95: {dep.p95_latency_ms}ms</span>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
