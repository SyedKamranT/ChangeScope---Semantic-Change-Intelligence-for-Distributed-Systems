import React from 'react'
import { clsx } from 'clsx'

export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string
  error?: string
  options: { label: string; value: string }[]
}

export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, label, error, options, id, ...props }, ref) => {
    const selectId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined)

    return (
      <div className="w-full space-y-1.5">
        {label && (
          <label htmlFor={selectId} className="block text-xs font-semibold text-slate-700">
            {label}
          </label>
        )}
        <select
          id={selectId}
          ref={ref}
          className={clsx(
            'w-full bg-white border rounded-lg text-xs text-slate-900 px-3 py-2 shadow-xs cursor-pointer',
            'transition-[border-color,box-shadow] duration-140',
            'focus:outline-none focus:border-slate-900 focus:ring-1 focus:ring-slate-900/10',
            error ? 'border-red-500' : 'border-slate-200 hover:border-slate-300',
            className
          )}
          {...props}
        >
          {options.map((opt) => (
            <option key={opt.value} value={opt.value} className="bg-white text-slate-900">
              {opt.label}
            </option>
          ))}
        </select>
        {error && <p className="text-[11px] text-red-600 font-medium">{error}</p>}
      </div>
    )
  }
)

Select.displayName = 'Select'
