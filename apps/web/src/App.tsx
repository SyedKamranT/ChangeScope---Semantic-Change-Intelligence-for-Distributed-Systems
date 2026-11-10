import { useState } from 'react'
import { Navbar } from './components/Navbar'
import { GraphView } from './components/GraphView'
import { ViolationsTable, ViolationItem } from './components/ViolationsTable'
import { ScanDetails } from './components/ScanDetails'
import { TriggerScanModal } from './components/TriggerScanModal'
import { GitPullRequest, Layers, AlertCircle, CheckCircle2 } from 'lucide-react'
import { Node, Edge } from '@xyflow/react'

export function App() {
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [selectedPR, setSelectedPR] = useState<number>(142)

  // Seeded scenario 1: PR 142 (Dangerous Semantic Violation)
  const pr142Nodes: Node[] = [
    {
      id: 'srv-inventory',
      position: { x: 280, y: 50 },
      data: { label: 'inventory-service\n(Provider / Target)', is_origin: true },
      style: {
        background: '#1e1b4b',
        border: '2px solid #ef4444',
        borderRadius: '12px',
        color: '#f8fafc',
        padding: '12px',
        fontWeight: 'bold',
        fontSize: '12px',
        textAlign: 'center',
        boxShadow: '0 0 20px rgba(239, 68, 68, 0.3)',
      },
    },
    {
      id: 'srv-checkout',
      position: { x: 80, y: 220 },
      data: { label: 'checkout-service\n(Tier 1 • Direct Caller)', is_origin: false },
      style: {
        background: '#101726',
        border: '1.5px solid #3b82f6',
        borderRadius: '10px',
        color: '#f8fafc',
        padding: '10px',
        fontSize: '11px',
        textAlign: 'center',
      },
    },
    {
      id: 'srv-analytics',
      position: { x: 480, y: 220 },
      data: { label: 'analytics-pipeline\n(Tier 2 • Kafka Consumer)', is_origin: false },
      style: {
        background: '#101726',
        border: '1.5px solid #3b82f6',
        borderRadius: '10px',
        color: '#f8fafc',
        padding: '10px',
        fontSize: '11px',
        textAlign: 'center',
      },
    },
    {
      id: 'srv-billing',
      position: { x: 80, y: 390 },
      data: { label: 'billing-ledger\n(Tier 1 • Transitive)', is_origin: false },
      style: {
        background: '#101726',
        border: '1.5px dashed #64748b',
        borderRadius: '10px',
        color: '#cbd5e1',
        padding: '10px',
        fontSize: '11px',
        textAlign: 'center',
      },
    },
  ]

  const pr142Edges: Edge[] = [
    {
      id: 'e-checkout-inv',
      source: 'srv-checkout',
      target: 'srv-inventory',
      label: 'POST /orders (12.5k RPM)',
      animated: true,
    },
    {
      id: 'e-analytics-inv',
      source: 'srv-analytics',
      target: 'srv-inventory',
      label: 'Channel: order.events',
      animated: true,
    },
    {
      id: 'e-billing-checkout',
      source: 'srv-billing',
      target: 'srv-checkout',
      label: 'RPC: VerifyCharge',
      animated: false,
    },
  ]

  const pr142Violations: ViolationItem[] = [
    {
      id: 'v1',
      rule_code: 'RULE_ENUM_NARROWED',
      severity: 'BLOCKING',
      file_path: 'src/api/schemas/order.py',
      start_line: 42,
      end_line: 48,
      message:
        "Enum narrowed: removed value 'CANCELLED'. Active downstream consumer 'checkout-service' deserializes this status and will crash.",
      impacted_service: 'checkout-service',
    },
    {
      id: 'v2',
      rule_code: 'RULE_CLOSED_WORLD_COLLISION',
      severity: 'BLOCKING',
      file_path: 'src/api/schemas/order.py',
      start_line: 65,
      end_line: 69,
      message:
        "Producer added optional property ['warehouse_zone'], but consumer 'checkout-service' enforces strict 'additionalProperties: false'.",
      impacted_service: 'checkout-service',
    },
    {
      id: 'v3',
      rule_code: 'RULE_DDL_COLUMN_SHRUNK',
      severity: 'BLOCKING',
      file_path: 'migrations/versions/v2_shrink_sku.sql',
      start_line: 12,
      end_line: 14,
      message:
        "Database column 'sku' shrunk from VARCHAR(64) to VARCHAR(16). Legacy records and downstream consumers query this table directly.",
      impacted_service: 'analytics-pipeline',
    },
  ]

  // Seeded scenario 2: PR 143 (Safe Refactor)
  const pr143Nodes: Node[] = [
    {
      id: 'srv-inventory',
      position: { x: 280, y: 100 },
      data: { label: 'inventory-service\n(Clean Backward-Compatible)', is_origin: true },
      style: {
        background: '#064e3b',
        border: '2px solid #10b981',
        borderRadius: '12px',
        color: '#f8fafc',
        padding: '12px',
        fontWeight: 'bold',
        fontSize: '12px',
        textAlign: 'center',
        boxShadow: '0 0 20px rgba(16, 185, 129, 0.3)',
      },
    },
    {
      id: 'srv-checkout',
      position: { x: 180, y: 260 },
      data: { label: 'checkout-service\n(Compatible Open World)', is_origin: false },
      style: {
        background: '#101726',
        border: '1.5px solid #10b981',
        borderRadius: '10px',
        color: '#f8fafc',
        padding: '10px',
        fontSize: '11px',
        textAlign: 'center',
      },
    },
  ]

  const pr143Edges: Edge[] = [
    {
      id: 'e-checkout-inv-safe',
      source: 'srv-checkout',
      target: 'srv-inventory',
      label: 'Compatible Contract',
      animated: true,
    },
  ]

  return (
    <div className="min-h-screen bg-[#090d16] text-slate-100 flex flex-col font-sans">
      <Navbar onOpenTriggerModal={() => setIsModalOpen(true)} />

      <main className="flex-1 max-w-7xl w-full mx-auto p-6 space-y-6">
        {/* Top PR Header / Switcher */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-card border border-border p-4 rounded-xl">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-slate-800 flex items-center justify-center text-blue-400 border border-slate-700">
              <GitPullRequest className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono text-slate-400">inventory-service</span>
                <span className="text-slate-500">/</span>
                <h2 className="text-sm font-bold text-white">
                  {selectedPR === 142
                    ? 'PR #142: Refactor inventory item status & alter SKU column'
                    : 'PR #143: Internal code cleanup and documentation update'}
                </h2>
              </div>
              <div className="text-xs text-slate-400 flex items-center gap-2 mt-0.5">
                <span>Branch: <code className="text-blue-400 font-mono">feature/status-refactor</code></span>
                <span>•</span>
                <span>Base: <code className="text-slate-300 font-mono">main</code></span>
              </div>
            </div>
          </div>

          {/* PR Scenario Switcher */}
          <div className="flex items-center gap-1.5 bg-[#090d16] p-1 rounded-lg border border-border self-start sm:self-auto">
            <button
              onClick={() => setSelectedPR(142)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors cursor-pointer ${
                selectedPR === 142
                  ? 'bg-red-500/10 text-red-400 border border-red-500/20'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <AlertCircle className="w-3.5 h-3.5" />
              <span>PR #142 (Violations)</span>
            </button>
            <button
              onClick={() => setSelectedPR(143)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors cursor-pointer ${
                selectedPR === 143
                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>PR #143 (Safe)</span>
            </button>
          </div>
        </div>

        {/* Interactive Knowledge Graph & Impact Details Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left: @xyflow/react Interactive Dependency Graph */}
          <div className="lg:col-span-7 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                <Layers className="w-4 h-4 text-blue-400" />
                Blast Radius Dependency Topology
              </h3>
              <span className="text-xs text-slate-400">Interactive DAG (Pan / Zoom / Inspect)</span>
            </div>
            <GraphView
              key={selectedPR}
              initialNodes={selectedPR === 142 ? pr142Nodes : pr143Nodes}
              initialEdges={selectedPR === 142 ? pr142Edges : pr143Edges}
            />
          </div>

          {/* Right: Metrics & Impact Breakdown */}
          <div className="lg:col-span-5">
            <ScanDetails
              riskScore={selectedPR === 142 ? 85 : 12}
              riskLevel={selectedPR === 142 ? 'CRITICAL' : 'LOW'}
              directConsumers={selectedPR === 142 ? 2 : 1}
              transitiveConsumers={selectedPR === 142 ? 1 : 0}
              impactedConsumers={
                selectedPR === 142
                  ? [
                      { name: 'checkout-service', tier: 'TIER_1', hop: 1, rpm: 12500, is_observed: true },
                      { name: 'analytics-pipeline', tier: 'TIER_2', hop: 1, rpm: 4200, is_observed: true },
                      { name: 'billing-ledger', tier: 'TIER_1', hop: 2, rpm: 8900, is_observed: true },
                    ]
                  : [{ name: 'checkout-service', tier: 'TIER_1', hop: 1, rpm: 12500, is_observed: true }]
              }
              recommendedTests={
                selectedPR === 142
                  ? [
                      'pytest --service=checkout-service tests/integration/test_orders.py',
                      'npm test --prefix=services/checkout-service test/contract.spec.ts',
                      'pytest --service=billing-ledger tests/integration/test_ledger_sync.py',
                    ]
                  : ['pytest tests/unit/']
              }
            />
          </div>
        </div>

        {/* Violations Table */}
        <ViolationsTable violations={selectedPR === 142 ? pr142Violations : []} />
      </main>

      <TriggerScanModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSubmit={(data) => {
          setSelectedPR(data.prNumber)
        }}
      />
    </div>
  )
}

export default App
