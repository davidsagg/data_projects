/*
 * Treino e saúde na mesma grade — sete dias nas colunas, os sinais nas linhas.
 *
 * Substitui a timeline de dois painéis altos (132 + 96 px de barras, mais o
 * rodapé de leitura), que ocupava meia tela para mostrar sete números de cada
 * lado. O formato aqui é o clássico das planilhas de treino e do intervals.icu:
 * denso, legível de relance, sem hover obrigatório — cada valor está escrito.
 *
 * A carga continua em barra, porque é magnitude e se compara por altura. A
 * saúde vem em número, tingido pela distância da média de 45 dias do próprio
 * atleta: "39 ms" não diz nada sozinho, "39 ms em amarelo" diz "abaixo da sua
 * base". O tom vai no fundo; o número fica em tinta de texto, e a legenda no
 * rodapé diz o que cada cor significa.
 */
import { useState } from "react"

import { duration, num } from "../../lib/format"

const WEEKDAYS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
const BAR_HEIGHT = 44

const FEEL_LABEL = { 1: "péssimo", 2: "ruim", 3: "normal", 4: "bom", 5: "ótimo" }

/* Réguas de tom. Saúde contra a base do próprio atleta, não contra tabela
   populacional: HRV de 39 ms é ótimo para uns e péssimo para outros. */
function sleepTone(hours) {
  if (hours == null) return null
  if (hours < 6) return "serious"
  if (hours < 7) return "warning"
  return "good"
}

function hrvTone(value, base) {
  if (value == null || !base) return null
  const ratio = value / base
  if (ratio >= 0.95) return "good"
  if (ratio >= 0.85) return "warning"
  return "serious"
}

function rhrTone(value, base) {
  if (value == null || !base) return null
  const delta = value - base
  if (delta <= 2) return "good"
  if (delta <= 4) return "warning"
  return "serious"
}

function batteryTone(value) {
  if (value == null) return null
  if (value >= 70) return "good"
  if (value >= 40) return null
  return "warning"
}

function feelTone(feel) {
  if (feel == null) return null
  if (feel <= 2) return "serious"
  if (feel >= 4) return "good"
  return null
}

function sleepText(hours) {
  const total = Math.round(hours * 60)
  return `${Math.floor(total / 60)}h${String(total % 60).padStart(2, "0")}`
}

function Chip({ tone, children, title }) {
  return (
    <span className={tone ? `wg-chip wg-chip--${tone}` : "wg-chip"} title={title}>
      {children}
    </span>
  )
}

export default function WeekGrid({ days, baseline, onSelectDay }) {
  const [hovered, setHovered] = useState(null)
  const today = new Date().toLocaleDateString("sv-SE")
  const maxTss = Math.max(...days.map((d) => Math.max(d.tss, d.planned_tss)), 1)

  /** Célula de uma coluna de dia, com destaque e clique compartilhados. */
  const cell = (day, index, content, style, rowKey) => (
    <div
      key={`${rowKey}-${day.date}`}
      className={[
        "wg-cell",
        hovered === index && "is-hovered",
        day.date === today && "is-today",
      ]
        .filter(Boolean)
        .join(" ")}
      onMouseEnter={() => setHovered(index)}
      onClick={() => onSelectDay?.(day)}
      style={style}
    >
      {content}
    </div>
  )

  const row = (label, render, style) => [
    <span key={`label-${label}`} className="wg-label">
      {label}
    </span>,
    ...days.map((day, index) => cell(day, index, render(day), style, label)),
  ]

  return (
    <section className="card card--static" style={{ display: "grid", gap: "var(--space-3)" }}>
      <header style={{ display: "flex", justifyContent: "space-between", gap: "var(--space-3)", flexWrap: "wrap" }}>
        <div>
          <h2 className="card-title">Treino e saúde na semana</h2>
          <p className="card-subtitle">Clique num dia para o detalhe e o feedback</p>
        </div>
        <div style={{ display: "flex", gap: "var(--space-3)", alignItems: "center", flexWrap: "wrap", fontSize: "var(--fs-micro)", color: "var(--text-tertiary)" }}>
          <span>contra a sua média de 45 dias:</span>
          <Chip tone="good">na base</Chip>
          <Chip tone="warning">atenção</Chip>
          <Chip tone="serious">fora</Chip>
        </div>
      </header>

      <div className="scroll-x">
        <div className="week-grid" role="table" style={{ minWidth: 560 }} onMouseLeave={() => setHovered(null)}>
          {/* Cabeçalho: dia da semana e data */}
          <span className="wg-label" />
          {days.map((day, index) =>
            cell(
              day,
              index,
              <span style={{ display: "grid", justifyItems: "center", lineHeight: 1.2 }}>
                <strong style={{ fontSize: "var(--fs-micro)", textTransform: "uppercase", letterSpacing: "0.06em", color: day.date === today ? "var(--accent)" : "var(--text-secondary)" }}>
                  {WEEKDAYS[index]}
                </strong>
                <span className="tabular" style={{ fontSize: "var(--fs-micro)", color: "var(--text-tertiary)" }}>
                  {day.date.slice(8, 10)}/{day.date.slice(5, 7)}
                </span>
              </span>,
              { borderTop: 0 },
              "head",
            ),
          )}

          {/* Carga: barra executada sobre o contorno do planejado */}
          {row(
            "Carga · TSS",
            (day) => (
              <div style={{ display: "grid", justifyItems: "center", gap: 2, width: "100%" }}>
                <span className="tabular" style={{ fontSize: "0.75rem", fontWeight: 600, color: day.tss ? "var(--text-primary)" : "var(--text-tertiary)" }}>
                  {day.tss ? num(day.tss, 0) : day.is_rest ? "descanso" : "—"}
                </span>
                <div style={{ position: "relative", height: BAR_HEIGHT, width: "56%", display: "flex", alignItems: "flex-end" }}>
                  {day.planned_tss > 0 && (
                    <div
                      title={`planejado ${num(day.planned_tss, 0)} TSS`}
                      style={{
                        position: "absolute",
                        bottom: 0,
                        left: 0,
                        right: 0,
                        height: (day.planned_tss / maxTss) * BAR_HEIGHT,
                        border: "1.5px dashed var(--text-tertiary)",
                        borderRadius: "4px 4px 0 0",
                      }}
                    />
                  )}
                  <div
                    style={{
                      width: "100%",
                      height: day.tss ? Math.max((day.tss / maxTss) * BAR_HEIGHT, 3) : 0,
                      background: "var(--ctl)",
                      borderRadius: "4px 4px 0 0",
                    }}
                  />
                </div>
              </div>
            ),
            { minHeight: BAR_HEIGHT + 26, alignItems: "flex-end", paddingTop: 4 },
          )}

          {row("Duração", (day) => (
            <span className="tabular" style={{ fontSize: "0.75rem", color: day.duration_s ? "var(--text-primary)" : "var(--text-tertiary)" }}>
              {day.duration_s ? duration(day.duration_s) : "—"}
              {day.activity_count > 1 && <span className="muted"> ·{day.activity_count}</span>}
            </span>
          ))}

          {row("Sono", (day) =>
            day.sleep_hours != null ? (
              <Chip tone={sleepTone(day.sleep_hours)}>{sleepText(day.sleep_hours)}</Chip>
            ) : (
              <span className="muted">—</span>
            ),
          )}

          {row("HRV", (day) =>
            day.hrv_rmssd_ms != null ? (
              <Chip
                tone={hrvTone(day.hrv_rmssd_ms, baseline?.hrv)}
                title={baseline?.hrv ? `média de 45 dias: ${num(baseline.hrv, 0)} ms` : undefined}
              >
                {num(day.hrv_rmssd_ms, 0)}
              </Chip>
            ) : (
              <span className="muted">—</span>
            ),
          )}

          {row("FC repouso", (day) =>
            day.resting_hr_bpm != null ? (
              <Chip
                tone={rhrTone(day.resting_hr_bpm, baseline?.rhr)}
                title={baseline?.rhr ? `média de 45 dias: ${num(baseline.rhr, 0)} bpm` : undefined}
              >
                {day.resting_hr_bpm}
              </Chip>
            ) : (
              <span className="muted">—</span>
            ),
          )}

          {row("Bateria", (day) =>
            day.body_battery != null ? (
              <Chip tone={batteryTone(day.body_battery)}>{day.body_battery}</Chip>
            ) : (
              <span className="muted">—</span>
            ),
          )}

          {row("Sensação", (day) =>
            day.feel || day.rpe || day.notes ? (
              <Chip tone={feelTone(day.feel)} title={day.notes || undefined}>
                {day.feel ? FEEL_LABEL[day.feel] : day.rpe ? `RPE ${day.rpe}` : "nota"}
                {day.notes && " ✎"}
              </Chip>
            ) : (
              <span className="muted">—</span>
            ),
          )}
        </div>
      </div>
    </section>
  )
}
