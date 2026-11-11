import React, { useEffect, useRef } from 'react'
import { Card } from './Card'
import { clsx } from 'clsx'
import gsap from 'gsap'

export interface StatCardProps {
  label: string
  value: string | number
  subValue?: string
  trend?: string
  trendDirection?: 'up' | 'down' | 'neutral'
  icon?: React.ReactNode
  statusIndicator?: 'success' | 'warning' | 'danger' | 'info'
}

export const StatCard: React.FC<StatCardProps> = ({
  label,
  value,
  subValue,
  trend,
  trendDirection = 'neutral',
  icon,
  statusIndicator,
}) => {
  const numberRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (typeof value === 'number' && numberRef.current) {
      const targetVal = value
      const obj = { val: 0 }
      const tween = gsap.to(obj, {
        val: targetVal,
        duration: 0.65,
        ease: 'power2.out',
        onUpdate: () => {
          if (numberRef.current) {
            numberRef.current.textContent = Math.round(obj.val).toLocaleString()
          }
        },
      })
      return () => {
        tween.kill()
      }
    }
  }, [value])

  const statusColors = {
    success: 'text-emerald-600',
    warning: 'text-amber-600',
    danger: 'text-red-600',
    info: 'text-sky-600',
  }

  return (
    <Card className="p-4 flex flex-col justify-between hoverEffect">
      <div className="flex items-center justify-between text-xs text-slate-500">
        <span className="font-medium text-slate-600">{label}</span>
        {icon && <span className="text-slate-400">{icon}</span>}
      </div>

      <div className="mt-2.5 flex items-baseline gap-2">
        <div
          ref={numberRef}
          className={clsx(
            'text-2xl font-bold tracking-tight tabular-nums',
            statusIndicator ? statusColors[statusIndicator] : 'text-slate-900'
          )}
        >
          {typeof value === 'number' ? value.toLocaleString() : value}
        </div>
        {subValue && <span className="text-xs text-slate-400">{subValue}</span>}
      </div>

      {trend && (
        <div className="mt-2 text-[11px] text-slate-500 flex items-center gap-1.5">
          <span
            className={clsx(
              'font-semibold',
              trendDirection === 'up' && 'text-emerald-600',
              trendDirection === 'down' && 'text-red-600',
              trendDirection === 'neutral' && 'text-slate-500'
            )}
          >
            {trend}
          </span>
        </div>
      )}
    </Card>
  )
}
