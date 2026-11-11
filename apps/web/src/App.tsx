import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { AppShell } from './components/layout/AppShell'
import { NavViewKey } from './components/layout/AppSidebar'
import { OverviewDashboard } from './components/views/OverviewDashboard'
import { RepositoryManagement } from './components/views/RepositoryManagement'
import { RepositoryDetail } from './components/views/RepositoryDetail'
import { PullRequestAnalysis } from './components/views/PullRequestAnalysis'
import { ChangeImpactExplorer } from './components/views/ChangeImpactExplorer'
import { SemanticDriftFindings } from './components/views/SemanticDriftFindings'
import { RuntimeDependencyGraph } from './components/views/RuntimeDependencyGraph'
import { OntologyExplorer } from './components/views/OntologyExplorer'
import { WorkflowImpactView } from './components/views/WorkflowImpactView'
import { EvidenceExplorer } from './components/views/EvidenceExplorer'
import { TestRecommendations } from './components/views/TestRecommendations'
import { AnalysisHistory } from './components/views/AnalysisHistory'
import { IntegrationManagement } from './components/views/IntegrationManagement'
import { WorkspaceTeamSettings } from './components/views/WorkspaceTeamSettings'
import { AuditLogsView } from './components/views/AuditLogsView'
import { TriggerScanModal } from './components/TriggerScanModal'
import { api } from './api/client'
import { WorkspaceItem, UserProfile } from './api/types'
import { DEFAULT_WORKSPACES } from './api/mockData'

export function App() {
  const [activeView, setActiveView] = useState<NavViewKey>('overview')
  const [selectedPR, setSelectedPR] = useState<number>(142)
  const [selectedRepoId, setSelectedRepoId] = useState<string>('repo-inventory')
  const [isScanModalOpen, setIsScanModalOpen] = useState(false)
  const [isRegisterRepoModalOpen, setIsRegisterRepoModalOpen] = useState(false)

  const [workspaces, setWorkspaces] = useState<WorkspaceItem[]>(DEFAULT_WORKSPACES)
  const [currentWorkspace, setCurrentWorkspace] = useState<WorkspaceItem>(DEFAULT_WORKSPACES[0])
  const currentUser: UserProfile = api.getCurrentUser()

  useEffect(() => {
    async function init() {
      const ws = await api.fetchWorkspaces()
      if (ws.length > 0) {
        setWorkspaces(ws)
        setCurrentWorkspace(ws[0])
      }
    }
    init()
  }, [])

  const handleNavigate = (view: NavViewKey, repoId?: string) => {
    if (repoId) setSelectedRepoId(repoId)
    setActiveView(view)
  }

  const handleAddWorkspace = (name: string, slug: string) => {
    const newWs: WorkspaceItem = {
      id: `ws-${Date.now()}`,
      tenant_id: currentUser.tenant_id,
      name,
      slug,
      created_at: new Date().toISOString(),
    }
    setWorkspaces((prev) => [...prev, newWs])
    setCurrentWorkspace(newWs)
  }

  const handleExecuteScan = async (data: { repo: string; baseSha: string; headSha: string; prNumber: number }) => {
    setSelectedPR(data.prNumber)
    await api.triggerScan({
      repository_id: data.repo,
      base_commit: data.baseSha,
      head_commit: data.headSha,
    })
    setIsScanModalOpen(false)
    setActiveView('pull_requests')
  }

  return (
    <AppShell
      workspaces={workspaces}
      currentWorkspace={currentWorkspace}
      onWorkspaceChange={setCurrentWorkspace}
      currentUser={currentUser}
      activeView={activeView}
      onSelectView={setActiveView}
      onTriggerScan={() => setIsScanModalOpen(true)}
    >
      <AnimatePresence mode="wait">
        <motion.div
          key={activeView}
          initial={{ opacity: 0, y: 6, filter: 'blur(1px)' }}
          animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
          exit={{ opacity: 0, y: -6, filter: 'blur(1px)' }}
          transition={{ duration: 0.18, ease: [0.23, 1, 0.32, 1] }}
          className="space-y-6"
        >
          {activeView === 'overview' && (
            <OverviewDashboard
              onNavigate={handleNavigate}
              onTriggerScan={() => setIsScanModalOpen(true)}
              onRegisterRepo={() => {
                setActiveView('repositories')
                setIsRegisterRepoModalOpen(true)
              }}
            />
          )}

          {activeView === 'repositories' && (
            <RepositoryManagement
              onNavigate={handleNavigate}
              onTriggerScan={() => {
                setIsScanModalOpen(true)
              }}
              isRegisterModalOpen={isRegisterRepoModalOpen}
              setIsRegisterModalOpen={setIsRegisterRepoModalOpen}
            />
          )}

          {activeView === 'repo_detail' && (
            <RepositoryDetail
              repoId={selectedRepoId}
              onNavigate={handleNavigate}
              onTriggerScan={() => setIsScanModalOpen(true)}
            />
          )}

          {activeView === 'pull_requests' && (
            <PullRequestAnalysis
              selectedPR={selectedPR}
              setSelectedPR={setSelectedPR}
              onNavigate={handleNavigate}
            />
          )}

          {activeView === 'impact_explorer' && (
            <ChangeImpactExplorer
              selectedPR={selectedPR}
              setSelectedPR={setSelectedPR}
            />
          )}

          {activeView === 'semantic_drift' && <SemanticDriftFindings />}

          {activeView === 'runtime_graph' && <RuntimeDependencyGraph />}

          {activeView === 'ontology' && <OntologyExplorer />}

          {activeView === 'workflow_impact' && <WorkflowImpactView />}

          {activeView === 'evidence' && <EvidenceExplorer />}

          {activeView === 'test_recommendations' && <TestRecommendations />}

          {activeView === 'history' && (
            <AnalysisHistory
              onNavigate={handleNavigate}
              onTriggerScan={() => setIsScanModalOpen(true)}
            />
          )}

          {activeView === 'integrations' && <IntegrationManagement />}

          {activeView === 'team_settings' && (
            <WorkspaceTeamSettings
              workspaces={workspaces}
              onAddWorkspace={handleAddWorkspace}
            />
          )}

          {activeView === 'audit_logs' && <AuditLogsView />}
        </motion.div>
      </AnimatePresence>

      {/* Trigger Scan Modal */}
      <TriggerScanModal
        isOpen={isScanModalOpen}
        onClose={() => setIsScanModalOpen(false)}
        onSubmit={handleExecuteScan}
      />
    </AppShell>
  )
}

export default App
