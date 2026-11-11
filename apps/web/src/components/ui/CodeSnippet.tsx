import React, { useState } from 'react'
import { Copy, Check } from 'lucide-react'

export interface CodeSnippetProps {
  code: string
  language?: string
  title?: string
}

export const CodeSnippet: React.FC<CodeSnippetProps> = ({ code, language, title }) => {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="bg-[#f8fafc] border border-slate-200/90 rounded-xl overflow-hidden font-mono text-xs shadow-xs">
      <div className="px-3.5 py-2 bg-white border-b border-slate-200 flex items-center justify-between text-slate-600">
        <span className="font-sans text-[11px] font-semibold text-slate-700">
          {title || language || 'code'}
        </span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 px-2 py-1 rounded-md hover:bg-slate-100 text-slate-500 hover:text-slate-800 transition-colors cursor-pointer"
          aria-label="Copy code"
        >
          {copied ? (
            <>
              <Check className="w-3.5 h-3.5 text-emerald-600" />
              <span className="text-[10px] text-emerald-600 font-sans font-medium">Copied</span>
            </>
          ) : (
            <>
              <Copy className="w-3.5 h-3.5" />
              <span className="text-[10px] font-sans font-medium">Copy</span>
            </>
          )}
        </button>
      </div>

      <div className="p-4 overflow-x-auto text-slate-800 leading-relaxed max-h-72 select-text font-mono">
        <pre>
          <code>{code}</code>
        </pre>
      </div>
    </div>
  )
}
