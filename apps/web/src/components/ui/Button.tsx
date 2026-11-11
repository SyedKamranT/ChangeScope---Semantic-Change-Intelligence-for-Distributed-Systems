import React from 'react'
import { clsx } from 'clsx'
import { Loader2 } from 'lucide-react'

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost' | 'outline'
  size?: 'sm' | 'md' | 'lg'
  isLoading?: boolean
  icon?: React.ReactNode
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = 'secondary',
      size = 'md',
      isLoading = false,
      icon,
      children,
      disabled,
      ...props
    },
    ref
  ) => {
    const sizeClasses = {
      sm: 'text-xs px-2.5 py-1.5 h-7 gap-1.5',
      md: 'text-xs font-medium px-3.5 py-2 h-9 gap-2',
      lg: 'text-sm font-medium px-4 py-2.5 h-10 gap-2.5',
    }

    const variantClasses = {
      primary:
        'bg-[#09090b] hover:bg-[#27272a] text-white shadow-xs border border-zinc-800 hover:border-zinc-700 active:scale-[0.97]',
      secondary:
        'bg-white hover:bg-slate-50/90 text-slate-700 hover:text-slate-900 border border-slate-200 hover:border-slate-300 shadow-xs active:scale-[0.97]',
      danger:
        'bg-red-50 hover:bg-red-100/80 text-red-700 border border-red-200 shadow-xs active:scale-[0.97]',
      ghost:
        'bg-transparent hover:bg-slate-100/70 text-slate-600 hover:text-slate-900 border border-transparent active:scale-[0.97]',
      outline:
        'bg-transparent hover:bg-white text-slate-700 hover:text-slate-900 border border-slate-200 hover:border-slate-300 shadow-xs active:scale-[0.97]',
    }

    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={clsx(
          'inline-flex items-center justify-center rounded-lg font-medium cursor-pointer',
          'transition-[transform,background-color,border-color,box-shadow] duration-140 ease-[cubic-bezier(0.16,1,0.3,1)]',
          'focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-900/30 focus-visible:ring-offset-1 focus-visible:ring-offset-white',
          'disabled:opacity-50 disabled:pointer-events-none disabled:cursor-not-allowed',
          sizeClasses[size],
          variantClasses[variant],
          className
        )}
        {...props}
      >
        {isLoading ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin text-current" />
        ) : (
          icon && <span className="shrink-0">{icon}</span>
        )}
        <span>{children}</span>
      </button>
    )
  }
)

Button.displayName = 'Button'
