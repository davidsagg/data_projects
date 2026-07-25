import { useRef, useState } from 'react'
import { UploadCloud, CheckCircle2 } from 'lucide-react'
import { importApi } from '../api/client'
import type { ImportSummary } from '../types'
import { Card } from '../components/Card'
import { BulkGeocodeButton } from '../components/BulkGeocodeButton'

export function ImportPage() {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [summary, setSummary] = useState<ImportSummary | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleFile(file: File) {
    setUploading(true)
    setError(null)
    try {
      const result = await importApi.linkedin(file)
      setSummary(result)
    } catch {
      setError('Não foi possível importar esse arquivo. Confirme que é o Connections.csv exportado do LinkedIn.')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-semibold text-text">Importar do LinkedIn</h1>
        <p className="text-sm text-muted">
          Exporte suas conexões em linkedin.com/psettings/member-data ("Get a copy of your data" →
          "Connections") e envie o arquivo <code className="rounded bg-accent-soft px-1 text-accent">Connections.csv</code> aqui.
          Reimportar não sobrescreve cidade, grupos, notas ou lembretes já preenchidos.
        </p>
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          const file = e.dataTransfer.files[0]
          if (file) handleFile(file)
        }}
        onClick={() => inputRef.current?.click()}
        className={`flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed p-12 text-center transition-colors ${
          dragging ? 'border-accent bg-accent-soft' : 'border-border bg-surface'
        }`}
      >
        <UploadCloud size={32} className="text-accent" />
        <p className="text-sm font-medium text-text">Arraste o Connections.csv aqui, ou clique para escolher</p>
        <input
          ref={inputRef}
          type="file"
          accept=".csv"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) handleFile(file)
          }}
        />
        {uploading && <p className="text-sm text-accent">Importando...</p>}
      </div>

      {error && <p className="text-sm text-red-500">{error}</p>}

      {summary && (
        <Card className="space-y-4">
          <div className="flex items-center gap-2 text-accent">
            <CheckCircle2 size={18} />
            <span className="font-medium">Import concluído</span>
          </div>
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <div className="text-2xl font-semibold text-text">{summary.created}</div>
              <div className="text-xs text-muted">novos</div>
            </div>
            <div>
              <div className="text-2xl font-semibold text-text">{summary.updated}</div>
              <div className="text-xs text-muted">atualizados</div>
            </div>
            <div>
              <div className="text-2xl font-semibold text-text">{summary.skipped_blank}</div>
              <div className="text-xs text-muted">ignorados (sem dados)</div>
            </div>
          </div>
          <div className="border-t border-border pt-4">
            <p className="mb-3 text-sm text-muted">
              Agora você pode sugerir a cidade dos seus contatos com base na empresa deles:
            </p>
            <BulkGeocodeButton />
          </div>
        </Card>
      )}
    </div>
  )
}
