import { Star } from 'lucide-react'
import clsx from 'clsx'

interface FavoriteStarProps {
  isFavorite: boolean
  onToggle: () => void
  size?: number
}

export function FavoriteStar({ isFavorite, onToggle, size = 18 }: FavoriteStarProps) {
  return (
    <button
      type="button"
      onClick={(e) => {
        e.preventDefault()
        e.stopPropagation()
        onToggle()
      }}
      aria-label={isFavorite ? 'Remover dos favoritos' : 'Marcar como favorito'}
      className={clsx(
        'flex items-center justify-center rounded-full p-1 transition-colors hover:bg-accent-soft',
        isFavorite ? 'text-amber-400' : 'text-border hover:text-amber-400',
      )}
    >
      <Star size={size} fill={isFavorite ? 'currentColor' : 'none'} />
    </button>
  )
}
