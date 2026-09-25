/*
 * Execução por quartos — como a intensidade se distribuiu ao longo do esforço.
 *
 * A leitura é visual e não precisa de número: se a primeira coluna está pesada
 * nas zonas altas e a última desabou para as baixas, o atleta saiu forte demais.
 * Quatro colunas parecidas significam execução regular.
 *
 * As zonas usam a rampa sequencial, não cores categóricas — zonas são ordinais,
 * e a ordem do claro ao escuro já comunica a intensidade sem legenda.
 */
import { useEffect, useState } from "react"

import ChartFrame from "../viz/ChartFrame"
import { api } from "../../lib/api"
import { duration, num } from "../../lib/format"

/* Mesma convenção Coggan da distribuição semanal — duas paletas para a mesma
   grandeza fariam o atleta reaprender a leitura a cada tela. */
const ZONE_TOKEN = {
  Z1: "--zone-1", Z2: "--zone-2", Z3: "--zone-3",
  Z4: "--zone-4", Z5: "--zone-5", Z6: "--zone-6", Z7: "--zone-7",
}

const VERDICT_TOKEN = {
  "saiu forte demais": "--status-warning",
  "negative split": "--status-good",
  "execução regular": "--status-good",
}

export default function PacingPanel({ activityId }) {
  const [data, setData] = useState(null)

  useEffect(() => {
    if (!activityId) return undefined
    let cancelled = false
    setData(null)

    api.analysis
      .pacing(activityId)
      .then((r) => !cancelled && setData(r))
      .catch(() => !cancelled && setData(null))

    return () => {
      cancelled = true
    }
  }, [activityId])

  if (!data?.quarters?.length) return null

  const drift = data.decoupling_first_to_last

  return (
    <ChartFrame
      title="Execução"
      subtitle="Distribuição de intensidade em cada quarto do esforço"
      action={
        <span
          style={{
            fontSize: "var(--fs-small)",
            display: "inline-flex",
            alignItems: "center",
            gap: 5,
            color: "var(--text-secondary)",
          }}
        >
          <span
            className="viz-swatch"
            style={{
              background: `var(${VERDICT_TOKEN[data.verdict] || "--text-tertiary"})`,
              borderRadius: "50%",
            }}
          />
          {data.verdict}
        </span>
      }
    >
      <div style={{ display: "grid", gap: "var(--space-5)" }}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, 1fr)",
            gap: "var(--space-4)",
            alignItems: "end",
            height: 170,
          }}
        >
          {data.quarters.map((q) => (
            <QuarterColumn key={q.quarter} quarter={q} />
          ))}
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, 1fr)",
            gap: "var(--space-4)",
            fontSize: "var(--fs-micro)",
            color: "var(--text-tertiary)",
          }}
        >
          {data.quarters.map((q) => (
            <div key={q.quarter} style={{ textAlign: "center", display: "grid", gap: 2 }}>
              <span className="label">{q.quarter}º quarto</span>
              <span className="tabular">{duration(q.duration_s)}</span>
              <span className="tabular">
                {q.normalized_power_w ? `NP ${num(q.normalized_power_w, 0)} W` : ""}
                {q.avg_hr_bpm ? ` · ${num(q.avg_hr_bpm, 0)} bpm` : ""}
              </span>
            </div>
          ))}
        </div>

        {drift !== null && drift !== undefined && (
          <p className="card-subtitle" style={{ margin: 0 }}>
            A razão potência/FC {drift < 0 ? "caiu" : "subiu"}{" "}
            <strong style={{ color: "var(--text-primary)" }}>
              {num(Math.abs(drift), 1)}%
            </strong>{" "}
            do primeiro ao último quarto
            {drift < -5
              ? " — custo cardíaco crescente, sinal de fadiga aeróbica."
              : "."}
          </p>
        )}
      </div>
    </ChartFrame>
  )
}

/** Uma coluna empilhada, do Z1 na base ao Z7 no topo. */
function QuarterColumn({ quarter }) {
  const zones = Object.entries(quarter.zone_pct)
    .filter(([, pct]) => pct > 0)
    .sort(([a], [b]) => b.localeCompare(a))

  return (
    <div
      style={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "flex-end",
        gap: 2,
      }}
    >
      {zones.map(([zone, pct]) => (
        <div
          key={zone}
          title={`${zone}: ${num(pct, 1)}%`}
          style={{
            height: `${pct}%`,
            background: `var(${ZONE_TOKEN[zone]})`,
            borderRadius: "var(--radius-sm)",
            minHeight: 2,
          }}
        />
      ))}
    </div>
  )
}
