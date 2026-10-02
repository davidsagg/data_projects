/*
 * Distribuição de zonas — barra única empilhada.
 *
 * Formato do relatório semanal do TrainingPeaks: uma barra horizontal com os
 * sete segmentos proporcionais, e a legenda carregando o percentual **e a faixa
 * de %FTP** de cada zona. A faixa é o que torna o número interpretável — "Z3
 * 13%" não diz nada sem saber que Z3 é 76–90% do FTP.
 *
 * Substitui as sete linhas empilhadas da versão anterior: ocupavam sete vezes a
 * altura para mostrar a mesma proporção, e a proporção lê-se melhor lado a lado
 * que em barras separadas com escalas próprias.
 */
import { duration, num } from "../../lib/format"

/* Cores da convenção Coggan/TrainingPeaks — as mesmas que o atleta lê no
   relatório semanal dele. O rótulo e o percentual acompanham cada faixa, então
   a identidade nunca depende só da cor. */
const ZONES = [
  { key: "Z1", label: "Recuperação", range: "< 55% FTP", token: "--zone-1" },
  { key: "Z2", label: "Endurance", range: "56–75%", token: "--zone-2" },
  { key: "Z3", label: "Tempo", range: "76–90%", token: "--zone-3" },
  { key: "Z4", label: "Limiar", range: "91–105%", token: "--zone-4" },
  { key: "Z5", label: "VO2máx", range: "106–120%", token: "--zone-5" },
  { key: "Z6", label: "Anaeróbico", range: "121–150%", token: "--zone-6" },
  { key: "Z7", label: "Neuromuscular", range: "> 150%", token: "--zone-7" },
]

/** Abaixo disso o segmento some na barra; o valor fica só na legenda. */
const MIN_VISIBLE_PCT = 2.5

/** Faixa em watts de uma zona, a partir das definições vigentes. */
function wattRange(definition) {
  if (!definition) return null
  if (definition.high == null) return `> ${num(definition.low)} W`
  return `${num(definition.low)}–${num(definition.high)} W`
}

/**
 * @param definitions faixas em watts vindas da API (opcional) — quando vêm,
 *   a legenda mostra watts ao lado do %FTP e o tempo absoluto em cada zona.
 */
export default function ZoneBar({
  zoneSeconds,
  intensity,
  distribution,
  definitions,
  emptyText = "Sem dados de potência nesta semana.",
}) {
  const total = Object.values(zoneSeconds || {}).reduce((a, b) => a + b, 0)

  if (!total) {
    return (
      <p className="muted" style={{ margin: 0 }}>
        {emptyText}
      </p>
    )
  }

  const rows = ZONES.map((zone) => {
    const seconds = zoneSeconds[zone.key] || 0
    const definition = definitions?.find((d) => d.zone === zone.key)
    return { ...zone, seconds, pct: (seconds / total) * 100, watts: wattRange(definition) }
  })

  return (
    <div style={{ display: "grid", gap: "var(--space-5)" }}>
      {/* 2px de gap deixa a superfície separar os segmentos sem borda. */}
      <div style={{ display: "flex", gap: 2, height: 30 }}>
        {rows
          .filter((z) => z.pct > 0)
          .map((zone) => (
            <div
              key={zone.key}
              title={`${zone.key} ${zone.label}: ${num(zone.pct, 1)}%`}
              style={{
                width: `${zone.pct}%`,
                minWidth: 3,
                background: `var(${zone.token})`,
                borderRadius: "var(--radius-sm)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "var(--fs-micro)",
                fontVariantNumeric: "tabular-nums",
                color: "#fff",
                overflow: "hidden",
              }}
            >
              {zone.pct >= MIN_VISIBLE_PCT ? `${num(zone.pct, 1)}%` : ""}
            </div>
          ))}
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
          gap: "var(--space-4) var(--space-5)",
        }}
      >
        {rows.map((zone) => (
          <div
            key={zone.key}
            style={{
              display: "grid",
              gridTemplateColumns: "auto 1fr auto",
              alignItems: "baseline",
              columnGap: "var(--space-2)",
              fontSize: "var(--fs-small)",
              opacity: zone.seconds ? 1 : 0.45,
            }}
          >
            <span
              className="viz-swatch"
              style={{ background: `var(${zone.token})`, flex: "none" }}
            />
            <span style={{ color: "var(--text-primary)", whiteSpace: "nowrap" }}>
              {zone.label}
            </span>
            <span
              className="tabular"
              style={{ color: "var(--text-secondary)", whiteSpace: "nowrap" }}
            >
              {num(zone.pct, 1)}%
            </span>
            {/* A faixa de %FTP vai na segunda linha, alinhada ao rótulo: em
                linha única ela quebrava no meio ("56–" / "75%") e virava ruído. */}
            <span />
            <span
              className="tabular"
              style={{
                gridColumn: "2 / -1",
                color: "var(--text-tertiary)",
                fontSize: "var(--fs-micro)",
                whiteSpace: "nowrap",
              }}
            >
              {zone.range}
              {zone.watts && ` · ${zone.watts}`}
              {definitions && ` · ${duration(zone.seconds)}`}
            </span>
          </div>
        ))}
      </div>

      {intensity?.easy && (
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "var(--space-2) var(--space-8)",
            paddingTop: "var(--space-4)",
            borderTop: "1px solid var(--border-subtle)",
            fontSize: "var(--fs-small)",
            color: "var(--text-secondary)",
          }}
        >
          <span>
            Padrão:{" "}
            <strong style={{ color: "var(--text-primary)" }}>{distribution}</strong>
          </span>
          <span className="tabular">fácil {num(intensity.easy.pct, 1)}%</span>
          <span className="tabular">limiar {num(intensity.threshold.pct, 1)}%</span>
          <span className="tabular">forte {num(intensity.hard.pct, 1)}%</span>
        </div>
      )}
    </div>
  )
}
