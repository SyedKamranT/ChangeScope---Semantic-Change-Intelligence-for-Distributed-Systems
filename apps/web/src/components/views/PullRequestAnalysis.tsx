import React from 'react'
import { Card, CardHeader, CardContent } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { CodeSnippet } from '../ui/CodeSnippet'
import {
  GitPullRequest,
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  FileCode,
  Layers,
  Code,
} from 'lucide-react'
import { DEFAULT_VIOLATIONS } from '../../api/mockData'
import { NavViewKey } from '../layout/AppSidebar'

export interface PullRequestAnalysisProps {
  selectedPR: number
  setSelectedPR: (pr: number) => void
  onNavigate: (view: NavViewKey) => void
}

export const PullRequestAnalysis: React.FC<PullRequestAnalysisProps> = ({
  selectedPR,
  setSelectedPR,
  onNavigate,
}) => {
  const isDangerousPR = selectedPR === 142
  const violations = isDangerousPR ? DEFAULT_VIOLATIONS : []

  const sampleDiff = isDangerousPR
    ? `--- a/src/api/schemas/order.py
+++ b/src/api/schemas/order.py
@@ -42,7 +42,6 @@ class OrderStatus(str, Enum):
     PENDING = "PENDING"
     CONFIRMED = "CONFIRMED"
     SHIPPED = "SHIPPED"
-    CANCELLED = "CANCELLED"
     REFUNDED = "REFUNDED"
 
 class OrderPayload(BaseModel):
@@ -64,4 +63,5 @@ class OrderPayload(BaseModel):
     order_id: str
     total_cents: int
+    warehouse_zone: Optional[str] = None`
    : `--- a/src/services/order.py
+++ b/src/services/order.py
@@ -15,4 +15,5 @@ def validate_order(order):
     # Code refactoring: optimized log statement
-    logger.info("checking order")
+    logger.debug("validating incoming order payload")
     return True`

  return (
    <div className="space-y-6">
      {/* Header and PR Selector */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white border border-slate-200/90 p-4 rounded-2xl shadow-premium">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-slate-100 border border-slate-200 flex items-center justify-center text-slate-800 shadow-2xs">
            <GitPullRequest className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs text-slate-500 font-semibold">inventory-service</span>
              <span className="text-slate-300">/</span>
              <h2 className="text-sm font-bold text-slate-900 tracking-tight">
                {isDangerousPR
                  ? 'PR #142: Refactor inventory item status & alter SKU column'
                  : 'PR #143: Internal code cleanup & logging optimization'}
              </h2>
            </div>
            <div className="text-xs text-slate-500 flex items-center gap-2 mt-0.5">
              <span>Branch: <code className="text-blue-700 font-mono font-medium">feature/status-refactor</code></span>
              <span>•</span>
              <span>Base: <code className="text-slate-700 font-mono">main</code></span>
            </div>
          </div>
        </div>

        {/* PR Quick Scenario Switcher */}
        <div className="flex items-center gap-1.5 bg-slate-100/80 p-1 rounded-xl border border-slate-200/80">
          <button
            onClick={() => setSelectedPR(142)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer transition-all active:scale-[0.98] ${
              isDangerousPR
                ? 'bg-red-50 text-red-700 border border-red-200 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <AlertCircle className="w-3.5 h-3.5" />
            <span>PR #142 (Violations)</span>
          </button>
          <button
            onClick={() => setSelectedPR(143)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer transition-all active:scale-[0.98] ${
              !isDangerousPR
                ? 'bg-emerald-50 text-emerald-800 border border-emerald-200 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>PR #143 (Safe)</span>
          </button>
        </div>
      </div>

      {/* PR Impact Summary Bar */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white border border-slate-200/90 rounded-2xl p-4 flex items-center justify-between shadow-premium">
          <div>
            <div className="text-xs text-slate-500 font-medium">Risk Assessment</div>
            <div className="text-xl font-bold text-slate-900 mt-1 tabular-nums font-mono">
              {isDangerousPR ? '85 / 100' : '12 / 100'}
            </div>
            <Badge variant={isDangerousPR ? 'danger' : 'success'} className="mt-1.5">
              {isDangerousPR ? 'CRITICAL RISK' : 'LOW RISK (SAFE)'}
            </Badge>
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={() => onNavigate('impact_explorer')}
            icon={<Layers className="w-3.5 h-3.5" />}
          >
            Topology
          </Button>
        </div>

        <div className="bg-white border border-slate-200/90 rounded-2xl p-4 shadow-premium">
          <div className="text-xs text-slate-500 font-medium">Impacted Downstream Consumers</div>
          <div className="text-xl font-bold text-slate-900 mt-1">
            {isDangerousPR ? '3 Services' : '0 Services'}
          </div>
          <div className="text-xs text-slate-600 mt-1 font-mono">
            {isDangerousPR ? 'checkout-service, billing-ledger, analytics' : 'Clean backward-compatible'}
          </div>
        </div>

        <div className="bg-white border border-slate-200/90 rounded-2xl p-4 shadow-premium">
          <div className="text-xs text-slate-500 font-medium">Remediation Status</div>
          <div className="text-sm font-semibold text-slate-900 mt-1 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            <span>2 Test Cases Synthesized</span>
          </div>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => onNavigate('test_recommendations')}
            className="mt-2 text-xs text-blue-700 font-semibold p-0 hover:bg-transparent"
          >
            Review Generated Tests →
          </Button>
        </div>
      </div>

      {/* Git Diff Preview Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <FileCode className="w-4 h-4 text-slate-700" />
            <h3 className="text-sm font-bold text-slate-900 tracking-tight">Unified Patch Diff</h3>
          </div>
          <span className="text-xs text-slate-500 font-mono font-medium">
            {isDangerousPR ? 'src/api/schemas/order.py' : 'src/services/order.py'}
          </span>
        </CardHeader>
        <CardContent className="p-0">
          <CodeSnippet code={sampleDiff} language="diff" title="Git Diff" />
        </CardContent>
      </Card>

      {/* Contract & Semantic Violations Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-red-600" />
            <h3 className="text-sm font-bold text-slate-900 tracking-tight">
              Semantic Contract Violations ({violations.length})
            </h3>
          </div>
          <span className="text-xs text-slate-500 font-medium">
            Detected via AST evaluation and Neo4j blast radius traversal
          </span>
        </CardHeader>
        <CardContent className="p-0">
          {violations.length === 0 ? (
            <div className="p-8 text-center">
              <CheckCircle2 className="w-8 h-8 text-emerald-600 mx-auto mb-2" />
              <h4 className="text-sm font-bold text-slate-900">Clean Contract Evolution</h4>
              <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto leading-relaxed">
                No breaking contract breaches, enum narrowings, or database schema collisions detected.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {violations.map((v) => (
                <div key={v.id} className="p-4 hover:bg-slate-50/70 transition-colors">
                  <div className="flex items-start gap-3">
                    {v.severity === 'BLOCKING' ? (
                      <div className="p-1.5 rounded-xl bg-red-50 text-red-700 border border-red-200 mt-0.5">
                        <AlertCircle className="w-4 h-4" />
                      </div>
                    ) : (
                      <div className="p-1.5 rounded-xl bg-amber-50 text-amber-700 border border-amber-200 mt-0.5">
                        <AlertTriangle className="w-4 h-4" />
                      </div>
                    )}

                    <div className="space-y-1.5 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-mono text-xs font-bold text-slate-900">{v.rule_code}</span>
                        <Badge variant={v.severity === 'BLOCKING' ? 'danger' : 'warning'} size="sm">
                          {v.severity}
                        </Badge>
                        {v.impacted_service && (
                          <span className="text-[11px] text-slate-700 bg-slate-100 px-2 py-0.5 rounded-md border border-slate-200 font-medium">
                            Downstream Crash: <strong className="text-slate-900">{v.impacted_service}</strong>
                          </span>
                        )}
                      </div>

                      <p className="text-xs text-slate-700 leading-relaxed font-normal">{v.message}</p>

                      <div className="flex items-center gap-3 text-[11px] text-slate-500 font-mono">
                        <span className="flex items-center gap-1 text-blue-700 font-medium">
                          <Code className="w-3 h-3 text-slate-400" />
                          {v.file_path}:{v.start_line}-{v.end_line}
                        </span>
                        {v.json_pointer && (
                          <span className="text-slate-400">JSONPointer: {v.json_pointer}</span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
