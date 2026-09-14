/*
 * Distribuição de intensidade da semana — os três domínios em uma barra.
 *
 * Os domínios são ordinais (fácil → limiar → forte), não categorias soltas, por
 * isso usam a rampa sequencial de um único hue em vez de cores distintas — a
 * mesma escolha já feita nas barras de zona da atividade. Cor mais escura é
 * intensidade maior, e a ordem visual carrega sentido sozinha.
 *
 * A leitura que interessa é a proporção, então a barra é 100% da largura e os
 * segmentos são percentuais. O veredito (polarizado / piramidal / limiar) vem
 * escrito, nunca só pela forma da barra.
 */
import { num } from "../../lib/format"

const DOMAINS = [
  { key: "easy", label: "Fácil (Z1–Z2)", token: "--seq-250" },
  { key: "threshold", label: "Limiar (Z3–Z4)", token: "--seq-400" },
  { key: "hard", label: "Forte (Z5+)", token: "--seq-700" },
]

/** Descrição do padrão, para o leitor que não conhece o vocabulário. */
const DISTRIBUTION_HINT = {
  polarizado: "muito fácil e muito forte, pouco no meio",
  piramidal: "base larga, afinando conforme a intensidade sobe",
  limiar: "concentrado em torno do limiar",
  base: "só volume aeróbico, sem trabalho intenso",
  "sem dados": "sem streams de potência nesta semana",
}

export default function IntensityBar({ intensity, distribution }) {
  const segments = DOMAINS.map((domain) => ({
    ...domain,
    pct: intensity?.[domain.key]?.pct ?? 0,
    seconds: intensity?.[domain.key]?.seconds ?? 0,
  }))

  const total = segments.reduce((sum, s) => sum + s.pct, 0)

  if (total <= 0) {
    return (
      <div>
        <p className="muted" style={{ margin: 0 }}>
          {DISTRIBUTION_HINT["sem dados"]}
        </p>
      </div>
    )
  }

  return (
    <div style={{ display: "grid", gap: "var(--space-3)" }}>
      {/* Os 2px de gap deixam a superfície aparecer entre os segmentos, o que
          separa as faixas sem precisar de borda. */}
      <div style={{ display: "flex", gap: 2, height: 22 }}>
        {segments
          .filter((s) => s.pct > 0)
          .map((s) => (
            <div
              key={s.key}
              title={`${s.label}: ${num(s.pct, 1)}%`}
              style={{
                width: `${s.pct}%`,
                background: `var(${s.token})`,
                borderRadius: "var(--radius-sm)",
              }}
            />
          ))}
      </div>

      <div className="viz-legend">
        {segments.map((s) => (
          <span className="viz-legend-item" key={s.key}>
            <span className="viz-swatch" style={{ background: `var(${s.token})` }} />
            {s.label}
            <span className="tabular muted" style={{ marginLeft: 4 }}>
              {num(s.pct, 1)}% · {Math.round(s.seconds / 60)} min
            </span>
          </span>
        ))}
      </div>

      <p className="card-subtitle" style={{ margin: 0 }}>
        Padrão: <strong style={{ color: "var(--text-primary)" }}>{distribution}</strong>
        {DISTRIBUTION_HINT[distribution] && ` — ${DISTRIBUTION_HINT[distribution]}`}
      </p>
    </div>
  )
}
