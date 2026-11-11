import React, { useState, useEffect } from 'react'
import { Card, CardHeader, CardContent } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { CodeSnippet } from '../ui/CodeSnippet'
import { TestTube, ShieldAlert, CheckCircle2, Download } from 'lucide-react'
import { api } from '../../api/client'
import { TestRecommendationItem } from '../../api/types'

export const TestRecommendations: React.FC = () => {
  const [recommendations, setRecommendations] = useState<TestRecommendationItem[]>([])

  useEffect(() => {
    async function loadData() {
      const data = await api.fetchTestRecommendations()
      setRecommendations(data)
    }
    loadData()
  }, [])

  const handleApprove = (id: string) => {
    setRecommendations((prev) =>
      prev.map((r) => (r.id === id ? { ...r, review_status: 'APPROVED' } : r))
    )
  }

  const handleDismiss = (id: string) => {
    setRecommendations((prev) =>
      prev.map((r) => (r.id === id ? { ...r, review_status: 'DISMISSED' } : r))
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
              <TestTube className="w-5 h-5 text-slate-700" />
              Automated Remediation & Test Generation
            </h1>
            <Badge variant="purple" size="sm">
              LangGraph Orchestrated
            </Badge>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Grounded regression tests synthesized directly from changed AST nodes and active consumer call sites.
          </p>
        </div>

        <Button
          size="sm"
          variant="outline"
          icon={<Download className="w-3.5 h-3.5" />}
          onClick={() => {
            const suite = recommendations.map((r) => r.test_code).join('\n\n')
            const blob = new Blob([suite], { type: 'text/x-python' })
            const url = URL.createObjectURL(blob)
            const a = document.createElement('a')
            a.href = url
            a.download = 'changescope_generated_tests.py'
            a.click()
          }}
        >
          Export Pytest Suite
        </Button>
      </div>

      {/* Mandatory Human Review Policy Alert */}
      <div className="bg-white border border-slate-200/90 rounded-2xl p-4 flex items-start gap-3 text-xs text-slate-700 shadow-premium">
        <ShieldAlert className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <span className="font-bold text-slate-900">Compliance Invariant:</span>
          <p className="text-slate-600 leading-relaxed font-normal">
            All AI-synthesized regression tests default to{' '}
            <code className="text-amber-800 font-bold bg-amber-50 px-1 py-0.5 rounded border border-amber-200">PENDING_HUMAN_REVIEW</code>.
            Tests are never merged into master or CI pipelines without explicit approval from a verified engineer or analyst.
          </p>
        </div>
      </div>

      {/* Test Recommendations Cards */}
      <div className="space-y-5">
        {recommendations.map((rec) => (
          <Card key={rec.id} className="space-y-4">
            <CardHeader className="bg-slate-50/70">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-xl bg-slate-100 text-slate-700 border border-slate-200">
                  <TestTube className="w-4 h-4" />
                </div>
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="text-sm font-bold text-slate-900 font-mono tracking-tight">{rec.test_name}</h3>
                    <Badge
                      variant={
                        rec.review_status === 'APPROVED'
                          ? 'success'
                          : rec.review_status === 'DISMISSED'
                          ? 'neutral'
                          : 'warning'
                      }
                      size="sm"
                    >
                      {rec.review_status}
                    </Badge>
                  </div>
                  <div className="text-[11px] text-slate-500 mt-0.5 font-mono">
                    Target Consumer: <strong className="text-slate-900 font-bold">{rec.target_service}</strong> •
                    Confidence: {(rec.confidence * 100).toFixed(0)}%
                  </div>
                </div>
              </div>

              {/* Approval Buttons */}
              <div className="flex items-center gap-2">
                {rec.review_status === 'PENDING_HUMAN_REVIEW' && (
                  <>
                    <Button
                      size="sm"
                      variant="primary"
                      onClick={() => handleApprove(rec.id)}
                      icon={<CheckCircle2 className="w-3.5 h-3.5" />}
                    >
                      Approve for CI
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => handleDismiss(rec.id)}
                    >
                      Dismiss
                    </Button>
                  </>
                )}
                {rec.review_status === 'APPROVED' && (
                  <span className="text-xs text-emerald-700 flex items-center gap-1 font-bold">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    Approved by Analyst
                  </span>
                )}
              </div>
            </CardHeader>

            <CardContent className="space-y-3.5 pt-0">
              <div className="text-xs text-slate-700">
                <span className="text-slate-500 font-bold uppercase tracking-wider text-[10px]">
                  Preconditions:
                </span>{' '}
                {rec.preconditions}
              </div>

              <div className="text-xs text-slate-500">
                <span className="text-slate-500 font-bold uppercase tracking-wider text-[10px]">
                  Addressed Finding:
                </span>{' '}
                <code className="text-red-700 font-mono text-[11px] font-semibold bg-red-50 px-1 py-0.5 rounded border border-red-200">{rec.relevant_finding}</code>
              </div>

              {/* Code Snippet with Copy */}
              <CodeSnippet code={rec.test_code} language="python" title="Generated Python Test" />
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
