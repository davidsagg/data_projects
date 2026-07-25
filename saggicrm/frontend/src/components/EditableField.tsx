import { useEffect, useState } from 'react'

interface EditableFieldProps {
  label: string
  value: string
  placeholder?: string
  onSave: (value: string) => void
}

export function EditableField({ label, value, placeholder, onSave }: EditableFieldProps) {
  const [draft, setDraft] = useState(value)

  useEffect(() => {
    setDraft(value)
  }, [value])

  return (
    <div>
      <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted">
        {label}
      </label>
      <input
        value={draft}
        placeholder={placeholder}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => {
          if (draft !== value) onSave(draft)
        }}
        className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text outline-none focus:border-accent"
      />
    </div>
  )
}
