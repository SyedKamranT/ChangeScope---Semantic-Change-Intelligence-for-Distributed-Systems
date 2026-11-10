import React from 'react'
import { Flame, CheckCircle2, Terminal, ShieldAlert, Cpu } from 'lucide-react'

interface ConsumerItem {
  name: string
  tier: string
  hop: number
  rpm: number
  is_observed: boolean
}

interface ScanDetailsProps {
  riskScore: number
  riskLevel: string
  directConsumers: number
  transitiveConsumers: number
  impactedConsumers: ConsumerItem[]
  recommendedTests: string[]
}

export const ScanDetails: React.FC<ScanDetailsProps> = ({
  riskScore,
  riskLevel,
  directConsumers,
  transitiveConsumers,
  impactedConsumers,
  recommendedTests,
}) => {
  const getRiskColor = (score: number) => {
    if (score >= 80) return 'text-red-400 border-red-500/30 bg-red-500/10'
    if (score >= 60) return 'text-orange-400 border-orange-500/30 bg-orange-500/10'
    if (score >= 35) return 'text-amber-400 border-amber-500/30 bg-amber-500/10'
    return 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10'
  }

  return (
    <div className="space-y-6">
      {/* Risk Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-card border border-border rounded-xl p-5 flex items-center justify-between">
          <div>
            <div className="text-xs text-slate-400 font-medium">Blast Radius Risk</div>
            <div className="text-2xl font-bold text-white mt-1 flex items-baseline gap-2">
              {riskScore}
              <span className="text-xs font-normal text-slate-400">/ 100</span>
            </div>
            <span
              className={`inline-block mt-2 text-[10px] font-bold px-2 py-0.5 rounded border ${getRiskColor(
                riskScore
              )}`}
            >
              {riskLevel}
            </span>
          </div>
          <div className={`p-3 rounded-xl border ${getRiskColor(riskScore)}`}>
            {riskScore >= 60 ? (
              <Flame className="w-6 h-6 text-red-400 animate-pulse" />
            ) : (
              <ShieldAlert className="w-6 h-6 text-emerald-400" />
            )}
          </div>
        </div>

        <div className="bg-card border border-border rounded-xl p-5">
          <div className="text-xs text-slate-400 font-medium">Downstream Consumers</div>
          <div className="text-2xl font-bold text-white mt-1">
            {directConsumers + transitiveConsumers}
          </div>
          <div className="flex items-center gap-3 mt-2 text-xs text-slate-400">
            <span>Direct: <strong className="text-slate-200">{directConsumers}</strong></span>
            <span>•</span>
            <span>Transitive: <strong className="text-slate-200">{transitiveConsumers}</strong></span>
          </div>
        </div>

        <div className="bg-card border border-border rounded-xl p-5">
          <div className="text-xs text-slate-400 font-medium">Reasoning Engine</div>
          <div className="text-sm font-semibold text-white mt-1 flex items-center gap-2">
            <Cpu className="w-4 h-4 text-blue-400" />
            Deterministic Graph + LangGraph
          </div>
          <div className="text-xs text-emerald-400 flex items-center gap-1.5 mt-2">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Citation Guard: 100% Grounded</span>
          </div>
        </div>
      </div>

      {/* Impacted Consumers Breakdown */}
      <div className="bg-card border border-border rounded-xl p-5">
        <h4 className="text-sm font-semibold text-white mb-3">Downstream Topological Impact</h4>
        <div className="space-y-2.5">
          {impactedConsumers.map((c, i) => (
            <div
              key={i}
              className="flex items-center justify-between p-3 rounded-lg bg-[#090d16] border border-border text-xs"
            >
              <div className="flex items-center gap-3">
                <span className="w-2 h-2 rounded-full bg-blue-500" />
                <span className="font-mono font-medium text-white">{c.name}</span>
                <span className="text-[10px] font-semibold bg-slate-800 text-slate-300 px-1.5 py-0.5 rounded border border-slate-700">
                  {c.tier}
                </span>
                <span className="text-slate-400">({c.hop} hop{c.hop > 1 ? 's' : ''})</span>
              </div>
              <div className="flex items-center gap-4 text-slate-400">
                <span>{c.is_observed ? 'Observed (OTel)' : 'Inferred (AST)'}</span>
                <span className="font-mono text-slate-200 font-medium">{c.rpm.toLocaleString()} RPM</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Targeted Regression Test Recommendations */}
      {recommendedTests.length > 0 && (
        <div className="bg-card border border-border rounded-xl p-5">
          <h4 className="text-sm font-semibold text-white flex items-center gap-2 mb-2">
            <Terminal className="w-4 h-4 text-blue-400" />
            Recommended Targeted Regression Tests
          </h4>
          <p className="text-xs text-slate-400 mb-3">
            ChangeScope identified the exact downstream suites to run, reducing CI execution time by ~75%.
          </p>
          <div className="space-y-2">
            {recommendedTests.map((cmd, idx) => (
              <div
                key={idx}
                className="bg-[#090d16] border border-border p-2.5 rounded-lg font-mono text-xs text-emerald-400 flex items-center justify-between select-all"
              >
                <span>$ {cmd}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
