import React, { useState, useEffect } from 'react'
import { Card, CardHeader, CardContent } from '../ui/Card'
import { Table, TableHeader, TableRow, TableHead, TableCell } from '../ui/Table'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Select } from '../ui/Select'
import { Drawer } from '../ui/Drawer'
import { Pagination } from '../ui/Pagination'
import { ScrollText, Search, Download, Code } from 'lucide-react'
import { api } from '../../api/client'
import { AuditLogItem } from '../../api/types'

export const AuditLogsView: React.FC = () => {
  const [logs, setLogs] = useState<AuditLogItem[]>([])
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('ALL')
  const [selectedLog, setSelectedLog] = useState<AuditLogItem | null>(null)
  const [currentPage, setCurrentPage] = useState(1)
  const pageSize = 5

  useEffect(() => {
    async function loadData() {
      const data = await api.fetchAuditLogs()
      setLogs(data)
    }
    loadData()
  }, [])

  const filtered = logs.filter((l) => {
    const matchesSearch =
      l.actor_id.toLowerCase().includes(search.toLowerCase()) ||
      l.event_type.toLowerCase().includes(search.toLowerCase()) ||
      l.resource_type.toLowerCase().includes(search.toLowerCase())
    const matchesType = typeFilter === 'ALL' || l.event_type === typeFilter
    return matchesSearch && matchesType
  })

  const totalPages = Math.ceil(filtered.length / pageSize)
  const paginatedLogs = filtered.slice(
    (currentPage - 1) * pageSize,
    currentPage * pageSize
  )

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
              <ScrollText className="w-5 h-5 text-slate-700" />
              Security & Compliance Audit Trail
            </h1>
            <Badge variant="purple" size="sm">
              SOC 2 Type II Compliance
            </Badge>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Immutable tenant-scoped audit records of authentication, authorization, BOLA defense, and scans.
          </p>
        </div>

        <Button
          size="sm"
          variant="outline"
          icon={<Download className="w-3.5 h-3.5" />}
          onClick={() => {
            const json = JSON.stringify(logs, null, 2)
            const blob = new Blob([json], { type: 'application/json' })
            const url = URL.createObjectURL(blob)
            const a = document.createElement('a')
            a.href = url
            a.download = 'changescope_security_audit_logs.json'
            a.click()
          }}
        >
          Export Compliance Log
        </Button>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-center gap-3 bg-white border border-slate-200/90 p-3 rounded-2xl shadow-premium">
        <div className="w-full sm:w-80">
          <Input
            placeholder="Search actor, event type, resource..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value)
              setCurrentPage(1)
            }}
            icon={<Search className="w-3.5 h-3.5" />}
          />
        </div>

        <div className="w-full sm:w-64">
          <Select
            value={typeFilter}
            onChange={(e) => {
              setTypeFilter(e.target.value)
              setCurrentPage(1)
            }}
            options={[
              { label: 'All Security Events', value: 'ALL' },
              { label: 'BOLA Attempts Blocked', value: 'BOLA_ATTEMPT_TRIGGER_SCAN' },
              { label: 'Scan Executions', value: 'SCAN_TRIGGERED' },
              { label: 'Credential Created', value: 'CREDENTIAL_CREATED' },
              { label: 'Privilege Violations', value: 'VERTICAL_PRIVILEGE_ATTEMPT' },
            ]}
          />
        </div>
      </div>

      {/* Audit Log Table */}
      <Card>
        <CardHeader>
          <h3 className="text-sm font-bold text-slate-900 tracking-tight">Audit Event Stream ({filtered.length})</h3>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Event Type</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Actor / Role</TableHead>
                <TableHead>Target Resource</TableHead>
                <TableHead>Client IP</TableHead>
                <TableHead>Timestamp (UTC)</TableHead>
                <TableHead className="text-right">Inspection</TableHead>
              </TableRow>
            </TableHeader>
            <tbody>
              {paginatedLogs.map((log) => (
                <TableRow key={log.id}>
                  <TableCell>
                    <div className="font-mono font-bold text-slate-900 text-xs">{log.event_type}</div>
                    <div className="text-[10px] text-slate-400 font-mono mt-0.5">{log.id}</div>
                  </TableCell>
                  <TableCell>
                    <Badge variant={log.status === 'SUCCESS' ? 'success' : 'danger'} size="sm">
                      {log.status}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="font-mono text-xs font-semibold text-slate-900">{log.actor_id}</div>
                    <div className="text-[10px] text-slate-500 font-mono">{log.actor_role}</div>
                  </TableCell>
                  <TableCell className="font-mono text-xs text-blue-700 font-medium">
                    {log.resource_type}
                    {log.resource_id && `:${log.resource_id}`}
                  </TableCell>
                  <TableCell className="font-mono text-xs text-slate-600 tabular-nums">
                    {log.client_ip || 'Internal'}
                  </TableCell>
                  <TableCell className="font-mono text-xs text-slate-600 tabular-nums">
                    {new Date(log.created_at).toLocaleString()}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setSelectedLog(log)}
                      icon={<Code className="w-3.5 h-3.5" />}
                    >
                      Payload
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

      {/* Payload Inspection Drawer */}
      <Drawer
        isOpen={Boolean(selectedLog)}
        onClose={() => setSelectedLog(null)}
        title={selectedLog ? `Audit Event: ${selectedLog.event_type}` : ''}
        subtitle={selectedLog ? `Log ID: ${selectedLog.id}` : ''}
      >
        {selectedLog && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3 text-xs bg-slate-50 p-3.5 rounded-xl border border-slate-200">
              <div>
                <span className="text-slate-500 font-medium">Actor ID:</span>
                <div className="font-mono text-slate-900 font-semibold mt-0.5">{selectedLog.actor_id}</div>
              </div>
              <div>
                <span className="text-slate-500 font-medium">Assigned Role:</span>
                <div className="font-mono text-slate-900 font-semibold mt-0.5">{selectedLog.actor_role}</div>
              </div>
              <div>
                <span className="text-slate-500 font-medium">Status:</span>
                <div className="mt-0.5">
                  <Badge variant={selectedLog.status === 'SUCCESS' ? 'success' : 'danger'}>
                    {selectedLog.status}
                  </Badge>
                </div>
              </div>
              <div>
                <span className="text-slate-500 font-medium">Client IP:</span>
                <div className="font-mono text-slate-900 font-semibold mt-0.5">{selectedLog.client_ip || 'N/A'}</div>
              </div>
            </div>

            <div>
              <div className="text-xs font-bold text-slate-900 mb-2">Structured Event Details:</div>
              <div className="bg-slate-50 border border-slate-200/90 rounded-xl p-3 font-mono text-xs text-slate-800 overflow-x-auto shadow-xs">
                <pre>{JSON.stringify(selectedLog.details, null, 2)}</pre>
              </div>
            </div>
          </div>
        )}
      </Drawer>
    </div>
  )
}
