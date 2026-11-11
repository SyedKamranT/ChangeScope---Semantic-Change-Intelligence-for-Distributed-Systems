import React, { useState, useEffect } from 'react'
import { Card, CardHeader, CardContent } from '../ui/Card'
import { Table, TableHeader, TableRow, TableHead, TableCell } from '../ui/Table'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Select } from '../ui/Select'
import { Modal } from '../ui/Modal'
import { Pagination } from '../ui/Pagination'
import { EmptyState } from '../ui/EmptyState'
import { Plus, Search, GitFork, ExternalLink, Play } from 'lucide-react'
import { api } from '../../api/client'
import { RepositoryItem } from '../../api/types'
import { NavViewKey } from '../layout/AppSidebar'

export interface RepositoryManagementProps {
  onNavigate: (view: NavViewKey, repoId?: string) => void
  onTriggerScan: (repoName?: string) => void
  isRegisterModalOpen: boolean
  setIsRegisterModalOpen: (open: boolean) => void
}

export const RepositoryManagement: React.FC<RepositoryManagementProps> = ({
  onNavigate,
  onTriggerScan,
  isRegisterModalOpen,
  setIsRegisterModalOpen,
}) => {
  const [repos, setRepos] = useState<RepositoryItem[]>([])
  const [searchTerm, setSearchTerm] = useState('')
  const [tierFilter, setTierFilter] = useState('ALL')
  const [currentPage, setCurrentPage] = useState(1)
  const pageSize = 5

  // Form states for Register Repository
  const [newRepoName, setNewRepoName] = useState('')
  const [newRepoUrl, setNewRepoUrl] = useState('')
  const [newRepoBranch, setNewRepoBranch] = useState('main')
  const [newRepoTier, setNewRepoTier] = useState('TIER_1_CRITICAL')
  const [formError, setFormError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    async function loadRepos() {
      const data = await api.fetchRepositories()
      setRepos(data)
    }
    loadRepos()
  }, [])

  const filteredRepos = repos.filter((r) => {
    const matchesSearch =
      r.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      r.clone_url.toLowerCase().includes(searchTerm.toLowerCase())
    const matchesTier = tierFilter === 'ALL' || r.tier === tierFilter
    return matchesSearch && matchesTier
  })

  const totalPages = Math.ceil(filteredRepos.length / pageSize)
  const paginatedRepos = filteredRepos.slice(
    (currentPage - 1) * pageSize,
    currentPage * pageSize
  )

  const handleRegisterSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError(null)
    setIsSubmitting(true)
    try {
      const registered = await api.registerRepository({
        name: newRepoName,
        clone_url: newRepoUrl,
        default_branch: newRepoBranch,
        tier: newRepoTier,
      })
      setRepos((prev) => [registered, ...prev])
      setIsRegisterModalOpen(false)
      setNewRepoName('')
      setNewRepoUrl('')
    } catch (err: any) {
      setFormError(err.message || 'Registration failed')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* View Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900">Repository Management</h1>
          <p className="text-xs text-slate-500 mt-1">
            Connected repositories with AST symbol extraction and contract change intelligence.
          </p>
        </div>

        <Button
          size="sm"
          variant="primary"
          onClick={() => setIsRegisterModalOpen(true)}
          icon={<Plus className="w-3.5 h-3.5" />}
        >
          Register Repository
        </Button>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-center gap-3 bg-white border border-slate-200/90 p-3 rounded-2xl shadow-premium">
        <div className="w-full sm:w-72">
          <Input
            placeholder="Search repositories..."
            value={searchTerm}
            onChange={(e) => {
              setSearchTerm(e.target.value)
              setCurrentPage(1)
            }}
            icon={<Search className="w-3.5 h-3.5" />}
          />
        </div>

        <div className="w-full sm:w-48">
          <Select
            value={tierFilter}
            onChange={(e) => {
              setTierFilter(e.target.value)
              setCurrentPage(1)
            }}
            options={[
              { label: 'All Criticality Tiers', value: 'ALL' },
              { label: 'Tier 1 Critical', value: 'TIER_1_CRITICAL' },
              { label: 'Tier 2 Standard', value: 'TIER_2_STANDARD' },
              { label: 'Tier 3 Internal', value: 'TIER_3_INTERNAL' },
            ]}
          />
        </div>
      </div>

      {/* Repositories Table Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <GitFork className="w-4 h-4 text-slate-600" />
            <h3 className="text-sm font-bold text-slate-900 tracking-tight">
              Connected Repositories ({filteredRepos.length})
            </h3>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {paginatedRepos.length === 0 ? (
            <EmptyState
              title="No repositories found"
              description="No registered repositories match the active filter criteria."
              actionLabel="Register Repository"
              onAction={() => setIsRegisterModalOpen(true)}
            />
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Repository Name</TableHead>
                    <TableHead>Clone Target</TableHead>
                    <TableHead>Criticality Tier</TableHead>
                    <TableHead>Language</TableHead>
                    <TableHead>Default Branch</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <tbody>
                  {paginatedRepos.map((repo) => (
                    <TableRow key={repo.id}>
                      <TableCell>
                        <div className="font-mono font-bold text-slate-900 text-xs">{repo.name}</div>
                        <div className="text-[10px] text-slate-500 mt-0.5">
                          ID: <span className="font-mono">{repo.id}</span>
                        </div>
                      </TableCell>
                      <TableCell className="font-mono text-[11px] text-slate-600 truncate max-w-xs">
                        {repo.clone_url}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={repo.tier === 'TIER_1_CRITICAL' ? 'danger' : 'neutral'}
                          size="sm"
                        >
                          {repo.tier === 'TIER_1_CRITICAL' ? 'TIER 1 (CRITICAL)' : 'TIER 2 (STANDARD)'}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant="info" size="sm">
                          {repo.language}
                        </Badge>
                      </TableCell>
                      <TableCell className="font-mono text-slate-700">
                        {repo.default_branch}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => onNavigate('repo_detail', repo.id)}
                            icon={<ExternalLink className="w-3 h-3" />}
                          >
                            Details
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => onTriggerScan(repo.name)}
                            icon={<Play className="w-3 h-3 fill-current" />}
                          >
                            Scan
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </tbody>
              </Table>

              <Pagination
                currentPage={currentPage}
                totalPages={totalPages}
                totalItems={filteredRepos.length}
                pageSize={pageSize}
                onPageChange={(p) => setCurrentPage(p)}
              />
            </>
          )}
        </CardContent>
      </Card>

      {/* Register Repository Modal */}
      <Modal
        isOpen={isRegisterModalOpen}
        onClose={() => {
          setIsRegisterModalOpen(false)
          setFormError(null)
        }}
        title="Register Repository"
        description="Connect a Git repository for automated AST extraction, contract validation, and dependency intelligence."
      >
        <form onSubmit={handleRegisterSubmit} className="space-y-4">
          <Input
            label="Repository Name"
            placeholder="e.g., payment-service"
            value={newRepoName}
            onChange={(e) => setNewRepoName(e.target.value)}
            required
          />

          <Input
            label="Git Clone URL (HTTPS)"
            placeholder="https://github.com/org/repo.git"
            value={newRepoUrl}
            onChange={(e) => setNewRepoUrl(e.target.value)}
            helperText="Protected by SSRF Guard (Private IPs, Localhost, and AWS Metadata rejected)."
            required
          />

          <div className="grid grid-cols-2 gap-3">
            <Input
              label="Default Branch"
              value={newRepoBranch}
              onChange={(e) => setNewRepoBranch(e.target.value)}
              required
            />

            <Select
              label="Criticality Tier"
              value={newRepoTier}
              onChange={(e) => setNewRepoTier(e.target.value)}
              options={[
                { label: 'Tier 1 Critical (Revenue Impact)', value: 'TIER_1_CRITICAL' },
                { label: 'Tier 2 Standard (Internal SLA)', value: 'TIER_2_STANDARD' },
                { label: 'Tier 3 Internal (Non-critical)', value: 'TIER_3_INTERNAL' },
              ]}
            />
          </div>

          {formError && (
            <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-xs text-red-700 font-medium">
              {formError}
            </div>
          )}

          <div className="flex items-center justify-end gap-2.5 pt-2">
            <Button
              type="button"
              variant="secondary"
              onClick={() => setIsRegisterModalOpen(false)}
            >
              Cancel
            </Button>
            <Button type="submit" variant="primary" isLoading={isSubmitting}>
              Register & Extract Symbols
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
