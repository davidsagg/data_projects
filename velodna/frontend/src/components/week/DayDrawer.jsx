/*
 * Drawer lateral com o detalhe de um dia.
 *
 * Drawer e não modal: a spec proíbe modal para exibir dados, e com razão — o
 * modal tapa o contexto de onde se veio, e aqui o contexto (a semana inteira)
 * é justamente o que dá sentido ao dia.
 */
import { useEffect } from "react"

import FeedbackForm from "./FeedbackForm"
import { duration, num, watts } from "../../lib/format"

export default function DayDrawer({
  day,
  activities,
  onClose,
  onOpenActivity,
  onFeedbackSaved,
}) {
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose()
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onClose])

  if (!day) return null

  const ofDay = (activities || []).filter((a) => a.date === day.date)
  const title = new Date(`${day.date}T12:00:00`).toLocaleDateString("pt-BR", {
    weekday: "long",
    day: "2-digit",
    month: "long",
  })

  return (
    <>
      <div
        onClick={onClose}
        style={{
          position: "fixed",
          inset: 0,
          background: "rgba(0, 0, 0, 0.4)",
          zIndex: 40,
        }}
      />
      <aside
        role="dialog"
        aria-label={`Detalhe de ${title}`}
        style={{
          position: "fixed",
          top: 0,
          right: 0,
          bottom: 0,
          width: "min(420px, 92vw)",
          background: "var(--surface-2)",
          borderLeft: "1px solid var(--border-subtle)",
          padding: "var(--space-8)",
          overflowY: "auto",
          zIndex: 41,
          display: "grid",
          gap: "var(--space-8)",
          alignContent: "start",
        }}
      >
        <header
          style={{
            display: "flex",
            alignItems: "baseline",
            justifyContent: "space-between",
            gap: "var(--space-4)",
          }}
        >
          <h2 style={{ margin: 0, fontSize: "var(--fs-lead)" }}>{title}</h2>
          <button
            onClick={onClose}
            aria-label="Fechar"
            style={{
              appearance: "none",
              border: 0,
              background: "transparent",
              color: "var(--text-secondary)",
              fontSize: "var(--fs-lead)",
              cursor: "pointer",
              lineHeight: 1,
            }}
          >
            ✕
          </button>
        </header>

        <section style={{ display: "grid", gap: "var(--space-4)" }}>
          <span className="label">Treino</span>
          {day.is_rest ? (
            <p className="muted" style={{ margin: 0 }}>
              Dia de descanso.
              {day.planned_tss > 0 &&
                ` Havia ${num(day.planned_tss, 0)} TSS planejados.`}
            </p>
          ) : (
            <>
              <Row label="Carga" value={`${num(day.tss, 0)} TSS`} />
              {day.planned_tss > 0 && (
                <Row label="Planejado" value={`${num(day.planned_tss, 0)} TSS`} />
              )}
              <Row label="Duração" value={duration(day.duration_s)} />
              {day.distance_m > 0 && (
                <Row label="Distância" value={`${num(day.distance_m / 1000, 1)} km`} />
              )}
            </>
          )}
        </section>

        <section style={{ display: "grid", gap: "var(--space-4)" }}>
          <span className="label">Saúde</span>
          {day.hrv_rmssd_ms == null &&
          day.sleep_hours == null &&
          day.resting_hr_bpm == null ? (
            <p className="muted" style={{ margin: 0 }}>
              Sem sincronização do Garmin neste dia.
            </p>
          ) : (
            <>
              {day.sleep_hours != null && (
                <Row label="Sono" value={formatSleep(day.sleep_hours)} />
              )}
              {day.sleep_quality_score != null && (
                <Row label="Qualidade do sono" value={`${day.sleep_quality_score}/100`} />
              )}
              {day.hrv_rmssd_ms != null && (
                <Row label="HRV" value={`${num(day.hrv_rmssd_ms, 0)} ms`} />
              )}
              {day.resting_hr_bpm != null && (
                <Row label="FC repouso" value={`${day.resting_hr_bpm} bpm`} />
              )}
              {day.body_battery != null && (
                <Row label="Body battery" value={String(day.body_battery)} />
              )}
            </>
          )}
        </section>

        {/* O feedback fica logo depois da saúde: é a mesma pergunta — como o
            corpo estava — mas do lado que nenhum sensor mede. */}
        <FeedbackForm
          date={day.date}
          activityId={ofDay.length === 1 ? ofDay[0].id : null}
          initial={{ rpe: day.rpe, feel: day.feel, notes: day.notes }}
          onSaved={onFeedbackSaved}
        />

        {ofDay.length > 0 && (
          <section style={{ display: "grid", gap: "var(--space-4)" }}>
            <span className="label">
              {ofDay.length === 1 ? "Atividade" : "Atividades"}
            </span>
            {ofDay.map((activity) => (
              <button
                key={activity.id}
                onClick={() => onOpenActivity?.(activity)}
                className="card"
                style={{
                  textAlign: "left",
                  cursor: onOpenActivity ? "pointer" : "default",
                  display: "grid",
                  gap: "var(--space-2)",
                  font: "inherit",
                  color: "inherit",
                  padding: "var(--space-4)",
                }}
              >
                <strong style={{ fontSize: "var(--fs-body)" }}>
                  {activity.sport_type}
                </strong>
                <span
                  className="tabular"
                  style={{ fontSize: "var(--fs-small)", color: "var(--text-secondary)" }}
                >
                  {duration(activity.moving_time_s || activity.elapsed_time_s)}
                  {activity.normalized_power_w
                    ? ` · NP ${watts(activity.normalized_power_w)}`
                    : ""}
                  {activity.intensity_factor
                    ? ` · IF ${num(activity.intensity_factor, 2)}`
                    : ""}
                </span>
              </button>
            ))}
          </section>
        )}
      </aside>
    </>
  )
}

function Row({ label, value }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        gap: "var(--space-4)",
        fontSize: "var(--fs-body)",
      }}
    >
      <span style={{ color: "var(--text-secondary)" }}>{label}</span>
      <span className="tabular">{value}</span>
    </div>
  )
}

function formatSleep(hours) {
  const total = Math.round(hours * 60)
  return `${Math.floor(total / 60)}h${String(total % 60).padStart(2, "0")}`
}
