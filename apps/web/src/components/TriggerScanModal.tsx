import React, { useState } from 'react'
import { X, Play } from 'lucide-react'
import { motion, AnimatePresence } from 'motion/react'

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

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.16, ease: [0.23, 1, 0.32, 1] }}
            className="fixed inset-0 bg-slate-900/30 backdrop-blur-xs"
            onClick={onClose}
          />

          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: 4 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 4 }}
            transition={{
              type: 'spring',
              duration: 0.28,
              bounce: 0.15,
            }}
            className="bg-white border border-slate-200/90 w-full max-w-md rounded-2xl p-6 shadow-modal relative z-10"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              onClick={onClose}
              className="absolute top-4 right-4 text-slate-400 hover:text-slate-700 p-1 rounded-lg hover:bg-slate-100 transition-colors cursor-pointer"
              aria-label="Close modal"
            >
              <X className="w-5 h-5" />
            </button>

            <h3 className="text-base font-bold text-slate-900 mb-1 tracking-tight">Simulate Pull Request Scan</h3>
            <p className="text-xs text-slate-500 mb-5">
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
                <label className="block text-xs font-semibold text-slate-700 mb-1">Target Repository</label>
                <input
                  type="text"
                  value={repo}
                  onChange={(e) => setRepo(e.target.value)}
                  className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-900 focus:outline-none focus:border-slate-900 focus:ring-1 focus:ring-slate-900/10 font-mono shadow-xs transition-colors"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Base Branch / SHA</label>
                  <input
                    type="text"
                    value={baseSha}
                    onChange={(e) => setBaseSha(e.target.value)}
                    className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-900 focus:outline-none focus:border-slate-900 focus:ring-1 focus:ring-slate-900/10 font-mono shadow-xs transition-colors"
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Head Branch / SHA</label>
                  <input
                    type="text"
                    value={headSha}
                    onChange={(e) => setHeadSha(e.target.value)}
                    className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-900 focus:outline-none focus:border-slate-900 focus:ring-1 focus:ring-slate-900/10 font-mono shadow-xs transition-colors"
                    required
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Pull Request Number</label>
                <input
                  type="number"
                  value={prNumber}
                  onChange={(e) => setPrNumber(parseInt(e.target.value, 10))}
                  className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-900 focus:outline-none focus:border-slate-900 focus:ring-1 focus:ring-slate-900/10 font-mono shadow-xs transition-colors"
                  required
                />
              </div>

              <div className="pt-2 flex justify-end gap-2.5">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-3.5 py-2 text-xs font-medium text-slate-700 hover:text-slate-900 bg-white hover:bg-slate-50 border border-slate-200 rounded-lg transition-colors cursor-pointer shadow-xs active:scale-[0.97]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-[#09090b] hover:bg-[#27272a] rounded-lg transition-colors shadow-sm cursor-pointer active:scale-[0.97]"
                >
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>Execute Scan</span>
                </button>
              </div>
            </form>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}
