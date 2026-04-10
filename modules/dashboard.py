# v2
"""
modules/dashboard.py — Dashboard principal rediseñado (estilo SaaS moderno)
"""

from datetime import date
import streamlit as st
from modules.database import get_supabase_client


# ── Helpers de tarjetas HTML ─────────────────────────────────────────────

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


def _alert_card(icon: str, title: str, body: str,
                accent: str, bg: str) -> str:
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


# ── Render principal ─────────────────────────────────────────────

def render_dashboard():

    db    = get_supabase_client()
    today = date.today()

    st.markdown("## 📊 Dashboard")
    st.caption(f"Resumen al {today.strftime('%d de %B de %Y')}")

    # ── Consultas ────────────────────────────────────────────────────────────────────
    month_invoices = (
        db.table("invoices")
        .select("total_amount, sale_type, status")
        .eq("fiscal_year",  today.year)
        .eq("fiscal_month", today.month)
        .neq("status", "ANULADA")
        .execute()
    )
    inv_data = month_invoices.data or []

    total_spent    = sum(i.get("total_amount", 0) or 0 for i in inv_data)
    cash_spent     = sum(i.get("total_amount", 0) or 0 for i in inv_data
                        if i.get("sale_type") == "CONTADO")
    pending_credit = sum(i.get("total_amount", 0) or 0 for i in inv_data
                        if i.get("sale_type") == "CREDITO"
                        and i.get("status") in ("PENDIENTE", "APROBADA"))

    stock_result = db.table("v_stock_status").select("stock_status").execute()
    stock_data   = stock_result.data or []
    red_stock    = sum(1 for s in stock_data if s.get("stock_status") == "ROJO")
    yellow_stock = sum(1 for s in stock_data if s.get("stock_status") == "AMARILLO")

    payable_result = (
        db.table("v_accounts_payable")
        .select("payment_urgency, total_amount")
        .execute()
    )
    payables       = payable_result.data or []
    overdue_count  = sum(1 for p in payables if p.get("payment_urgency") == "VENCIDA")
    overdue_amount = sum(
        p.get("total_amount", 0) or 0
        for p in payables if p.get("payment_urgency") == "VENCIDA"
    )

    # ── Fila 1: KPIs financieros ─────────────────────────────────────────────────────
    st.markdown(
        "<p style='margin:1.2rem 0 0.6rem;font-size:0.8rem;font-weight:700;"
        "color:#64748B;text-transform:uppercase;letter-spacing:0.08em;'>"
        "Este mes</p>",
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(
        _kpi_card("Total compras",    f"₡{total_spent:,.2f}",
                  "Todas las facturas del mes", "#6366F1"),
        unsafe_allow_html=True,
    )
    c2.markdown(
        _kpi_card("Pagado (contado)", f"₡{cash_spent:,.2f}",
                  "Facturas de contado", "#10B981"),
        unsafe_allow_html=True,
    )
    c3.markdown(
        _kpi_card("Por pagar", f"₡{pending_credit:,.2f}",
                  "Crédito pendiente",
                  "#F59E0B" if pending_credit > 0 else "#10B981"),
        unsafe_allow_html=True,
    )
    c4.markdown(
        _kpi_card("Facturas cargadas", str(len(inv_data)),
                  "Este mes", "#3B82F6"),
        unsafe_allow_html=True,
    )

    # ── Fila 2: Alertas activas ────────────────────────────────────────────────────────────────────
    st.markdown(
        "<p style='margin:2rem 0 0.6rem;font-size:0.8rem;font-weight:700;"
        "color:#64748B;text-transform:uppercase;letter-spacing:0.08em;'>"
        "Alertas activas</p>",
        unsafe_allow_html=True,
    )

    a1, a2, a3 = st.columns(3)

    # — Stock crítico
    if red_stock > 0:
        a1.markdown(
            _alert_card("🔴", f"{red_stock} producto(s) críticos",
                        "Stock por debajo del mínimo", "#EF4444", "#FEF2F2"),
            unsafe_allow_html=True,
        )
        a1.button("Ver inventario →", key="dash_red", use_container_width=True)
    else:
        a1.markdown(
            _alert_card("🟢", "Sin stock crítico",
                        "Todos los niveles están OK", "#10B981", "#F0FDF4"),
            unsafe_allow_html=True,
        )

    # — Stock bajo
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

    # — Facturas vencidas
    if overdue_count > 0:
        a3.markdown(
            _alert_card("🔴", f"{overdue_count} factura(s) vencida(s)",
                        f"₡{overdue_amount:,.2f} pendientes", "#EF4444", "#FEF2F2"),
            unsafe_allow_html=True,
        )
        a3.button("Ver cuentas →", key="dash_payable", use_container_width=True)
    else:
        a3.markdown(
            _alert_card("🟢", "Sin facturas vencidas",
                        "Cuentas por pagar al día", "#10B981", "#F0FDF4"),
            unsafe_allow_html=True,
        )

    # ── Gráfico por categoría ──────────────────────────────────────────────────────────────────────────────
    cat_result = (
        db.table("v_accounting_summary")
        .select("category_name, total_amount")
        .eq("fiscal_year",  today.year)
        .eq("fiscal_month", today.month)
        .execute()
    )
    cat_data = cat_result.data or []

    if cat_data:
        st.markdown(
            "<p style='margin:2rem 0 0.6rem;font-size:0.8rem;font-weight:700;"
            "color:#64748B;text-transform:uppercase;letter-spacing:0.08em;'>"
            "Gastos por categoría</p>",
            unsafe_allow_html=True,
        )
        import pandas as pd
        df_cat = pd.DataFrame(cat_data).rename(
            columns={"category_name": "Categoría", "total_amount": "Total (₡)"}
        )
        st.bar_chart(df_cat.set_index("Categoría")["Total (₡)"])

    # ── Últimas 5 facturas ────────────────────────────────────────────────────────────────────────────────
    st.markdown(
        "<p style='margin:2rem 0 0.6rem;font-size:0.8rem;font-weight:700;"
        "color:#64748B;text-transform:uppercase;letter-spacing:0.08em;'>"
        "Últimas 5 facturas</p>",
        unsafe_allow_html=True,
    )

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

    st.markdown('<div class="table-wrap">', unsafe_allow_html=True)
    if not recent:
        st.info("Aún no hay facturas. Usa 📷 Escanear Factura para cargar la primera.")
    else:
        import pandas as pd
        rows = [
            {
                "Proveedor": (inv.get("suppliers") or {}).get("name", "—"),
                "Categoría": (inv.get("invoice_categories") or {}).get("name", "—"),
                "Fecha":     inv.get("invoice_date", "—"),
                "Monto":     f"₡{inv.get('total_amount', 0):,.2f}",
                "Estado":    inv.get("status", ""),
            }
            for inv in recent
        ]
        st.dataframe(
            pd.DataFrame(rows),
            width="stretch",
            hide_index=True,
        )
    st.markdown('</div>', unsafe_allow_html=True)
