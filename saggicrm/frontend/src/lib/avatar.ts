const PALETTE = [
  '#6d4aff',
  '#0ea5a4',
  '#e2622b',
  '#2563eb',
  '#c026d3',
  '#16a34a',
  '#d946ef',
  '#ea580c',
  '#0891b2',
  '#9333ea',
]

function hashString(value: string): number {
  let hash = 0
  for (let i = 0; i < value.length; i++) {
    hash = (hash << 5) - hash + value.charCodeAt(i)
    hash |= 0
  }
  return Math.abs(hash)
}

export function initials(firstName: string, lastName: string): string {
  const a = firstName.trim().charAt(0)
  const b = lastName.trim().charAt(0)
  return (a + b).toUpperCase() || '?'
}

export function colorFor(seed: string): string {
  if (!seed) return PALETTE[0]
  return PALETTE[hashString(seed) % PALETTE.length]
}
