/*
 * Registro de sensação — a camada que o acervo não tinha.
 *
 * Tudo no VeloDNA é medido: watts, batimentos, horas de sono. Isso deixa os
 * outliers sem explicação — um treino fraco com HRV normal e sono bom não tem
 * causa visível, mas o atleta soube no primeiro minuto que as pernas não
 * estavam lá. Esse é o dado que faltava.
 *
 * O formulário é deliberadamente curto: três toques e uma frase. Feedback que
 * dá trabalho não é preenchido, e feedback não preenchido não vale nada.
 */
import { useEffect, useState } from "react"

import { api } from "../../lib/api"

const RPE_LABEL = {
  1: "muito leve", 2: "leve", 3: "moderado", 4: "um pouco duro", 5: "duro",
  6: "duro", 7: "muito duro", 8: "muito duro", 9: "quase máximo", 10: "máximo",
}

const FEEL_LABEL = {
  1: "péssimo", 2: "ruim", 3: "normal", 4: "bom", 5: "ótimo",
}

export default function FeedbackForm({ date, activityId, initial, onSaved }) {
  const [rpe, setRpe] = useState(initial?.rpe ?? null)
  const [feel, setFeel] = useState(initial?.feel ?? null)
  const [notes, setNotes] = useState(initial?.notes ?? "")
  const [status, setStatus] = useState("idle")

  useEffect(() => {
    setRpe(initial?.rpe ?? null)
    setFeel(initial?.feel ?? null)
    setNotes(initial?.notes ?? "")
    setStatus("idle")
  }, [initial, date, activityId])

  const save = async (patch) => {
    setStatus("saving")
    try {
      await api.feedback.save({
        date,
        activity_id: activityId ?? null,
        rpe: patch.rpe ?? rpe,
        feel: patch.feel ?? feel,
        notes: patch.notes ?? notes,
      })
      setStatus("saved")
      onSaved?.()
    } catch {
      setStatus("error")
    }
  }

  return (
    <section style={{ display: "grid", gap: "var(--space-4)" }}>
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          gap: "var(--space-3)",
        }}
      >
        <span className="label">Como foi</span>
        <span
          style={{
            fontSize: "var(--fs-micro)",
            color:
              status === "error" ? "var(--status-critical)" : "var(--text-tertiary)",
          }}
        >
          {status === "saving" && "salvando…"}
          {status === "saved" && "salvo"}
          {status === "error" && "não salvou"}
        </span>
      </div>

      {activityId && (
        <Scale
          label="Esforço percebido"
          hint={rpe ? RPE_LABEL[rpe] : "escala de Borg, 1 a 10"}
          max={10}
          value={rpe}
          onChange={(v) => {
            setRpe(v)
            save({ rpe: v })
          }}
        />
      )}

      <Scale
        label="Sensação do corpo"
        hint={feel ? FEEL_LABEL[feel] : "1 péssimo, 5 ótimo"}
        max={5}
        value={feel}
        onChange={(v) => {
          setFeel(v)
          save({ feel: v })
        }}
      />

      <label style={{ display: "grid", gap: "var(--space-2)" }}>
        <span className="label">Nota</span>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          onBlur={() => notes !== (initial?.notes ?? "") && save({ notes })}
          rows={3}
          placeholder={
            activityId
              ? "vento, trânsito, como as pernas responderam…"
              : "sono, estresse, o que afetou o dia…"
          }
          style={{
            font: "inherit",
            fontSize: "var(--fs-small)",
            color: "var(--text-primary)",
            background: "var(--surface-sunken)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "var(--radius-sm)",
            padding: "var(--space-3)",
            resize: "vertical",
          }}
        />
      </label>
    </section>
  )
}

/** Escala discreta em botões — mais rápida que slider no toque e no clique. */
function Scale({ label, hint, max, value, onChange }) {
  return (
    <div style={{ display: "grid", gap: "var(--space-2)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: "var(--space-3)" }}>
        <span style={{ fontSize: "var(--fs-small)", color: "var(--text-secondary)" }}>
          {label}
        </span>
        <span style={{ fontSize: "var(--fs-micro)", color: "var(--text-tertiary)" }}>
          {hint}
        </span>
      </div>
      <div style={{ display: "flex", gap: 4 }}>
        {Array.from({ length: max }, (_, i) => i + 1).map((n) => (
          <button
            key={n}
            aria-pressed={value === n}
            aria-label={`${label} ${n}`}
            onClick={() => onChange(value === n ? null : n)}
            className="tabular"
            style={{
              flex: 1,
              appearance: "none",
              cursor: "pointer",
              font: "inherit",
              fontSize: "var(--fs-small)",
              padding: "var(--space-2) 0",
              borderRadius: "var(--radius-sm)",
              border: "1px solid var(--border-subtle)",
              background:
                value === n ? "var(--ctl)" : "var(--surface-sunken)",
              color: value === n ? "#fff" : "var(--text-secondary)",
            }}
          >
            {n}
          </button>
        ))}
      </div>
    </div>
  )
}
