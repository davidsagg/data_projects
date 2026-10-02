/* Texto e cores compartilhados de metas e modalidades. */
import { num } from "./format"

/** Token de cor de cada modalidade — a mesma ordem do backend. */
export const MODALITY_TOKENS = {
  outdoor: "--mod-outdoor",
  indoor: "--mod-indoor",
  strength: "--mod-strength",
  other: "--mod-other",
}

/** Casas decimais por unidade: horas e W/kg pedem decimal, watts não. */
function digitsFor(unit) {
  return unit === "W" || unit === "" ? 0 : 1
}

/**
 * Quanto falta para a meta, em texto: "−3,0 kg até a meta", "68% da meta".
 *
 * O sentido da métrica já vem resolvido da API (`lower_is_better`), então a
 * mesma regra serve ao peso e ao volume.
 */
export function goalText(goal) {
  if (!goal) return null
  const digits = digitsFor(goal.unit)
  if (goal.status === "unknown") return "sem valor atual"
  if (goal.status === "achieved") return "meta atingida"
  if (goal.pct_of_target != null) return `${num(goal.pct_of_target, 0)}% da meta`
  const sign = goal.lower_is_better ? "−" : "+"
  return `${sign}${num(goal.remaining, digits)} ${goal.unit} até a meta`
}
