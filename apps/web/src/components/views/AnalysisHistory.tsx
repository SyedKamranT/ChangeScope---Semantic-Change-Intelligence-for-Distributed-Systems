import React, { useState, useEffect } from 'react'
import { Card, CardHeader, CardContent } from '../ui/Card'
import { Table, TableHeader, TableRow, TableHead, TableCell } from '../ui/Table'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Select } from '../ui/Select'
import { Pagination } from '../ui/Pagination'
import { History, Search, Download, ExternalLink, Play } from 'lucide-react'
import { api } from '../../api/client'
import { ScanRunItem } from '../../api/types'
import { NavViewKey } from '../layout/AppSidebar'

export interface AnalysisHistoryProps {
  onNavigate: (view: NavViewKey) => void
  onTriggerScan: () => void
}

export const AnalysisHistory: React.FC<AnalysisHistoryProps> = ({
  onNavigate,
  onTriggerScan,
}) => {
  const [scans, setScans] = useState<ScanRunItem[]>([])
  const [search, setSearch] = useState('')
  const [riskFilter, setRiskFilter] = useState('ALL')
  const [currentPage, setCurrentPage] = useState(1)
  const pageSize = 5

  useEffect(() => {
    async function loadData() {
      const data = await api.fetchScans()
      setScans(data)
    }
    loadData()
  }, [])

  const filtered = scans.filter((s) => {
    const matchesSearch =
      s.repository_id.toLowerCase().includes(search.toLowerCase()) ||
      (s.repository_name && s.repository_name.toLowerCase().includes(search.toLowerCase())) ||
      s.source_branch.toLowerCase().includes(search.toLowerCase()) ||
      s.target_branch.toLowerCase().includes(search.toLowerCase())
    const matchesRisk = riskFilter === 'ALL' || s.risk_level === riskFilter
    return matchesSearch && matchesRisk
  })

  const totalPages = Math.ceil(filtered.length / pageSize)
  const paginatedScans = filtered.slice(
    (currentPage - 1) * pageSize,
    currentPage * pageSize
  )

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
            <History className="w-5 h-5 text-slate-700" />
            Analysis Run History
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Complete audit trail of all AST and contract change intelligence scans across branches.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <Button
            size="sm"
            variant="outline"
            icon={<Download className="w-3.5 h-3.5" />}
            onClick={() => {
              const json = JSON.stringify(scans, null, 2)
              const blob = new Blob([json], { type: 'application/json' })
              const url = URL.createObjectURL(blob)
              const a = document.createElement('a')
              a.href = url
              a.download = 'changescope_analysis_history.json'
              a.click()
            }}
          >
            Export Logs (JSON)
          </Button>
          <Button
            size="sm"
            variant="primary"
            onClick={onTriggerScan}
            icon={<Play className="w-3.5 h-3.5 fill-current" />}
          >
            New Scan
          </Button>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="flex flex-col sm:flex-row items-center gap-3 bg-white border border-slate-200/90 p-3 rounded-2xl shadow-premium">
        <div className="w-full sm:w-72">
          <Input
            placeholder="Search scans, branches, repos..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value)
              setCurrentPage(1)
            }}
            icon={<Search className="w-3.5 h-3.5" />}
          />
        </div>

        <div className="w-full sm:w-48">
          <Select
            value={riskFilter}
            onChange={(e) => {
              setRiskFilter(e.target.value)
              setCurrentPage(1)
            }}
            options={[
              { label: 'All Risk Levels', value: 'ALL' },
              { label: 'Critical Risk', value: 'CRITICAL' },
              { label: 'High Risk', value: 'HIGH' },
              { label: 'Low Risk', value: 'LOW' },
            ]}
          />
        </div>
      </div>

      {/* Scans Table */}
      <Card>
        <CardHeader>
          <h3 className="text-sm font-bold text-slate-900 tracking-tight">Execution Runs ({filtered.length})</h3>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Repository</TableHead>
                <TableHead>Branches / Commits</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Risk Score</TableHead>
                <TableHead>Violations Detected</TableHead>
                <TableHead>Duration</TableHead>
                <TableHead>Scanned At</TableHead>
                <TableHead className="text-right">Action</TableHead>
              </TableRow>
            </TableHeader>
            <tbody>
              {paginatedScans.map((scan) => (
                <TableRow key={scan.id}>
                  <TableCell className="font-mono font-bold text-slate-900">
                    {scan.repository_name || scan.repository_id}
                  </TableCell>
                  <TableCell className="font-mono text-[11px] text-slate-600">
                    {scan.source_branch} → {scan.target_branch}
                  </TableCell>
                  <TableCell>
                    <Badge variant="success" size="sm">
                      {scan.status}
                    </Badge>
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
                      size="sm"
                    >
                      {scan.risk_level || 'UNKNOWN'} ({scan.risk_score || 0})
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {scan.blocking_violations_count > 0 ? (
                      <span className="text-red-700 font-bold">
                        {scan.blocking_violations_count} blocking
                      </span>
                    ) : (
                      <span className="text-emerald-700 font-semibold">0 Clean</span>
                    )}
                  </TableCell>
                  <TableCell className="font-mono text-slate-500 tabular-nums">
                    {scan.duration_ms} ms
                  </TableCell>
                  <TableCell className="font-mono text-xs text-slate-500 tabular-nums">
                    {new Date(scan.created_at).toLocaleString()}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => onNavigate('pull_requests')}
                      icon={<ExternalLink className="w-3.5 h-3.5" />}
                    >
                      Inspect
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </tbody>
          </Table>

          <Pagination
            currentPage={currentPage}
            totalPages={totalPages}
            totalItems={filtered.length}
            pageSize={pageSize}
            onPageChange={(p) => setCurrentPage(p)}
          />
        </CardContent>
      </Card>
    </div>
  )
}
