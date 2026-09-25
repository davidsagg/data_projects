"""
Recomendação diária — o que os sinais do dia sugerem treinar.

Não é um plano de treino: é a leitura conjunta dos sinais que o atleta já tem
espalhados por quatro telas — prontidão, forma, o que a semana já acumulou e
onde está o limitador de capacidade. A pergunta que responde é "posso forçar
hoje?", que é a primeira coisa que se pergunta ao acordar e a última que o
produto respondia.

As regras são ordenadas por **prioridade de risco**: um sinal de alarme vence
qualquer oportunidade. Não adianta o perfil apontar que falta trabalho
anaeróbico se o TSB está em −32; nesse estado, a sessão intensa não produz
adaptação, produz buraco.

Os limiares seguem a literatura usual de periodização (Coggan/Friel para TSB,
Seiler para distribuição) e estão todos nomeados como constante — não há número
mágico embutido em `if`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# --- Faixas de TSB (Coggan/Friel) -----------------------------------------
# Abaixo disso o atleta está em buraco profundo; treino intenso não adapta.
TSB_OVERREACHED = -30.0
# Faixa produtiva: cansado o bastante para adaptar, fresco o bastante para render.
TSB_PRODUCTIVE = -10.0
# Acima disso a forma está fresca demais e a carga vem caindo.
TSB_FRESH = 15.0

# --- Prontidão -------------------------------------------------------------
READINESS_POOR = 40.0
READINESS_GOOD = 65.0

# Acima deste percentual da carga semanal típica, a semana já cumpriu o volume.
WEEK_LOAD_FULL_PCT = 95.0


@dataclass(frozen=True)
class Recommendation:
    """O que os sinais do dia sugerem, e por quê."""

    headline: str
    detail: str
    intensity: str
    signals: list[str] = field(default_factory=list)
    focus: str | None = None

    def to_dict(self) -> dict:
        return {
            "headline": self.headline,
            "detail": self.detail,
            "intensity": self.intensity,
            "signals": self.signals,
            "focus": self.focus,
        }


def recommend(
    readiness: float | None,
    tsb: float | None,
    ctl: float | None,
    week_tss: float,
    baseline_weekly_tss: float | None,
    limiters: list[str] | None = None,
    days_since_hard: int | None = None,
) -> Recommendation:
    """Sintetiza os sinais do dia numa recomendação.

    Args:
        readiness: score de prontidão de hoje (0–100).
        tsb: frescor atual.
        ctl: forma acumulada.
        week_tss: TSS já acumulado na semana corrente.
        baseline_weekly_tss: carga semanal típica das últimas semanas.
        limiters: durações em que o atleta está abaixo do próprio recorde.
        days_since_hard: dias desde a última sessão intensa.

    Returns:
        Recommendation com a leitura e os sinais que a produziram.
    """
    signals = _describe_signals(readiness, tsb, week_tss, baseline_weekly_tss)

    # 1. Alarme vence tudo. Nesta faixa, intensidade não gera adaptação.
    if tsb is not None and tsb < TSB_OVERREACHED:
        return Recommendation(
            headline="Descanso ou recuperação ativa",
            detail=(
                f"TSB em {tsb:.0f} — abaixo de {TSB_OVERREACHED:.0f} o corpo está em "
                "déficit profundo. Forçar aqui acumula fadiga sem adaptar."
            ),
            intensity="recuperação",
            signals=signals,
        )

    if readiness is not None and readiness < READINESS_POOR:
        return Recommendation(
            headline="Descanso ou recuperação ativa",
            detail=(
                f"Prontidão em {readiness:.0f}. Sono, HRV e FC de repouso indicam "
                "que o corpo ainda não se recuperou da carga anterior."
            ),
            intensity="recuperação",
            signals=signals,
        )

    # 2. Destreinando: a carga caiu e a forma está escorrendo.
    if tsb is not None and tsb > TSB_FRESH:
        return Recommendation(
            headline="Voltar a carregar",
            detail=(
                f"TSB em +{tsb:.0f}: fresco demais. A forma acumulada (CTL "
                f"{ctl:.0f}) começa a cair quando a carga fica baixa por muitas "
                "semanas — é hora de volume."
                if ctl
                else f"TSB em +{tsb:.0f}: fresco demais para continuar aliviando."
            ),
            intensity="endurance longo",
            signals=signals,
        )

    # 3. Semana já cumprida: segurar em vez de somar.
    if baseline_weekly_tss and week_tss >= baseline_weekly_tss * (
        WEEK_LOAD_FULL_PCT / 100
    ):
        return Recommendation(
            headline="Volume da semana já cumprido",
            detail=(
                f"{week_tss:.0f} TSS contra uma base de {baseline_weekly_tss:.0f}. "
                "Somar carga agora sobe a rampa sem plano — melhor consolidar."
            ),
            intensity="leve ou descanso",
            signals=signals,
        )

    # 4. Verde para intensidade. Aqui o limitador decide o foco.
    if (
        readiness is not None
        and readiness >= READINESS_GOOD
        and (tsb is None or tsb > TSB_PRODUCTIVE)
    ):
        focus = limiters[0] if limiters else None
        return Recommendation(
            headline="Janela para trabalho intenso",
            detail=(
                f"Prontidão {readiness:.0f} e TSB {tsb:+.0f} — o corpo aceita "
                "estímulo forte hoje."
                + (
                    f" O perfil aponta {focus} como o limitador mais marcado; "
                    "é o que rende mais agora."
                    if focus
                    else ""
                )
            ),
            intensity="intervalado",
            signals=signals,
            focus=focus,
        )

    # 5. Zona produtiva sem sinal verde claro: manter a base.
    return Recommendation(
        headline="Treino moderado",
        detail=(
            "Os sinais não pedem descanso nem autorizam máxima intensidade. "
            "Endurance com alguns blocos de tempo sustenta a base sem cavar buraco."
        ),
        intensity="endurance",
        signals=signals,
    )


def _describe_signals(
    readiness: float | None,
    tsb: float | None,
    week_tss: float,
    baseline_weekly_tss: float | None,
) -> list[str]:
    """Lista os sinais que entraram na decisão, para a recomendação ser auditável.

    Uma recomendação sem os sinais à vista é um palpite com cara de resultado —
    o atleta precisa poder discordar dela sabendo do quê.
    """
    signals: list[str] = []

    if readiness is not None:
        state = (
            "boa" if readiness >= READINESS_GOOD
            else "baixa" if readiness < READINESS_POOR
            else "moderada"
        )
        signals.append(f"prontidão {readiness:.0f} ({state})")

    if tsb is not None:
        state = (
            "sobrecarga" if tsb < TSB_OVERREACHED
            else "produtivo" if tsb < TSB_PRODUCTIVE
            else "fresco" if tsb > TSB_FRESH
            else "equilíbrio"
        )
        signals.append(f"TSB {tsb:+.0f} ({state})")

    if baseline_weekly_tss:
        pct = week_tss / baseline_weekly_tss * 100
        signals.append(f"semana em {pct:.0f}% da carga típica")
    elif week_tss:
        signals.append(f"{week_tss:.0f} TSS na semana")

    return signals
