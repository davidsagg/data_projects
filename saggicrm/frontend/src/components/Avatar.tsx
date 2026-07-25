import { colorFor, initials } from '../lib/avatar'

interface AvatarProps {
  firstName: string
  lastName: string
  seed?: string
  size?: number
}

export function Avatar({ firstName, lastName, seed, size = 40 }: AvatarProps) {
  const color = colorFor(seed || `${firstName}${lastName}`)
  return (
    <div
      className="flex shrink-0 items-center justify-center rounded-full font-semibold text-white"
      style={{ width: size, height: size, background: color, fontSize: size * 0.4 }}
    >
      {initials(firstName, lastName)}
    </div>
  )
}
