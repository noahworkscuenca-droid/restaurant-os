"""
modules/dashboard.py — Dashboard principal (estilo SaaS moderno)
"""

from datetime import date
import streamlit as st
import pandas as pd
from modules.database import get_supabase_client


# ── Helpers de tarjetas HTML ─────────────────────────────────────────────────

def _kpi_card(label: str, value: str, sublabel: str = "", accent: str = "#6366F1") -> str:
    """Tarjeta de KPI financiero con acento superior de color."""
    return f"""
    <div style="
        background: #fff;
        border-radius: 14px;
        padding: 1.2rem 1.4rem;
        box-shadow: 0 1px 8px rgba(0,0,0,0.07);
        border-top: 4px solid {accent};
        min-height: 110px;
    ">
        <p style="margin:0; font-size:0.7rem; font-weight:600; color:#9CA3AF;
                  text-transform:uppercase; letter-spacing:0.07em;">{label}</p>
        <p style="margin:0.3rem 0 0.2rem; font-size:1.85rem; font-weight:800;
                  color:#0F172A; line-height:1.1;">{value}</p>
        <p style="margin:0; font-size:0.78rem; color:#94A3B8;">{sublabel}</p>
    </div>"""


def _alert_card(icon: str, title: str, body: str, accent: str, bg: str) -> str:
    """Tarjeta de alerta con acento lateral de color."""
    return f"""
    <div style="
        background: {bg};
        border-radius: 14px;
        padding: 1.1rem 1.3rem;
        box-shadow: 0 1px 8px rgba(0,0,0,0.06);
        border-left: 5px solid {accent};
        min-height: 95px;
    ">
        <p style="margin:0; font-size:1.6rem; line-height:1;">{icon}</p>
        <p style="margin:0.35rem 0 0.1rem; font-size:0.97rem; font-weight:700;
                  color:#0F172A;">{title}</p>
        <p style="margin:0; font-size:0.8rem; color:#64748B;">{body}</p>
    </div>"""


# ── Render principal ─────────────────────────────────────────────────────────

def render_dashboard():

    db    = get_supabase_client()
    today = date.today()

    st.markdown("## 📊 Dashboard")
    st.caption(f"Resumen al {today.strftime('%d de %B de %Y')}")

    # ── Obtener TODAS las facturas para las métricas globales ─────────────────
    try:
        all_invoices_res = (
            db.table("invoices")
            .select("id, total_amount, invoice_date, created_at")
            .neq("status", "ANULADA")
            .execute()
        )
        all_invoices = all_invoices_res.data or []
    except Exception as e:
        st.error(f"Error al cargar facturas: {e}")
        all_invoices = []

    # ── 3 métricas globales con st.metric ────────────────────────────────────
    total_spend    = sum(float(i.get("total_amount") or 0) for i in all_invoices)
    total_invoices = len(all_invoices)
    avg_amount     = (total_spend / total_invoices) if total_invoices > 0 else 0.0

    if not all_invoices:
        st.info("No hay facturas registradas todavía.")
    else:
        m1, m2, m3 = st.columns(3)
        m1.metric("💰 Gasto total", f"\u20a1{total_spend:,.2f}")
        m2.metric("🧾 Facturas totales", str(total_invoices))
        m3.metric("📊 Promedio por factura", f"\u20a1{avg_amount:,.2f}")

    # ── Gráfico de gasto por día ──────────────────────────────────────────────
    if all_invoices:
        st.markdown(
            "<p style='margin:1.5rem 0 0.5rem;font-size:0.8rem;font-weight:700;"
            "color:#64748B;text-transform:uppercase;letter-spacing:0.08em;'>"
            "Gasto acumulado por día</p>",
            unsafe_allow_html=True,
        )

        df_all = pd.DataFrame(all_invoices)

        # Usar invoice_date si existe, si no created_at
        date_col = "invoice_date" if "invoice_date" in df_all.columns else "created_at"
        df_all["_fecha"] = pd.to_datetime(df_all[date_col], errors="coerce").dt.date
        df_all["total_amount"] = pd.to_numeric(df_all["total_amount"], errors="coerce").fillna(0)

        df_daily = (
            df_all.dropna(subset=["_fecha"])
            .groupby("_fecha")["total_amount"]
            .sum()
            .reset_index()
            .rename(columns={"_fecha": "Fecha", "total_amount": "Gasto (\u20a1)"})
            .sort_values("Fecha")
        )

        if not df_daily.empty:
            st.line_chart(df_daily.set_index("Fecha")["Gasto (\u20a1)"])
        else:
            st.info("No hay datos de fechas para generar el gráfico.")

    st.divider()

    # ── Consultas para el mes actual ─────────────────────────────────────────
    try:
        month_invoices = (
            db.table("invoices")
            .select("total_amount, sale_type, status")
            .neq("status", "ANULADA")
            .execute()
        )
        inv_data = month_invoices.data or []
    except Exception:
        inv_data = []

    total_spent    = sum(float(i.get("total_amount") or 0) for i in inv_data)
    cash_spent     = sum(
        float(i.get("total_amount") or 0) for i in inv_data
        if i.get("sale_type") == "CONTADO"
    )
    pending_credit = sum(
        float(i.get("total_amount") or 0) for i in inv_data
        if i.get("sale_type") == "CREDITO"
        and i.get("status") in ("PENDIENTE", "APROBADA")
    )

    # Stock y cuentas por pagar
    try:
        stock_result = db.table("v_stock_status").select("stock_status").execute()
        stock_data   = stock_result.data or []
    except Exception:
        stock_data = []

    red_stock    = sum(1 for s in stock_data if s.get("stock_status") == "ROJO")
    yellow_stock = sum(1 for s in stock_data if s.get("stock_status") == "AMARILLO")

    try:
        payable_result = (
            db.table("v_accounts_payable")
            .select("payment_urgency, total_amount")
            .execute()
        )
        payables = payable_result.data or []
    except Exception:
        payables = []

    overdue_count  = sum(1 for p in payables if p.get("payment_urgency") == "VENCIDA")
    overdue_amount = sum(
        float(p.get("total_amount") or 0)
        for p in payables if p.get("payment_urgency") == "VENCIDA"
    )

    # ── Fila de KPIs del mes ─────────────────────────────────────────────────
    st.markdown(
        "<p style='margin:1.2rem 0 0.6rem;font-size:0.8rem;font-weight:700;"
        "color:#64748B;text-transform:uppercase;letter-spacing:0.08em;'>"
        "Resumen general</p>",
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(
        _kpi_card("Total compras",    f"\u20a1{total_spent:,.2f}",
                  "Todas las facturas", "#6366F1"),
        unsafe_allow_html=True,
    )
    c2.markdown(
        _kpi_card("Pagado (contado)", f"\u20a1{cash_spent:,.2f}",
                  "Facturas de contado", "#10B981"),
        unsafe_allow_html=True,
    )
    c3.markdown(
        _kpi_card("Por pagar", f"\u20a1{pending_credit:,.2f}",
                  "Crédito pendiente",
                  "#F59E0B" if pending_credit > 0 else "#10B981"),
        unsafe_allow_html=True,
    )
    c4.markdown(
        _kpi_card("Facturas cargadas", str(len(inv_data)),
                  "Total registradas", "#3B82F6"),
        unsafe_allow_html=True,
    )

    # ── Alertas activas ──────────────────────────────────────────────────────
    st.markdown(
        "<p style='margin:2rem 0 0.6rem;font-size:0.8rem;font-weight:700;"
        "color:#64748B;text-transform:uppercase;letter-spacing:0.08em;'>"
        "Alertas activas</p>",
        unsafe_allow_html=True,
    )

    a1, a2, a3 = st.columns(3)

    if red_stock > 0:
        a1.markdown(
            _alert_card("🔴", f"{red_stock} producto(s) críticos",
                        "Stock por debajo del mínimo", "#EF4444", "#FEF2F2"),
            unsafe_allow_html=True,
        )
    else:
        a1.markdown(
            _alert_card("🟢", "Sin stock crítico",
                        "Todos los niveles están OK", "#10B981", "#F0FDF4"),
            unsafe_allow_html=True,
        )

    if yellow_stock > 0:
        a2.markdown(
            _alert_card("🟡", f"{yellow_stock} producto(s) bajos",
                        "Reabastecer pronto", "#F59E0B", "#FFFBEB"),
            unsafe_allow_html=True,
        )
    else:
        a2.markdown(
            _alert_card("🟢", "Stock saludable",
                        "Sin alertas de reabastecimiento", "#10B981", "#F0FDF4"),
            unsafe_allow_html=True,
        )

    if overdue_count > 0:
        a3.markdown(
            _alert_card("🔴", f"{overdue_count} factura(s) vencida(s)",
                        f"\u20a1{overdue_amount:,.2f} pendientes", "#EF4444", "#FEF2F2"),
            unsafe_allow_html=True,
        )
    else:
        a3.markdown(
            _alert_card("🟢", "Sin facturas vencidas",
                        "Cuentas por pagar al día", "#10B981", "#F0FDF4"),
            unsafe_allow_html=True,
        )

    # ── Gráfico por categoría ────────────────────────────────────────────────
    try:
        cat_result = (
            db.table("v_accounting_summary")
            .select("category_name, total_amount")
            .execute()
        )
        cat_data = cat_result.data or []
    except Exception:
        cat_data = []

    if cat_data:
        st.markdown(
            "<p style='margin:2rem 0 0.6rem;font-size:0.8rem;font-weight:700;"
            "color:#64748B;text-transform:uppercase;letter-spacing:0.08em;'>"
            "Gastos por categoría</p>",
            unsafe_allow_html=True,
        )
        df_cat = pd.DataFrame(cat_data).rename(
            columns={"category_name": "Categoría", "total_amount": "Total (\u20a1)"}
        )
        st.bar_chart(df_cat.set_index("Categoría")["Total (\u20a1)"])

    # ── Últimas 5 facturas ───────────────────────────────────────────────────
    st.markdown(
        "<p style='margin:2rem 0 0.6rem;font-size:0.8rem;font-weight:700;"
        "color:#64748B;text-transform:uppercase;letter-spacing:0.08em;'>"
        "Últimas 5 facturas</p>",
        unsafe_allow_html=True,
    )

    try:
        recent_result = (
            db.table("invoices")
            .select(
                "invoice_number, invoice_date, total_amount, currency, status, "
                "suppliers(name), invoice_categories(name)"
            )
            .order("created_at", desc=True)
            .limit(5)
            .execute()
        )
        recent = recent_result.data or []
    except Exception:
        recent = []

    if not recent:
        st.info("Aún no hay facturas. Usa 📷 Escanear Factura para cargar la primera.")
    else:
        rows_table = [
            {
                "Proveedor": (inv.get("suppliers") or {}).get("name", "—"),
                "Categoría": (inv.get("invoice_categories") or {}).get("name", "—"),
                "Fecha":     inv.get("invoice_date", "—"),
                "Monto":     f"\u20a1{float(inv.get('total_amount') or 0):,.2f}",
                "Estado":    inv.get("status", ""),
            }
            for inv in recent
        ]
        st.dataframe(
            pd.DataFrame(rows_table),
            use_container_width=True,
            hide_index=True,
        )
