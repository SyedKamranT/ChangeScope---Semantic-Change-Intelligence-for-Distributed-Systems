import React from 'react'
import { clsx } from 'clsx'

export const Table: React.FC<React.TableHTMLAttributes<HTMLTableElement>> = ({
  className,
  children,
  ...props
}) => {
  return (
    <div className="w-full overflow-x-auto rounded-xl border border-slate-200/80 bg-white shadow-premium">
      <table className={clsx('w-full text-left text-xs text-slate-700', className)} {...props}>
        {children}
      </table>
    </div>
  )
}

export const TableHeader: React.FC<React.HTMLAttributes<HTMLTableSectionElement>> = ({
  className,
  children,
  ...props
}) => {
  return (
    <thead
      className={clsx(
        'bg-slate-50/80 border-b border-slate-200 text-[11px] font-semibold text-slate-500 uppercase tracking-wider',
        className
      )}
      {...props}
    >
      {children}
    </thead>
  )
}

export const TableRow: React.FC<React.HTMLAttributes<HTMLTableRowElement>> = ({
  className,
  children,
  ...props
}) => {
  return (
    <tr
      className={clsx('border-b border-slate-100 hover:bg-slate-50/60 transition-colors duration-100', className)}
      {...props}
    >
      {children}
    </tr>
  )
}

export const TableHead: React.FC<React.ThHTMLAttributes<HTMLTableCellElement>> = ({
  className,
  children,
  ...props
}) => {
  return (
    <th className={clsx('py-3 px-4 font-semibold text-slate-600', className)} {...props}>
      {children}
    </th>
  )
}

export const TableCell: React.FC<React.TdHTMLAttributes<HTMLTableCellElement>> = ({
  className,
  children,
  ...props
}) => {
  return (
    <td className={clsx('py-3.5 px-4 text-slate-700', className)} {...props}>
      {children}
    </td>
  )
}
