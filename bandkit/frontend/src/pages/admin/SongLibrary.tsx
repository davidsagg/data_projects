import { useEffect, useRef, useState, useCallback } from 'react'
import { songsApi } from '../../api/client'
import type { Song } from '../../types'

const STATUS_STYLE: Record<string, string> = {
  parsed: 'bg-green-100 text-green-700',
  failed:  'bg-red-100 text-red-700',
  pending: 'bg-gray-100 text-gray-600',
  manual:  'bg-blue-100 text-blue-700',
}

/** Extrai {key: X} do conteúdo BKCP. */
function extractKey(bkcp: string): string | null {
  const m = bkcp.match(/\{key:\s*([^}]+)\}/i)
  return m ? m[1].trim() : null
}

export default function SongLibrary() {
  const [songs,     setSongs]     = useState<Song[]>([])
  const [search,    setSearch]    = useState('')
  const [selected,  setSelected]  = useState<Song | null>(null)
  const [bkcp,      setBkcp]      = useState('')
  const [isDirty,   setIsDirty]   = useState(false)
  const [saving,    setSaving]    = useState(false)
  const [saveMsg,   setSaveMsg]   = useState<'ok' | 'err' | null>(null)
  const [uploading, setUploading] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    songsApi.list().then((data) => setSongs(data as Song[]))
  }, [])

  const filtered = songs.filter(
    (s) =>
      s.title.toLowerCase().includes(search.toLowerCase()) ||
      (s.artist ?? '').toLowerCase().includes(search.toLowerCase())
  )

  const handleSelect = (song: Song) => {
    if (isDirty && !confirm('Há alterações não salvas. Descartar?')) return
    setSelected(song)
    setBkcp(song.bkcp_content ?? '')
    setIsDirty(false)
    setSaveMsg(null)
  }

  const handleBkcpChange = (value: string) => {
    setBkcp(value)
    setIsDirty(value !== (selected?.bkcp_content ?? ''))
    setSaveMsg(null)
  }

  const handleSave = useCallback(async () => {
    if (!selected || !isDirty) return
    setSaving(true)
    try {
      const key_original = extractKey(bkcp)
      const updated = await songsApi.patch(selected.id, {
        bkcp_content: bkcp,
        key_original,   // atualiza o tom a partir do {key: X} no BKCP
      }) as Song
      setSongs((ss) => ss.map((s) => s.id === updated.id ? updated : s))
      setSelected(updated)
      setIsDirty(false)
      setSaveMsg('ok')
      setTimeout(() => setSaveMsg(null), 2500)
    } catch {
      setSaveMsg('err')
    } finally {
      setSaving(false)
    }
  }, [selected, bkcp, isDirty])

  // Ctrl+S / Cmd+S para salvar
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault()
        handleSave()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [handleSave])

  const handleDelete = async (song: Song) => {
    if (!confirm(`Apagar "${song.title}" e o PDF original?`)) return
    try {
      await songsApi.delete(song.id)
      setSongs((ss) => ss.filter((s) => s.id !== song.id))
      if (selected?.id === song.id) { setSelected(null); setBkcp(''); setIsDirty(false) }
    } catch {
      alert('Erro ao apagar a música')
    }
  }

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      const song = await songsApi.upload(file)
      setSongs((ss) => [...ss, song as Song])
      handleSelect(song as Song)
    } catch {
      alert('Erro no upload do PDF')
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  return (
    <div className="flex h-screen bg-gray-50">

      {/* Sidebar */}
      <div className="w-72 bg-white border-r border-gray-200 flex flex-col shrink-0">
        <div className="p-4 border-b border-gray-100">
          <h1 className="text-lg font-semibold text-gray-900 mb-3">Músicas</h1>
          <input
            type="text"
            placeholder="Buscar título ou artista…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
        </div>

        <div className="flex-1 overflow-auto divide-y divide-gray-50">
          {filtered.length === 0 && (
            <p className="text-sm text-gray-400 text-center py-8">Nenhuma música encontrada</p>
          )}
          {filtered.map((song) => (
            <div
              key={song.id}
              className={`group flex items-start px-4 py-3 hover:bg-gray-50 transition cursor-pointer ${
                selected?.id === song.id ? 'bg-blue-50 border-l-2 border-blue-500' : ''
              }`}
              onClick={() => handleSelect(song)}
            >
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-gray-900 truncate">{song.title}</div>
                {song.artist && (
                  <div className="text-xs text-gray-500 truncate">{song.artist}</div>
                )}
                <div className="mt-1.5 flex items-center gap-2">
                  <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${
                    STATUS_STYLE[song.parse_status] ?? 'bg-gray-100 text-gray-600'
                  }`}>
                    {song.parse_status}
                  </span>
                  {song.key_original && (
                    <span className="text-xs text-gray-400">{song.key_original}</span>
                  )}
                </div>
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); handleDelete(song) }}
                className="ml-2 mt-0.5 opacity-0 group-hover:opacity-100 text-gray-300 hover:text-red-500 transition p-1 shrink-0"
                title="Apagar música"
              >
                🗑
              </button>
            </div>
          ))}
        </div>

        <div className="p-4 border-t border-gray-100">
          <input ref={fileRef} type="file" accept=".pdf" className="hidden" onChange={handleUpload} />
          <button
            onClick={() => fileRef.current?.click()}
            disabled={uploading}
            className="w-full bg-blue-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium"
          >
            {uploading ? 'Enviando…' : '↑ Upload PDF'}
          </button>
        </div>
      </div>

      {/* Editor */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {selected ? (
          <>
            {/* Header com botão Salvar */}
            <div className="px-6 py-4 bg-white border-b border-gray-200 shrink-0 flex items-start justify-between gap-4">
              <div className="min-w-0">
                <h2 className="text-lg font-semibold text-gray-900 truncate">{selected.title}</h2>
                <div className="flex items-center gap-3 mt-1 text-sm text-gray-500 flex-wrap">
                  {selected.artist && <span>{selected.artist}</span>}
                  {selected.key_original && <span>Tom: <strong>{selected.key_original}</strong></span>}
                  {isDirty && (
                    <span className="text-amber-600 text-xs font-medium">● alterações não salvas</span>
                  )}
                  {saveMsg === 'ok' && (
                    <span className="text-green-600 text-xs font-medium">✓ salvo</span>
                  )}
                  {saveMsg === 'err' && (
                    <span className="text-red-600 text-xs font-medium">✗ erro ao salvar</span>
                  )}
                </div>
              </div>

              <button
                onClick={handleSave}
                disabled={!isDirty || saving}
                className="shrink-0 bg-blue-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-blue-700
                           disabled:opacity-40 disabled:cursor-not-allowed transition font-medium"
                title="Salvar (Ctrl+S)"
              >
                {saving ? 'Salvando…' : 'Salvar'}
              </button>
            </div>

            {/* Textarea BKCP */}
            <div className="flex-1 p-4 overflow-hidden">
              <textarea
                value={bkcp}
                onChange={(e) => handleBkcpChange(e.target.value)}
                className="w-full h-full font-mono text-sm border border-gray-200 rounded-xl p-4 resize-none
                           focus:outline-none focus:ring-2 focus:ring-blue-400"
                spellCheck={false}
                placeholder="Conteúdo BKCP vazio&#10;&#10;Exemplo:&#10;{title: Nome da Música}&#10;{artist: Artista}&#10;{key: D}&#10;&#10;[Verso]&#10;[D]Letra da [G]música aqui"
              />
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-gray-400">
            <div className="text-center">
              <div className="text-4xl mb-3">🎵</div>
              <p className="text-sm">Selecione uma música ou faça upload de um PDF</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
