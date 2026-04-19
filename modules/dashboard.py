"""
modules/dashboard.py — Dashboard financiero de RestaurantOS
Gráfico principal: Plotly stacked bar desde v_accounting_summary.
KPIs, alertas de stock (v_stock_status) y cuentas por pagar.
"""

from datetime import date
import streamlit as st
import pandas as pd
import plotly.express as px
from modules.database import get_supabase_client


def _kpi_card(label: str, value: str, sublabel: str = "", accent: str = "#58A6FF") -> str:
    return f"""
    <div style="background:#161B22;border-radius:8px;padding:1.2rem 1.4rem;
                border:1px solid #30363D;border-top:4px solid {accent};
                min-height:110px;">
        <p style="margin:0;font-size:0.7rem;font-weight:600;color:#8B949E;
                  text-transform:uppercase;letter-spacing:0.07em;">{label}</p>
        <p style="margin:0.3rem 0 0.2rem;font-size:1.85rem;font-weight:800;
                  color:#E6EDF3;line-height:1.1;">{value}</p>
        <p style="margin:0;font-size:0.78rem;color:#8B949E;">{sublabel}</p>
    </div>"""


def _alert_card(icon: str, title: str, body: str, accent: str) -> str:
    return f"""
    <div style="background:#161B22;border-radius:8px;padding:1.1rem 1.3rem;
                border:1px solid #30363D;border-left:5px solid {accent};
                min-height:95px;">
        <p style="margin:0;font-size:1.6rem;line-height:1;">{icon}</p>
        <p style="margin:0.35rem 0 0.1rem;font-size:0.97rem;font-weight:700;
                  color:#E6EDF3;">{title}</p>
        <p style="margin:0;font-size:0.8rem;color:#8B949E;">{body}</p>
    </div>"""


def render_dashboard():
    db    = get_supabase_client()
    today = date.today()

    st.markdown("## 📊 Dashboard")
    st.caption(f"Resumen al {today.strftime('%d de %B de %Y')}")

    try:
        res = (
            db.table("invoices")
            .select("id, invoice_date, total_amount, sale_type, status, created_at")
            .neq("status", "ANULADA")
            .order("created_at", desc=True)
            .execute()
        )
        all_invoices = res.data or []
    except Exception as e:
        st.error(f"⚠️ Error al cargar facturas: {e}")
        all_invoices = []

    if not all_invoices:
        st.info("📭 Aún no hay facturas registradas. ¡Empieza escaneando una!")
    else:
        total_spend    = sum(float(i.get("total_amount") or 0) for i in all_invoices)
        total_invoices = len(all_invoices)
        avg_amount     = total_spend / total_invoices if total_invoices else 0.0

        m1, m2, m3 = st.columns(3)
        m1.metric("💰 Gasto total",          f"₡{total_spend:,.2f}")
        m2.metric("🧾 Facturas registradas", str(total_invoices))
        m3.metric("📊 Promedio por factura", f"₡{avg_amount:,.2f}")

    st.markdown(
        "<p style='margin:1.5rem 0 0.4rem;font-size:0.78rem;font-weight:700;"
        "color:#8B949E;text-transform:uppercase;letter-spacing:0.08em;'>"
        "Gasto por categoría y mes</p>",
        unsafe_allow_html=True,
    )

    try:
        summary_res  = db.table("v_accounting_summary").select("*").execute()
        summary_data = summary_res.data or []
    except Exception as e:
        st.warning(f"No se pudo cargar el resumen contable: {e}")
        summary_data = []

    if summary_data:
        df_summary = pd.DataFrame(summary_data)
        df_summary["total_amount"] = pd.to_numeric(df_summary["total_amount"], errors="coerce").fillna(0)
        df_summary["periodo"] = (
            df_summary["fiscal_year"].astype(str)
            + "-"
            + df_summary["fiscal_month"].astype(str).str.zfill(2)
        )
        color_map = {}
        if "color_hex" in df_summary.columns:
            for _, row in df_summary.drop_duplicates("category_name").iterrows():
                if row.get("color_hex"):
                    color_map[row["category_name"]] = row["color_hex"]

        fig = px.bar(
            df_summary.sort_values("periodo"),
            x="periodo", y="total_amount", color="category_name",
            color_discrete_map=color_map if color_map else None,
            color_discrete_sequence=["#10B981","#58A6FF","#6366F1","#F59E0B","#EF4444","#8B5CF6"],
            barmode="stack",
            labels={"periodo":"Período","total_amount":"Gasto (₡)","category_name":"Categoría"},
            template="plotly_dark",
        )
        fig.update_layout(
            paper_bgcolor="#161B22", plot_bgcolor="#161B22",
            legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="right",x=1,title_text="",font=dict(color="#8B949E")),
            xaxis=dict(gridcolor="#30363D",color="#8B949E"),
            yaxis=dict(gridcolor="#30363D",color="#8B949E"),
            xaxis_title="", yaxis_title="Gasto (₡)",
            margin=dict(t=30,b=0,l=0,r=0), height=350,
        )
        fig.update_traces(hovertemplate="<b>%{x}</b><br>%{fullData.name}: ₡%{y:,.2f}<extra></extra>")
        st.plotly_chart(fig, use_container_width=True)
    else:
        if all_invoices:
            df = pd.DataFrame(all_invoices)
            _date_col = "invoice_date" if "invoice_date" in df.columns else "created_at"
            df["_fecha"] = pd.to_datetime(df[_date_col], errors="coerce").dt.date
            df["total_amount"] = pd.to_numeric(df["total_amount"], errors="coerce").fillna(0)
            df_daily = (
                df.dropna(subset=["_fecha"])
                .groupby("_fecha")["total_amount"].sum().reset_index()
                .rename(columns={"_fecha":"Fecha","total_amount":"Gasto (₡)"})
                .sort_values("Fecha")
            )
            if not df_daily.empty:
                fig_line = px.line(df_daily, x="Fecha", y="Gasto (₡)", template="plotly_dark")
                fig_line.update_traces(line_color="#58A6FF", line_width=2)
                fig_line.update_layout(
                    paper_bgcolor="#161B22", plot_bgcolor="#161B22",
                    xaxis=dict(gridcolor="#30363D",color="#8B949E"),
                    yaxis=dict(gridcolor="#30363D",color="#8B949E"),
                    margin=dict(t=10,b=0,l=0,r=0), height=300,
                )
                st.plotly_chart(fig_line, use_container_width=True)

    st.divider()

    st.markdown(
        "<p style='margin:0 0 0.6rem;font-size:0.78rem;font-weight:700;"
        "color:#8B949E;text-transform:uppercase;letter-spacing:0.08em;'>"
        "Resumen general</p>",
        unsafe_allow_html=True,
    )

    total_spent    = sum(float(i.get("total_amount") or 0) for i in all_invoices)
    cash_spent     = sum(float(i.get("total_amount") or 0) for i in all_invoices if (i.get("sale_type") or "").upper() == "CONTADO")
    pending_credit = sum(float(i.get("total_amount") or 0) for i in all_invoices
                         if (i.get("sale_type") or "").upper() == "CREDITO"
                         and (i.get("status") or "") in ("PENDIENTE","APROBADA"))

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(_kpi_card("Total compras",    f"₡{total_spent:,.2f}",    "Todas las facturas",  "#6366F1"), unsafe_allow_html=True)
    c2.markdown(_kpi_card("Pagado (contado)", f"₡{cash_spent:,.2f}",    "Facturas de contado", "#10B981"), unsafe_allow_html=True)
    c3.markdown(_kpi_card("Por pagar",        f"₡{pending_credit:,.2f}", "Crédito pendiente", "#F59E0B" if pending_credit > 0 else "#10B981"), unsafe_allow_html=True)
    c4.markdown(_kpi_card("Facturas cargadas", str(len(all_invoices)),        "Total registradas",   "#58A6FF"), unsafe_allow_html=True)

    st.markdown(
        "<p style='margin:2rem 0 0.6rem;font-size:0.78rem;font-weight:700;"
        "color:#8B949E;text-transform:uppercase;letter-spacing:0.08em;'>"
        "Alertas activas</p>",
        unsafe_allow_html=True,
    )

    red_stock = yellow_stock = overdue_count = 0
    overdue_amount = 0.0

    try:
        s = db.table("v_stock_status").select("stock_status").execute()
        stock_data   = s.data or []
        red_stock    = sum(1 for x in stock_data if x.get("stock_status") == "ROJO")
        yellow_stock = sum(1 for x in stock_data if x.get("stock_status") == "AMARILLO")
    except Exception:
        pass

    try:
        p = db.table("v_accounts_payable").select("payment_urgency, total_amount").execute()
        payables      = p.data or []
        overdue_count = sum(1 for x in payables if x.get("payment_urgency") == "VENCIDA")
        overdue_amount= sum(float(x.get("total_amount") or 0) for x in payables if x.get("payment_urgency") == "VENCIDA")
    except Exception:
        pass

    a1, a2, a3 = st.columns(3)
    a1.markdown(
        _alert_card("🔴", f"{red_stock} producto(s) críticos",  "Stock bajo mínimo",    "#EF4444")
        if red_stock > 0 else
        _alert_card("🟢", "Sin stock crítico",                  "Todos los niveles OK", "#238636"),
        unsafe_allow_html=True,
    )
    a2.markdown(
        _alert_card("🟡", f"{yellow_stock} producto(s) bajos", "Reabastecer pronto",   "#F59E0B")
        if yellow_stock > 0 else
        _alert_card("🟢", "Stock saludable",                   "Sin alertas de stock", "#238636"),
        unsafe_allow_html=True,
    )
    a3.markdown(
        _alert_card("🔴", f"{overdue_count} factura(s) vencida(s)", f"₡{overdue_amount:,.2f} pendientes", "#EF4444")
        if overdue_count > 0 else
        _alert_card("🟢", "Sin facturas vencidas", "Cuentas al día", "#238636"),
        unsafe_allow_html=True,
    )

    st.markdown(
        "<p style='margin:2rem 0 0.6rem;font-size:0.78rem;font-weight:700;"
        "color:#8B949E;text-transform:uppercase;letter-spacing:0.08em;'>"
        "Últimas 5 facturas</p>",
        unsafe_allow_html=True,
    )

    if not all_invoices:
        st.info("Aún no hay facturas. Usa 📷 Escanear Factura para cargar la primera.")
    else:
        recientes = all_invoices[:5]
        rows = [
            {
                "Fecha":  r.get("invoice_date") or r.get("created_at", "—")[:10],
                "Monto":  f"₡{float(r.get('total_amount') or 0):,.2f}",
                "Tipo":   r.get("sale_type", "—"),
                "Estado": r.get("status", "—"),
            }
            for r in recientes
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
