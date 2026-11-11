import React, { useState, useEffect } from 'react'
import { Card, CardHeader, CardContent } from '../ui/Card'
import { Table, TableHeader, TableRow, TableHead, TableCell } from '../ui/Table'
import { Badge } from '../ui/Badge'
import { Input } from '../ui/Input'
import { Network, Search, ShieldCheck, Share2, Info } from 'lucide-react'
import { api } from '../../api/client'
import { OntologyConceptItem } from '../../api/types'

export const OntologyExplorer: React.FC = () => {
  const [concepts, setConcepts] = useState<OntologyConceptItem[]>([])
  const [search, setSearch] = useState('')

  useEffect(() => {
    async function loadData() {
      const data = await api.fetchOntologyConcepts()
      setConcepts(data)
    }
    loadData()
  }, [])

  const relationships = [
    { name: 'CALLS', source: 'Service / Function', target: 'APIEndpoint', rule: 'Static AST or HTTP call' },
    { name: 'IMPORTS', source: 'Module', target: 'Module', rule: 'Static module dependencies' },
    { name: 'PRODUCES', source: 'APIEndpoint', target: 'APIField', rule: 'Response schema mapping' },
    { name: 'CONSUMES', source: 'APIEndpoint', target: 'APIField', rule: 'Request schema mapping' },
    { name: 'MAPS_TO', source: 'APIField', target: 'BusinessConcept', rule: 'Semantic concept alignment' },
    { name: 'READS', source: 'Function', target: 'DatabaseTable', rule: 'ORM / SQL SELECT queries' },
    { name: 'WRITES', source: 'Function', target: 'DatabaseTable', rule: 'INSERT / UPDATE mutations' },
    { name: 'PERSISTS_AS', source: 'DatabaseTable', target: 'Database', rule: 'Physical persistence' },
    { name: 'PUBLISHES', source: 'Service', target: 'Event', rule: 'Kafka / AMQP event emission' },
    { name: 'SUBSCRIBES_TO', source: 'Service', target: 'Event', rule: 'Consumer message handler' },
    { name: 'PART_OF_WORKFLOW', source: 'Service', target: 'Workflow', rule: 'Critical business journey' },
    { name: 'OWNED_BY', source: 'Service / Repo', target: 'Owner', rule: 'CODEOWNERS accountability' },
    { name: 'REQUIRES_PERMISSION', source: 'APIEndpoint', target: 'Permission', rule: 'RBAC authorization gate' },
    { name: 'DEPENDS_ON', source: 'Service', target: 'Service', rule: 'Direct service dependency' },
    { name: 'TRANSFORMS_INTO', source: 'APIField', target: 'DatabaseColumn', rule: 'Data pipeline transformation' },
  ]

  const filteredConcepts = concepts.filter((c) =>
    c.name.toLowerCase().includes(search.toLowerCase()) ||
    c.urn_pattern.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2">
          <h1 className="text-xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
            <Network className="w-5 h-5 text-slate-700" />
            Software Engineering Ontology Explorer
          </h1>
          <Badge variant="purple" size="sm">
            CSEO v1.0.0
          </Badge>
        </div>
        <p className="text-xs text-slate-500 mt-1">
          Formal domain-specific ontology for distributed software knowledge graphs and change impact reasoning.
        </p>
      </div>

      {/* Integration Notice */}
      <div className="bg-white border border-slate-200/90 rounded-2xl p-4 flex items-start gap-3 text-xs text-slate-700 shadow-premium">
        <Info className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <span className="font-bold text-slate-900">NVIDIA Auto-Ontology Verified Layer:</span>
          <p className="text-slate-600 leading-relaxed font-normal">
            ChangeScope implements a dual provider abstraction: <code className="text-slate-900 font-semibold">LocalOntologyProvider</code> operates fully offline,
            while <code className="text-slate-900 font-semibold">NvidiaAutoOntologyProvider</code> reconciles high-order semantic concepts via verified Ossie YAML contracts.
          </p>
        </div>
      </div>

      {/* Two Column Layout: 26 Core Entities & 15 Canonical Relationships */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: 26 Core Entities */}
        <div className="lg:col-span-7 space-y-4">
          <Card>
            <CardHeader>
              <div>
                <h3 className="text-sm font-bold text-slate-900 tracking-tight">
                  Core Ontology Entities ({filteredConcepts.length})
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">First-class software knowledge graph nodes</p>
              </div>

              <div className="w-48">
                <Input
                  placeholder="Filter entities..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  icon={<Search className="w-3.5 h-3.5" />}
                />
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Entity Name</TableHead>
                    <TableHead>Canonical URN Pattern</TableHead>
                    <TableHead>Certification</TableHead>
                  </TableRow>
                </TableHeader>
                <tbody>
                  {filteredConcepts.map((c) => (
                    <TableRow key={c.name}>
                      <TableCell className="font-bold text-slate-900 font-mono">{c.name}</TableCell>
                      <TableCell className="font-mono text-[11px] text-blue-700">
                        {c.urn_pattern}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={
                            c.status === 'CERTIFIED_DETERMINISTIC' ? 'success' : 'purple'
                          }
                          size="sm"
                        >
                          {c.status === 'CERTIFIED_DETERMINISTIC' ? 'DETERMINISTIC' : 'NVIDIA VERIFIED'}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </tbody>
              </Table>
            </CardContent>
          </Card>
        </div>

        {/* Right Column: 15 Canonical Relationships */}
        <div className="lg:col-span-5 space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Share2 className="w-4 h-4 text-emerald-600" />
                <div>
                  <h3 className="text-sm font-bold text-slate-900 tracking-tight">15 Canonical Relationships</h3>
                  <p className="text-xs text-slate-500 mt-0.5">Strict typing and domain/range invariants</p>
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <div className="divide-y divide-slate-100 max-h-[580px] overflow-y-auto">
                {relationships.map((rel) => (
                  <div key={rel.name} className="p-3.5 hover:bg-slate-50/70 transition-colors text-xs">
                    <div className="flex items-center justify-between">
                      <span className="font-mono font-bold text-blue-700">{rel.name}</span>
                      <span className="text-[10px] text-emerald-700 font-semibold flex items-center gap-1">
                        <ShieldCheck className="w-3 h-3 text-emerald-600" />
                        Evidence Required
                      </span>
                    </div>
                    <div className="text-[11px] text-slate-800 font-mono mt-1 font-medium">
                      {rel.source} → {rel.target}
                    </div>
                    <div className="text-[11px] text-slate-500 mt-0.5">{rel.rule}</div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
