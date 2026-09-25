/*
 * Sparkline — a tendência ao lado do número.
 *
 * "HRV 40 ms" não informa; "HRV 40, subindo há cinco dias" informa. O número
 * isolado é um ponto sem série, e ler tendência é justamente o que separa um
 * painel de um relógio.
 *
 * Sem eixo, sem grade, sem rótulo: a sparkline é uma palavra dentro da frase do
 * card, não um gráfico. A faixa de referência (média ± desvio) aparece ao fundo
 * quando informada, porque "alto" só quer dizer algo contra uma base.
 */
export default function Sparkline({
  values,
  width = 132,
  height = 30,
  token = "--ctl",
  band,
}) {
  const clean = (values || []).filter((v) => v !== null && v !== undefined)
  if (clean.length < 2) return null

  const min = Math.min(...clean)
  const max = Math.max(...clean)
  const span = max - min || 1

  // A série pode ter buracos (dia sem sincronização); o eixo X é posicional
  // para que a lacuna não desloque o desenho inteiro.
  const step = width / (values.length - 1)
  const points = values
    .map((v, i) =>
      v === null || v === undefined
        ? null
        : `${(i * step).toFixed(1)},${(height - ((v - min) / span) * height).toFixed(1)}`,
    )
    .filter(Boolean)

  const last = clean[clean.length - 1]
  const lastIndex = values.findLastIndex((v) => v !== null && v !== undefined)

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      aria-hidden="true"
      style={{ display: "block", overflow: "visible" }}
    >
      {band && band.high > band.low && (
        <rect
          x="0"
          y={height - ((band.high - min) / span) * height}
          width={width}
          height={Math.max(
            ((band.high - band.low) / span) * height,
            1,
          )}
          fill={`var(${token})`}
          opacity="0.10"
        />
      )}
      <polyline
        points={points.join(" ")}
        fill="none"
        stroke={`var(${token})`}
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      <circle
        cx={lastIndex * step}
        cy={height - ((last - min) / span) * height}
        r="2.5"
        fill={`var(${token})`}
      />
    </svg>
  )
}
