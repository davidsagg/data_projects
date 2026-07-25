import type { ReactNode } from 'react'

interface StatTileProps {
  label: string
  value: string | number
  icon?: ReactNode
}

export function StatTile({ label, value, icon }: StatTileProps) {
  return (
    <div className="flex items-center gap-4 rounded-xl border border-border bg-surface p-5">
      {icon && (
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent-soft text-accent">
          {icon}
        </div>
      )}
      <div>
        <div className="text-sm text-muted">{label}</div>
        <div className="text-2xl font-semibold text-text">{value}</div>
      </div>
    </div>
  )
}
