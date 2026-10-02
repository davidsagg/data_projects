/*
 * Metas e marcos — o cadastro do contexto que não vem de sensor.
 *
 * O mesmo que `set_athlete_profile.py --goal` e `add_milestone.py` fazem pelo
 * terminal, para não exigir terminal de quem só quer anotar o resultado de um
 * exame. Os formulários ficam no fim do Panorama: são consulta rara, não leitura.
 */
import { useEffect, useState } from "react"

import { api } from "../../lib/api"
import { num } from "../../lib/format"
import { goalText } from "../../lib/goals"

const KINDS = [
  { value: "exame", label: "Exame" },
  { value: "plano", label: "Início de plano" },
  { value: "prova", label: "Prova" },
  { value: "achado", label: "Achado" },
]

const field = {
  font: "inherit",
  fontSize: "var(--fs-small)",
  padding: "6px 10px",
  borderRadius: "var(--radius-sm)",
  border: "1px solid var(--border-strong)",
  background: "var(--surface-1)",
  color: "var(--text-primary)",
  minWidth: 0,
}

const primary = {
  ...field,
  border: 0,
  background: "var(--accent-fill)",
  color: "#fff",
  fontWeight: 600,
  cursor: "pointer",
}

/** Lê "vo2max_ml_kg_min=47,5; fatmax_w=120" em {nome: valor}. */
function parseMeasurements(text) {
  const result = {}
  for (const part of text.split(/[;\n]/)) {
    const [name, value] = part.split("=").map((s) => s?.trim())
    if (!name) continue
    const parsed = Number(String(value ?? "").replace(",", "."))
    if (!value || Number.isNaN(parsed)) throw new Error(`Valor inválido em "${part.trim()}"`)
    result[name] = parsed
  }
  return result
}

export default function CycleSettings({ goals, onChanged }) {
  const [metrics, setMetrics] = useState([])
  const [goalForm, setGoalForm] = useState({ metric: "weight_kg", target: "", target_date: "" })
  const [milestone, setMilestone] = useState({
    date: new Date().toISOString().slice(0, 10),
    kind: "exame",
    title: "",
    summary: "",
    measurements: "",
    source: "",
  })
  const [status, setStatus] = useState(null)

  useEffect(() => {
    api.goals.metrics().then(setMetrics).catch(() => {})
  }, [])

  const run = async (action, message) => {
    setStatus(null)
    try {
      await action()
      setStatus({ ok: true, text: message })
      onChanged?.()
    } catch (error) {
      setStatus({ ok: false, text: error.message })
    }
  }

  const saveGoal = (event) => {
    event.preventDefault()
    const target = Number(String(goalForm.target).replace(",", "."))
    if (!target) return setStatus({ ok: false, text: "Informe um valor de meta." })
    run(
      () =>
        api.goals.save({
          metric: goalForm.metric,
          target,
          target_date: goalForm.target_date || null,
        }),
      "Meta salva.",
    )
  }

  const saveMilestone = (event) => {
    event.preventDefault()
    if (!milestone.title.trim()) return setStatus({ ok: false, text: "Dê um título ao marco." })
    run(async () => {
      await api.milestones.create({
        date: milestone.date,
        kind: milestone.kind,
        title: milestone.title.trim(),
        summary: milestone.summary.trim() || null,
        source: milestone.source.trim() || null,
        measurements: parseMeasurements(milestone.measurements),
      })
      setMilestone((m) => ({ ...m, title: "", summary: "", measurements: "", source: "" }))
    }, "Marco registrado.")
  }

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
        gap: "var(--card-gap)",
        alignItems: "start",
      }}
    >
      <section className="card card--static" style={{ display: "grid", gap: "var(--space-3)" }}>
        <h3 className="card-title">Metas</h3>
        {goals?.length > 0 ? (
          <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "grid", gap: "var(--space-2)" }}>
            {goals.map((g) => (
              <li
                key={g.metric}
                style={{ display: "flex", justifyContent: "space-between", gap: "var(--space-3)", fontSize: "var(--fs-small)" }}
              >
                <span>
                  {g.label}: <span className="tabular">{num(g.target, g.unit === "W" ? 0 : 1)} {g.unit}</span>
                  <span className="muted"> · {goalText(g)}</span>
                </span>
                <button
                  type="button"
                  className="table-toggle"
                  style={{ margin: 0, color: "var(--text-tertiary)", fontWeight: 500 }}
                  onClick={() => run(() => api.goals.remove(g.metric), "Meta removida.")}
                >
                  remover
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted" style={{ margin: 0, fontSize: "var(--fs-small)" }}>Nenhuma meta cadastrada.</p>
        )}
        <form onSubmit={saveGoal} style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-2)" }}>
          <select
            aria-label="Métrica"
            style={field}
            value={goalForm.metric}
            onChange={(e) => setGoalForm({ ...goalForm, metric: e.target.value })}
          >
            {metrics.map((m) => (
              <option key={m.metric} value={m.metric}>
                {m.label}
                {m.unit ? ` (${m.unit})` : ""}
              </option>
            ))}
          </select>
          <input
            aria-label="Valor alvo"
            placeholder="alvo"
            inputMode="decimal"
            style={{ ...field, width: 90 }}
            value={goalForm.target}
            onChange={(e) => setGoalForm({ ...goalForm, target: e.target.value })}
          />
          <input
            aria-label="Prazo"
            type="date"
            style={field}
            value={goalForm.target_date}
            onChange={(e) => setGoalForm({ ...goalForm, target_date: e.target.value })}
          />
          <button type="submit" style={primary}>Salvar meta</button>
        </form>
      </section>

      <section className="card card--static" style={{ display: "grid", gap: "var(--space-3)" }}>
        <h3 className="card-title">Registrar marco</h3>
        <form onSubmit={saveMilestone} style={{ display: "grid", gap: "var(--space-2)" }}>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-2)" }}>
            <input
              aria-label="Data"
              type="date"
              style={field}
              value={milestone.date}
              onChange={(e) => setMilestone({ ...milestone, date: e.target.value })}
            />
            <select
              aria-label="Tipo"
              style={field}
              value={milestone.kind}
              onChange={(e) => setMilestone({ ...milestone, kind: e.target.value })}
            >
              {KINDS.map((k) => (
                <option key={k.value} value={k.value}>{k.label}</option>
              ))}
            </select>
            <input
              aria-label="Título"
              placeholder="Título — ex.: Ergoespirometria"
              style={{ ...field, flex: 1 }}
              value={milestone.title}
              onChange={(e) => setMilestone({ ...milestone, title: e.target.value })}
            />
          </div>
          <textarea
            aria-label="Conclusão"
            placeholder="Conclusão — ex.: VO2max ~10% abaixo de 2023 com FTP estável"
            rows={2}
            style={{ ...field, resize: "vertical" }}
            value={milestone.summary}
            onChange={(e) => setMilestone({ ...milestone, summary: e.target.value })}
          />
          <input
            aria-label="Valores medidos"
            placeholder="Valores: vo2max_ml_kg_min=47,5; fatmax_w=120"
            style={field}
            value={milestone.measurements}
            onChange={(e) => setMilestone({ ...milestone, measurements: e.target.value })}
          />
          <div style={{ display: "flex", gap: "var(--space-2)" }}>
            <input
              aria-label="Fonte"
              placeholder="Fonte — laboratório, dossiê…"
              style={{ ...field, flex: 1 }}
              value={milestone.source}
              onChange={(e) => setMilestone({ ...milestone, source: e.target.value })}
            />
            <button type="submit" style={primary}>Registrar</button>
          </div>
        </form>
      </section>

      {status && (
        <p
          role="status"
          style={{
            margin: 0,
            gridColumn: "1 / -1",
            fontSize: "var(--fs-small)",
            color: status.ok ? "var(--text-secondary)" : "var(--status-critical)",
          }}
        >
          {status.text}
        </p>
      )}
    </div>
  )
}
