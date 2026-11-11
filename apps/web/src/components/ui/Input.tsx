import React from 'react'
import { clsx } from 'clsx'

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  helperText?: string
  icon?: React.ReactNode
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, helperText, icon, id, ...props }, ref) => {
    const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined)

    return (
      <div className="w-full space-y-1.5">
        {label && (
          <label htmlFor={inputId} className="block text-xs font-semibold text-slate-700">
            {label}
          </label>
        )}
        <div className="relative">
          {icon && (
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
              {icon}
            </div>
          )}
          <input
            id={inputId}
            ref={ref}
            className={clsx(
              'w-full bg-white border rounded-lg text-xs text-slate-900 placeholder-slate-400',
              'py-2 transition-[border-color,box-shadow] duration-140 shadow-xs',
              'focus:outline-none focus:border-slate-900 focus:ring-1 focus:ring-slate-900/10',
              icon ? 'pl-9 pr-3' : 'px-3',
              error ? 'border-red-500' : 'border-slate-200 hover:border-slate-300',
              className
            )}
            {...props}
          />
        </div>
        {error ? (
          <p className="text-[11px] text-red-600 font-medium">{error}</p>
        ) : (
          helperText && <p className="text-[11px] text-slate-500">{helperText}</p>
        )}
      </div>
    )
  }
)

Input.displayName = 'Input'
