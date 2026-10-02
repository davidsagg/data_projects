/*
 * Notas do ciclo — os marcos em cards, do mais recente ao mais antigo.
 *
 * É a seção "Notas do projeto" do painel de referência, com uma diferença: lá
 * o texto era escrito à mão no HTML; aqui vem do acervo (`milestones` e os
 * testes de CP do histórico de FTP), então o card de amanhã já sai pronto.
 */
import { useState } from "react"

import { Pill } from "../viz/GoalPill"
import { MILESTONE_LABELS } from "../viz/milestoneLines"
import { fullDate, num } from "../../lib/format"

/* Tipo do marco não é estado — vai em etiqueta neutra. Só o achado, que é por
   definição um alerta, ganha o tom de atenção. */
const KIND_TONE = { achado: "serious" }

const MEASURE_LABELS = {
  vo2max_ml_kg_min: ["VO2máx", "ml/kg/min"],
  vo2max_l_min: ["VO2máx", "L/min"],
  fatmax_w: ["FATmax", "W"],
  fatmax_g_min: ["Gordura máx.", "g/min"],
  lt1_w: ["LL", "W"],
  lt1_hr_bpm: ["FC no LL", "bpm"],
  lt2_w: ["LTP", "W"],
  lt2_hr_bpm: ["FC no LTP", "bpm"],
  peak_w: ["Pico", "W"],
  lactate_peak_mmol: ["Lactato pico", "mmol/L"],
  ftp_w: ["FTP", "W"],
  cp_w: ["CP", "W"],
  w_prime_kj: ["W'", "kJ"],
  hr_max_bpm: ["FC máx", "bpm"],
  weight_kg: ["Peso", "kg"],
}

function measureText(key, value) {
  const [label, unit] = MEASURE_LABELS[key] ?? [key, ""]
  const digits = Number.isInteger(value) ? 0 : value < 10 ? 2 : 1
  return `${label} ${num(value, digits)}${unit ? ` ${unit}` : ""}`
}

export default function MilestoneCards({ milestones, limit = 4, onDelete }) {
  // Remoção em dois cliques: o primeiro arma, o segundo confirma.
  const [armed, setArmed] = useState(null)
  if (!milestones?.length) {
    return (
      <div className="card card--static">
        <p className="muted" style={{ margin: 0, fontSize: "var(--fs-small)" }}>
          Nenhum marco registrado. Exames (ergoespirometria, lactato), início de
          planos, provas e achados entram aqui — pelo formulário abaixo ou com{" "}
          <code>scripts/add_milestone.py</code>.
        </p>
      </div>
    )
  }

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
        gap: "var(--card-gap)",
      }}
    >
      {milestones.slice(0, limit).map((m) => (
        <article
          key={m.id}
          className="card card--static"
          style={{ display: "grid", gap: "var(--space-2)", alignContent: "start" }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--space-2)",
              flexWrap: "wrap",
            }}
          >
            <Pill tone={KIND_TONE[m.kind]}>{MILESTONE_LABELS[m.kind] ?? m.kind}</Pill>
            <h3 className="card-title">{m.title}</h3>
          </div>
          <span className="tabular" style={{ fontSize: "var(--fs-micro)", color: "var(--text-tertiary)" }}>
            {fullDate(m.date)}
            {m.source && ` · ${m.source}`}
          </span>
          {Object.keys(m.measurements || {}).length > 0 && (
            <div
              className="tabular"
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: "var(--space-1) var(--space-4)",
                fontSize: "var(--fs-small)",
              }}
            >
              {Object.entries(m.measurements).map(([key, value]) => (
                <span key={key}>{measureText(key, value)}</span>
              ))}
            </div>
          )}
          {m.summary && (
            <p style={{ margin: 0, fontSize: "var(--fs-small)", color: "var(--text-secondary)", lineHeight: 1.55 }}>
              {m.summary}
            </p>
          )}
          {onDelete && m.origin === "milestone" && (
            <button
              type="button"
              className="table-toggle"
              style={{ color: "var(--text-tertiary)", fontWeight: 500 }}
              onClick={() => (armed === m.id ? onDelete(m) : setArmed(m.id))}
              onBlur={() => setArmed(null)}
            >
              {armed === m.id ? "clique de novo para remover" : "remover"}
            </button>
          )}
        </article>
      ))}
    </div>
  )
}
