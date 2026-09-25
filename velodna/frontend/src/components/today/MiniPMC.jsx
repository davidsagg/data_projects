/*
 * PMC compacto — a forma sem trocar de tela.
 *
 * A Fitness tem o PMC completo, com faixas de TSB, seletor de período e camada
 * de HRV. Aqui a pergunta é mais rasa: "como a forma chegou até hoje?". Sessenta
 * dias, três séries, sem controles — quem quiser investigar clica e vai à Fitness.
 */
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import ChartFrame from "../viz/ChartFrame"
import VizTooltip from "../viz/Tooltip"
import { useCssVars } from "../../lib/useCssVar"
import { dayMonth, fullDate, num } from "../../lib/format"

const TOKENS = [
  "--ctl", "--atl", "--tsb-positive", "--gridline", "--axis", "--text-tertiary",
]

export default function MiniPMC({ pmc, onOpenFitness }) {
  const colors = useCssVars(TOKENS)

  if (!pmc?.length) return null

  const rows = pmc.slice(-60)
  const latest = rows[rows.length - 1]
  const axis = {
    stroke: colors["--axis"],
    tick: { fill: colors["--text-tertiary"], fontSize: 11 },
    tickLine: false,
    axisLine: false,
  }

  return (
    <ChartFrame
      title="Forma — últimos 60 dias"
      subtitle={`CTL ${num(latest.ctl, 1)} · ATL ${num(latest.atl, 1)} · TSB ${num(latest.tsb, 1)}`}
      series={[
        { label: "CTL · forma", color: colors["--ctl"] },
        { label: "ATL · fadiga", color: colors["--atl"] },
        { label: "TSB · frescor", color: colors["--tsb-positive"] },
      ]}
      action={
        onOpenFitness && (
          <button
            onClick={onOpenFitness}
            style={{
              appearance: "none", border: 0, background: "transparent",
              font: "inherit", fontSize: "var(--fs-small)",
              color: "var(--text-secondary)", cursor: "pointer", padding: 0,
            }}
          >
            ver completo →
          </button>
        )
      }
    >
      <ResponsiveContainer width="100%" height={180}>
        <ComposedChart data={rows} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="miniCtl" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={colors["--ctl"]} stopOpacity={0.18} />
              <stop offset="100%" stopColor={colors["--ctl"]} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={colors["--gridline"]} vertical={false} opacity={0.35} />
          <XAxis dataKey="date" tickFormatter={dayMonth} minTickGap={40} {...axis} />
          {/* Largura suficiente para "47,8" e para o TSB negativo: com 34px
              os rótulos saíam cortados em "5, 0, 5". */}
          <YAxis {...axis} width={42} />
          <ReferenceLine y={0} stroke={colors["--axis"]} />
          <Tooltip
            content={<VizTooltip formatValue={(v) => num(v, 1)} />}
            labelFormatter={fullDate}
          />
          <Area
            dataKey="ctl" name="CTL · forma" stroke={colors["--ctl"]}
            strokeWidth={2} fill="url(#miniCtl)" dot={false} isAnimationActive={false}
          />
          <Line
            dataKey="atl" name="ATL · fadiga" stroke={colors["--atl"]}
            strokeWidth={1.5} dot={false} isAnimationActive={false}
          />
          <Line
            dataKey="tsb" name="TSB · frescor" stroke={colors["--tsb-positive"]}
            strokeWidth={1.5} strokeDasharray="3 3" dot={false} isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>

      {/* A régua de cada série, no formato do guia do atleta: os três números
          só significam algo com a janela de cálculo e a faixa de leitura à
          vista. "TSB −15" sem saber que é CTL − ATL não diz nada. */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))",
          gap: "var(--space-4)",
          marginTop: "var(--space-5)",
          paddingTop: "var(--space-4)",
          borderTop: "1px solid var(--border-subtle)",
        }}
      >
        <Note token="--ctl" label="CTL · fitness">
          Média móvel do TSS diário em <strong>42 dias</strong>. É a capacidade
          acumulada — sobe devagar e cai devagar.
        </Note>
        <Note token="--atl" label="ATL · fadiga">
          Média móvel de <strong>7 dias</strong>. É o cansaço recente: sobe e
          desce rápido conforme os últimos treinos.
        </Note>
        <Note token="--tsb-positive" label="TSB · forma">
          CTL − ATL. Bem negativo é fadiga acumulada; perto de zero ou positivo,
          corpo descansado — o ideal às vésperas de prova.
        </Note>
      </div>

      <p
        style={{
          margin: "var(--space-4) 0 0",
          fontSize: "var(--fs-micro)",
          lineHeight: 1.6,
          color: "var(--text-tertiary)",
        }}
      >
        Os três vêm do TSS, que é uma <em>estimativa</em> de carga — não medem
        recuperação real (sono, HRV, estresse). Use como tendência, nunca
        isoladamente.
      </p>
    </ChartFrame>
  )
}

/** Uma régua de série: o quadradinho da cor, o nome e como ler. */
function Note({ token, label, children }) {
  return (
    <div style={{ display: "grid", gap: "var(--space-2)" }}>
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "var(--space-2)",
          fontSize: "var(--fs-micro)",
          letterSpacing: "var(--tracking-label)",
          textTransform: "uppercase",
          color: "var(--text-tertiary)",
        }}
      >
        <span className="viz-swatch" style={{ background: `var(${token})` }} />
        {label}
      </span>
      <span
        style={{
          fontSize: "var(--fs-micro)",
          lineHeight: 1.6,
          color: "var(--text-tertiary)",
        }}
      >
        {children}
      </span>
    </div>
  )
}
