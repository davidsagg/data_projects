import { useMemo } from 'react'
import type { ReactNode } from 'react'
import { transposeChord } from '../utils/transpose'

export interface ChordViewerProps {
  bkcp: string
  semitones: number
  darkMode?: boolean
}

interface ChordLyricPair {
  chord: string  // empty string = texto sem cifra acima
  text: string
}

const CHORD_FIRST = /^[A-G]/
const META_RE     = /^\{(\w+):\s*(.*)\}$/
const SECTION_RE  = /^\[([^\]]+)\]$/

/**
 * Converte uma linha BKCP em pares (cifra, texto).
 * Ex: "[Am]Quando eu[G] te vejo" →
 *   [{chord:'Am', text:'Quando eu'}, {chord:'G', text:' te vejo'}]
 */
function parseChordLyric(line: string): ChordLyricPair[] {
  const pairs: ChordLyricPair[] = []
  const parts = line.split(/(\[[^\]]+\])/)

  let currentChord = ''
  let textBuf = ''

  for (const part of parts) {
    if (part.startsWith('[') && part.endsWith(']')) {
      const inner = part.slice(1, -1)
      if (CHORD_FIRST.test(inner)) {
        pairs.push({ chord: currentChord, text: textBuf })
        currentChord = inner
        textBuf = ''
      } else {
        textBuf += part  // section label inline — keep as text
      }
    } else {
      textBuf += part
    }
  }
  pairs.push({ chord: currentChord, text: textBuf })

  return pairs.filter((p) => p.chord || p.text)
}

function hasChords(pairs: ChordLyricPair[]) {
  return pairs.some((p) => p.chord !== '')
}

export function ChordViewer({ bkcp, semitones, darkMode = false }: ChordViewerProps) {
  const { title, blocks } = useMemo(() => {
    let title = ''
    const blocks: ReactNode[] = []

    const chordCls = darkMode
      ? 'text-blue-400 font-bold text-base leading-none'
      : 'text-blue-600 font-bold text-xs leading-none'
    const lyricCls = darkMode
      ? 'text-gray-100 text-xl leading-snug'
      : 'text-gray-800 text-sm leading-snug'
    const sectionCls = darkMode
      ? 'text-yellow-400 text-base font-semibold uppercase mt-8 mb-2'
      : 'text-gray-400 text-xs font-semibold uppercase tracking-widest mt-6 mb-1'

    bkcp.split('\n').forEach((line, i) => {
      // metadata: {key: value}
      const metaM = META_RE.exec(line)
      if (metaM) {
        if (metaM[1]?.toLowerCase() === 'title') title = metaM[2] ?? ''
        return
      }

      // section header: [SectionName] (not a chord)
      const secM = SECTION_RE.exec(line)
      if (secM && !CHORD_FIRST.test(secM[1] ?? '')) {
        blocks.push(
          <h3 key={i} data-section-header className={sectionCls}>
            {secM[1]}
          </h3>
        )
        return
      }

      if (!line.trim()) {
        blocks.push(<div key={i} className={darkMode ? 'h-5' : 'h-3'} />)
        return
      }

      const pairs = parseChordLyric(line)
      const withChords = hasChords(pairs)

      blocks.push(
        <div key={i} className="flex flex-wrap">
          {pairs.map((pair, j) => (
            <span key={j} className="inline-flex flex-col mr-1">
              {/* Cifra acima — mantém altura mesmo vazia para alinhar letras */}
              {withChords && (
                <span className={chordCls} style={{ minWidth: '0.25rem' }}>
                  {pair.chord
                    ? transposeChord(pair.chord, semitones)
                    : ' ' /* espaço não-quebrável */}
                </span>
              )}
              {/* Letra */}
              <span className={lyricCls}>
                {pair.text || (pair.chord ? ' ' : '')}
              </span>
            </span>
          ))}
        </div>
      )
    })

    return { title, blocks }
  }, [bkcp, semitones, darkMode])

  const titleCls = darkMode
    ? 'text-3xl font-bold text-white mb-6'
    : 'text-2xl font-bold text-gray-900 mb-4'

  return (
    <div className="chord-viewer font-mono">
      {title && <h2 className={titleCls}>{title}</h2>}
      <div className="space-y-1">{blocks}</div>
    </div>
  )
}
