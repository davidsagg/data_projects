/*
 * Timeline unificada — treino e saúde no mesmo eixo de tempo.
 *
 * É o componente-assinatura do produto. Nenhuma plataforma de ciclismo coloca
 * carga de treino e resposta fisiológica na mesma linha do tempo: o TrainingPeaks
 * tem as duas coisas em abas diferentes, o Garmin Connect idem. Separadas, a
 * pergunta "a noite ruim de quarta explica o treino fraco de quinta?" exige o
 * usuário memorizar um gráfico e ir olhar o outro.
 *
 * Construído em SVG e grid, não em Recharts. São sete colunas discretas com
 * destaque sincronizado entre dois painéis e leitura fixa no rodapé — controle
 * que o Recharts só entregaria com cursor customizado e `syncId`, por um caminho
 * mais longo. O Recharts continua nos gráficos contínuos, onde ganha.
 *
 * Conforme a spec: sem tooltip flutuante. O hover destaca a coluna inteira nos
 * dois painéis e os valores aparecem numa linha fixa no rodapé — o olho não
 * persegue uma caixa que se move.
 */
import { useMemo, useState } from "react"

import { duration, num } from "../../lib/format"

const WEEKDAYS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]

const TRAINING_HEIGHT = 132
const HEALTH_HEIGHT = 96

/** Altura mínima visível para um dia com carga baixa mas não nula. */
const MIN_BAR_PX = 3

export default function WeekTimeline({ days, onSelectDay }) {
  const [hovered, setHovered] = useState(null)

  const scale = useMemo(() => {
    const maxTss = Math.max(...days.map((d) => Math.max(d.tss, d.planned_tss)), 1)
    const sleeps = days.map((d) => d.sleep_hours).filter((v) => v != null)
    const hrvs = days.map((d) => d.hrv_rmssd_ms).filter((v) => v != null)
    return {
      maxTss,
      maxSleep: Math.max(...sleeps, 8),
      hrvMin: hrvs.length ? Math.min(...hrvs) : 0,
      hrvMax: hrvs.length ? Math.max(...hrvs) : 1,
      hasHrv: hrvs.length > 1,
      hasSleep: sleeps.length > 0,
    }
  }, [days])

  const active = hovered != null ? days[hovered] : null
  const today = new Date().toISOString().slice(0, 10)

  return (
    <section className="card card--static" style={{ display: "grid", gap: "var(--space-5)" }}>
      <header>
        <h2 className="card-title">Treino e saúde na mesma linha</h2>
        <p className="card-subtitle">
          Passe o cursor por um dia para ver os dois lados; clique para o detalhe
        </p>
      </header>

      <div
        style={{ display: "grid", gap: "var(--space-2)" }}
        onMouseLeave={() => setHovered(null)}
      >
        <PanelLabel>Treino · TSS</PanelLabel>
        <Columns
          days={days}
          hovered={hovered}
          today={today}
          onHover={setHovered}
          onSelectDay={onSelectDay}
          height={TRAINING_HEIGHT}
          render={(day) => (
            <TrainingBars day={day} scale={scale} height={TRAINING_HEIGHT} />
          )}
        />

        <PanelLabel style={{ marginTop: "var(--space-4)" }}>
          Saúde · HRV e sono
        </PanelLabel>
        <div style={{ position: "relative" }}>
          {scale.hasHrv && <HrvLine days={days} scale={scale} height={HEALTH_HEIGHT} />}
          <Columns
            days={days}
            hovered={hovered}
            today={today}
            onHover={setHovered}
            onSelectDay={onSelectDay}
            height={HEALTH_HEIGHT}
            render={(day) => (
              <SleepBar day={day} scale={scale} height={HEALTH_HEIGHT} />
            )}
          />
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(7, 1fr)",
            gap: "var(--space-2)",
            marginTop: "var(--space-2)",
          }}
        >
          {days.map((day, index) => (
            <span
              key={day.date}
              style={{
                textAlign: "center",
                fontSize: "var(--fs-micro)",
                letterSpacing: "var(--tracking-label)",
                textTransform: "uppercase",
                color:
                  index === hovered
                    ? "var(--text-primary)"
                    : "var(--text-tertiary)",
                borderTop:
                  day.date === today
                    ? "2px solid var(--text-primary)"
                    : "2px solid transparent",
                paddingTop: "var(--space-2)",
              }}
            >
              {WEEKDAYS[index]}
            </span>
          ))}
        </div>
      </div>

      <Readout day={active} />
    </section>
  )
}

/* -------------------------------------------------------------------------- */

function PanelLabel({ children, style }) {
  return (
    <span className="label" style={style}>
      {children}
    </span>
  )
}

/** Grade de sete colunas com a faixa de destaque, compartilhada pelos painéis. */
function Columns({ days, hovered, today, onHover, onSelectDay, height, render }) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(7, 1fr)",
        gap: "var(--space-2)",
        height,
        alignItems: "end",
      }}
    >
      {days.map((day, index) => (
        <div
          key={day.date}
          role="button"
          tabIndex={0}
          aria-label={`${day.date}: ${num(day.tss, 0)} TSS`}
          onMouseEnter={() => onHover(index)}
          onFocus={() => onHover(index)}
          onClick={() => onSelectDay?.(day)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault()
              onSelectDay?.(day)
            }
          }}
          style={{
            height: "100%",
            display: "flex",
            alignItems: "flex-end",
            justifyContent: "center",
            gap: 2,
            cursor: onSelectDay ? "pointer" : "default",
            background:
              index === hovered ? "var(--surface-sunken)" : "transparent",
            borderRadius: "var(--radius-sm)",
            transition: "background 120ms ease",
            outline: "none",
            position: "relative",
          }}
        >
          {render(day)}
        </div>
      ))}
    </div>
  )
}

/** Barra de TSS executado, com o planejado como contorno atrás. */
function TrainingBars({ day, scale, height }) {
  const available = height - 8
  const actual = day.tss > 0 ? Math.max((day.tss / scale.maxTss) * available, MIN_BAR_PX) : 0
  const planned =
    day.planned_tss > 0 ? (day.planned_tss / scale.maxTss) * available : 0

  return (
    <>
      {planned > 0 && (
        <div
          title={`planejado ${num(day.planned_tss, 0)} TSS`}
          style={{
            width: 12,
            height: planned,
            border: "1px dashed var(--border-strong)",
            borderBottom: "none",
            borderRadius: "var(--radius-sm) var(--radius-sm) 0 0",
          }}
        />
      )}
      {actual > 0 ? (
        <div
          style={{
            width: 14,
            height: actual,
            background: "var(--ctl)",
            borderRadius: "var(--radius-sm) var(--radius-sm) 0 0",
          }}
        />
      ) : (
        /* Dia de descanso é um traço, não ausência — some senão parece falha. */
        <div style={{ width: 14, height: 2, background: "var(--text-tertiary)" }} />
      )}
    </>
  )
}

/** Barra de sono, com o rótulo fixo abaixo — codificação secundária da cor. */
function SleepBar({ day, scale, height }) {
  if (day.sleep_hours == null) {
    return (
      <span style={{ fontSize: "var(--fs-micro)", color: "var(--text-tertiary)" }}>
        —
      </span>
    )
  }

  const available = height - 24
  const bar = Math.max((day.sleep_hours / scale.maxSleep) * available, MIN_BAR_PX)

  return (
    <div style={{ display: "grid", justifyItems: "center", gap: 4 }}>
      <div
        style={{
          width: 14,
          height: bar,
          background: "var(--sleep)",
          borderRadius: "var(--radius-sm) var(--radius-sm) 0 0",
        }}
      />
      <span
        className="tabular"
        style={{ fontSize: "var(--fs-micro)", color: "var(--text-tertiary)" }}
      >
        {formatSleep(day.sleep_hours)}
      </span>
    </div>
  )
}

/**
 * Linha de HRV sobreposta ao painel de saúde.
 *
 * Fica em SVG absoluto porque precisa atravessar as colunas — é justamente a
 * continuidade entre os dias que revela a tendência. `preserveAspectRatio="none"`
 * permite usar coordenadas percentuais e deixar o SVG esticar com o container.
 */
function HrvLine({ days, scale, height }) {
  const span = scale.hrvMax - scale.hrvMin || 1
  const usable = height - 40

  const points = days
    .map((day, index) => {
      if (day.hrv_rmssd_ms == null) return null
      const x = ((index + 0.5) / days.length) * 100
      const y = 8 + (1 - (day.hrv_rmssd_ms - scale.hrvMin) / span) * usable
      return { x, y }
    })
    .filter(Boolean)

  if (points.length < 2) return null

  return (
    <svg
      viewBox={`0 0 100 ${height}`}
      preserveAspectRatio="none"
      aria-hidden="true"
      style={{
        position: "absolute",
        inset: 0,
        width: "100%",
        height,
        pointerEvents: "none",
        overflow: "visible",
      }}
    >
      <polyline
        points={points.map((p) => `${p.x},${p.y}`).join(" ")}
        fill="none"
        stroke="var(--hrv)"
        strokeWidth="2"
        strokeLinejoin="round"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
      />
      {/* Retângulo, não círculo: com `preserveAspectRatio="none"` o eixo X é
          esticado para a largura do container, e um `<circle>` vira uma elipse
          achatada. O losango de lados iguais em unidades de usuário sofre a
          mesma distorção, então a marca é desenhada como quadrado pequeno —
          que distorce para um retângulo discreto em vez de uma elipse gritante. */}
      {points.map((p) => (
        <rect
          key={p.x}
          x={p.x - 0.35}
          y={p.y - 3}
          width="0.7"
          height="6"
          rx="0.2"
          fill="var(--hrv)"
        />
      ))}
    </svg>
  )
}

/** Leitura fixa no rodapé — substitui o tooltip flutuante. */
function Readout({ day }) {
  const empty = !day

  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        gap: "var(--space-8)",
        paddingTop: "var(--space-5)",
        borderTop: "1px solid var(--border-subtle)",
        minHeight: 56,
        color: empty ? "var(--text-tertiary)" : "var(--text-primary)",
      }}
    >
      {empty ? (
        <span style={{ fontSize: "var(--fs-small)" }}>
          Passe o cursor sobre um dia para ler os valores
        </span>
      ) : (
        <>
          <ReadoutItem
            label={new Date(`${day.date}T12:00:00`).toLocaleDateString("pt-BR", {
              weekday: "long",
              day: "2-digit",
              month: "short",
            })}
            value={day.is_rest ? "descanso" : `${num(day.tss, 0)} TSS`}
            token={day.is_rest ? null : "--ctl"}
          />
          {!day.is_rest && (
            <ReadoutItem label="Duração" value={duration(day.duration_s)} />
          )}
          {!day.is_rest && day.distance_m > 0 && (
            <ReadoutItem label="Distância" value={`${num(day.distance_m / 1000, 1)} km`} />
          )}
          <ReadoutItem
            label="HRV"
            value={day.hrv_rmssd_ms ? `${num(day.hrv_rmssd_ms, 0)} ms` : "—"}
            token={day.hrv_rmssd_ms ? "--hrv" : null}
          />
          <ReadoutItem
            label="Sono"
            value={day.sleep_hours ? formatSleep(day.sleep_hours) : "—"}
            token={day.sleep_hours ? "--sleep" : null}
          />
          {day.resting_hr_bpm && (
            <ReadoutItem label="FC repouso" value={`${day.resting_hr_bpm} bpm`} />
          )}
        </>
      )}
    </div>
  )
}

function ReadoutItem({ label, value, token }) {
  return (
    <div style={{ display: "grid", gap: 2 }}>
      <span className="label">{label}</span>
      <span
        className="tabular"
        style={{
          fontSize: "var(--fs-lead)",
          display: "inline-flex",
          alignItems: "center",
          gap: "var(--space-2)",
        }}
      >
        {token && (
          <span className="viz-swatch" style={{ background: `var(${token})` }} />
        )}
        {value}
      </span>
    </div>
  )
}

/** Horas decimais para `7h12`. */
function formatSleep(hours) {
  const total = Math.round(hours * 60)
  return `${Math.floor(total / 60)}h${String(total % 60).padStart(2, "0")}`
}
