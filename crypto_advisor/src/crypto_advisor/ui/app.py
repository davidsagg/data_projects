"""Streamlit UI — Validação de recomendações, portfólio e performance.

Iniciar:
    streamlit run src/crypto_advisor/ui/app.py
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ─── DB connection ────────────────────────────────────────────────────────────

@st.cache_resource
def _get_conn() -> sqlite3.Connection:
    from crypto_advisor.db.schema import init_db
    db_path = os.getenv("DB_PATH", "./data/crypto_advisor.db")
    conn = init_db(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# ─── App config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="CryptoAdvisor",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Sidebar nav ──────────────────────────────────────────────────────────────

st.sidebar.title("📊 CryptoAdvisor")
page = st.sidebar.radio(
    "Navegar",
    ["Recomendações", "Portfólio", "Performance", "Status Fiscal"],
)

conn = _get_conn()


# ─── Page: Recomendações ─────────────────────────────────────────────────────

def page_recommendations() -> None:
    from crypto_advisor.db.repository import RecommendationRepository
    repo = RecommendationRepository(conn)

    st.title("🎯 Recomendações")
    tab_pending, tab_history = st.tabs(["Pendentes", "Histórico"])

    with tab_pending:
        pending = repo.get_pending()
        if not pending:
            st.info("Nenhuma recomendação pendente. Execute a análise semanal para gerar novas.")
            return

        for rec in pending:
            with st.expander(
                f"{'🟢' if rec['action']=='BUY' else '🔴' if rec['action']=='SELL' else '🔵'} "
                f"**{rec['symbol']}** — {rec['action']}  |  {rec['confidence'].upper()}  "
                f"|  semana {rec['week_date']}",
                expanded=True,
            ):
                col1, col2, col3 = st.columns(3)
                if rec["entry_price_usd"]:
                    col1.metric("Entry", f"${rec['entry_price_usd']:,.0f}")
                    col2.metric("Stop",  f"${rec['stop_loss_usd']:,.0f}")
                    col3.metric("Alvo",  f"${rec['target_price_usd']:,.0f}")

                if rec["risk_reward_ratio"]:
                    st.metric("Risk/Reward", f"{rec['risk_reward_ratio']:.1f}x")

                st.markdown(f"**Análise:** {rec['reasoning']}")
                if rec["tax_impact"]:
                    st.warning(f"🧾 {rec['tax_impact']}")

                col_approve, col_reject = st.columns(2)
                if col_approve.button("✅ Aprovar", key=f"approve_{rec['id']}"):
                    repo.update_status(rec["id"], "approved")
                    st.success(
                        f"Recomendação #{rec['id']} aprovada. "
                        "Execute o trade manualmente no Mercado Bitcoin."
                    )
                    st.rerun()
                if col_reject.button("❌ Rejeitar", key=f"reject_{rec['id']}"):
                    repo.update_status(rec["id"], "rejected")
                    st.info(f"Recomendação #{rec['id']} rejeitada.")
                    st.rerun()

    with tab_history:
        rows = conn.execute(
            "SELECT * FROM recommendations ORDER BY created_at DESC LIMIT 100"
        ).fetchall()
        if not rows:
            st.info("Nenhuma recomendação no histórico ainda.")
            return

        status_filter = st.multiselect(
            "Filtrar por status",
            ["pending", "approved", "rejected", "executed"],
            default=["approved", "rejected"],
        )
        filtered = [r for r in rows if r["status"] in status_filter]

        for rec in filtered:
            status_icon = {"approved": "✅", "rejected": "❌",
                           "pending": "⏳", "executed": "🏁"}.get(rec["status"], "•")
            st.write(
                f"{status_icon} **{rec['symbol']}** {rec['action']} "
                f"| {rec['week_date']} | {rec['status']}"
            )


# ─── Page: Portfólio ──────────────────────────────────────────────────────────

def page_portfolio() -> None:
    from crypto_advisor.db.repository import PortfolioRepository
    repo = PortfolioRepository(conn)

    st.title("💼 Portfólio")

    positions = repo.get_all()
    if not positions:
        st.info("Portfólio vazio. Sincronize com o Mercado Bitcoin ao rodar a análise semanal.")
        return

    col1, col2 = st.columns(2)
    total_cost = sum(p.quantity * p.avg_price_brl for p in positions)
    col1.metric("Custo total investido", f"R$ {total_cost:,.2f}")
    col2.metric("Posições abertas", str(len(positions)))

    st.subheader("Posições")
    for pos in positions:
        with st.container():
            c1, c2, c3 = st.columns([2, 1, 2])
            c1.markdown(f"**{pos.symbol}**")
            c2.write(f"{pos.quantity:.6g}")
            c3.write(f"Médio: R$ {pos.avg_price_brl:,.2f}")
        st.divider()


# ─── Page: Performance ────────────────────────────────────────────────────────

def page_performance() -> None:
    from crypto_advisor.db.repository import PerformanceRepository
    repo = PerformanceRepository(conn)

    st.title("📈 Performance")

    summary = repo.get_summary()
    now = datetime.now(timezone.utc)
    monthly_pnl = repo.get_monthly_pnl(now.year, now.month)
    goal_brl = 3_000.0
    progress = repo.get_income_goal_progress(now.year, now.month, goal_brl)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Win Rate",        f"{summary.win_rate_pct:.1f}%")
    col2.metric("R-múltiplo médio", f"{summary.avg_r_multiple:.2f}x")
    col3.metric("P&L total",        f"R$ {summary.total_pnl_brl:,.2f}")
    col4.metric("Trades fechados",  str(summary.total_trades))

    st.subheader(f"Meta mensal: R$ {goal_brl:,.0f}/mês")
    st.progress(min(progress / 100, 1.0), text=f"R$ {monthly_pnl:,.2f} ({progress:.1f}%)")

    if summary.win_rate_pct < 40 and summary.total_trades >= 4:
        st.warning("⚠️ Win rate abaixo de 40% nas últimas semanas. Revise a estratégia.")
    if summary.avg_r_multiple < 1.0 and summary.total_trades >= 4:
        st.warning("⚠️ R-múltiplo médio abaixo de 1.0. Verifique a relação risco/retorno.")


# ─── Page: Status Fiscal ─────────────────────────────────────────────────────

def page_tax() -> None:
    from crypto_advisor.tax.optimizer import TaxOptimizer

    st.title("🧾 Status Fiscal")
    st.caption("Isenção de IR: até R$ 35.000/mês por exchange — IN RFB 2.312/2026")

    opt = TaxOptimizer(conn)
    now = datetime.now(timezone.utc)

    # Current month
    status = opt.get_monthly_status(now.year, now.month)
    pct = status.total_sold_brl / status.limit_brl * 100

    zone_colors = {"safe": "green", "warning": "orange", "critical": "red", "blocked": "red"}
    zone_labels = {"safe": "✅ SAFE", "warning": "⚠️ WARNING",
                   "critical": "🟠 CRITICAL", "blocked": "🚫 BLOCKED"}

    col1, col2, col3 = st.columns(3)
    col1.metric("Vendido este mês", f"R$ {status.total_sold_brl:,.2f}")
    col2.metric("Margem disponível", f"R$ {status.margin_available_brl:,.2f}")
    col3.metric("Zona", zone_labels[status.zone])

    st.progress(min(pct / 100, 1.0), text=f"{pct:.1f}% do limite mensal")

    # Last 12 months
    st.subheader("Histórico (12 meses)")
    rows = conn.execute(
        """SELECT year, month, total_sold_brl, realized_gain_brl,
                  realized_loss_brl, tax_status
           FROM tax_tracker
           ORDER BY year DESC, month DESC
           LIMIT 12"""
    ).fetchall()

    if rows:
        import pandas as pd
        df = pd.DataFrame([dict(r) for r in rows])
        df["período"] = df.apply(lambda r: f"{r['year']}-{r['month']:02d}", axis=1)
        df = df[["período", "total_sold_brl", "realized_gain_brl",
                 "realized_loss_brl", "tax_status"]]
        df.columns = ["Período", "Vendido (R$)", "Ganho (R$)", "Perda (R$)", "Status"]
        st.dataframe(df, use_container_width=True)

        if st.button("📥 Exportar CSV"):
            csv = df.to_csv(index=False)
            st.download_button(
                "Download tax_history.csv",
                data=csv,
                file_name="tax_history.csv",
                mime="text/csv",
            )
    else:
        st.info("Nenhum registro fiscal ainda.")

    st.caption(
        "⚠️ Esta ferramenta é auxiliar de planejamento. "
        "Consulte um contador especializado em criptoativos para declaração de IR."
    )


# ─── Router ───────────────────────────────────────────────────────────────────

if page == "Recomendações":
    page_recommendations()
elif page == "Portfólio":
    page_portfolio()
elif page == "Performance":
    page_performance()
elif page == "Status Fiscal":
    page_tax()
