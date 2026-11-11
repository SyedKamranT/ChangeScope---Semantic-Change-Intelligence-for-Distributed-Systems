import React from 'react'
import { clsx } from 'clsx'

export type BadgeVariant =
  | 'default'
  | 'danger'
  | 'warning'
  | 'success'
  | 'info'
  | 'neutral'
  | 'purple'

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant
  size?: 'sm' | 'md'
  dot?: boolean
}

const variantStyles: Record<BadgeVariant, { bg: string; dotColor: string }> = {
  default: {
    bg: 'bg-blue-50 text-blue-700 border-blue-200',
    dotColor: 'bg-blue-500',
  },
  danger: {
    bg: 'bg-red-50 text-red-700 border-red-200',
    dotColor: 'bg-red-500',
  },
  warning: {
    bg: 'bg-amber-50 text-amber-800 border-amber-200',
    dotColor: 'bg-amber-500',
  },
  success: {
    bg: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    dotColor: 'bg-emerald-500',
  },
  info: {
    bg: 'bg-sky-50 text-sky-700 border-sky-200',
    dotColor: 'bg-sky-500',
  },
  neutral: {
    bg: 'bg-slate-100 text-slate-700 border-slate-200',
    dotColor: 'bg-slate-400',
  },
  purple: {
    bg: 'bg-indigo-50 text-indigo-700 border-indigo-200',
    dotColor: 'bg-indigo-500',
  },
}

export const Badge: React.FC<BadgeProps> = ({
  variant = 'default',
  size = 'sm',
  dot = false,
  className,
  children,
  ...props
}) => {
  const styles = variantStyles[variant]

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 font-medium border rounded-md uppercase tracking-wider',
        size === 'sm' ? 'text-[10px] px-2 py-0.5' : 'text-xs px-2.5 py-1',
        styles.bg,
        className
      )}
      {...props}
    >
      {dot && <span className={clsx('w-1.5 h-1.5 rounded-full', styles.dotColor)} />}
      {children}
    </span>
  )
}
