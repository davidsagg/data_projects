import { X } from 'lucide-react'
import type { Group } from '../types'

export function GroupChip({ group, onRemove }: { group: Group; onRemove?: () => void }) {
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium"
      style={{ background: `${group.color}22`, color: group.color }}
    >
      {group.name}
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          className="rounded-full opacity-70 hover:opacity-100"
          aria-label={`Remover grupo ${group.name}`}
        >
          <X size={12} />
        </button>
      )}
    </span>
  )
}
