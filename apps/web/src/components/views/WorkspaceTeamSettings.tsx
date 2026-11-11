import React, { useState } from 'react'
import { Card, CardHeader, CardContent } from '../ui/Card'
import { Table, TableHeader, TableRow, TableHead, TableCell } from '../ui/Table'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Modal } from '../ui/Modal'
import { Users, Database, Shield, Plus, Check, X } from 'lucide-react'
import { WorkspaceItem } from '../../api/types'

export interface WorkspaceTeamSettingsProps {
  workspaces: WorkspaceItem[]
  onAddWorkspace: (name: string, slug: string) => void
}

export const WorkspaceTeamSettings: React.FC<WorkspaceTeamSettingsProps> = ({
  workspaces,
  onAddWorkspace,
}) => {
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [newWsName, setNewWsName] = useState('')
  const [newWsSlug, setNewWsSlug] = useState('')

  const teamMembers = [
    { name: 'Alex Rivera', email: 'alex.rivera@enterprise.com', role: 'ADMINISTRATOR', added: '2026-11-01' },
    { name: 'Sarah Chen', email: 'sarah.chen@enterprise.com', role: 'ORGANIZATION_OWNER', added: '2026-10-15' },
    { name: 'Marcus Vance', email: 'marcus.vance@enterprise.com', role: 'ANALYST', added: '2026-11-05' },
    { name: 'Elena Rostov', email: 'elena.rostov@enterprise.com', role: 'VIEWER', added: '2026-11-09' },
  ]

  const permissionsMatrix = [
    { capability: 'View Scans & Impact Graphs', owner: true, admin: true, analyst: true, viewer: true },
    { capability: 'Trigger Automated Scans', owner: true, admin: true, analyst: true, viewer: false },
    { capability: 'Approve Generated Test Recommendations', owner: true, admin: true, analyst: true, viewer: false },
    { capability: 'Register Repositories', owner: true, admin: true, analyst: true, viewer: false },
    { capability: 'Inspect Security Audit Logs', owner: true, admin: true, analyst: false, viewer: false },
    { capability: 'Manage Integration Credentials', owner: true, admin: true, analyst: false, viewer: false },
    { capability: 'Reveal Plaintext Secrets', owner: true, admin: true, analyst: false, viewer: false },
  ]

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    onAddWorkspace(newWsName, newWsSlug || newWsName.toLowerCase().replace(/\s+/g, '-'))
    setIsModalOpen(false)
    setNewWsName('')
    setNewWsSlug('')
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
            <Users className="w-5 h-5 text-slate-700" />
            Workspace & RBAC Access Controls
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Enterprise tenancy management with multi-layer cryptographic authorization and tenant boundaries.
          </p>
        </div>

        <Button
          size="sm"
          variant="primary"
          onClick={() => setIsModalOpen(true)}
          icon={<Plus className="w-3.5 h-3.5" />}
        >
          New Workspace
        </Button>
      </div>

      {/* Workspaces List */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Database className="w-4 h-4 text-slate-600" />
            <h3 className="text-sm font-bold text-slate-900 tracking-tight">Configured Workspaces ({workspaces.length})</h3>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Workspace Name</TableHead>
                <TableHead>Identifier Slug</TableHead>
                <TableHead>Tenant ID</TableHead>
                <TableHead>Created At</TableHead>
              </TableRow>
            </TableHeader>
            <tbody>
              {workspaces.map((ws) => (
                <TableRow key={ws.id}>
                  <TableCell className="font-bold text-slate-900 font-mono">{ws.name}</TableCell>
                  <TableCell className="font-mono text-blue-700 text-xs font-medium">{ws.slug}</TableCell>
                  <TableCell className="font-mono text-slate-500 text-xs">{ws.tenant_id}</TableCell>
                  <TableCell className="font-mono text-xs text-slate-500">
                    {new Date(ws.created_at).toLocaleDateString()}
                  </TableCell>
                </TableRow>
              ))}
            </tbody>
          </Table>
        </CardContent>
      </Card>

      {/* Team Members and RBAC Roles */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Shield className="w-4 h-4 text-emerald-600" />
            <h3 className="text-sm font-bold text-slate-900 tracking-tight">Team Members & Assigned Roles</h3>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>User</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Member Since</TableHead>
              </TableRow>
            </TableHeader>
            <tbody>
              {teamMembers.map((m, i) => (
                <TableRow key={i}>
                  <TableCell className="font-semibold text-slate-900">{m.name}</TableCell>
                  <TableCell className="font-mono text-slate-500">{m.email}</TableCell>
                  <TableCell>
                    <Badge
                      variant={
                        m.role === 'ORGANIZATION_OWNER'
                          ? 'danger'
                          : m.role === 'ADMINISTRATOR'
                          ? 'purple'
                          : m.role === 'ANALYST'
                          ? 'info'
                          : 'neutral'
                      }
                    >
                      {m.role}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-mono text-xs text-slate-500">{m.added}</TableCell>
                </TableRow>
              ))}
            </tbody>
          </Table>
        </CardContent>
      </Card>

      {/* Visual Role Permission Matrix */}
      <Card>
        <CardHeader>
          <div>
            <h3 className="text-sm font-bold text-slate-900 tracking-tight">RBAC Permission Matrix</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Service and API layer least-privilege boundary enforcement
            </p>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>System Capability</TableHead>
                <TableHead className="text-center">Viewer</TableHead>
                <TableHead className="text-center">Analyst</TableHead>
                <TableHead className="text-center">Administrator</TableHead>
                <TableHead className="text-center">Organization Owner</TableHead>
              </TableRow>
            </TableHeader>
            <tbody>
              {permissionsMatrix.map((row, i) => (
                <TableRow key={i}>
                  <TableCell className="font-semibold text-slate-800 text-xs">{row.capability}</TableCell>
                  <TableCell className="text-center">
                    {row.viewer ? (
                      <Check className="w-4 h-4 text-emerald-600 mx-auto" />
                    ) : (
                      <X className="w-4 h-4 text-slate-300 mx-auto" />
                    )}
                  </TableCell>
                  <TableCell className="text-center">
                    {row.analyst ? (
                      <Check className="w-4 h-4 text-emerald-600 mx-auto" />
                    ) : (
                      <X className="w-4 h-4 text-slate-300 mx-auto" />
                    )}
                  </TableCell>
                  <TableCell className="text-center">
                    {row.admin ? (
                      <Check className="w-4 h-4 text-emerald-600 mx-auto" />
                    ) : (
                      <X className="w-4 h-4 text-slate-300 mx-auto" />
                    )}
                  </TableCell>
                  <TableCell className="text-center">
                    {row.owner ? (
                      <Check className="w-4 h-4 text-emerald-600 mx-auto" />
                    ) : (
                      <X className="w-4 h-4 text-slate-300 mx-auto" />
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </tbody>
          </Table>
        </CardContent>
      </Card>

      {/* Create Workspace Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Create New Workspace"
        description="Establish an isolated environment boundary for distributed repositories."
      >
        <form onSubmit={handleCreate} className="space-y-4">
          <Input
            label="Workspace Name"
            placeholder="e.g., Mobile & Consumer API"
            value={newWsName}
            onChange={(e) => setNewWsName(e.target.value)}
            required
          />

          <Input
            label="Slug Identifier"
            placeholder="e.g., mobile-consumer-api"
            value={newWsSlug}
            onChange={(e) => setNewWsSlug(e.target.value)}
            helperText="Unique URL slug scoped to current organization tenant."
          />

          <div className="flex items-center justify-end gap-2.5 pt-2">
            <Button type="button" variant="secondary" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary">
              Create Workspace
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
