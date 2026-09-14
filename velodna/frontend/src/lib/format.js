/* Formatadores compartilhados — pt-BR, unidades métricas. */

const NBSP = " "

/** Formata um número com casas fixas; devolve travessão para valores ausentes. */
export function num(value, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—"
  return value.toLocaleString("pt-BR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

/**
 * Duração em segundos para `2h14` ou `47min`.
 *
 * Trata valores negativos, que aparecem nas diferenças entre atividades: sem
 * isolar o sinal, `-12960` viraria "-3h-56" em vez de "-3h36".
 */
export function duration(seconds) {
  if (seconds === null || seconds === undefined || Number.isNaN(seconds)) {
    return "—"
  }

  const sign = seconds < 0 ? "-" : ""
  const total = Math.abs(Math.round(seconds))
  const hours = Math.floor(total / 3600)
  const minutes = Math.round((total % 3600) / 60)

  if (hours === 0) return `${sign}${minutes}min`
  return `${sign}${hours}h${String(minutes).padStart(2, "0")}`
}

/** Duração curta para eixos da curva de potência: `5s`, `12min`, `1h`. */
export function shortDuration(seconds) {
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.round(seconds / 60)}min`
  const hours = seconds / 3600
  return `${hours % 1 === 0 ? hours : hours.toFixed(1)}h`
}

export function km(meters, digits = 1) {
  if (meters === null || meters === undefined) return "—"
  return `${num(meters / 1000, digits)}${NBSP}km`
}

export function watts(value) {
  return value === null || value === undefined ? "—" : `${num(value)}${NBSP}W`
}

/** Data curta: `25 jul`. Aceita string ISO ou Date. */
export function shortDate(value) {
  if (!value) return "—"
  return new Date(value).toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "short",
  })
}

/** Data com ano: `25 jul 2026`. */
export function fullDate(value) {
  if (!value) return "—"
  return new Date(value).toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  })
}

/** Data para eixos longos: mês e ano abreviados. */
export function monthYear(value) {
  if (!value) return ""
  return new Date(value).toLocaleDateString("pt-BR", {
    month: "short",
    year: "2-digit",
  })
}

/** Data para eixos curtos: dia e mês. */
export function dayMonth(value) {
  if (!value) return ""
  return new Date(value).toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "short",
  })
}

/**
 * Escolhe o formato do eixo conforme a janela de tempo.
 *
 * Num intervalo de poucos meses cabem vários ticks dentro do mesmo mês, e um
 * rótulo só de mês se repete — o que faz o eixo parecer quebrado. Abaixo de um
 * ano, o dia entra no rótulo para que cada tick seja único.
 *
 * @param {number} spanDays Amplitude da série, em dias.
 * @returns {(value: string) => string} Formatador de tick.
 */
export function axisDateFormatter(spanDays) {
  return spanDays <= 400 ? dayMonth : monthYear
}

/**
 * Classifica o TSB nas faixas usuais de forma.
 * Retorna o rótulo e o token de cor de estado correspondente.
 */
export function formState(tsb) {
  if (tsb === null || tsb === undefined) return { label: "—", token: null }
  if (tsb > 15) return { label: "Destreinando", token: "--status-warning" }
  if (tsb > 5) return { label: "Descansado", token: "--status-good" }
  if (tsb >= -10) return { label: "Neutro", token: null }
  if (tsb >= -30) return { label: "Produtivo", token: "--status-good" }
  return { label: "Sobrecarga", token: "--status-critical" }
}
