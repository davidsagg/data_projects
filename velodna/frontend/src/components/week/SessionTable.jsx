/*
 * Treinos da semana — planejado versus executado.
 *
 * Segue o bloco "dia a dia" do relatório: cada linha traz o que foi de fato
 * registrado (TSS, NP, potência média, cadência, FC) ao lado do que estava
 * prescrito, e o **compliance** — o quão perto o treino chegou do plano.
 *
 * O Pw:Hr ganha coluna própria porque a régua é conhecida e fixa: até ~5% indica
 * boa base aeróbica para aquela duração; acima disso vale olhar hidratação,
 * calor ou volume. Um número com régua é acionável; sem régua é decoração.
 */
import { duration, num, shortDate, watts } from "../../lib/format"
import { MODALITY_TOKENS } from "../../lib/goals"

const MODALITY_LABELS = {
  outdoor: "Pedal na rua",
  indoor: "Pedal no rolo",
  strength: "Força",
  other: "Outros",
}

/** Acima deste percentual, a deriva cardíaca sai da faixa esperada. */
const DECOUPLING_THRESHOLD = 5.0

const FEEL_LABEL = { 1: "péssimo", 2: "ruim", 3: "normal", 4: "bom", 5: "ótimo" }

export default function SessionTable({ activities, onOpenActivity }) {
  if (!activities?.length) {
    return (
      <p className="muted" style={{ margin: 0 }}>
        Nenhuma atividade registrada nesta semana.
      </p>
    )
  }

  const hasPlan = activities.some((a) => a.planned_tss)

  return (
    <div className="scroll-x">
      <table
        className="tabular"
        style={{ width: "100%", minWidth: 900, fontSize: "var(--fs-small)" }}
      >
        <thead>
          <tr style={{ textAlign: "left", color: "var(--text-tertiary)" }}>
            <Th>Dia</Th>
            <Th>Treino</Th>
            <Th align="right">Duração</Th>
            <Th align="right">Dist.</Th>
            <Th align="right">Elev.</Th>
            <Th align="right">NP</Th>
            <Th align="right">Média</Th>
            <Th align="right">IF</Th>
            <Th align="right">Cad.</Th>
            <Th align="right">FC</Th>
            <Th align="right">Pw:Hr</Th>
            <Th align="right">TSS</Th>
            {hasPlan && <Th align="right">Plano</Th>}
            <Th align="right">Sensação</Th>
          </tr>
        </thead>
        <tbody>
          {activities.map((a) => (
            <tr
              key={a.id}
              onClick={() => onOpenActivity?.(a)}
              style={{
                borderTop: "1px solid var(--border-subtle)",
                cursor: onOpenActivity ? "pointer" : "default",
              }}
            >
              <td>{shortDate(a.date || a.started_at)}</td>
              <td style={{ fontFamily: "var(--font)", maxWidth: 280 }}>
                <span
                  style={{ display: "inline-flex", alignItems: "center", gap: 6, minWidth: 0 }}
                  title={a.name || undefined}
                >
                  {a.modality && (
                    <span
                      className="viz-swatch"
                      aria-label={MODALITY_LABELS[a.modality]}
                      style={{
                        background: `var(${MODALITY_TOKENS[a.modality]})`,
                        borderRadius: "50%",
                      }}
                    />
                  )}
                  <span
                    style={{
                      fontWeight: 600,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {a.name || a.planned_name || a.sport_type}
                  </span>
                </span>
                {a.name && a.planned_name && (
                  <div className="muted" style={{ fontSize: "var(--fs-micro)" }}>
                    plano: {a.planned_name}
                  </div>
                )}
              </td>
              <td style={{ textAlign: "right" }}>
                {duration(a.moving_time_s || a.elapsed_time_s)}
              </td>
              <td style={{ textAlign: "right" }}>
                {a.distance_m ? `${num(a.distance_m / 1000, 1)} km` : "—"}
              </td>
              <td style={{ textAlign: "right" }}>
                {a.elevation_gain_m ? `${num(a.elevation_gain_m, 0)} m` : "—"}
              </td>
              <td style={{ textAlign: "right" }}>{watts(a.normalized_power_w)}</td>
              <td style={{ textAlign: "right", color: "var(--text-secondary)" }}>
                {watts(a.avg_power_w)}
              </td>
              <td style={{ textAlign: "right" }}>{num(a.intensity_factor, 2)}</td>
              <td style={{ textAlign: "right", color: "var(--text-secondary)" }}>
                {a.avg_cadence_rpm ? num(a.avg_cadence_rpm, 0) : "—"}
              </td>
              <td style={{ textAlign: "right", color: "var(--text-secondary)" }}>
                {a.avg_hr_bpm ? `${num(a.avg_hr_bpm, 0)}` : "—"}
              </td>
              <td
                style={{
                  textAlign: "right",
                  color:
                    a.decoupling_pct > DECOUPLING_THRESHOLD
                      ? "var(--status-warning)"
                      : "var(--text-secondary)",
                }}
                title={
                  a.decoupling_pct > DECOUPLING_THRESHOLD
                    ? "Acima de 5% — deriva cardíaca fora da faixa esperada"
                    : undefined
                }
              >
                {a.decoupling_pct != null ? `${num(a.decoupling_pct, 1)}%` : "—"}
              </td>
              <td style={{ textAlign: "right", fontWeight: 500 }}>
                {num(a.tss, 0)}
              </td>
              {hasPlan && (
                <td style={{ textAlign: "right" }}>
                  {a.planned_tss ? (
                    <span
                      style={{
                        color:
                          a.compliance_pct >= 80
                            ? "var(--status-good)"
                            : "var(--status-warning)",
                      }}
                    >
                      {num(a.compliance_pct, 0)}%
                      <span className="muted"> de {num(a.planned_tss, 0)}</span>
                    </span>
                  ) : (
                    "—"
                  )}
                </td>
              )}
              <td style={{ textAlign: "right", color: "var(--text-tertiary)" }}>
                {a.feel ? FEEL_LABEL[a.feel] : a.rpe ? `RPE ${a.rpe}` : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Th({ children, align = "left" }) {
  return <th style={{ fontWeight: 500, textAlign: align }}>{children}</th>
}
