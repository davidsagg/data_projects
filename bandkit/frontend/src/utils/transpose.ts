const CHROMATIC_SHARP = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
const CHROMATIC_FLAT  = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']
const ENHARMONIC: Record<string, string> = {
  Db: 'C#', Eb: 'D#', Gb: 'F#', Ab: 'G#', Bb: 'A#',
}

function normalizeRoot(root: string): string {
  if (!CHROMATIC_SHARP.includes(root) && CHROMATIC_FLAT.includes(root)) {
    return ENHARMONIC[root] ?? root
  }
  return root
}

export function transposeRoot(root: string, semitones: number, preferFlat = false): string {
  const sharp = normalizeRoot(root)
  const idx = CHROMATIC_SHARP.indexOf(sharp)
  if (idx === -1) return root
  const newIdx = ((idx + semitones) % 12 + 12) % 12
  return preferFlat ? CHROMATIC_FLAT[newIdx] : CHROMATIC_SHARP[newIdx]
}

export function transposeChord(chord: string, semitones: number): string {
  if (semitones === 0) return chord
  const m = chord.match(
    /^([A-G][#b]?)(m|maj|min|dim|aug|sus[24]?|add\d?|M)?(\d*)((?:\/[A-G][#b]?)?)$/
  )
  if (!m) return chord
  const root    = m[1] ?? ''
  const quality = m[2] ?? ''
  const ext     = m[3] ?? ''
  const bass    = m[4] ?? ''
  const newRoot = transposeRoot(root, semitones)
  const newBass = bass ? '/' + transposeRoot(bass.slice(1), semitones) : ''
  return newRoot + quality + ext + newBass
}

/** Quantos semitons de `from` até `to` (0–11). */
export function semitonesBetween(from: string, to: string): number {
  const fRoot = from.match(/^([A-G][#b]?)/)?.[1] ?? ''
  const tRoot = to.match(/^([A-G][#b]?)/)?.[1] ?? ''
  const fIdx = CHROMATIC_SHARP.indexOf(normalizeRoot(fRoot))
  const tIdx = CHROMATIC_SHARP.indexOf(normalizeRoot(tRoot))
  if (fIdx === -1 || tIdx === -1) return 0
  return ((tIdx - fIdx) + 12) % 12
}

export function getKeyName(originalKey: string, semitones: number): string {
  const m = originalKey.match(/^([A-G][#b]?)(.*)$/)
  if (!m) return originalKey
  const root   = m[1] ?? ''
  const suffix = m[2] ?? ''
  const preferFlat = suffix.includes('b') || /Db|Eb|Gb|Ab|Bb/.test(suffix)
  return transposeRoot(root, semitones, preferFlat) + suffix
}
