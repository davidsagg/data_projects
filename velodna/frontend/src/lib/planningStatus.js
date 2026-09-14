/*
 * Estados de um dia no calendário de treino.
 *
 * Vive fora dos componentes porque é consumido pela grade e pela tabela de
 * planejados — e porque exportar constantes de um arquivo de componente
 * desliga o Fast Refresh dele.
 */
export const DAY_STATUS = {
  completed: { label: "Cumprido", token: "--status-good" },
  partial: { label: "Parcial", token: "--status-warning" },
  missed: { label: "Não feito", token: "--status-critical" },
  unplanned: { label: "Sem plano", token: "--series-1" },
  scheduled: { label: "Agendado", token: "--text-muted" },
  in_progress: { label: "Em andamento", token: "--text-muted" },
  rest: { label: "Descanso", token: null },
}

/** Rótulo em português de um estado, com fallback para o valor cru. */
export function statusLabel(status) {
  return DAY_STATUS[status]?.label || status
}
