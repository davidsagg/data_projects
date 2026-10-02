/*
 * Marcos como linhas verticais — exame, plano, prova, achado, teste de CP.
 *
 * Um exame de fevereiro explica uma curva de CTL de março; sem a linha no
 * gráfico, a ligação fica na memória do atleta. O rótulo é curto (o tipo) e o
 * título completo vai no `title` do SVG e no card de notas — o gráfico não é
 * lugar de parágrafo.
 */
import { ReferenceLine } from "recharts"

export const MILESTONE_LABELS = {
  exame: "exame",
  plano: "plano",
  prova: "prova",
  achado: "achado",
  teste: "teste CP",
}

/**
 * Devolve as linhas de referência dos marcos que caem dentro do eixo.
 *
 * @param {Array} milestones marcos da API (`date`, `kind`, `title`).
 * @param {Set<string>|null} dates datas presentes no eixo X categórico; marcos
 *   fora delas são descartados (o Recharts não desenha linha fora da categoria).
 * @param {Object} colors tokens resolvidos (`--text-tertiary`).
 */
export function milestoneLines(milestones, dates, colors) {
  return (milestones || [])
    .filter((m) => !dates || dates.has(m.date))
    .map((m) => (
      <ReferenceLine
        key={`${m.id}-${m.date}`}
        x={m.date}
        stroke={colors["--text-tertiary"]}
        strokeDasharray="3 3"
        ifOverflow="discard"
        label={{
          value: MILESTONE_LABELS[m.kind] ?? m.kind,
          position: "insideTopRight",
          fill: colors["--text-tertiary"],
          fontSize: 10,
        }}
      >
        <title>{m.title}</title>
      </ReferenceLine>
    ))
}
