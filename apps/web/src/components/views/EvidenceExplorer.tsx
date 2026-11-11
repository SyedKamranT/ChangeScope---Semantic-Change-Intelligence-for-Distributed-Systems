import React, { useState, useEffect } from 'react'
import { Card, CardHeader, CardContent } from '../ui/Card'
import { Table, TableHeader, TableRow, TableHead, TableCell } from '../ui/Table'
import { Badge } from '../ui/Badge'
import { Input } from '../ui/Input'
import { FileCode, Search, Lock, Hash } from 'lucide-react'
import { api } from '../../api/client'
import { EvidenceItem } from '../../api/types'

export const EvidenceExplorer: React.FC = () => {
  const [evidenceList, setEvidenceList] = useState<EvidenceItem[]>([])
  const [search, setSearch] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('ALL')

  useEffect(() => {
    async function loadData() {
      const data = await api.fetchEvidence()
      setEvidenceList(data)
    }
    loadData()
  }, [])

  const filtered = evidenceList.filter((e) => {
    const matchesSearch =
      e.identifier.toLowerCase().includes(search.toLowerCase()) ||
      e.file_path.toLowerCase().includes(search.toLowerCase()) ||
      e.sha256.toLowerCase().includes(search.toLowerCase())
    const matchesCategory = categoryFilter === 'ALL' || e.category === categoryFilter
    return matchesSearch && matchesCategory
  })

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2">
          <h1 className="text-xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
            <FileCode className="w-5 h-5 text-emerald-600" />
            Evidence Explorer & Grounding Citations
          </h1>
          <Badge variant="success" size="sm">
            100% Deterministic Grounding
          </Badge>
        </div>
        <p className="text-xs text-slate-500 mt-1">
          Cryptographically hashed evidence records verifying static AST symbols, schemas, and scrubbed trace spans.
        </p>
      </div>

      {/* Filter Toolbar */}
      <div className="flex flex-col sm:flex-row items-center gap-3 bg-white border border-slate-200/90 p-3 rounded-2xl shadow-premium">
        <div className="w-full sm:w-80">
          <Input
            placeholder="Search identifier, file path, SHA256..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            icon={<Search className="w-3.5 h-3.5" />}
          />
        </div>

        <div className="flex items-center gap-1.5 flex-wrap">
          {['ALL', 'TREE_SITTER_AST', 'OPENAPI_SPEC', 'OTEL_SPAN'].map((cat) => (
            <button
              key={cat}
              onClick={() => setCategoryFilter(cat)}
              className={`px-2.5 py-1 text-xs rounded-lg font-semibold cursor-pointer transition-all active:scale-[0.97] ${
                categoryFilter === cat
                  ? 'bg-slate-900 text-white shadow-xs'
                  : 'bg-white text-slate-600 hover:text-slate-900 border border-slate-200'
              }`}
            >
              {cat === 'ALL' ? 'All Sources' : cat}
            </button>
          ))}
        </div>
      </div>

      {/* Evidence Table */}
      <Card>
        <CardHeader>
          <h3 className="text-sm font-bold text-slate-900 tracking-tight">Verified Grounding Artifacts ({filtered.length})</h3>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Evidence Identifier</TableHead>
                <TableHead>Provenance Category</TableHead>
                <TableHead>File / Target Path</TableHead>
                <TableHead>SHA-256 Checksum</TableHead>
                <TableHead>PII Protection</TableHead>
                <TableHead className="text-right">Observed At</TableHead>
              </TableRow>
            </TableHeader>
            <tbody>
              {filtered.map((item) => (
                <TableRow key={item.id}>
                  <TableCell>
                    <div className="font-mono font-bold text-slate-900 text-xs">{item.identifier}</div>
                    <div className="text-[10px] text-slate-400 font-mono mt-0.5">{item.id}</div>
                  </TableCell>
                  <TableCell>
                    <Badge variant={item.category === 'OTEL_SPAN' ? 'neutral' : 'purple'} size="sm">
                      {item.category}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-mono text-blue-700 text-[11px] font-medium">
                    {item.file_path}
                    {item.line_number && `:${item.line_number}`}
                  </TableCell>
                  <TableCell className="font-mono text-slate-500 text-[11px] truncate max-w-xs">
                    <span className="flex items-center gap-1">
                      <Hash className="w-3 h-3 text-slate-400 shrink-0" />
                      <span className="truncate">{item.sha256}</span>
                    </span>
                  </TableCell>
                  <TableCell>
                    {item.pii_scrubbed ? (
                      <span className="flex items-center gap-1 text-[11px] text-emerald-700 font-semibold">
                        <Lock className="w-3 h-3 text-emerald-600" />
                        Scrubbed
                      </span>
                    ) : (
                      <span className="text-slate-500 text-[11px]">Raw AST</span>
                    )}
                  </TableCell>
                  <TableCell className="text-right font-mono text-xs text-slate-500 tabular-nums">
                    {new Date(item.observed_at).toLocaleTimeString()}
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
