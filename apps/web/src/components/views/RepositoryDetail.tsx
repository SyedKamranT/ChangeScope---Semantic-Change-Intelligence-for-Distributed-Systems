import React, { useState, useEffect } from 'react'
import { Card, CardHeader, CardContent } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Table, TableHeader, TableRow, TableHead, TableCell } from '../ui/Table'
import {
  GitBranch,
  FileCode,
  Play,
  ArrowLeft,
  Layers,
} from 'lucide-react'
import { api } from '../../api/client'
import { RepositoryItem, ScanRunItem } from '../../api/types'
import { NavViewKey } from '../layout/AppSidebar'

export interface RepositoryDetailProps {
  repoId?: string
  onNavigate: (view: NavViewKey) => void
  onTriggerScan: (repoName: string) => void
}

export const RepositoryDetail: React.FC<RepositoryDetailProps> = ({
  repoId = 'repo-inventory',
  onNavigate,
  onTriggerScan,
}) => {
  const [repo, setRepo] = useState<RepositoryItem | null>(null)
  const [scans, setScans] = useState<ScanRunItem[]>([])

  useEffect(() => {
    async function loadData() {
      const allRepos = await api.fetchRepositories()
      const current = allRepos.find((r) => r.id === repoId) || allRepos[0]
      setRepo(current)

      const allScans = await api.fetchScans(current?.id)
      setScans(allScans)
    }
    loadData()
  }, [repoId])

  if (!repo) {
    return <div className="text-xs text-slate-500">Loading repository details...</div>
  }

  const contracts = [
    {
      name: 'OpenAPI 3.1 Service Specification',
      file: 'docs/api/openapi.json',
      type: 'REST API',
      operations: 14,
      lastUpdated: '2026-11-10',
    },
    {
      name: 'AsyncAPI 2.6 Event Channel',
      file: 'docs/events/order-events.yaml',
      type: 'KAFKA',
      operations: 4,
      lastUpdated: '2026-11-08',
    },
    {
      name: 'PostgreSQL Relational Schema (Alembic DDL)',
      file: 'migrations/versions/v2_shrink_sku.sql',
      type: 'DATABASE_DDL',
      operations: 8,
      lastUpdated: '2026-11-11',
    },
  ]

  const symbols = [
    { name: 'process_order_state_change', type: 'Function', file: 'src/api/routes.py', lines: '45-92' },
    { name: 'OrderStatus', type: 'EnumSchema', file: 'src/api/schemas/order.py', lines: '42-48' },
    { name: 'InventoryItemRecord', type: 'ORM Model', file: 'src/models/inventory.py', lines: '18-64' },
    { name: 'reserve_warehouse_stock', type: 'Function', file: 'src/services/stock.py', lines: '102-140' },
  ]

  return (
    <div className="space-y-6">
      {/* Back button and Header */}
      <div>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => onNavigate('repositories')}
          icon={<ArrowLeft className="w-3.5 h-3.5" />}
          className="mb-3"
        >
          Back to Repositories
        </Button>

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-slate-100 border border-slate-200 flex items-center justify-center text-slate-700 shadow-2xs">
              <GitBranch className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-bold text-slate-900 font-mono tracking-tight">{repo.name}</h1>
                <Badge variant={repo.tier === 'TIER_1_CRITICAL' ? 'danger' : 'neutral'}>
                  {repo.tier}
                </Badge>
              </div>
              <div className="text-xs text-slate-500 mt-0.5 flex items-center gap-2">
                <span className="font-mono">{repo.clone_url}</span>
                <span>•</span>
                <span>Default: <code className="text-blue-700 font-mono font-medium">{repo.default_branch}</code></span>
              </div>
            </div>
          </div>

          <Button
            size="sm"
            variant="primary"
            onClick={() => onTriggerScan(repo.name)}
            icon={<Play className="w-3.5 h-3.5 fill-current" />}
          >
            Trigger Scan
          </Button>
        </div>
      </div>

      {/* Grid: Contracts and Symbols */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Contracts Registered */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-slate-600" />
              <h3 className="text-sm font-bold text-slate-900 tracking-tight">Registered API & Schema Contracts</h3>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Contract Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Target Path</TableHead>
                </TableRow>
              </TableHeader>
              <tbody>
                {contracts.map((c, i) => (
                  <TableRow key={i}>
                    <TableCell className="font-semibold text-slate-800">{c.name}</TableCell>
                    <TableCell>
                      <Badge variant="neutral" size="sm">
                        {c.type}
                      </Badge>
                    </TableCell>
                    <TableCell className="font-mono text-[11px] text-blue-700">{c.file}</TableCell>
                  </TableRow>
                ))}
              </tbody>
            </Table>
          </CardContent>
        </Card>

        {/* Tree-sitter Extracted AST Symbols */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <FileCode className="w-4 h-4 text-emerald-600" />
              <h3 className="text-sm font-bold text-slate-900 tracking-tight">Extracted AST Symbols (Tree-sitter)</h3>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Symbol Identifier</TableHead>
                  <TableHead>Kind</TableHead>
                  <TableHead>Source Lines</TableHead>
                </TableRow>
              </TableHeader>
              <tbody>
                {symbols.map((s, i) => (
                  <TableRow key={i}>
                    <TableCell className="font-mono text-slate-900 text-xs font-semibold">{s.name}</TableCell>
                    <TableCell>
                      <Badge variant="neutral" size="sm">
                        {s.type}
                      </Badge>
                    </TableCell>
                    <TableCell className="font-mono text-[11px] text-slate-500">
                      {s.file}:{s.lines}
                    </TableCell>
                  </TableRow>
                ))}
              </tbody>
            </Table>
          </CardContent>
        </Card>
      </div>

      {/* Recent Scans for this Repository */}
      <Card>
        <CardHeader>
          <h3 className="text-sm font-bold text-slate-900 tracking-tight">Repository Scan History</h3>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Scan ID</TableHead>
                <TableHead>Branch / Commit</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Risk Level</TableHead>
                <TableHead>Violations</TableHead>
                <TableHead>Duration</TableHead>
              </TableRow>
            </TableHeader>
            <tbody>
              {scans.map((scan) => (
                <TableRow key={scan.id}>
                  <TableCell className="font-mono text-slate-900 font-semibold">{scan.id}</TableCell>
                  <TableCell className="font-mono text-[11px] text-slate-600">
                    {scan.source_branch}
                  </TableCell>
                  <TableCell>
                    <Badge variant="success" size="sm">
                      {scan.status}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={scan.risk_level === 'CRITICAL' ? 'danger' : 'neutral'}
                      size="sm"
                    >
                      {scan.risk_level} ({scan.risk_score})
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {scan.blocking_violations_count > 0 ? (
                      <span className="text-red-700 font-semibold">
                        {scan.blocking_violations_count} blocking
                      </span>
                    ) : (
                      <span className="text-emerald-700 font-medium">0</span>
                    )}
                  </TableCell>
                  <TableCell className="font-mono text-slate-500 tabular-nums">
                    {scan.duration_ms}ms
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
