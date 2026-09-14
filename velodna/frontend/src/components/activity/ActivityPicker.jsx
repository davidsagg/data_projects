/*
 * Lista de atividades com seleção múltipla.
 *
 * Selecionar mais de uma entra em modo de comparação. O limite de três é
 * deliberado: a paleta categórica só garante separação segura para daltonismo
 * nos três primeiros tons quando todos os pares aparecem juntos, que é o caso
 * de curvas sobrepostas.
 */
import { useMemo, useState } from "react"

import { duration, fullDate, km, num, shortDate } from "../../lib/format"
import { useCssVars } from "../../lib/useCssVar"

export const MAX_COMPARE = 3
const SERIES_TOKENS = ["--series-1", "--series-2", "--series-3"]

export default function ActivityPicker({ activities, selected, onToggle }) {
  const [search, setSearch] = useState("")
  const [sport, setSport] = useState("cycling")
  const colors = useCssVars(SERIES_TOKENS)

  // Ciclismo primeiro (é o uso principal), depois os demais esportes presentes.
  const sportOptions = useMemo(() => {
    const present = [...new Set((activities || []).map((a) => a.sport_type))]
    const others = present.filter((s) => s !== "cycling").sort()
    return ["cycling", ...others.slice(0, 2), "all"]
  }, [activities])

  const rows = useMemo(() => {
    const term = search.trim().toLowerCase()
    return (activities || [])
      .filter((a) => sport === "all" || a.sport_type === sport)
      .filter((a) => !term || fullDate(a.started_at).toLowerCase().includes(term))
      .sort((a, b) => (a.started_at < b.started_at ? 1 : -1))
  }, [activities, search, sport])

  return (
    <section className="card" style={{ display: "grid", gap: "var(--space-3)" }}>
      <div>
        <h2 className="card-title">Atividades</h2>
        <p className="card-subtitle">
          Selecione até {MAX_COMPARE} para comparar · {rows.length} no filtro
        </p>
      </div>

      <div className="toolbar" style={{ marginBottom: 0 }}>
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Buscar por data…"
          aria-label="Buscar atividades"
          style={{
            flex: "1 1 140px",
            minWidth: 0,
            font: "inherit",
            fontSize: "var(--fs-small)",
            padding: "5px 8px",
            borderRadius: "var(--radius-sm)",
            border: "1px solid var(--border)",
            background: "var(--surface-1)",
            color: "var(--text-primary)",
          }}
        />
        <div className="segmented" role="group" aria-label="Esporte">
          {sportOptions.map((s) => (
            <button key={s} aria-pressed={sport === s} onClick={() => setSport(s)}>
              {s === "all" ? "Todos" : s}
            </button>
          ))}
        </div>
      </div>

      {/* Sem rolagem horizontal: a lista é estreita por design, então as
          colunas menos essenciais saem em vez de a tabela transbordar. */}
      <div style={{ maxHeight: 460, overflowY: "auto" }}>
        <table className="data" style={{ tableLayout: "fixed", width: "100%" }}>
          <thead>
            <tr>
              <th style={{ width: 22 }} aria-label="Seleção" />
              <th>Data</th>
              <th style={{ width: 52 }}>Dist.</th>
              <th style={{ width: 56 }}>Tempo</th>
              <th style={{ width: 44 }}>TSS</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((a) => {
              const index = selected.findIndex((s) => s.id === a.id)
              const isSelected = index >= 0
              return (
                <tr
                  key={a.id}
                  onClick={() => onToggle(a)}
                  style={{
                    cursor: "pointer",
                    background: isSelected ? "var(--surface-sunken)" : undefined,
                  }}
                >
                  <td>
                    <span
                      className="viz-swatch"
                      style={{
                        display: "inline-block",
                        background: isSelected
                          ? colors[SERIES_TOKENS[index]]
                          : "transparent",
                        border: isSelected
                          ? "none"
                          : "1px solid var(--axis)",
                        borderRadius: 2,
                      }}
                    />
                  </td>
                  <td style={{ whiteSpace: "nowrap" }}>{shortDate(a.started_at)}</td>
                  <td>{km(a.distance_m, 0)}</td>
                  <td>{duration(a.elapsed_time_s)}</td>
                  <td>{num(a.tss, 0)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}
