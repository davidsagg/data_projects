export interface TransposeControlsProps {
  semitones: number
  keyName: string
  onTranspose: (delta: number) => void
}

export function TransposeControls({ semitones, keyName, onTranspose }: TransposeControlsProps) {
  const sign = semitones > 0 ? '+' : ''

  return (
    <div className="flex items-center gap-3">
      <button
        aria-label="−"
        onClick={() => onTranspose(-1)}
        className="w-8 h-8 rounded-full bg-gray-200 hover:bg-gray-300 flex items-center justify-center font-bold text-base select-none"
      >
        −
      </button>

      <span className="text-sm font-medium min-w-[8rem] text-center">
        Tom: <strong>{keyName}</strong>{' '}
        <span className="text-gray-500">({sign}{semitones})</span>
      </span>

      <button
        aria-label="+"
        onClick={() => onTranspose(1)}
        className="w-8 h-8 rounded-full bg-gray-200 hover:bg-gray-300 flex items-center justify-center font-bold text-base select-none"
      >
        +
      </button>

      {semitones !== 0 && (
        <button
          onClick={() => onTranspose(-semitones)}
          className="text-xs text-gray-400 hover:text-gray-700 underline"
        >
          Reset
        </button>
      )}
    </div>
  )
}
