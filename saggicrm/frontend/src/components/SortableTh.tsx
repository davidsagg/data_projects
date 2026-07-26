import { ArrowUp, ArrowDown, ChevronsUpDown } from 'lucide-react'
import clsx from 'clsx'

interface SortableThProps<T extends string> {
  field: T
  label: string
  activeField: T
  direction: 'asc' | 'desc'
  onSort: (field: T) => void
  align?: 'left' | 'right'
}

export function SortableTh<T extends string>({
  field,
  label,
  activeField,
  direction,
  onSort,
  align = 'left',
}: SortableThProps<T>) {
  const isActive = field === activeField
  return (
    <th className="p-0">
      <button
        type="button"
        onClick={() => onSort(field)}
        title={`Ordenar por ${label}`}
        className={clsx(
          'flex w-full cursor-pointer select-none items-center gap-1 px-2 py-3 text-xs font-medium uppercase tracking-wide hover:bg-accent-soft/60 hover:text-accent',
          align === 'right' && 'flex-row-reverse text-right',
          isActive ? 'text-accent' : 'text-muted',
        )}
      >
        {label}
        {isActive ? (
          direction === 'asc' ? (
            <ArrowUp size={12} />
          ) : (
            <ArrowDown size={12} />
          )
        ) : (
          <ChevronsUpDown size={12} className="opacity-40" />
        )}
      </button>
    </th>
  )
}
