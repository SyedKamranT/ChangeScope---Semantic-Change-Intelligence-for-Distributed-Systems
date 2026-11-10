import React, { useState } from 'react'
import { X, Play } from 'lucide-react'

interface TriggerScanModalProps {
  isOpen: boolean
  onClose: () => void
  onSubmit: (data: { repo: string; baseSha: string; headSha: string; prNumber: number }) => void
}

export const TriggerScanModal: React.FC<TriggerScanModalProps> = ({ isOpen, onClose, onSubmit }) => {
  const [repo, setRepo] = useState('inventory-service')
  const [baseSha, setBaseSha] = useState('main')
  const [headSha, setHeadSha] = useState('feature/narrow-order-status')
  const [prNumber, setPrNumber] = useState(142)

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-[#101726] border border-border w-full max-w-md rounded-2xl p-6 shadow-2xl relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors cursor-pointer"
        >
          <X className="w-5 h-5" />
        </button>

        <h3 className="text-base font-bold text-white mb-1">Simulate Pull Request Scan</h3>
        <p className="text-xs text-slate-400 mb-5">
          Trigger change intelligence analysis across Tree-sitter AST, OpenAPI schemas, and Neo4j graph.
        </p>

        <form
          onSubmit={(e) => {
            e.preventDefault()
            onSubmit({ repo, baseSha, headSha, prNumber })
            onClose()
          }}
          className="space-y-4"
        >
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">Target Repository</label>
            <input
              type="text"
              value={repo}
              onChange={(e) => setRepo(e.target.value)}
              className="w-full bg-[#090d16] border border-border rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-500 font-mono"
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Base Branch / SHA</label>
              <input
                type="text"
                value={baseSha}
                onChange={(e) => setBaseSha(e.target.value)}
                className="w-full bg-[#090d16] border border-border rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-500 font-mono"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Head Branch / SHA</label>
              <input
                type="text"
                value={headSha}
                onChange={(e) => setHeadSha(e.target.value)}
                className="w-full bg-[#090d16] border border-border rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-500 font-mono"
                required
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">Pull Request Number</label>
            <input
              type="number"
              value={prNumber}
              onChange={(e) => setPrNumber(parseInt(e.target.value, 10))}
              className="w-full bg-[#090d16] border border-border rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-500 font-mono"
              required
            />
          </div>

          <div className="pt-2 flex justify-end gap-2.5">
            <button
              type="button"
              onClick={onClose}
              className="px-3.5 py-2 text-xs font-medium text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 rounded-lg transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-500 rounded-lg transition-colors shadow-lg shadow-blue-600/20 cursor-pointer"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>Execute Scan</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
