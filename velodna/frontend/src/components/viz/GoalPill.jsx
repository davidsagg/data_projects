/*
 * Etiqueta de meta — quanto falta, em texto, com o estado no ícone e no fundo.
 *
 * Recebe o progresso como a API devolve (`analytics.goals`): o sentido da
 * métrica já vem resolvido, então "−3 kg até a meta" e "68% da meta" saem da
 * mesma regra sem o componente saber que peso é "menor é melhor".
 */
import { goalText } from "../../lib/goals"

const TONE = {
  achieved: "good",
  near: "warning",
  far: "serious",
  unknown: null,
}

export default function GoalPill({ goal, children }) {
  if (!goal) return null
  const tone = TONE[goal.status]
  return (
    <span className={tone ? `pill pill--${tone}` : "pill"}>
      <span className="pill-icon" aria-hidden="true" />
      {children ?? goalText(goal)}
    </span>
  )
}

/** Etiqueta avulsa com tom explícito, para estados que não são metas. */
export function Pill({ tone, children }) {
  return (
    <span className={tone ? `pill pill--${tone}` : "pill"}>
      <span className="pill-icon" aria-hidden="true" />
      {children}
    </span>
  )
}
