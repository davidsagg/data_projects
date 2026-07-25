import { useState } from 'react'
import { MapPinned } from 'lucide-react'
import { geocodeApi } from '../api/client'

export function BulkGeocodeButton({ onDone }: { onDone?: () => void }) {
  const [running, setRunning] = useState(false)
  const [processed, setProcessed] = useState(0)

  async function run() {
    setRunning(true)
    setProcessed(0)
    let remaining = 1
    let total = 0
    while (remaining > 0) {
      const result = await geocodeApi.bulk(15)
      total += result.processed
      remaining = result.remaining
      setProcessed(total)
      if (result.processed === 0) break
    }
    setRunning(false)
    onDone?.()
  }

  return (
    <button
      onClick={run}
      disabled={running}
      className="flex items-center gap-2 rounded-lg border border-accent px-4 py-2 text-sm font-medium text-accent hover:bg-accent-soft disabled:opacity-50"
    >
      <MapPinned size={16} />
      {running ? `Geocodificando empresas... (${processed})` : 'Sugerir cidades por empresa (em lote)'}
    </button>
  )
}
